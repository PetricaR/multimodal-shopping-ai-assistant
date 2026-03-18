#!/usr/bin/env python3
"""
Bringo Full Pipeline - Cloud Run Jobs
======================================
Complete data pipeline:
  1. Parallel category scraping → BigQuery
  2. Generate multimodal embeddings → GCS
  3. Update Vector Search Index
  4. Sync Feature Store

Usage:
    python run_parallel_scraper.py [--max-concurrent N] [--no-details] [--skip-pipeline]
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger("bringo_pipeline")


async def extract_categories_dynamically(store: str = "carrefour_park_lake") -> dict:
    """
    Extract ALL categories from the Bringo store-details page.
    Falls back to sidebar scraping if store-details doesn't return results.
    """
    import ssl
    import aiohttp
    from bs4 import BeautifulSoup

    logger.info(f"🔍 Extracting ALL categories for store '{store}'...")

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.bringo.ro/',
    }

    # Try to reuse an existing authenticated session
    try:
        from api.tools.authentication import get_authentication_from_state
        import json as _json
        auth_state = _json.loads(get_authentication_from_state())
        if auth_state.get('status') == 'authenticated':
            phpsessid = auth_state.get('session_cookie')
            headers['Cookie'] = f'PHPSESSID={phpsessid}'
            logger.info("🔐 Using existing authenticated session for category extraction")
    except Exception:
        pass  # Auth not available — proceed unauthenticated

    async with aiohttp.ClientSession(connector=connector) as session:
        # Method 1: store-details page — full category grid (requires auth)
        store_details_url = f"https://www.bringo.ro/ro/store-details/{store}"
        try:
            async with session.get(store_details_url, headers=headers, allow_redirects=True) as resp:
                final_url = str(resp.url)
                if resp.status == 200 and final_url not in (
                    "https://www.bringo.ro/ro/", "https://www.bringo.ro/"
                ):
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    grid_box = soup.find('div', class_='bringo-category-list-box')
                    if grid_box:
                        links = grid_box.find_all('a', class_='box-inner')
                        categories = {}
                        for link in links:
                            href = link.get('href', '')
                            h4 = link.find('h4')
                            name = h4.get_text(strip=True) if h4 else link.get_text(strip=True)
                            slug = href.strip('/').split('/')[-1]
                            if name and slug:
                                categories[name] = slug
                        if categories:
                            logger.info(f"✅ Extracted {len(categories)} categories from store-details page")
                            return categories
                        logger.warning("⚠️ store-details page loaded but no categories found in grid")
                    else:
                        logger.warning("⚠️ bringo-category-list-box not found — page may require authentication")
                else:
                    logger.warning(f"⚠️ store-details redirected or failed (status={resp.status})")
        except Exception as e:
            logger.warning(f"⚠️ store-details fetch failed: {e}")

        # Method 2: sidebar fallback from a single category page (partial list)
        logger.info("↩️ Falling back to sidebar extraction from a category page...")
        try:
            from bringo_catalog.bringo_products_v3 import extract_categories_from_page
            categories = await extract_categories_from_page(session, store)
            if categories:
                logger.info(f"✅ Extracted {len(categories)} categories via sidebar fallback")
                return categories
        except Exception as e:
            logger.warning(f"⚠️ Sidebar fallback failed: {e}")

    logger.warning("⚠️ All category extraction methods returned no results")
    return {}


def load_categories(use_dynamic: bool = False, store: str = "carrefour_park_lake") -> dict:
    """
    Load categories from BigQuery. If BQ is empty, extract dynamically from the
    live site and save the results back to BQ for future runs.

    Args:
        use_dynamic: When True, always re-extract from the live site and refresh BQ.
        store: Store slug used for both dynamic extraction and BQ filtering.

    Returns:
        Dict of {category_name: category_slug}
    """
    from data.bigquery_client import BigQueryClient

    bq_client = BigQueryClient()

    # 1. Try BigQuery first (skip if --dynamic-categories forces a refresh)
    if not use_dynamic:
        categories = bq_client.load_categories_from_bq(store)
        if categories:
            return categories
        logger.info("📭 No categories in BigQuery yet — extracting dynamically...")

    # 2. Extract dynamically from live site
    logger.info(f"🔍 Extracting categories dynamically for store '{store}'...")
    categories = asyncio.run(extract_categories_dynamically(store))

    if not categories:
        logger.error("❌ Dynamic category extraction returned no results. Cannot proceed.")
        sys.exit(1)

    # 3. Save to BigQuery so future runs don't need dynamic extraction
    try:
        bq_client.save_categories(categories, store)
        logger.info(f"✅ Saved {len(categories)} categories to BigQuery for store '{store}'")
    except Exception as e:
        logger.warning(f"⚠️ Could not save categories to BigQuery: {e} — continuing anyway")

    return categories


async def scrape_single_category(category_name: str, category_slug: str, fetch_details: bool = True, existing_ids: set = None) -> dict:
    """
    Scrape a single category using bringo_products_v3.
    Returns stats dict with category name and product count.
    """
    from bringo_catalog import bringo_products_v3
    
    store = os.getenv("BRINGO_STORE", "carrefour_park_lake")
    output_file = f"/tmp/{category_slug}.csv"
    
    logger.info(f"🚀 Starting: {category_name} ({category_slug})")
    start_time = time.time()
    
    try:
        count = await bringo_products_v3.main_single_category(
            store=store,
            category_slug=category_slug,
            category_name=category_name,
            output_file=output_file,
            fetch_details=fetch_details,
            max_products=None,  # No limit
            existing_ids=existing_ids
        )
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Completed: {category_name} - {count} products in {elapsed:.1f}s")
        
        return {
            "category": category_name,
            "slug": category_slug,
            "products": count or 0,
            "elapsed_seconds": elapsed,
            "status": "success"
        }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Failed: {category_name} - {e}")
        return {
            "category": category_name,
            "slug": category_slug,
            "products": 0,
            "elapsed_seconds": elapsed,
            "status": "failed",
            "error": str(e)
        }


async def run_parallel_scrape(categories: dict, max_concurrent: int = 10, fetch_details: bool = True, existing_ids: set = None, sequential: bool = True):
    """
    Run scraping across all categories (Parallel or Sequential).
    """
    logger.info("=" * 70)
    logger.info("STEP 1: CATEGORY SCRAPING")
    logger.info("=" * 70)
    logger.info(f"Total categories: {len(categories)}")
    logger.info(f"Mode: {'SEQUENTIAL (One by One)' if sequential else f'PARALLEL (Max {max_concurrent} concurrent)'}")
    logger.info(f"Fetch details: {fetch_details}")
    if existing_ids:
        logger.info(f"Existing IDs to skip: {len(existing_ids)}")
    logger.info("=" * 70)
    
    start_time = time.time()
    results = []

    if sequential:
        # --- SEQUENTIAL EXECUTION ---
        for i, (name, slug) in enumerate(categories.items(), 1):
            logger.info(f"Processing category {i}/{len(categories)}: {name}")
            try:
                # Await directly to ensure strict sequential order
                res = await scrape_single_category(name, slug, fetch_details, existing_ids)
                results.append(res)
            except Exception as e:
                logger.error(f"Error in category {name}: {e}")
                results.append(e)
    else:
        # --- PARALLEL EXECUTION ---
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_scrape(name: str, slug: str):
            async with semaphore:
                return await scrape_single_category(name, slug, fetch_details, existing_ids)
        
        # Create all tasks
        tasks = [
            bounded_scrape(name, slug)
            for name, slug in categories.items()
        ]
        
        # Run all tasks and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    total_elapsed = time.time() - start_time
    successful = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
    failed = [r for r in results if isinstance(r, dict) and r.get("status") == "failed"]
    errors = [r for r in results if isinstance(r, Exception)]
    
    total_products = sum(r.get("products", 0) for r in successful)
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("SCRAPING COMPLETE - SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    logger.info(f"Categories scraped: {len(successful)}/{len(categories)}")
    logger.info(f"Total products: {total_products}")
    logger.info(f"Failed categories: {len(failed)}")
    
    if failed:
        logger.warning("\nFailed categories:")
        for f in failed:
            logger.warning(f"  - {f['category']}: {f.get('error', 'Unknown error')}")
    
    return {
        "total_categories": len(categories),
        "successful": len(successful),
        "failed": len(failed),
        "total_products": total_products,
        "elapsed_seconds": total_elapsed,
    }


def run_embeddings_step():
    """Step 2: Generate embeddings and save to GCS"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 2: GENERATING EMBEDDINGS")
    logger.info("=" * 70)
    
    from data import BigQueryClient
    from embeddings import BatchEmbeddingProcessor
    
    start_time = time.time()
    
    # Fetch products from BigQuery
    bq_client = BigQueryClient()
    df = bq_client.fetch_products()
    logger.info(f"Fetched {len(df)} products from BigQuery")
    
    if df.empty:
        logger.warning("No products found in BigQuery. Skipping embeddings.")
        return None
    
    # Prepare and generate embeddings
    products = bq_client.prepare_for_embedding(df)
    processor = BatchEmbeddingProcessor()
    
    logger.info(f"Generating embeddings for {len(products)} products (Text-Only Batch)...")
    gcs_uri = processor.process_and_save(
        products=products,
        filename="bringo_products_embeddings_text.json",
        force_regenerate=True
    )
    
    elapsed = time.time() - start_time
    logger.info(f"✅ Embeddings saved to: {gcs_uri} ({elapsed:.1f}s)")
    
    return gcs_uri


def run_vector_search_step(gcs_uri: str):
    """Step 3: Update Vector Search Index"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 3: UPDATING VECTOR SEARCH INDEX")
    logger.info("=" * 70)
    
    from vector_search.index_manager import IndexManager
    from config.settings import settings
    
    start_time = time.time()
    
    index_manager = IndexManager()
    index_name = settings.VS_INDEX_NAME
    
    # Convert file path to directory for Vertex AI
    if gcs_uri.endswith('.json') or gcs_uri.endswith('.jsonl'):
        gcs_dir = gcs_uri.rsplit('/', 1)[0] + '/'
    else:
        gcs_dir = gcs_uri
    
    logger.info(f"Updating index '{index_name}' from {gcs_dir}")
    
    try:
        operation = index_manager.update_index(
            index_name=index_name,
            embeddings_gcs_uri=gcs_dir
        )
        
        logger.info("Waiting for index update to complete (this may take 20+ mins)...")
        index_manager.wait_for_completion(operation, "Index Update")
        
        # CRITICAL STEP: Ensure index is deployed to endpoint
        logger.info("Ensuring index is deployed to endpoint...")
        endpoint_name = settings.VS_ENDPOINT_NAME
        
        # Get or create endpoint
        endpoint = index_manager.get_or_create_endpoint(endpoint_name)
        
        # Check if index is deployed
        index = index_manager.get_existing_index(index_name)
        is_deployed = False
        for deployed_index in endpoint.deployed_indexes:
            if deployed_index.index == index.resource_name:
                is_deployed = True
                logger.info(f"✅ Index '{index_name}' is already deployed to endpoint '{endpoint_name}'")
                break
        
        if not is_deployed:
            logger.info(f"🚀 Deploying index '{index_name}' to endpoint '{endpoint_name}'...")
            index_manager.deploy_index(index=index, endpoint=endpoint)
            
        elapsed = time.time() - start_time
        logger.info(f"✅ Vector Index updated and verified deployed successfully ({elapsed:.1f}s)")
        
    except Exception as e:
        logger.error(f"❌ Vector Search update failed: {e}")
        raise


def run_feature_store_step():
    """Step 4: Sync Feature Store"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 4: SYNCING FEATURE STORE")
    logger.info("=" * 70)
    
    from features.sync_feature_store import trigger_sync
    
    start_time = time.time()
    
    try:
        trigger_sync()
        elapsed = time.time() - start_time
        logger.info(f"✅ Feature Store sync initiated ({elapsed:.1f}s)")
    except Exception as e:
        logger.error(f"❌ Feature Store sync failed: {e}")
        raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Bringo Full Pipeline for Cloud Run Jobs')
    parser.add_argument('--max-concurrent', type=int, default=10,
                        help='Maximum concurrent category scrapes (default: 10)')
    parser.add_argument('--no-details', action='store_true',
                        help='Skip fetching detailed product info (faster)')
    parser.add_argument('--categories', type=str, nargs='*',
                        help='Specific category slugs to scrape (default: all)')
    parser.add_argument('--dynamic-categories', action='store_true',
                        help='Enable dynamic category discovery (mapped to JSON names)')
    parser.add_argument('--skip-pipeline', action='store_true',
                        help='Skip post-scraping steps (embeddings, vector search, feature store)')
    parser.add_argument('--skip-scraping', action='store_true',
                        help='Skip scraping, only run pipeline steps (embeddings, vector search, feature store)')
    parser.add_argument('--parallel-categories', action='store_true',
                        help='Run categories in parallel (default: sequential one-by-one)')
    
    args = parser.parse_args()
    
    pipeline_start = time.time()
    
    logger.info("=" * 70)
    logger.info("🚀 BRINGO FULL PIPELINE - CLOUD RUN JOB")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 70)
    
    # Step 1: Scraping
    if not args.skip_scraping:
        # Load categories with optional dynamic discovery
        all_categories = load_categories(use_dynamic=args.dynamic_categories)
        
        if args.categories:
            categories = {
                name: slug for name, slug in all_categories.items()
                if slug in args.categories
            }
            if not categories:
                logger.error(f"No matching categories found for: {args.categories}")
                sys.exit(1)
        else:
            categories = all_categories
        
        fetch_details = not args.no_details
        
        # --- OPTIMIZATION: Fetch existing IDs once ---
        existing_ids = set()
        try:
            from data.bigquery_client import BigQueryClient
            bq_client = BigQueryClient()
            
            # Determine store context to filter existing IDs
            # run_parallel_scrape uses load_categories which uses env var or default
            current_store = os.getenv("BRINGO_STORE", "carrefour_park_lake")
            
            existing_ids = bq_client.get_existing_product_ids(store=current_store)
            logger.info(f"Loaded {len(existing_ids)} existing product IDs for store '{current_store}' globally.")
        except Exception as e:
            logger.warning(f"Failed to load existing IDs globally: {e}. Worker threads will try individually.")
        
        scrape_result = asyncio.run(run_parallel_scrape(
            categories=categories,
            max_concurrent=args.max_concurrent,
            fetch_details=fetch_details,
            existing_ids=existing_ids,
            sequential=not args.parallel_categories
        ))
        
        if scrape_result["failed"] > 0:
            logger.warning(f"⚠️  {scrape_result['failed']} categories failed, continuing with pipeline...")
    else:
        logger.info("Skipping scraping step (--skip-scraping)")
    
    # Steps 2-4: Pipeline (if not skipped)
    if not args.skip_pipeline:
        try:
            # Step 2: Embeddings
            gcs_uri = run_embeddings_step()
            
            if gcs_uri:
                # Step 3: Vector Search
                run_vector_search_step(gcs_uri)
                
                # Step 4: Feature Store
                run_feature_store_step()
            else:
                logger.warning("No embeddings generated, skipping vector search and feature store")
                
        except Exception as e:
            logger.error(f"💥 Pipeline step failed: {e}")
            sys.exit(1)
    else:
        logger.info("Skipping pipeline steps (--skip-pipeline)")
    
    # Final summary
    total_elapsed = time.time() - pipeline_start
    logger.info("\n" + "=" * 70)
    logger.info("🎉 PIPELINE COMPLETED SUCCESSFULLY")
    logger.info(f"Total elapsed time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()

