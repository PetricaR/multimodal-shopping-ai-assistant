
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_search")

def test_urls():
    base_url = "https://www.bringo.ro"
    store_id = "carrefour_park_lake"
    query = "lapte"
    
    # Cookie is needed? Usually search page works without login, but let's see.
    # We will try without cookies first.
    
    urls = [
        f"{base_url}/ro/{store_id}", # Store Homepage
        f"{base_url}/ro/{store_id}/products",
        f"{base_url}/ro/magazin/carrefour-park-lake", # Try slug variation
        f"{base_url}/ro/carrefour-park-lake",
        f"{base_url}/ro/search" # Global search?
    ]
    
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    })

    for url in urls:
        try:
            logger.info(f"Testing: {url}")
            resp = s.get(url, timeout=10)
            logger.info(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                if "product-" in resp.text:
                    logger.info("✅ Found product links in response!")
                else:
                    logger.info("⚠️ 200 OK but no products found in HTML (might be empty or JS rendered)")
        except Exception as e:
            logger.error(f"Error: {e}")

if __name__ == "__main__":
    test_urls()
