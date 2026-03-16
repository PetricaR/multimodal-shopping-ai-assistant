import re
import json
import time
import requests
import logging
from typing import Dict, Any, Optional

from services import product_cache
from config.settings import settings

logger = logging.getLogger(__name__)

class CartService:

    @staticmethod
    def extract_product_details_from_url(product_url: str, phpsessid: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract product details from product URL (scrapes if not in cache)
        Robust method with search fallback
        """
        logger.info(f"🔍 Extracting product details from URL: {product_url}")
        
        # Check cache
        cached = product_cache.load_product_details(product_url)
        if cached:
            logger.info("⚡ CACHE HIT! Returning cached details")
            return cached
        
        # Scrape
        logger.info("🌐 Cache miss, scraping product page...")
        try:
            # Extract basic IDs for tracking
            store_id_match = re.search(r'/ro/([^/]+)/', product_url)
            store_id = store_id_match.group(1) if store_id_match else "unknown"
            
            product_id_match = re.search(r'/(\d+)(?:-ro)?/?$', product_url)
            if not product_id_match:
                product_id_match = re.search(r'product[/-](\d+)', product_url)
            
            product_id = product_id_match.group(1) if product_id_match else "unknown"
            
            # Setup session
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
            
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            })
            
            # Fetch
            response = session.get(product_url, timeout=30)
            
            # Fallback Search logic
            if response.status_code != 200:
                logger.warning(f"Product page failed ({response.status_code}). Attempting search fallback for {product_id}...")
                
                search_url = f"{settings.BRINGO_BASE_URL}/ro/{store_id}/search"
                search_response = session.get(search_url, params={'query': product_id})
                
                if search_response.status_code == 200:
                    html = search_response.text
                    # Find product link
                    link_match = re.search(rf'href="([^"]*products/[^"]*/{product_id})"', html)
                    if not link_match:
                        link_match = re.search(rf'href="([^"]*products/[^"]*{product_id}[^\"]*)\"', html)
                        
                    if link_match:
                        new_url = link_match.group(1)
                        if not new_url.startswith("http"):
                            new_url = f"{settings.BRINGO_BASE_URL}{new_url}"
                        
                        logger.info(f"Found product via search: {new_url}")
                        product_url = new_url # Update for cache
                        response = session.get(new_url, timeout=30)
            
            if response.status_code != 200:
                return {
                    'status': 'error',
                    'message': f'Product page returned status {response.status_code} even after fallback',
                    'product_id': product_id
                }
            
            html = response.text
            
            # Extract variant ID - Try multiple patterns
            variant_match = re.search(r'sylius_add_to_cart\[cartItem\]\[variant\].*?value="([^"]+)"', html)
            variant_id = variant_match.group(1) if variant_match else None
            
            if not variant_id:
                # Fallback variant pattern (hidden input)
                variant_match = re.search(r'name="sylius_add_to_cart\[cartItem\]\[variant\]" value="([^"]+)"', html)
                variant_id = variant_match.group(1) if variant_match else None

            if not variant_id:
                # Try data attribute on add-to-cart button or form
                variant_match = re.search(r'data-variant-id="([^"]+)"', html)
                variant_id = variant_match.group(1) if variant_match else None

            if not variant_id:
                # Try another common pattern (JSON payload embedded)
                variant_match = re.search(r'"variantId"\s*:\s*"([^"]+)"', html)
                variant_id = variant_match.group(1) if variant_match else None

            if not variant_id:
                return {
                    'status': 'error',
                    'message': 'Variant ID not found on product page',
                    'product_id': product_id
                }
            
            # Extract CSRF token
            token_match = re.search(r'sylius_add_to_cart\[_token\].*?value="([^"]+)"', html)
            token = token_match.group(1) if token_match else None
            
            if not token:
                # Fallback token pattern
                token_match = re.search(r'name="sylius_add_to_cart\[_token\]" value="([^"]+)"', html)
                token = token_match.group(1) if token_match else None
            
            # Extract name
            name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            product_name = name_match.group(1).strip() if name_match else f"Product {product_id}"
            
            # Extract price
            price = 0.0
            price_match = re.search(r'data-price="([^"]+)"', html)
            if price_match:
                price = float(price_match.group(1))
            else:
                # Try JSON-LD or schema.org
                price_match = re.search(r'"price":\s*"([^"]+)"', html)
                if price_match:
                    price = float(price_match.group(1))
                else:
                    # Generic pattern for Romanian currency
                    price_match = re.search(r'(\d+[,.]\d{2})\s*lei', html, re.I)
                    if price_match:
                        price = float(price_match.group(1).replace(',', '.'))
            
            # Extract image
            image_url = None
            img_match = re.search(r'property="og:image" content="([^"]+)"', html)
            if img_match:
                image_url = img_match.group(1)
            else:
                img_match = re.search(r'data-zoom-image="([^"]+)"', html)
                if img_match:
                    image_url = img_match.group(1)
            
            # Cache it
            product_cache.save_product_details(
                product_url=product_url,
                product_id=product_id,
                variant_id=variant_id,
                product_name=product_name,
                store_id=store_id,
                price=price,
                image_url=image_url
            )
            
            return {
                'status': 'success',
                'source': 'scraped',
                'product_id': product_id,
                'variant_id': variant_id,
                'token': token,
                'product_name': product_name,
                'product_url': product_url,
                'store_id': store_id,
                'price': price,
                'image_url': image_url
            }
                    
        except Exception as e:
            logger.error(f"Error extracting product details: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'product_url': product_url
            }

    @staticmethod
    def add_product_to_cart(
        product_id: str,
        variant_id: str,
        quantity: int,
        phpsessid: str,
        cookies: Dict[str, str],
        store: str = "carrefour_park_lake",
        product_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add product to Bringo cart
        """
        # If details missing, try to resolve from cache to get richer data (price, image)
        if not product_details:
             cached = product_cache.load_variant_by_product_id(product_id, store)
             if cached:
                 product_details = cached

        # Periodic cache cleanup
        import random
        if random.random() < 0.1:
            try:
                deleted = product_cache.cleanup_expired_cache(max_age_hours=48)
                if deleted > 0:
                    logger.info(f"🗑️ Auto-cleanup: removed {deleted} expired cache entries")
            except Exception as e:
                logger.warning(f"Cache cleanup failed: {e}")

        # 1. Get CSRF Token - Prioritizeprovided details, then fresh token endpoint
        token = product_details.get('token') if product_details else None
        
        if not token:
            logger.info("🔑 CSRF token missing, fetching from dedicated endpoint...")
            token = CartService.get_csrf_token(phpsessid, cookies)

        # Validation - variant_id must be in vsp- format for Bringo API
        # If we have valid product_details with variant_id, trust it to avoid redundant scraping
        is_variant_valid = variant_id and str(variant_id).startswith("vsp-")
        
        if not is_variant_valid:
            logger.warning(f"⚠️ Invalid variant_id format: '{variant_id}' (expected 'vsp-X-XXX-XXXXX')")
            
            # If product_details provided but invalid, we can't trust it. Force scrape.
            logger.info("🔎 Attempting to scrape correct variant_id from product page...")

            try:
                base_url = settings.BRINGO_BASE_URL
                product_url = f"{base_url}/ro/{store}/products/product-{product_id}"
                scrape_cookies = dict(cookies) if cookies else {}
                
                # Re-scrape to get fresh details including token (token from endpoint fallback already tried)
                details = CartService.extract_product_details_from_url(product_url, phpsessid, scrape_cookies)

                if details.get('status') == 'success' and details.get('variant_id', '').startswith('vsp-'):
                    variant_id = details['variant_id']
                    # Update token if found on page (might be fresher)
                    if details.get('token'):
                        token = details['token']
                    logger.info(f"✅ Scraped valid variant_id: {variant_id}")
                else:
                    logger.error(f"❌ Could not scrape valid variant_id. Details: {details.get('message', 'unknown')}")
                    return {
                        "status": "error",
                        "message": f"Invalid variant_id format and scraping fallback failed. Got '{variant_id}'"
                    }
            except Exception as e:
                logger.error(f"❌ Scraping fallback failed: {e}")
                return {
                    "status": "error",
                    "message": f"Invalid variant_id format and scraping fallback failed: {str(e)}"
                }
        
        logger.info(f"Adding product {product_id} (variant: {variant_id}, qty: {quantity}) to cart")
        if token:
            logger.info("🔑 Using CSRF token for request")
        
        try:
            base_url = settings.BRINGO_BASE_URL
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'x-requested-with': 'XMLHttpRequest',
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": base_url,
                "Referer": f"{base_url}/ro/{store}/products/product-{product_id}"
            }
            
            session.headers.update(headers)
            
            add_to_cart_url = f"{base_url}/ro/ajax/cart/add-item/{product_id}"
            form_data = {
                "sylius_add_to_cart[cartItem][variant]": variant_id,
                "sylius_add_to_cart[cartItem][quantity]": str(quantity)
            }
            
            if token:
                form_data["sylius_add_to_cart[_token]"] = token
            
            logger.info(f"Posting to: {add_to_cart_url}")
            
            # Retry logic
            max_retries = 2
            cart_response = None
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    cart_response = session.post(add_to_cart_url, data=form_data, timeout=30)
                    if cart_response.status_code == 500 and attempt < max_retries:
                        time.sleep(2 * (attempt + 1))
                        continue
                    break
                except requests.exceptions.Timeout as e:
                    last_error = e
                    if attempt < max_retries:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
            
            if cart_response is None:
                raise last_error or Exception("Failed to add to cart")
            
            logger.info(f"Response status: {cart_response.status_code}")

            if cart_response.status_code == 200:
                logger.info(f"Successfully added product {product_id} to cart")
                
                # Cache the successful mapping if not already cached
                product_cache.save_product_details(
                    product_url=f"{base_url}/ro/{store}/products/product-{product_id}",
                    product_id=product_id,
                    variant_id=variant_id,
                    product_name=product_details.get('product_name') if product_details else None,
                    store_id=store
                )

                return {
                    "status": "success",
                    "message": f"Added {quantity}x product {product_id} to cart",
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "product_name": product_details.get('product_name') if product_details else None,
                    "price": product_details.get('price') if product_details else 0,
                    "image_url": product_details.get('image_url') if product_details else None
                }
            else:
                logger.warning(f"Failed: Status {cart_response.status_code}")
                return {
                    "status": "error",
                    "message": f"Server returned status {cart_response.status_code}",
                    "http_status": cart_response.status_code,
                    "response_text": cart_response.text[:300]
                }
                
        except Exception as e:
            logger.error(f"Cart operation error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def resolve_variant_id(product_id: str, store_id: str, product_url: str, phpsessid: str, cookies: Dict[str, str], extra_data: Optional[Dict] = None) -> Optional[str]:
        """
        Resolve variant_id using Cache -> Feature Store -> Scraping
        """
        # 0. Check extra_data
        if extra_data and extra_data.get('variant_id') and str(extra_data['variant_id']).startswith('vsp-'):
             return extra_data['variant_id']

        # 1. Try cache
        cached_variant = product_cache.load_variant_by_product_id(product_id, store_id)
        if cached_variant and cached_variant.get('variant_id', '').startswith('vsp-'):
            logger.info(f"⚡ CACHE HIT! variant_id for {product_id}: {cached_variant['variant_id']}")
            return cached_variant['variant_id']

        logger.info(f"📦 Cache MISS for {product_id}, trying Feature Store...")

        # 2. Try Feature Store (via Vector Search enrichment)
        try:
            from features.realtime_server import RealTimeFeatureServer
            from api import dependencies
            feature_server = dependencies.get_feature_server()
            metadata = feature_server.get_product_metadata([str(product_id)])

            if str(product_id) in metadata:
                fs_variant = metadata[str(product_id)].get('variant_id')
                if fs_variant and str(fs_variant).startswith('vsp-'):
                    logger.info(f"⚡ Feature Store HIT! variant_id: {fs_variant}")
                    # Cache it for next time
                    product_cache.save_product_details(
                        product_url=product_url,
                        product_id=product_id,
                        variant_id=str(fs_variant),
                        product_name=metadata[str(product_id)].get('product_name'),
                        store_id=store_id
                    )
                    return str(fs_variant)
                else:
                    logger.warning(f"⚠️ Feature Store has product {product_id} but variant_id='{fs_variant}' (not vsp- format)")
            else:
                logger.warning(f"⚠️ Product {product_id} not found in Feature Store")
        except Exception as e:
            logger.warning(f"⚠️ Feature Store lookup failed: {e}")

        # 3. Fallback: scrape product page
        logger.info(f"🔎 Scraping product page for variant_id: {product_url}")
        details = CartService.extract_product_details_from_url(product_url, phpsessid, cookies)
        if details.get('status') == 'success' and details.get('variant_id', '').startswith('vsp-'):
            logger.info(f"✅ Scraped variant_id: {details['variant_id']}")
            return details['variant_id']

        logger.error(f"❌ Could not resolve variant_id for product {product_id} from any source")
        return None

    @staticmethod
    def add_product_optimized(
        product_id: str,
        store_id: str,
        product_url: str,
        quantity: int,
        phpsessid: str,
        cookies: Dict[str, str],
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Optimized add-to-cart: Cache -> Feature Store -> Scrape -> Add
        """
        # 1. Get full details (Cache -> Scrape -> Fallback)
        details = CartService.extract_product_details_from_url(product_url, phpsessid, cookies)
        
        if details.get('status') == 'error':
            # Fallback if URL scraping failed but potentially ID lookup works
            variant_id = CartService.resolve_variant_id(product_id, store_id, product_url, phpsessid, cookies)
            if not variant_id:
                return details
            details = {'variant_id': variant_id, 'status': 'success', 'product_id': product_id}
            
        variant_id = details.get('variant_id')

        return CartService.add_product_to_cart(
            product_id,
            variant_id,
            quantity,
            phpsessid,
            cookies,
            store_id,
            product_details=details
        )

    @staticmethod
    def add_products_batch(
        items: list,
        store_id: str,
        phpsessid: str,
        cookies: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Add multiple products to cart concurrently using ThreadPoolExecutor.

        Args:
            items: List of dicts with product_id, quantity, product_name (optional)
            store_id: Bringo store ID
            phpsessid: PHP session cookie
            cookies: Full cookie dict

        Returns:
            Dict with items_added, failed_items, and summary
        """
        import concurrent.futures
        import time as _time

        base_url = settings.BRINGO_BASE_URL
        results_added = []
        results_failed = []

        t0 = _time.time()

        # Phase 1: Resolve all variant_ids concurrently
        logger.info(f"🔄 Resolving variant_ids for {len(items)} products concurrently...")

        def resolve_one(item):
            pid = item['product_id']
            
            # 1. Check if we already have a valid variant_id from input
            if item.get('variant_id') and str(item['variant_id']).startswith('vsp-'):
                return {**item, 'source': 'input'}

            # 2. Use provided URL or construct default
            product_url = item.get('product_url')
            if not product_url:
                product_url = f"{base_url}/ro/{store_id}/products/product-{pid}"
            
            # 3. Resolve
            variant_id = CartService.resolve_variant_id(pid, store_id, product_url, phpsessid, cookies, extra_data=item)
            return {**item, 'variant_id': variant_id, 'product_url': product_url}

        resolved_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(resolve_one, item): item for item in items}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result.get('variant_id'):
                    resolved_items.append(result)
                else:
                    results_failed.append({
                        "product_id": result['product_id'],
                        "product_name": result.get('product_name', ''),
                        "error": "Could not resolve variant_id"
                    })

        t_resolve = (_time.time() - t0) * 1000
        logger.info(f"✅ Resolved {len(resolved_items)}/{len(items)} variant_ids in {t_resolve:.0f}ms")

        # Phase 2: Add resolved items to cart concurrently
        logger.info(f"🛒 Adding {len(resolved_items)} products to cart concurrently...")
        t1 = _time.time()

        def add_one(item):
            return CartService.add_product_to_cart(
                product_id=item['product_id'],
                variant_id=item['variant_id'],
                quantity=item.get('quantity', 1),
                phpsessid=phpsessid,
                cookies=cookies,
                store=store_id
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(add_one, item): item for item in resolved_items}
            for future in concurrent.futures.as_completed(futures):
                item = futures[future]
                result = future.result()
                if result.get('status') == 'success':
                    results_added.append({
                        "product_id": item['product_id'],
                        "product_name": item.get('product_name', ''),
                        "variant_id": item['variant_id'],
                        **result
                    })
                else:
                    results_failed.append({
                        "product_id": item['product_id'],
                        "product_name": item.get('product_name', ''),
                        "error": result.get('message', 'Unknown error')
                    })

        t_add = (_time.time() - t1) * 1000
        total_ms = (_time.time() - t0) * 1000

        logger.info(f"✅ Batch complete: {len(results_added)} added, {len(results_failed)} failed in {total_ms:.0f}ms")
        logger.info(f"   Resolve: {t_resolve:.0f}ms | Add: {t_add:.0f}ms")

        return {
            "status": "success" if results_added else "error",
            "message": f"Added {len(results_added)}/{len(items)} products to cart in {total_ms:.0f}ms",
            "items_added": results_added,
            "failed_items": results_failed,
            "timing_ms": {
                "total": round(total_ms),
                "resolve": round(t_resolve),
                "add": round(t_add)
            }
        }

    @staticmethod
    def clear_cart(phpsessid: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Attempt to clear the cart to resolve store conflicts
        """
        try:
            base_url = settings.BRINGO_BASE_URL
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
                
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': base_url,
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            })
            
            # Common Sylius/Bringo clear endpoints
            endpoints = [
                f"{base_url}/ro/cart/clear",
                f"{base_url}/ro/cart/remove-all",
                f"{base_url}/ro/ajax/cart/clear"
            ]
            
            # Try multiple HTTP methods for each endpoint (POST, GET, DELETE)
            for url in endpoints:
                logger.info(f"🗑️ Attempting to clear cart via {url} (POST)...")
                try:
                    resp = session.post(url, timeout=10, headers={'Referer': f"{base_url}/ro/cart"})
                    if resp.status_code in [200, 302, 204]:
                        logger.info("✅ Cart clear request success (POST)")
                        return {"status": "success", "message": "Cart cleared"}
                except Exception as e:
                    logger.debug(f"POST clear attempt failed for {url}: {e}")

                logger.info(f"🗑️ Attempting to clear cart via {url} (GET)...")
                try:
                    resp = session.get(url, timeout=10, headers={'Referer': f"{base_url}/ro/cart"})
                    if resp.status_code in [200, 302, 204]:
                        logger.info("✅ Cart clear request success (GET)")
                        return {"status": "success", "message": "Cart cleared"}
                except Exception as e:
                    logger.debug(f"GET clear attempt failed for {url}: {e}")

                logger.info(f"🗑️ Attempting to clear cart via {url} (DELETE)...")
                try:
                    resp = session.delete(url, timeout=10, headers={'Referer': f"{base_url}/ro/cart"})
                    if resp.status_code in [200, 202, 204]:
                        logger.info("✅ Cart clear request success (DELETE)")
                        return {"status": "success", "message": "Cart cleared"}
                except Exception as e:
                    logger.debug(f"DELETE clear attempt failed for {url}: {e}")

            # Fallback: fetch cart page and remove individual items (more reliable)
            logger.info("🗑️ Fallback: attempting to remove individual cart items")
            try:
                cart_page = session.get(f"{base_url}/ro/cart", timeout=10)
                if cart_page.status_code == 200:
                    html = cart_page.text
                    # Try to find cart item ids (common patterns)
                    import re as _re
                    item_ids = set()
                    # data-item-id or data-cart-item-id or input names
                    for m in _re.finditer(r'data-cart-item-id="?(\d+)"?', html):
                        item_ids.add(m.group(1))
                    for m in _re.finditer(r'data-item-id="?(\d+)"?', html):
                        item_ids.add(m.group(1))
                    for m in _re.finditer(r'cart_item_id["\']?[:=\\"\']?(\d+)', html):
                        item_ids.add(m.group(1))

                    if not item_ids:
                        logger.warning("No cart item ids found on cart page for per-item removal")
                    else:
                        for cid in item_ids:
                            remove_url = f"{base_url}/ro/ajax/cart/remove-item/{cid}"
                            try:
                                logger.info(f"🗑️ Removing cart item {cid} via {remove_url}")
                                resp = session.delete(remove_url, timeout=10, headers={'Referer': f"{base_url}/ro/cart"})
                                if resp.status_code in [200, 202, 204]:
                                    logger.info(f"✅ Removed item {cid}")
                                    continue
                                # Try GET-based update to zero qty as alternative
                                resp = session.get(f"{base_url}/ro/ajax/cart/update_qty", params={"item_id": cid, "qty": "0"}, timeout=10, headers={'Referer': f"{base_url}/ro/cart"})
                                if resp.status_code in [200, 202, 204]:
                                    logger.info(f"✅ Updated qty to 0 for item {cid}")
                                    continue
                            except Exception as e:
                                logger.debug(f"Failed removing item {cid}: {e}")

                        # Re-check cart summary
                        summary = CartService.get_cart_summary(phpsessid, cookies)
                        if summary.get('cart_count', 0) == 0:
                            return {"status": "success", "message": "Cart cleared"}

            except Exception as e:
                logger.debug(f"Fallback per-item removal failed: {e}")

            return {"status": "error", "message": "Could not clear cart"}
            
        except Exception as e:
            logger.error(f"Error clearing cart: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_csrf_token(phpsessid: str, cookies: Dict[str, str]) -> Optional[str]:
        """
        Get a fresh CSRF token from the dedicated customer token endpoint.
        Falls back to scraping the cart page if the JSON endpoint returns an empty body.
        """
        try:
            base_url = settings.BRINGO_BASE_URL
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }

            # --- Primary: JSON endpoint ---
            url = f"{base_url}/ro/customer/get-token"
            try:
                response = session.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    body = response.text.strip()
                    if body:  # Only parse if body is non-empty
                        try:
                            data = response.json()
                            token = data.get('token') or data.get('csrf_token') or data.get('value')
                            if token:
                                logger.info("✅ CSRF token retrieved from JSON endpoint")
                                return token
                        except Exception:
                            pass  # Fall through to HTML fallback
                    else:
                        logger.warning("⚠️ CSRF endpoint returned empty body, trying HTML fallback...")
                else:
                    logger.warning(f"⚠️ CSRF endpoint returned HTTP {response.status_code}, trying HTML fallback...")
            except Exception as e:
                logger.warning(f"⚠️ CSRF JSON endpoint error: {e}, trying HTML fallback...")

            # --- Fallback: scrape CSRF token from cart page HTML ---
            import re as _re
            try:
                cart_url = f"{base_url}/ro/cart"
                page_resp = session.get(cart_url, timeout=10)
                if page_resp.status_code == 200:
                    html = page_resp.text
                    patterns = [
                        r'name="sylius_add_to_cart\[_token\]"\s+value="([^"]+)"',
                        r'name="[^"]*_token[^"]*"\s+value="([^"]{10,})"',
                        r'value="([^"]{20,})"\s+name="[^"]*_token[^"]*"',
                    ]
                    for pat in patterns:
                        m = _re.search(pat, html)
                        if m:
                            token = m.group(1)
                            logger.info("✅ CSRF token scraped from cart HTML fallback")
                            return token
            except Exception as e:
                logger.warning(f"⚠️ CSRF HTML fallback failed: {e}")

            logger.warning("⚠️ Could not retrieve CSRF token — continuing without it")
            return None

        except Exception as e:
            logger.error(f"Error getting CSRF token: {e}")
            return None

    @staticmethod
    def get_cart_items_mapping(phpsessid: str, cookies: Dict[str, str]) -> Dict[str, str]:
        """
        Retrieves the cart content and creates a mapping from product_id to cart_item_id.
        Necessary for deletion via Bringo API.
        """
        try:
            url = f"{settings.BRINGO_BASE_URL}/ro/cart"
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
            
            response = session.get(url, timeout=15)
            if response.status_code != 200:
                return {}
            
            html = response.text
            mapping = {}
            
            # Use regex to find product links and their corresponding cart item IDs
            # Typical pattern: <a href=".../products/.../PRODUCT_ID">... data-cart-item-id="ITEM_ID"
            # Or inputs: name="sylius_cart[items][INDEX][quantity]" data-product-id="PID" ... then find CID
            
            # Pattern 1: Regex for data-item-id and data-product-id nearby
            # This is a bit of a scrape, but necessary.
            import re as _re
            
            # Simple approach: find all item IDs and see if we can associate them
            # We'll use a more robust way: find blocks of items
            item_blocks = _re.findall(r'<tr[^>]*class="[^"]*sylius-cart-item[^"]*"[^>]*>(.*?)</tr>', html, _re.DOTALL)
            
            for block in item_blocks:
                pid_match = _re.search(r'/products/[^/]+/product-(\d+)', block)
                if not pid_match:
                    pid_match = _re.search(r'data-product-id="(\d+)"', block)
                
                cid_match = _re.search(r'data-cart-item-id="(\d+)"', block)
                if not cid_match:
                    cid_match = _re.search(r'data-item-id="(\d+)"', block)
                
                if pid_match and cid_match:
                    pid = pid_match.group(1)
                    cid = cid_match.group(1)
                    mapping[pid] = cid
                    logger.debug(f"Mapped Product {pid} to Cart Item {cid}")

            return mapping
        except Exception as e:
            logger.error(f"Error mapping cart items: {e}")
            return {}

    @staticmethod
    def remove_item_from_cart(product_id: str, phpsessid: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Remove a specific product from the cart.
        Logic: Map product_id -> cart_item_id -> DELETE call
        """
        try:
            mapping = CartService.get_cart_items_mapping(phpsessid, cookies)
            cart_item_id = mapping.get(str(product_id))
            
            if not cart_item_id:
                return {
                    "status": "error",
                    "message": f"Product {product_id} not found in cart."
                }
            
            base_url = settings.BRINGO_BASE_URL
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
            
            # The removal usually requires a DELETE request to an AJAX endpoint
            remove_url = f"{base_url}/ro/ajax/cart/remove-item/{cart_item_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f"{base_url}/ro/cart",
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            
            logger.info(f"🗑️ Removing product {product_id} (Item ID: {cart_item_id})")
            response = session.delete(remove_url, headers=headers, timeout=15)
            
            if response.status_code in [200, 204, 202]:
                logger.info(f"✅ Successfully removed product {product_id}")
                return {
                    "status": "success",
                    "message": f"Product {product_id} removed from cart",
                    "cart_item_id": cart_item_id
                }
            else:
                logger.warning(f"⚠️ Failed to remove item: Status {response.status_code}")
                return {
                    "status": "error",
                    "message": f"Server returned status {response.status_code}",
                    "response": response.text[:200]
                }
                
        except Exception as e:
            logger.error(f"Error removing item: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def update_item_quantity(product_id: str, quantity: int, phpsessid: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """
        Update quantity for a specific product in the cart.
        """
        try:
            mapping = CartService.get_cart_items_mapping(phpsessid, cookies)
            cart_item_id = mapping.get(str(product_id))
            
            if not cart_item_id:
                # If not in cart, try adding it instead?
                # User wants "add more", so it should be there.
                return {
                    "status": "error",
                    "message": f"Product {product_id} not found in cart."
                }
            
            base_url = settings.BRINGO_BASE_URL
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')
            
            update_url = f"{base_url}/ro/ajax/cart/save-quantity/{cart_item_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f"{base_url}/ro/cart",
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
            
            logger.info(f"🔢 Updating product {product_id} to qty {quantity}")
            response = session.post(update_url, data={'qty': str(quantity)}, headers=headers, timeout=15)
            
            if response.status_code in [200, 204, 202]:
                return {
                    "status": "success",
                    "message": f"Product {product_id} quantity updated to {quantity}",
                    "quantity": quantity
                }
            else:
                return {
                    "status": "error",
                    "message": f"Server returned status {response.status_code}",
                    "response": response.text[:200]
                }
        except Exception as e:
            logger.error(f"Error updating qty: {e}")
            return {"status": "error", "message": str(e)}



    @staticmethod
    def get_cart_summary(phpsessid: str, cookies: Dict[str, str]) -> Dict[str, Any]:
        """Get current cart contents with full item details"""
        try:
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='www.bringo.ro')

            # Fetch the full cart page to extract items
            url = f"{settings.BRINGO_BASE_URL}/ro/cart"
            response = session.get(url, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "partial",
                    "cart_count": -1,
                    "items": [],
                    "message": f"HTTP {response.status_code}"
                }

            html = response.text
            items = []

            import re as _re
            item_blocks = _re.findall(r'<tr[^>]*class="[^"]*sylius-cart-item[^"]*"[^>]*>(.*?)</tr>', html, _re.DOTALL)

            for block in item_blocks:
                pid_match = _re.search(r'/products/[^/]+/product-(\d+)', block)
                if not pid_match:
                    pid_match = _re.search(r'data-product-id="(\d+)"', block)

                cid_match = _re.search(r'data-cart-item-id="(\d+)"', block)
                if not cid_match:
                    cid_match = _re.search(r'data-item-id="(\d+)"', block)

                name_match = _re.search(r'<a[^>]*>([^<]+)</a>', block)
                product_name = name_match.group(1).strip() if name_match else "Unknown Product"

                qty_match = _re.search(r'value="(\d+)"[^>]*name="[^"]*quantity[^"]*"', block)
                if not qty_match:
                    qty_match = _re.search(r'name="[^"]*quantity[^"]*"[^>]*value="(\d+)"', block)
                quantity = int(qty_match.group(1)) if qty_match else 1

                price = 0.0
                price_match = _re.search(r'(\d+[.,]\d{2})\s*lei', block)
                if price_match:
                    price = float(price_match.group(1).replace(',', '.'))

                img_match = _re.search(r'<img[^>]*src="([^"]+)"', block)
                image_url = img_match.group(1) if img_match else None

                if pid_match:
                    items.append({
                        "product_id": pid_match.group(1),
                        "cart_item_id": cid_match.group(1) if cid_match else None,
                        "product_name": product_name,
                        "quantity": quantity,
                        "price": price,
                        "image_url": image_url
                    })

            return {
                "status": "success",
                "cart_count": len(items),
                "items": items
            }
        except Exception as e:
            logger.error(f"Error fetching cart: {e}")
            return {"status": "error", "message": str(e), "items": []}
