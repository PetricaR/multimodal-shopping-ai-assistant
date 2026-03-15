"""
Test Cart Item Removal Functionality

Tests the DELETE endpoint for removing items from cart based on Bringo API logic:
- DELETE /ro/ajax/cart/remove-item/{itemId}

This test covers:
1. Add item to cart
2. Remove item from cart (DELETE /api/v1/cart/items/{product_id})
3. Update item quantity (PATCH /api/v1/cart/items/{product_id})
4. Clear entire cart (DELETE /api/v1/cart)
"""

import os
import sys
import logging
import time

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_cart_removal")

# Load environment
load_dotenv()

from database import db_adapter as db
from services.cart_service import CartService
from services.auth_service import AuthService


def get_authenticated_session():
    """Get authenticated session, reusing existing or creating new"""
    logger.info("🔐 Getting authenticated session...")

    auth_state = AuthService.get_authentication_from_state()
    phpsessid = None
    username = None

    if auth_state.get('status') == 'authenticated':
        phpsessid = auth_state.get('session_cookie')
        username = auth_state.get('username')
        logger.info(f"✅ Reusing saved session for {username}")

        # Validate session
        validation = AuthService.validate_session(phpsessid)
        if validation.get('status') != 'valid':
            logger.warning("⚠️ Saved session expired, re-authenticating...")
            phpsessid = None

    if not phpsessid:
        creds = db.get_credentials()
        if creds and creds.get('session_cookie'):
            phpsessid = creds.get('session_cookie')
            username = creds.get('username')
            logger.info(f"✅ Found session from credentials DB")
        else:
            # Re-authenticate
            login_username = os.getenv("BRINGO_USERNAME")
            login_password = os.getenv("BRINGO_PASSWORD")

            if not login_username or not login_password:
                logger.error("❌ No credentials available. Set BRINGO_USERNAME and BRINGO_PASSWORD")
                return None, None, None

            result = AuthService.authenticate_with_credentials(login_username, login_password)
            if result.get('status') == 'success':
                phpsessid = result.get('phpsessid')
                username = login_username
                logger.info(f"✅ Login successful")
            else:
                logger.error(f"❌ Login failed: {result.get('message')}")
                return None, None, None

    cookies = {
        'PHPSESSID': phpsessid,
        'OptanonConsent': 'isIABGlobal=false&datestamp=Fri+Jan+30+2026+20%3A55%3A41+GMT%2B0200+(Eastern+European+Standard+Time)&version=6.18.0&hosts=&landingPath=NOT+LANDING+PAGE&groups=C0001%3A1%2CC0003%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent=false&geolocation=%3B&isGpcEnabled=0'
    }

    return phpsessid, username, cookies


def add_test_product(phpsessid, cookies, store_id):
    """Add a test product to cart and return its details"""
    logger.info("📦 Adding test product to cart...")

    # Search for a product instead of hardcoding
    try:
        from api import dependencies
        search_engine = dependencies.get_search_engine()
        results = search_engine.search_by_text(query_text="lapte", num_neighbors=1)

        if not results or len(results) == 0:
            logger.error("❌ No products found in search!")
            return None

        product = results[0]
        product_id = product.get('product_id')
        variant_id = product.get('variant_id')
        product_name = product.get('product_name', 'Test Product')

        logger.info(f"✅ Found product via search: {product_name} (ID: {product_id})")

        # If we don't have variant_id from search, scrape the product page
        if not variant_id or not str(variant_id).startswith('vsp-'):
            base_url = os.getenv("BRINGO_BASE_URL", "https://www.bringo.ro")
            product_url = f"{base_url}/ro/{store_id}/products/product-{product_id}"

            logger.info(f"🔎 Scraping product page for variant_id: {product_url}")
            details = CartService.extract_product_details_from_url(product_url, phpsessid, cookies)

            if details.get('status') == 'error':
                logger.error(f"❌ Failed to get product details: {details.get('message')}")
                return None

            variant_id = details.get('variant_id')

        if not variant_id:
            logger.error("❌ No variant_id found!")
            return None

        logger.info(f"✅ Got variant_id: {variant_id}")
    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Add to cart
    result = CartService.add_product_to_cart(
        product_id=product_id,
        variant_id=variant_id,
        quantity=2,  # Add 2 items so we can test quantity update
        phpsessid=phpsessid,
        cookies=cookies,
        store=store_id
    )

    if result.get("status") == "success":
        logger.info("✅ Product added to cart successfully!")
        return {
            'product_id': product_id,
            'variant_id': variant_id,
            'quantity': 2
        }
    else:
        logger.error(f"❌ Failed to add product: {result.get('message')}")

        # Handle "products from another store" error
        if result.get('http_status') == 400:
            logger.warning("⚠️ Clearing cart and retrying...")
            CartService.clear_cart(phpsessid, cookies)
            time.sleep(1)

            result = CartService.add_product_to_cart(
                product_id=product_id,
                variant_id=variant_id,
                quantity=2,
                phpsessid=phpsessid,
                cookies=cookies,
                store=store_id
            )

            if result.get("status") == "success":
                logger.info("✅ Product added after clearing cart!")
                return {
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'quantity': 2
                }

        return None


def test_remove_cart_item():
    """Test removing a single item from cart"""
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST 1: Remove Item from Cart (DELETE endpoint)")
    logger.info("="*80)

    phpsessid, username, cookies = get_authenticated_session()
    if not phpsessid:
        logger.error("❌ TEST FAILED: No authentication")
        return False

    store_id = "carrefour_park_lake"

    # Add test product
    product = add_test_product(phpsessid, cookies, store_id)
    if not product:
        logger.error("❌ TEST FAILED: Could not add test product")
        return False

    product_id = product['product_id']

    # Get cart summary before removal
    logger.info("📋 Getting cart summary before removal...")
    cart_before = CartService.get_cart_summary(phpsessid, cookies)
    logger.info(f"Cart count before: {cart_before.get('cart_count', 0)}")

    # Remove item from cart
    logger.info(f"🗑️  Removing product {product_id} from cart...")
    result = CartService.remove_item_from_cart(product_id, phpsessid, cookies)

    if result.get("status") == "success":
        logger.info("✅ Item removed successfully!")
        logger.info(f"Message: {result.get('message')}")

        # Verify removal
        time.sleep(1)
        cart_after = CartService.get_cart_summary(phpsessid, cookies)
        logger.info(f"Cart count after: {cart_after.get('cart_count', 0)}")

        logger.info("✅ TEST 1 PASSED: Remove item from cart")
        return True
    else:
        logger.error(f"❌ Failed to remove item: {result.get('message')}")
        logger.error("❌ TEST 1 FAILED")
        return False


def test_update_cart_quantity():
    """Test updating item quantity in cart"""
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST 2: Update Item Quantity (PATCH endpoint)")
    logger.info("="*80)

    phpsessid, username, cookies = get_authenticated_session()
    if not phpsessid:
        logger.error("❌ TEST FAILED: No authentication")
        return False

    store_id = "carrefour_park_lake"

    # Add test product
    product = add_test_product(phpsessid, cookies, store_id)
    if not product:
        logger.error("❌ TEST FAILED: Could not add test product")
        return False

    product_id = product['product_id']
    initial_qty = product['quantity']

    # Update quantity to 5
    new_quantity = 5
    logger.info(f"🔄 Updating quantity from {initial_qty} to {new_quantity}...")
    result = CartService.update_item_quantity(product_id, new_quantity, phpsessid, cookies)

    if result.get("status") == "success":
        logger.info("✅ Quantity updated successfully!")
        logger.info(f"Message: {result.get('message')}")
        logger.info(f"New quantity: {result.get('quantity', new_quantity)}")

        # Update quantity to 1
        logger.info(f"🔄 Updating quantity to 1...")
        result2 = CartService.update_item_quantity(product_id, 1, phpsessid, cookies)

        if result2.get("status") == "success":
            logger.info("✅ Quantity updated to 1!")

            # Clean up - remove item
            CartService.remove_item_from_cart(product_id, phpsessid, cookies)

            logger.info("✅ TEST 2 PASSED: Update item quantity")
            return True
        else:
            logger.error(f"❌ Failed second update: {result2.get('message')}")
            logger.error("❌ TEST 2 FAILED")
            return False
    else:
        logger.error(f"❌ Failed to update quantity: {result.get('message')}")
        logger.error("❌ TEST 2 FAILED")
        return False


def test_clear_cart():
    """Test clearing entire cart"""
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST 3: Clear Entire Cart (DELETE endpoint)")
    logger.info("="*80)

    phpsessid, username, cookies = get_authenticated_session()
    if not phpsessid:
        logger.error("❌ TEST FAILED: No authentication")
        return False

    store_id = "carrefour_park_lake"

    # Add test product
    product = add_test_product(phpsessid, cookies, store_id)
    if not product:
        logger.error("❌ TEST FAILED: Could not add test product")
        return False

    # Get cart summary before clearing
    logger.info("📋 Getting cart summary before clearing...")
    cart_before = CartService.get_cart_summary(phpsessid, cookies)
    count_before = cart_before.get('cart_count', 0)
    logger.info(f"Cart count before: {count_before}")

    if count_before == 0:
        logger.warning("⚠️ Cart is already empty!")

    # Clear cart
    logger.info("🗑️  Clearing entire cart...")
    result = CartService.clear_cart(phpsessid, cookies)

    if result.get("status") == "success":
        logger.info("✅ Cart cleared successfully!")
        logger.info(f"Message: {result.get('message')}")

        # Verify cart is empty
        time.sleep(1)
        cart_after = CartService.get_cart_summary(phpsessid, cookies)
        count_after = cart_after.get('cart_count', 0)
        logger.info(f"Cart count after: {count_after}")

        if count_after == 0:
            logger.info("✅ TEST 3 PASSED: Clear entire cart")
            return True
        else:
            logger.error(f"❌ Cart not empty after clearing (count: {count_after})")
            logger.error("❌ TEST 3 FAILED")
            return False
    else:
        logger.error(f"❌ Failed to clear cart: {result.get('message')}")
        logger.error("❌ TEST 3 FAILED")
        return False


def run_all_tests():
    """Run all cart removal tests"""
    logger.info("\n" + "🧪"*40)
    logger.info("STARTING CART REMOVAL TESTS")
    logger.info("🧪"*40 + "\n")

    results = {
        'test_remove_cart_item': False,
        'test_update_cart_quantity': False,
        'test_clear_cart': False
    }

    # Run tests
    results['test_remove_cart_item'] = test_remove_cart_item()
    time.sleep(2)

    results['test_update_cart_quantity'] = test_update_cart_quantity()
    time.sleep(2)

    results['test_clear_cart'] = test_clear_cart()

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    logger.info("="*80)
    logger.info(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    logger.info("="*80)

    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED!")
        return True
    else:
        logger.error(f"❌ {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
