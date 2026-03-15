"""
API Routes for Bringo Product Similarity Search
Single unified endpoint for all similarity search operations
"""
from fastapi import APIRouter, HTTPException, Depends
import logging
import time
import json
from typing import Optional

import asyncio
from api.models import SearchRequest, SearchResponse, ProductInfo, HealthResponse
from api import dependencies
from services.search_service import SearchService
from services.search_logger import log_search_event

logger = logging.getLogger(__name__)


async def _enrich_query(raw_query: str) -> dict:
    """
    Use Gemini to parse a natural-language grocery query into:
      - clean_query: product name only (grammar-fixed, no price terms)
      - price_min / price_max: extracted RON constraints (or None)

    Example: "ulei de masline pana in 30 lei" ->
      {"clean_query": "ulei de masline", "price_min": null, "price_max": 30.0}
    """
    from google import genai
    from google.genai import types as genai_types
    from config.settings import settings

    # Prefer API key — Vertex AI path doesn't have
    # the generation model available in all regions/projects.
    if settings.GOOGLE_API_KEY:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    else:
        client = genai.Client(
            vertexai=True,
            project=settings.PROJECT_ID,
            location=settings.GENERATION_LOCATION,
        )

    prompt = (
        "Ești un parser de interogări pentru un catalog de produse alimentare românesc.\n"
        "Primești o interogare în română și extragi:\n"
        "1. clean_query: numele produsului fără constrângeri de preț, corectat gramatical\n"
        "2. price_min: prețul minim în RON (null dacă nu e menționat)\n"
        "3. price_max: prețul maxim în RON (null dacă nu e menționat)\n\n"
        "Exemple:\n"
        '- "ulei de masline pana in 30 lei" -> {"clean_query":"ulei de masline","price_min":null,"price_max":30.0}\n'
        '- "lapte integral sub 8 ron" -> {"clean_query":"lapte integral","price_min":null,"price_max":8.0}\n'
        '- "branza intre 5 si 20 lei" -> {"clean_query":"branza","price_min":5.0,"price_max":20.0}\n'
        '- "cafea" -> {"clean_query":"cafea","price_min":null,"price_max":null}\n'
        '- "pui proaspat ieftin" -> {"clean_query":"pui proaspat","price_min":null,"price_max":null}\n\n'
        f'Interogare: "{raw_query}"\n\n'
        "Răspunde DOAR cu JSON valid, fără explicații."
    )

    try:
        response = client.models.generate_content(
            model=settings.GENERATION_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=128,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        logger.warning(f"Query enrichment failed, using raw query: {e}")
        return {"clean_query": raw_query, "price_min": None, "price_max": None}

router = APIRouter()


@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        components={
            "vector_search": "initialized" if dependencies._search_engine else "not_loaded",
            "ranking_api": "initialized" if dependencies._reranker else "not_loaded",
            "bigquery": "initialized" if dependencies._bq_client else "not_loaded"
        }
    )


@router.post("/api/v1/search", response_model=SearchResponse, dependencies=[Depends(dependencies.verify_api_key)])
async def search_similar_products(request: SearchRequest):
    """
    Universal product similarity search endpoint

    Use Cases:
    1. Find similar products: {"product_name": "X", "top_k": 20}
    2. Find substitutes: {"product_name": "X", "in_stock_only": true}
    3. Text search: {"query_text": "lapte", "top_k": 10}

    OPTIMAL Flow (with Feature Store):
    1. Feature Store: Get product metadata (2-5ms)
    2. Vector Search: Find candidates (150ms)
    3. Feature Store Batch: Enrich metadata (5-10ms)
    4. Ranking API: Rerank results (80ms)
    Total: ~250ms

    Fallback: Uses BigQuery if Feature Store unavailable (~350ms)
    """
    start_time = time.time()

    if not request.product_name and not request.query_text and not request.queries:
        raise HTTPException(status_code=400, detail="Either product_name, query_text or queries must be provided")

    try:
        search_engine = dependencies.get_search_engine()
        feature_server = dependencies.get_feature_server()

        candidates = []
        enriched_query_text: Optional[str] = None
        price_min = request.price_min
        price_max = request.price_max

        # ── Gemini query enrichment ─────────────────────────────────────────
        if request.use_query_enrichment and request.query_text:
            enrichment = await _enrich_query(request.query_text)
            enriched_query_text = enrichment.get("clean_query") or request.query_text
            # Merge extracted price constraints with any explicit ones (explicit wins)
            if price_min is None and enrichment.get("price_min") is not None:
                price_min = float(enrichment["price_min"])
            if price_max is None and enrichment.get("price_max") is not None:
                price_max = float(enrichment["price_max"])
            logger.info(
                f"Query enrichment: '{request.query_text}' -> '{enriched_query_text}' "
                f"price=[{price_min}, {price_max}]"
            )

        # STEP 1: Multi-query handling via Vector Search + Feature Store
        if request.queries and (len(request.queries) > 1 or request.multi_store):
            logger.info(f"Performing multi-query search for {len(request.queries)} queries via Vector Search")

            query_text = " ".join(request.queries)
            query_product = None
            base_price = None
            product = None

            # Use Vector Search for each query, merge results
            seen_ids = set()
            loop = asyncio.get_running_loop()

            for q in request.queries:
                # Wrap blocking sync call in executor
                q_candidates = await loop.run_in_executor(
                    None,
                    lambda: search_engine.search_by_text(
                        query_text=q,
                        num_neighbors=150,
                        filter_in_stock=request.in_stock_only
                    )
                )
                for c in q_candidates:
                    cid = c['id']
                    if cid not in seen_ids:
                        candidates.append(c)
                        seen_ids.add(cid)

        # STEP 1 (Legacy/Single): Get product data (Feature Store ONLY)
        elif request.product_name:
            # Try Feature Store (2-5ms)
            product_metadata = feature_server.get_product_metadata([request.product_name])
            if request.product_name in product_metadata:
                data = product_metadata[request.product_name]
                product = {
                    'product_id': str(data.get('product_id', request.product_name)),
                    'combined_text': f"{data.get('product_name', '')} {data.get('category', '')} {data.get('producer', '')}",
                    'image_url': data.get('image_url'),
                    'metadata': {
                        'product_name': data.get('product_name', request.product_name),
                        'category': data.get('category', ''),
                        'producer': data.get('producer', ''),
                        'in_stock': data.get('in_stock', False),
                        'price': data.get('price_ron') or data.get('price', 0.0)
                    }
                }
                logger.info(f"Feature Store lookup: <5ms")
            else:
                logger.error(f"Product not found in Feature Store: {request.product_name}")
                raise HTTPException(status_code=404, detail=f"Product not found in AI Index: {request.product_name}")

            query_text = product['combined_text']
            query_product = ProductInfo(
                product_id=str(product.get('product_id', request.product_name)),
                variant_id=str(product.get('variant_id', '')) if product.get('variant_id') else None,
                product_name=product['metadata']['product_name'],
                category=product['metadata']['category'],
                producer=product['metadata']['producer'],
                image_url=product.get('image_url'),
                price=product['metadata']['price'],
                in_stock=product['metadata']['in_stock'],
                url=product.get('url'),
                store_id=product.get('store_id'),
                store_name=product.get('store_name')
            )
            base_price = product['metadata']['price']
        else:
            query_text = enriched_query_text or request.query_text
            query_product = None
            product = None
            base_price = None

        # STEP 2: Vector Search (Only if not already populated by multi-query)
        if not candidates:
            loop = asyncio.get_running_loop()

            if product:
                # Wrap blocking sync call
                candidates = await loop.run_in_executor(
                    None,
                    lambda: search_engine.search_by_product_name(
                        product_name=product['metadata']['product_name'],
                        product_text=product['combined_text'],
                        product_image_url=product.get('image_url'),
                        num_neighbors=150,
                        filter_in_stock=request.in_stock_only
                    )
                )
            else:
                # Wrap blocking sync call
                candidates = await loop.run_in_executor(
                    None,
                    lambda: search_engine.search_by_text(
                        query_text=query_text,
                        num_neighbors=150,
                        filter_in_stock=request.in_stock_only
                    )
                )

        # STEP 3: Enrich metadata (Feature Store ONLY)
        if candidates:
            candidate_ids = [c['id'] for c in candidates]
            try:
                # Try Feature Store batch (5-10ms)
                fs_data = feature_server.get_product_metadata(candidate_ids)
                products_metadata = {
                    pid: {
                        'product_id': str(d.get('product_id', pid)),
                        'metadata': {
                            'product_name': d.get('product_name', 'Unknown Product'),
                            'category': d.get('category', ''),
                            'producer': d.get('producer', ''),
                            'in_stock': d.get('in_stock', False),
                            'price': d.get('price_ron') or d.get('price', 0.0),
                            'variant_id': str(d.get('variant_id')) if d.get('variant_id') else None,
                            'url': d.get('url'),
                            'store_id': d.get('store_id'),
                            'store_name': d.get('store_name')
                        },
                        'image_url': d.get('image_url')
                    }
                    for pid, d in fs_data.items()
                }
                logger.info(f"Feature Store batch: {len(products_metadata)} products, <10ms")

                enriched_candidates = []
                for candidate in candidates:
                    prod = products_metadata.get(candidate['id'])
                    if prod:
                        candidate.update({
                            'product_name': prod['metadata']['product_name'],
                            'category': prod['metadata']['category'],
                            'producer': prod['metadata']['producer'],
                            'image_url': prod.get('image_url'),
                            'price': prod['metadata']['price'],
                            'in_stock': prod['metadata']['in_stock'],
                            'variant_id': prod['metadata'].get('variant_id'),
                            'url': prod['metadata'].get('url'),
                            'store_id': prod['metadata'].get('store_id'),
                            'store_name': prod['metadata'].get('store_name'),
                            'combined_text': f"{prod['metadata']['product_name']} {prod['metadata']['category']} {prod['metadata']['producer']}"
                        })
                        enriched_candidates.append(candidate)
            except Exception as e:
                logger.error(f"Feature Store enrichment failed: {e}")
                raise HTTPException(status_code=500, detail="Search enrichment failed: AI data unavailable")
        else:
            enriched_candidates = candidates

        # STEP 4: Advanced Comparison (Reference alignment)
        enriched_candidates = SearchService.compare_products(enriched_candidates)

        # STEP 4b: Price filtering (applied after enrichment so prices are populated)
        if price_min is not None or price_max is not None:
            before = len(enriched_candidates)
            enriched_candidates = [
                c for c in enriched_candidates
                if c.get('price') is not None
                and (price_min is None or c['price'] >= price_min)
                and (price_max is None or c['price'] <= price_max)
            ]
            logger.info(
                f"Price filter [{price_min}-{price_max} RON]: {before} -> {len(enriched_candidates)} products"
            )

        # STEP 5: Ranking API
        if request.use_ranking and enriched_candidates:
            reranker = dependencies.get_reranker()
            enriched_candidates = reranker.rerank(query=query_text, candidates=enriched_candidates, top_n=request.top_k)
            candidates_ranked = len(enriched_candidates)
        else:
            enriched_candidates = enriched_candidates[:request.top_k]
            candidates_ranked = None


        # STEP 6: Format response
        similar_products = [
            ProductInfo(
                product_id=str(c.get('product_id', c['id'])),
                variant_id=str(c.get('variant_id', '')) if c.get('variant_id') else None,
                product_name=c.get('product_name', ''),
                category=c.get('category'),
                producer=c.get('producer'),
                image_url=c.get('image_url'),
                price=c.get('price'),
                in_stock=c.get('in_stock', False),
                store_id=c.get('store_id'),
                store_name=c.get('store_name'),
                url=c.get('url'),
                similarity_score=c.get('similarity_score'),
                ranking_score=c.get('ranking_score'),
                distance=c.get('distance'),
                # New fields from compare_products
                price_score=c.get('price_score'),
                quality_score=c.get('quality_score'),
                match_reason=f"Quality: {c.get('quality_score')} | Price Rank: {c.get('price_score')}",
                # Calculate price difference if we have a base price
                price_difference=c.get('price') - base_price if base_price and c.get('price') else None
            )
            for c in enriched_candidates
        ]

        # Log top results for debugging/visibility
        logger.info(f"Search results for '{query_text}':")
        for i, p in enumerate(similar_products[:10]):
             logger.info(f"  {i+1}. {p.product_name} ({p.price} RON)")

        query_time_ms = (time.time() - start_time) * 1000
        logger.info(f"Search: {query_time_ms:.1f}ms, {len(similar_products)} results")

        applied_filters = {}
        if price_min is not None:
            applied_filters["price_min"] = price_min
        if price_max is not None:
            applied_filters["price_max"] = price_max
        if request.in_stock_only:
            applied_filters["in_stock_only"] = True

        search_method = "feature_store_vector_ranking" if request.use_ranking else "feature_store_vector_only"
        response = SearchResponse(
            query_product=query_product,
            similar_products=similar_products,
            search_method=search_method,
            candidates_retrieved=len(candidates),
            candidates_ranked=candidates_ranked,
            query_time_ms=query_time_ms,
            enriched_query=enriched_query_text,
            applied_filters=applied_filters if applied_filters else None,
        )

        # Fire-and-forget BQ logging — no await, zero latency impact
        try:
            bq = dependencies.get_bq_client()
            asyncio.create_task(log_search_event(
                bq_client=bq.client,
                query_text=request.query_text or request.product_name or "",
                enriched_query=enriched_query_text,
                result_count=len(similar_products),
                candidates_retrieved=len(candidates),
                latency_ms=query_time_ms,
                filters=applied_filters or {},
                search_method=search_method,
            ))
        except Exception:
            pass  # never block the response

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
