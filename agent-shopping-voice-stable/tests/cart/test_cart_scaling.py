import logging
import os
import sys
import random
import requests
import re
from typing import List, Dict

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

from services.cart_service import CartService
from services.auth_service import AuthService
from database import db_adapter as db

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_cart_scaling")

def get_active_session():
    """Get valid session reusing DB or re-authenticating"""
    # 1. Try DB
    auth_state = AuthService.get_authentication_from_state()
    if auth_state.get('status') == 'authenticated':
        phpsessid = auth_state.get('session_cookie')
        username = auth_state.get('username')
        validation = AuthService.validate_session(phpsessid)
        if validation.get('status') == 'valid':
            logger.info(f"✅ Reusing valid session for {username}")
            return phpsessid, username

    # 2. Re-auth
    logger.info("🔐 Authenticating...")
    username = os.getenv("BRINGO_USERNAME")
    password = os.getenv("BRINGO_PASSWORD")
    if not username or not password:
        logger.error("❌ Credentials missing in .env")
        return None, None
    
    result = AuthService.authenticate_with_credentials(username, password)
    if result.get('status') == 'success':
        return result['phpsessid'], username
    return None, None

from services.search_service import SearchService

def get_random_products_via_search(store_id: str, count: int = 30) -> List[Dict]:
    """Find products using SearchService logic (more robust)"""
    logger.info(f"🔍 Finding {count} products using SearchService...")
    
    # Common search terms likely to have many results
    search_terms = ["lapte", "paine", "oua", "apa", "suc", "ciocolata", "cafea", "mere", "cartofi", "pui"]
    
    products = []
    seen_ids = set()
    
    for term in search_terms:
        if len(products) >= count:
            break
            
        logger.info(f"   Searching for '{term}'...")
        result = SearchService._search_product_sync(term, store_id, "test_store")
        
        if result.get('success'):
            found_items = result.get('products', [])
            logger.info(f"   Found {len(found_items)} items for '{term}'")
            
            for item in found_items:
                pid = item.get('product_id')
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    # Use the details found by SearchService directly!
                    products.append({
                        "product_id": pid,
                        "variant_id": item.get('variant_id'), # SearchService might extract this
                        "product_name": item.get('name'),
                        "quantity": 1
                    })
                    if len(products) >= count:
                        break
        else:
            logger.warning(f"   Search failed for '{term}': {result.get('error')}")
            
    return products[:count]

def test_scaling_cart():
    phpsessid, username = get_active_session()
    if not phpsessid:
        logger.error("❌ Auth failed")
        return False

    store_id = "carrefour_park_lake" # Default test store
    base_url = os.getenv("BRINGO_BASE_URL", "https://www.bringo.ro")
    
    cookies = {
        'PHPSESSID': phpsessid,
        'OptanonConsent': 'isIABGlobal=false&datestamp=Fri+Jan+30+2026+20%3A55%3A41+GMT%2B0200+(Eastern+European+Standard+Time)&version=6.18.0&hosts=&landingPath=NOT+LANDING+PAGE&groups=C0001%3A1%2CC0003%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent=false&geolocation=%3B&isGpcEnabled=0'
    }

    # 1. Clear Cart first
    logger.info("🗑️ Clearing cart...")
    CartService.clear_cart(phpsessid, cookies)

    # 2. Get 30 products
    items = get_random_products_via_search(store_id, 30)
    if len(items) < 30:
        logger.warning(f"⚠️ Could only find {len(items)} products")

    logger.info(f"📦 Found {len(items)} products to add")

    # 3. Batch Add
    logger.info("🚀 Starting Batch Add...")
    result = CartService.add_products_batch(items, store_id, phpsessid, cookies)
    
    # 4. Verify
    logger.info("📊 Batch Result:")
    logger.info(f"   Added: {len(result['items_added'])}")
    logger.info(f"   Failed: {len(result['failed_items'])}")
    logger.info(f"   Total Time: {result['timing_ms']['total']}ms")
    
    summary = CartService.get_cart_summary(phpsessid, cookies)
    cart_count = summary.get('cart_count', 0)
    
    logger.info(f"🛒 Final Cart Count (from Bringo): {cart_count}")
    
    if len(result['items_added']) > 0 and cart_count >= len(result['items_added']):
        logger.info("✅ Scaling test PASSED")
        return True
    else:
        logger.error("❌ Scaling test FAILED (Cart mismatch)")
        return False

if __name__ == "__main__":
    test_scaling_cart()
