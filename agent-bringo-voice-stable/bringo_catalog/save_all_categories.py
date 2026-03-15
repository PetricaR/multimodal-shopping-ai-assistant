import asyncio
import aiohttp
import ssl
import json
import logging
import re
from pathlib import Path
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fetch_categories(store="carrefour_park_lake"):
    """
    Fetches all/most categories by visiting the store details/landing page.
    """
    # The "Back" link from Bacanie points here, likely the department list
    base_url = f"https://www.bringo.ro/ro/store-details/{store}"
    
    logger.info(f"Fetching categories from: {base_url}")

    # Standard headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    # SSL context 
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(base_url, headers=headers) as response:
            if response.status != 200:
                logger.error(f"Failed to load page. Status: {response.status}")
                return {}
            
            html = await response.text()
            
            # Save debug HTML
            with open("debug_nav_root.html", "w") as f:
                f.write(html)
            logger.info("Saved debug_nav_root.html")

            soup = BeautifulSoup(html, 'html.parser')

            categories = {}
            
            # Find sidebar links pattern: /ro/store/<store_slug>/<category_slug>
            # This regex captures the category slug at the end
            pattern = re.compile(rf'/ro/store/{store}/([\w-]+(?:-\d+)?)$')
            
            links = []
            
            # Strategy 1: Look for the main category grid (store landing page)
            # Based on user HTML, this is inside div.bringo-category-list-box
            grid_box = soup.find('div', class_='bringo-category-list-box')
            if grid_box:
                logger.info("Found 'bringo-category-list-box' grid. Extracting departments...")
                # Links are often in 'box-inner' class or just direct anchors
                links.extend(grid_box.find_all('a', href=True))
            
            # Strategy 2: Look for sidebar menu (if on a category page)
            # div.bringo-product-listing-category-menu
            sidebar_menu = soup.find('div', class_='bringo-product-listing-category-menu')
            if sidebar_menu:
                 logger.info("Found 'bringo-product-listing-category-menu' sidebar. Extracting...")
                 links.extend(sidebar_menu.find_all('a', href=True))

            # Strategy 3: Fallback - all links if we found nothing specific
            if not links:
                logger.warning("No specific category container found. Scanning all links...")
                links = soup.find_all('a', href=True)

            logger.info(f"Scanning {len(links)} links...")
            
            # Simple regex to check if we are seeing ANY store links
            # Pattern: /ro/store/{store}/...
            generic_pattern = re.compile(r'/ro/store/([^/]+)/([^/]+)$')

            for link in links:
                href = link['href']
                
                # Debug log for meaningful links
                if "/ro/store/" in href:
                    logger.info(f"Checking: {href}")
                
                match = generic_pattern.search(href)
                if match:
                    found_store = match.group(1)
                    slug = match.group(2)
                    
                    if found_store == store:
                        # Try to find a good name
                        h4 = link.find('h4')
                        if h4:
                            name = h4.get_text(strip=True)
                        else:
                            name = link.get_text(strip=True)
                        
                        # Basic cleanup
                        if not name:
                            name = slug.replace('-', ' ').title()
                        
                        # Filter out short/junk matches and 'Back' links
                        if len(name) > 2 and "inapoi" not in name.lower() and slug not in categories.values():
                            categories[name] = slug
                            logger.info(f"  MATCH! Added: {name} -> {slug}")
                    else:
                        logger.debug(f"  Skipping store mismatch: {found_store} != {store}")
                else:
                    if "/ro/store/" in href and store in href:
                         logger.warning(f"  Regex failed for: {href}")

            logger.info(f"Found {len(categories)} unique categories.")

            logger.info(f"Found {len(categories)} unique categories.")
            return categories

def save_categories(categories, output_dir):
    """Saves categories dict to JSON"""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_file = path / "bringo_categories.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Successfully saved categories to: {output_file}")
    print(f"\nSaved {len(categories)} categories to {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract Bringo Categories")
    parser.add_argument("--store", default="carrefour_park_lake", help="Store slug")
    args = parser.parse_args()
    
    # Run
    output_directory = Path(__file__).parent
    cats = asyncio.run(fetch_categories(args.store))
    
    if cats:
        save_categories(cats, output_directory)
    else:
        logger.error("No categories extracted.")
