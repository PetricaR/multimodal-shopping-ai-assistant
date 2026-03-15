
import os
import sys
import logging
import json

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_cart_with_feature_store")

# Load environment
load_dotenv()

from database import db_adapter as db
from services.cart_service import CartService
from services.auth_service import AuthService


def get_active_session():
    """
    Get an active PHPSESSID, reusing saved session from database if still valid.
    Falls back to re-authentication only as a last resort.

    Returns:
        tuple: (phpsessid, username) or (None, None) if all methods fail
    """
    # 1. Check saved auth state in database
    logger.info("🔐 Step 1: Checking saved auth state in database...")
    auth_state = AuthService.get_authentication_from_state()

    if auth_state.get('status') == 'authenticated':
        phpsessid = auth_state.get('session_cookie')
        username = auth_state.get('username')
        logger.info(f"   Found saved session for {username} (PHPSESSID: {phpsessid[:8]}...)")

        # Validate session is still active
        validation = AuthService.validate_session(phpsessid)
        if validation.get('status') == 'valid':
            logger.info(f"✅ Saved session is VALID for {username}")
            return phpsessid, username
        else:
            logger.warning(f"⚠️ Saved session expired: {validation.get('message')}")

    # 2. Check raw credentials DB for session cookie
    logger.info("🔐 Step 2: Checking credentials DB for session cookie...")
    creds = db.get_credentials()
    if creds and creds.get('session_cookie'):
        phpsessid = creds['session_cookie']
        username = creds.get('username', 'unknown')
        logger.info(f"   Found session cookie for {username}")

        validation = AuthService.validate_session(phpsessid)
        if validation.get('status') == 'valid':
            logger.info(f"✅ DB session is VALID for {username}")
            return phpsessid, username
        else:
            logger.warning(f"⚠️ DB session also expired")

    # 3. Last resort: re-authenticate via Selenium
    logger.info("🔐 Step 3: No valid session found. Attempting re-authentication...")
    login_username = os.getenv("BRINGO_USERNAME")
    login_password = os.getenv("BRINGO_PASSWORD")

    if not login_username or not login_password:
        logger.error("❌ No credentials available. Set BRINGO_USERNAME and BRINGO_PASSWORD or run test_auth.py first.")
        return None, None

    result = AuthService.authenticate_with_credentials(login_username, login_password)
    if result.get('status') == 'success':
        logger.info(f"✅ Re-authentication successful for {login_username}")
        return result['phpsessid'], login_username

    logger.error(f"❌ Re-authentication failed: {result.get('message')}")
    return None, None


def test_cart_with_feature_store():
    """
    End-to-end test: Vector Search -> Feature Store enrichment -> Add to Cart

    Flow:
    1. Authenticate (reuse saved session from DB if valid)
    2. Vector Search for products (e.g., "cafea")
    3. Feature Store enriches results with metadata (product_id, variant_id, price, etc.)
    4. If variant_id is valid (vsp- format), add directly to cart
    5. If variant_id is missing/invalid, scrape product page as fallback
    6. Add product to Bringo cart
    """
    logger.info("=" * 70)
    logger.info("🛒 TEST: Cart with Feature Store Enrichment (End-to-End)")
    logger.info("=" * 70)

    # ─── STEP 1: Authentication ───
    phpsessid, username = get_active_session()
    if not phpsessid:
        logger.error("❌ ABORT: Could not obtain active session")
        return False

    store_id = "carrefour_park_lake"
    base_url = os.getenv("BRINGO_BASE_URL", "https://www.bringo.ro")

    cookies = {
        'PHPSESSID': phpsessid,
        'OptanonConsent': 'isIABGlobal=false&datestamp=Fri+Jan+30+2026+20%3A55%3A41+GMT%2B0200+(Eastern+European+Standard+Time)&version=6.18.0&hosts=&landingPath=NOT+LANDING+PAGE&groups=C0001%3A1%2CC0003%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent=false&geolocation=%3B&isGpcEnabled=0'
    }

    # ─── STEP 2: Vector Search (150 candidates) + Feature Store Enrichment ───
    logger.info("")
    logger.info("🔍 Step 2: Vector Search + Feature Store Enrichment...")
    logger.info("-" * 50)

    try:
        from api import dependencies
        from services.search_service import SearchService
        search_engine = dependencies.get_search_engine()
        feature_server = dependencies.get_feature_server()
    except Exception as e:
        logger.error(f"❌ Failed to initialize search/feature store: {e}")
        import traceback
        traceback.print_exc()
        return False

    search_query = "cafea"
    logger.info(f"   Query: '{search_query}'")

    try:
        # STEP 2a: Vector Search - retrieve 150 candidates (enriched by Feature Store)
        import time as _time
        t0 = _time.time()
        candidates = search_engine.search_by_text(query_text=search_query, num_neighbors=150)
        t_vs = (_time.time() - t0) * 1000

        if not candidates:
            logger.error("❌ No products found in Vector Search!")
            return False

        logger.info(f"✅ Vector Search: {len(candidates)} candidates in {t_vs:.0f}ms")

        # STEP 2b: Feature Store batch enrichment (metadata for all candidates)
        t0 = _time.time()
        candidate_ids = [c['id'] for c in candidates]
        fs_data = feature_server.get_product_metadata(candidate_ids)
        t_fs = (_time.time() - t0) * 1000

        enriched_candidates = []
        for candidate in candidates:
            pid = candidate['id']
            if pid in fs_data:
                d = fs_data[pid]
                # Normalize store fields: some FS use 'store', others 'store_id'
                fs_store = d.get('store') or d.get('store_id') or d.get('store_name')
                candidate.update({
                    'product_name': d.get('product_name', ''),
                    'category': d.get('category', ''),
                    'producer': d.get('producer', ''),
                    'image_url': d.get('image_url'),
                    'price': d.get('price_ron') or d.get('price', 0.0),
                    'in_stock': d.get('in_stock', False),
                    'variant_id': str(d.get('variant_id')) if d.get('variant_id') else None,
                    'url': d.get('url') or d.get('product_url'),
                    'store_id': fs_store,
                    'store_name': d.get('store_name') or fs_store,
                    'combined_text': f"{d.get('product_name', '')} {d.get('category', '')} {d.get('producer', '')}"
                })
                enriched_candidates.append(candidate)

        logger.info(f"✅ Feature Store: enriched {len(enriched_candidates)}/{len(candidates)} in {t_fs:.0f}ms")

        # STEP 2c: Compare products (quality/price scoring)
        t0 = _time.time()
        enriched_candidates = SearchService.compare_products(enriched_candidates)
        t_cmp = (_time.time() - t0) * 1000
        logger.info(f"✅ Compare products: scored in {t_cmp:.0f}ms")

        # STEP 2d: Ranking API - rerank to top results
        t0 = _time.time()
        try:
            reranker = dependencies.get_reranker()
            results = reranker.rerank(query=search_query, candidates=enriched_candidates, top_n=10)
            t_rank = (_time.time() - t0) * 1000
            logger.info(f"✅ Ranking API: top {len(results)} results in {t_rank:.0f}ms")
        except Exception as e:
            logger.warning(f"⚠️ Ranking API failed ({e}), using Vector Search order")
            results = enriched_candidates[:10]
            t_rank = 0

        # Filter results to only use products from the target store (carrefour_park_lake)
        try:
            filtered = [r for r in results if (r.get('store_id') or r.get('store') or r.get('store_name')) == store_id]
            if not filtered:
                logger.warning(f"⚠️ No ranked results found for store '{store_id}'. Falling back to unfiltered results (test may hit other-store validation).")
            else:
                results = filtered
                logger.info(f"✅ Filtered results to store '{store_id}': {len(results)} candidates remain")
        except Exception:
            # In case of unexpected shapes, skip filtering but warn
            logger.warning("⚠️ Could not apply store filter to results due to unexpected result shape")

        total_ms = t_vs + t_fs + t_cmp + t_rank
        logger.info(f"")
        logger.info(f"📊 Pipeline total: {total_ms:.0f}ms (VS:{t_vs:.0f} + FS:{t_fs:.0f} + CMP:{t_cmp:.0f} + RANK:{t_rank:.0f})")
        logger.info("")

        # Display top results
        for i, product in enumerate(results[:5]):
            rank_score = product.get('ranking_score', '-')
            quality = product.get('quality_score', '-')
            logger.info(f"   [{i+1}] {product.get('product_name', 'Unknown')}")
            logger.info(f"       Product ID:  {product.get('product_id', 'N/A')}")
            logger.info(f"       Variant ID:  {product.get('variant_id', 'N/A')}")
            logger.info(f"       Price:       {product.get('price', 'N/A')} RON")
            logger.info(f"       Category:    {product.get('category', 'N/A')}")
            logger.info(f"       In Stock:    {product.get('in_stock', 'N/A')}")
            logger.info(f"       Similarity:  {product.get('similarity_score', 0):.2%}")
            logger.info(f"       Rank Score:  {rank_score}")
            logger.info(f"       Quality:     {quality}")
            logger.info("")

    except Exception as e:
        logger.error(f"❌ Search pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ─── STEP 3: Select best ranked product and resolve variant_id ───
    # Pick the first product that has a valid variant_id and is in stock (prefer safe add)
    product = None
    for cand in results:
        if cand.get('variant_id') and str(cand.get('variant_id')).startswith('vsp-') and cand.get('in_stock'):
            product = cand
            break

    if not product:
        # Fallback: take first result with a variant_id even if out of stock
        for cand in results:
            if cand.get('variant_id') and str(cand.get('variant_id')).startswith('vsp-'):
                product = cand
                break

    if not product:
        logger.error("❌ No suitable product (with valid variant_id) found in filtered results for the target store")
        return False

    product_id = product.get('product_id')
    variant_id = product.get('variant_id')
    product_name = product.get('product_name', 'Unknown')

    logger.info(f"🎯 Selected product: {product_name} (ID: {product_id})")
    logger.info("-" * 50)

    if not product_id:
        logger.error("❌ Missing product_id from Feature Store enrichment!")
        return False

    # Check if Feature Store provided a valid variant_id (vsp- format)
    if variant_id and str(variant_id).startswith("vsp-"):
        logger.info(f"⚡ Feature Store provided valid variant_id: {variant_id}")
        logger.info("   No scraping needed! Direct add-to-cart possible.")
        variant_source = "feature_store"
    else:
        # Need to scrape product page for correct variant_id
        if variant_id:
            logger.warning(f"⚠️ Feature Store variant_id '{variant_id}' is NOT in vsp- format")
        else:
            logger.warning("⚠️ Feature Store did not provide variant_id")

        logger.info(f"🔎 Scraping product page for variant_id...")
        product_url = f"{base_url}/ro/{store_id}/products/product-{product_id}"
        logger.info(f"   URL: {product_url}")

        details = CartService.extract_product_details_from_url(product_url, phpsessid, cookies)

        if details.get('status') == 'success' and details.get('variant_id', '').startswith('vsp-'):
            variant_id = details['variant_id']
            logger.info(f"✅ Scraped valid variant_id: {variant_id}")
            variant_source = "scraped"
        else:
            logger.error(f"❌ Could not get valid variant_id. Details: {details.get('message', 'unknown')}")
            logger.error("   Cannot add to cart without valid variant_id.")
            return False

    # ─── STEP 4: Add to Cart ───
    logger.info("")
    logger.info(f"🛒 Step 4: Adding to cart...")
    logger.info("-" * 50)
    logger.info(f"   Product:    {product_name}")
    logger.info(f"   Product ID: {product_id}")
    logger.info(f"   Variant ID: {variant_id} (from {variant_source})")
    logger.info(f"   Store:      {store_id}")
    logger.info(f"   Quantity:   1")

    result = CartService.add_product_to_cart(
        product_id=str(product_id),
        variant_id=str(variant_id),
        quantity=1,
        phpsessid=phpsessid,
        cookies=cookies,
        store=store_id
    )

    if result.get("status") == "success":
        logger.info("")
        logger.info("=" * 50)
        logger.info("✅ ADD TO CART SUCCESS!")
        logger.info(f"   Message: {result.get('message')}")
        logger.info("=" * 50)

        # Verify cart
        logger.info("")
        logger.info("🔍 Verifying cart contents...")
        cart = CartService.get_cart_summary(phpsessid, cookies)
        logger.info(f"   Cart count: {cart.get('cart_count', 'unknown')}")

        return True

    else:
        logger.error(f"❌ Add to Cart FAILED: {result.get('message')}")
        response_text = str(result.get('response_text', ''))
        if response_text:
            logger.error(f"   Response: {response_text[:200]}")

        # Handle "products from another store" conflict
        if result.get('http_status') == 400 and ("alt magazin" in response_text or "Validation Failed" in result.get('message', '')):
            logger.warning("⚠️ Cart has products from another store. Clearing and retrying...")

            clear_res = CartService.clear_cart(phpsessid, cookies)
            if clear_res.get('status') == 'success':
                logger.info("✅ Cart cleared. Retrying...")

                result_retry = CartService.add_product_to_cart(
                    product_id=str(product_id),
                    variant_id=str(variant_id),
                    quantity=1,
                    phpsessid=phpsessid,
                    cookies=cookies,
                    store=store_id
                )

                if result_retry.get("status") == "success":
                    logger.info("✅ RETRY SUCCESS!")
                    return True
                else:
                    logger.error(f"❌ Retry also failed: {result_retry.get('message')}")
            else:
                logger.error(f"❌ Could not clear cart: {clear_res.get('message')}")

        return False


def test_feature_store_metadata_directly():
    """
    Standalone test: Check what metadata Feature Store provides for products.
    Useful for debugging variant_id availability.
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("📋 TEST: Feature Store Metadata Inspection")
    logger.info("=" * 70)

    try:
        from api import dependencies
        feature_server = dependencies.get_feature_server()
    except Exception as e:
        logger.error(f"❌ Failed to initialize Feature Store: {e}")
        return

    # Test with known product IDs
    test_ids = ["2388", "11493", "857828"]
    logger.info(f"   Testing with product IDs: {test_ids}")
    logger.info("")

    metadata = feature_server.get_product_metadata(test_ids)

    for pid in test_ids:
        if pid in metadata:
            data = metadata[pid]
            logger.info(f"   [{pid}] {data.get('product_name', 'Unknown')}")
            logger.info(f"       Fields available: {list(data.keys())}")
            logger.info(f"       variant_id:  {data.get('variant_id', 'NOT AVAILABLE')}")
            logger.info(f"       price_ron:   {data.get('price_ron', data.get('price', 'N/A'))}")
            logger.info(f"       category:    {data.get('category', 'N/A')}")
            logger.info(f"       in_stock:    {data.get('in_stock', 'N/A')}")
            logger.info(f"       image_url:   {str(data.get('image_url', 'N/A'))[:60]}...")
            logger.info("")
        else:
            logger.warning(f"   [{pid}] NOT FOUND in Feature Store")
            logger.info("")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test cart with Feature Store enrichment")
    parser.add_argument("--inspect", action="store_true", help="Only inspect Feature Store metadata (no cart operation)")
    args = parser.parse_args()

    if args.inspect:
        test_feature_store_metadata_directly()
    else:
        # Run both tests
        test_feature_store_metadata_directly()
        logger.info("\n")
        success = test_cart_with_feature_store()
        logger.info("")
        if success:
            logger.info("🎉 ALL TESTS PASSED")
        else:
            logger.info("💔 TEST FAILED")
        sys.exit(0 if success else 1)
