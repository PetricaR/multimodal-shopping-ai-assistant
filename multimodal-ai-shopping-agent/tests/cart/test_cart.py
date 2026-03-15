
import os
import sys
import logging
import json

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_cart")

# Load environment
load_dotenv()

from database import db_adapter as db
from services.cart_service import CartService
from services.auth_service import AuthService

def test_cart():
    logger.info("🛒 Testing Cart Functionality...")

    # 1. Get Authentication - prefer saved session from database
    logger.info("🔐 Checking for active session in database...")
    auth_state = AuthService.get_authentication_from_state()

    phpsessid = None
    username = None

    if auth_state.get('status') == 'authenticated':
        phpsessid = auth_state.get('session_cookie')
        username = auth_state.get('username')
        logger.info(f"✅ Reusing saved session for {username} (PHPSESSID: {phpsessid[:8]}...)")

        # Optionally validate session is still active
        validation = AuthService.validate_session(phpsessid)
        if validation.get('status') != 'valid':
            logger.warning("⚠️ Saved session expired, need to re-authenticate...")
            phpsessid = None

    if not phpsessid:
        # Fallback: try credentials from DB
        creds = db.get_credentials()
        if creds and creds.get('session_cookie'):
            phpsessid = creds.get('session_cookie')
            username = creds.get('username')
            logger.info(f"✅ Found session from credentials DB for {username} (PHPSESSID: {phpsessid[:8]}...)")
        else:
            # Last resort: re-authenticate
            logger.info("🔐 No active session found. Attempting login...")
            login_username = os.getenv("BRINGO_USERNAME")
            login_password = os.getenv("BRINGO_PASSWORD")

            if not login_username or not login_password:
                logger.error("❌ No session and no credentials available. Set BRINGO_USERNAME and BRINGO_PASSWORD or run test_auth.py first.")
                return

            result = AuthService.authenticate_with_credentials(login_username, login_password)
            if result.get('status') == 'success':
                phpsessid = result.get('phpsessid')
                username = login_username
                logger.info(f"✅ Login successful for {username}")
            else:
                logger.error(f"❌ Login failed: {result.get('message')}")
                return

    store_id = "carrefour_park_lake"

    # 2. Search for Product (Vector Search + Feature Store Enrichment)
    logger.info("🔍 Searching for products via Vector Search + Feature Store...")
    try:
        from api import dependencies
        search_engine = dependencies.get_search_engine()

        # Search returns enriched results from Feature Store
        results = search_engine.search_by_text(query_text="cafea", num_neighbors=1)

        if not results:
            logger.error("❌ No products found!")
            return

        # Get first result (already enriched with Feature Store metadata)
        product = results[0]

        logger.info(f"✅ Search Result (enriched from Feature Store):")
        logger.info(f"   Product name: {product.get('product_name')}")
        logger.info(f"   Product ID: {product.get('product_id')}")
        logger.info(f"   Variant ID: {product.get('variant_id')}")
        logger.info(f"   Price: {product.get('price')} RON")
        logger.info(f"   Similarity: {product.get('similarity_score', 0):.2%}")

        # Extract required fields
        product_id = product.get('product_id')
        variant_id_from_search = product.get('variant_id')

        # Validate we have required fields
        if not product_id:
            logger.error("❌ Missing product_id from Feature Store enrichment!")
            logger.error("ℹ️  Make sure Feature Store is synced with product data")
            return

        if not variant_id_from_search:
            logger.warning("⚠️  Missing variant_id from Feature Store enrichment")
            logger.info("   Will fetch from product page...")

    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return

    store_id = "carrefour_park_lake"

    # Cookies for requests
    cookies = {
        'PHPSESSID': phpsessid,
        'OptanonConsent': 'isIABGlobal=false&datestamp=Fri+Jan+30+2026+20%3A55%3A41+GMT%2B0200+(Eastern+European+Standard+Time)&version=6.18.0&hosts=&landingPath=NOT+LANDING+PAGE&groups=C0001%3A1%2CC0003%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent=false&geolocation=%3B&isGpcEnabled=0'
    }

    base_url = os.getenv("BRINGO_BASE_URL", "https://www.bringo.ro")

    # Correct product page URL pattern for Bringo
    if product_id and product_id.isdigit():
        product_url = f"{base_url}/ro/{store_id}/products/product-{product_id}"
    else:
        # Fallback to known working product for "cafea" test
        logger.info("⚠️ Falling back to hardcoded test product (2388)")
        product_id = "2388"
        product_url = f"{base_url}/ro/{store_id}/products/product-2388"

    # Check if variant_id from search is valid (must start with "vsp-" for Bringo)
    if variant_id_from_search and str(variant_id_from_search).startswith("vsp-"):
        variant_id = variant_id_from_search
        logger.info(f"⚡ Using valid variant_id from search: {variant_id}")
    else:
        # Must scrape from product page to get correct vsp- format variant_id
        if variant_id_from_search:
            logger.warning(f"⚠️  variant_id from search '{variant_id_from_search}' is not in vsp- format")
        logger.info(f"🔎 Scraping product page for variant_id: {product_url}")

        details = CartService.extract_product_details_from_url(product_url, phpsessid, cookies)
        if details.get('status') == 'error':
            logger.error(f"❌ Failed to get details: {details.get('message')}")
            return

        variant_id = details.get('variant_id')
        logger.info(f"✅ Extracted variant_id from page: {variant_id}")

        if not variant_id:
            logger.error("❌ No variant_id found!")
            return

    # 3. Add to Cart
    logger.info("🛒 Adding to cart...")

    result = CartService.add_product_to_cart(
        product_id=product_id,
        variant_id=variant_id,
        quantity=1,
        phpsessid=phpsessid,
        cookies=cookies,
        store=store_id
    )

    if result.get("status") == "success":
        logger.info("✅ Add to Cart SUCCESS!")
        logger.info(f"Message: {result.get('message')}")
    else:
        logger.error(f"❌ Add to Cart FAILED: {result.get('message')}")
        response_text = str(result.get('response_text', ''))
        if result.get('response_text'):
             logger.error(f"Response: {response_text}")

        # Handling "Ai produse de la alt magazin" (You have products from another store)
        if result.get('http_status') == 400 and ("alt magazin" in response_text or "Validation Failed" in result.get('message', '')):
            logger.warning("⚠️ Application has products from another store. Clearing cart...")

            clear_res = CartService.clear_cart(phpsessid, cookies)
            if clear_res.get('status') == 'success':
                logger.info("✅ Cart cleared successfully. Retrying add to cart...")

                result_retry = CartService.add_product_to_cart(
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=1,
                    phpsessid=phpsessid,
                    cookies=cookies,
                    store=store_id
                )

                if result_retry.get("status") == "success":
                    logger.info("✅ Retry Add to Cart SUCCESS!")
                    logger.info(f"Message: {result_retry.get('message')}")
                else:
                    logger.error(f"❌ Retry Add to Cart FAILED: {result_retry.get('message')}")
            else:
                logger.error(f"❌ Failed to clear cart: {clear_res.get('message')}")

if __name__ == "__main__":
    test_cart()
