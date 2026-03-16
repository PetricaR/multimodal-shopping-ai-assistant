"""
Product Search Service
Real web scraping for searching products on Bringo
"""
import logging
import json
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Union, Any, Optional

from config.settings import settings
from services.search_cache import (
    save_search_results,
    load_search_results,
    cleanup_expired_cache
)

logger = logging.getLogger(__name__)

# Constants
MAX_PRODUCTS_PER_SEARCH = 10
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
}

class SearchService:
    @staticmethod
    def _search_product_sync(product_query: str, store_id: str, store_name: str) -> Dict[str, Any]:
        """Internal sync search for threading"""
        logger.info(f"🔍 Searching '{product_query}' at store: {store_id}")
        
        search_url = f"{settings.BRINGO_BASE_URL}/ro/search/{store_id}"
        params = {'criteria[search][value]': product_query}
        
        last_error = None
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(
                    search_url,
                    params=params,
                    headers=HTTP_HEADERS,
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < MAX_RETRIES:
                        continue
                    else:
                        return {
                            'success': False,
                            'store_id': store_id,
                            'store_name': store_name,
                            'error': last_error
                        }
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                product_elements = soup.select('div.box-product')[:MAX_PRODUCTS_PER_SEARCH]
                
                products = []
                for elem in product_elements:
                    try:
                        name_link = elem.select_one('a.bringo-product-name')
                        if not name_link: continue
                        
                        name = name_link.get_text(strip=True)
                        href = name_link.get('href')
                        url = href if href.startswith('http') else f"{settings.BRINGO_BASE_URL}{href}"
                        
                        price_elem = elem.select_one('div.bringo-product-price')
                        price_text = price_elem.get_text(strip=True) if price_elem else "0"
                        price_match = re.search(r'(\d+[,.]\d+)', price_text.replace(' ', ''))
                        price = float(price_match.group(1).replace(',', '.')) if price_match else 0.0
                        
                        if price == 0.0: continue
                        
                        available = 'out-of-stock' not in str(elem).lower()
                        
                        # Extract product_id and variant_id from the result box
                        # Usually Bringo has these in data attributes or hidden inputs
                        product_id = None
                        variant_id = None
                        
                        # Try to find product_id in URL or data attributes
                        url_match = re.search(r'/products/[^/]*/(\d+)$', url)
                        if url_match:
                            product_id = url_match.group(1)
                        
                        # Alternative product_id extraction from data attributes
                        if not product_id:
                            product_link = elem.select_one('a.bringo-product-name')
                            if product_link:
                                product_id = product_link.get('data-product-id')
                        
                        # Try to find variant ID in hidden input or data attributes
                        variant_input = elem.find('input', {'name': 'sylius_add_to_cart[cartItem][variant]'})
                        if variant_input:
                            variant_id = variant_input.get('value')

                        if not variant_id:
                            # Try data attribute
                            variant_id = elem.get('data-variant-id')

                        products.append({
                            'name': name,
                            'price': price,
                            'url': url,
                            'product_id': product_id,
                            'variant_id': variant_id,
                            'available': available,
                            'store_id': store_id,
                            'store_name': store_name
                        })
                    except:
                        continue
                        
                return {
                    'success': True,
                    'store_id': store_id,
                    'store_name': store_name,
                    'products': products
                }
                
            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return {
                        'success': False,
                        'store_id': store_id,
                        'store_name': store_name,
                        'error': last_error
                    }

    @staticmethod
    def search_multi_store(product_queries: List[str], stores: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Search for products across multiple stores in parallel
        
        Args:
            product_queries: List of product names
            stores: List of dicts with store_id and store_name
        """
        start_time = datetime.now()
        
        all_results = {}
        futures = {}
        executor = ThreadPoolExecutor(max_workers=10)
        
        try:
            # Create tasks
            for query in product_queries:
                all_results[query] = {
                    "query": query,
                    "products": [],
                    "searched_stores": []
                }
                
                for store in stores:
                    store_id = store.get('store_id')
                    store_name = store.get('store_name', store_id)
                    
                    if not store_id: continue
                    
                    future = executor.submit(
                        SearchService._search_product_sync, 
                        query, store_id, store_name
                    )
                    futures[future] = (query, store_name)
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    query, store_name = futures[future]
                    
                    if result['success']:
                        all_results[query]['products'].extend(result['products'])
                        if store_name not in all_results[query]['searched_stores']:
                            all_results[query]['searched_stores'].append(store_name)
                            
                except Exception as e:
                    logger.error(f"Search task failed: {e}")
            
            # Sort by price
            for query in all_results:
                products = all_results[query]['products']
                if products:
                    products.sort(key=lambda x: x['price'])
                    all_results[query]['cheapest_price'] = products[0]['price']
                    all_results[query]['total_found'] = len(products)
                else:
                    all_results[query]['cheapest_price'] = None
                    all_results[query]['total_found'] = 0
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            result = {
                "status": "success",
                "results": all_results,
                "elapsed_seconds": elapsed,
                "searched_at": datetime.now().isoformat()
            }
            
            # Cache results
            cache_key = save_search_results(result)
            if cache_key:
                result["cache_key"] = cache_key
                
            return result
            
        finally:
            executor.shutdown(wait=False)

    @staticmethod
    def compare_products(products: List[Dict[str, Any]], target_category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Compare products using robust logic from reference implementation
        Calculates quality scores based on brands, sizes, and categories
        """
        if not products:
            return []
            
        logger.info(f"📊 Comparing {len(products)} products...")
        
        # Reference Brand tiers
        PREMIUM_BRANDS = [
            "bio", "organic", "zuzu", "napolact", "olymp", "danone", "hochland", 
            "president", "fuchs", "kotanyi", "illy", "jacobs", "lavazza", 
            "barilla", "de cecco", "purgis", "muller", "milka", "kinder"
        ]
        
        ECONOMY_BRANDS = ["carrefour", "simpl", "drag de romania", "365", "k-classic", "pilos"]
        
        scored_products = []
        for p in products:
            name = (p.get('name') or p.get('product_name') or '').lower()
            price = p.get('price') or 0.0
            
            # 1. Base Quality Score
            quality_score = 0.5 # Neutral
            
            # Brand analysis
            is_premium = any(brand in name for brand in PREMIUM_BRANDS)
            is_economy = any(brand in name for brand in ECONOMY_BRANDS)
            
            if is_premium:
                quality_score += 0.3
            elif is_economy:
                quality_score -= 0.1
                
            # 2. Rating simulation (until real ratings available)
            # Higher price often correlates with higher perceived quality in some cats
            # but we use a normalized score
            rating = 4.0 if not is_premium else 4.5
            if is_economy: rating = 3.8
            
            p['quality_score'] = round(min(quality_score, 1.0), 2)
            p['rating'] = rating
            
            # 3. Price Score (competitive analysis)
            # Find price rank
            p['price_score'] = 1.0 # Will normalize later
            
            scored_products.append(p)
            
        # Normalize Price Score across results
        if scored_products:
            prices = [p['price'] for p in scored_products if p['price'] > 0]
            if prices:
                min_p, max_p = min(prices), max(prices)
                price_range = max_p - min_p if max_p > min_p else 1.0
                
                for p in scored_products:
                    # Lower price = Higher score (1.0 = cheapest)
                    p['price_score'] = round(1.0 - ((p['price'] - min_p) / price_range), 2)
        
        # Sort by composite score (Relevance)
        scored_products.sort(key=lambda x: (x.get('available', True), x.get('quality_score', 0) * 0.4 + x.get('price_score', 0) * 0.6), reverse=True)
        
        return scored_products

    @staticmethod
    def optimize_budget_for_quality(cache_key: str, budget_ron: float) -> Dict[str, Any]:
        """
        Optimize shopping list to fit budget while maximizing quality
        Logic from 'optimize_budget_for_quality' reference tool
        """
        data = load_search_results(cache_key)
        if not data:
            return {"status": "error", "message": "Cache key not found or expired"}
            
        results = data.get("results", {})
        if not results:
             return {"status": "error", "message": "No search results found to optimize"}
             
        # Initial selection: Best Quality-to-Price ratio
        items_to_buy = []
        
        for query, q_data in results.items():
            products = q_data.get("products", [])
            if not products: continue
            
            # Enrich with scores
            scored = SearchService.compare_products(products)
            # Pick best balance
            best_pick = scored[0] # compare_products already sorts by quality + price balance
            items_to_buy.append({
                "query": query,
                "best_pick": best_pick,
                "alternatives": scored[1:3]
            })
            
        # Budget adjustment loop
        current_total = sum(item['best_pick']['price'] for item in items_to_buy)
        
        if current_total > budget_ron:
            logger.info(f"⚠️ Initial total {current_total} RON exceeds budget {budget_ron} RON. Adjusting...")
            # Optimization: swap higher quality for cheaper alternatives till under budget
            # sorted by absolute price to cut costs fastest
            items_to_buy.sort(key=lambda x: x['best_pick']['price'], reverse=True)
            
            for i in range(len(items_to_buy)):
                if current_total <= budget_ron: break
                
                item = items_to_buy[i]
                if item['alternatives']:
                    # Find cheaper alt
                    cheaper = min(item['alternatives'], key=lambda x: x['price'])
                    if cheaper['price'] < item['best_pick']['price']:
                        diff = item['best_pick']['price'] - cheaper['price']
                        current_total -= diff
                        item['best_pick'] = cheaper
                        
        return {
            "status": "success",
            "budget": budget_ron,
            "final_total": round(current_total, 2),
            "items": [item['best_pick'] for item in items_to_buy],
            "under_budget": current_total <= budget_ron,
            "savings": round(budget_ron - current_total, 2) if budget_ron > current_total else 0
        }

    @staticmethod
    def clean_ingredient_for_search(ingredient: str) -> str:
        """
        Clean an ingredient string to create a better search query.
        Removes quantities, units, and common Romanian stop words.
        """
        # Lowercase and remove punctuation
        clean = ingredient.lower()
        clean = re.sub(r'[^\w\s]', ' ', clean)
        
        # Remove numbers
        clean = re.sub(r'\d+', ' ', clean)
        
        # Romanian units and stop-words
        # Note: we use a more robust list and ensure they are removed as whole words
        stop_words = [
            'gram', 'grame', 'kg', 'g', 'ml', 'l', 'litru', 'litri',
            'lingura', 'linguri', 'lingurita', 'lingurite', 'bucata', 'bucati',
            'cana', 'cani', 'pachet', 'pachete', 'legatura', 'legaturi',
            'varf de cutit', 'dupa gust', 'sare', 'piper', 'de', 'si', 'un', 'o',
            'bine', 'scursa', 'grasa', 'pufosi', 'copilariei', 'video'
        ]
        
        # Sort by length descending to match longer phrases first
        stop_words.sort(key=len, reverse=True)
        
        for word in stop_words:
            pattern = r'\b' + re.escape(word) + r'\b'
            clean = re.sub(pattern, ' ', clean)
        
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        
        # Limit to first 3-4 keywords to avoid over-specific searches
        keywords = clean.split()
        if len(keywords) > 4:
            clean = ' '.join(keywords[:4])
            
        return clean

    @staticmethod
    def optimize_cart(cache_key: str) -> Dict[str, Any]:
        """
        Optimize cart based on cached search results
        Strategy: Single store vs Mixed store cheapest options
        """
        data = load_search_results(cache_key)
        if not data:
            return {"status": "error", "message": "Cache key not found or expired"}
            
        results = data.get("results", {})
        if not results:
             return {"status": "error", "message": "No search results found to optimize"}
             
        # Determine available stores
        all_stores = set()
        for query_data in results.values():
            for p in query_data.get("products", []):
                if p.get("store_name"):
                    all_stores.add(p.get("store_name"))
        
        # Strategy 1: Cheapest global (Best Price - Mixed Stores)
        cheapest_cart = []
        total_cheapest = 0
        
        # Strategy 2: Single Store carts
        store_carts = {store: {"items": [], "total": 0, "missing": []} for store in all_stores}
        
        for query, q_data in results.items():
            products = q_data.get("products", [])
            
            if not products:
                # Mark missing in all stores
                for store in all_stores:
                    store_carts[store]["missing"].append(query)
                continue
                
            # Cheapest global
            cheapest = products[0]
            cheapest_cart.append(cheapest)
            total_cheapest += cheapest['price']
            
            # Per store
            products_by_store = {p['store_name']: p for p in products}
            
            for store in all_stores:
                if store in products_by_store:
                    p = products_by_store[store]
                    store_carts[store]["items"].append(p)
                    store_carts[store]["total"] += p['price']
                else:
                    store_carts[store]["missing"].append(query)
                    
        # Find best single store (the one with least missing and lowest price)
        # We sort by (number of missing, total price)
        sorted_stores = sorted(
            store_carts.items(), 
            key=lambda x: (len(x[1]["missing"]), x[1]["total"])
        )
        
        best_single_store = sorted_stores[0] if sorted_stores else None
            
        return {
            "status": "success",
            "optimization": {
                "cheapest_mixed": {
                    "total": round(total_cheapest, 2),
                    "items": cheapest_cart,
                    "delivery_count": len(set(p['store_name'] for p in cheapest_cart))
                },
                "best_single_store": {
                    "store": best_single_store[0] if best_single_store else None,
                    "total": round(best_single_store[1]["total"], 2) if best_single_store else 0,
                    "items": best_single_store[1]["items"] if best_single_store else [],
                    "missing_items": best_single_store[1]["missing"] if best_single_store else list(results.keys())
                },
                "all_store_options": store_carts
            }
        }
