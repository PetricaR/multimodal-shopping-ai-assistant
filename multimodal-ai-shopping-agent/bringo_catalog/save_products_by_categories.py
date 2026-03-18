"""
Extract products from specific Bringo categories using authenticated session.
Supports multiple input methods: CLI args, JSON file, or direct script editing.

Based on existing scripts:
- Authentication: save_all_categories.py
- Product extraction: bringo_products_v2.py
"""
import asyncio
import aiohttp
import ssl
import json
import logging
import sys
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import pandas as pd

# Add parent directory to path to import authentication module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.tools.authentication import authenticate_with_credentials, get_authentication_from_state, validate_session
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION: Edit these categories directly for quick testing
# ============================================================================
DEFAULT_CATEGORIES = [
    # Add category slugs here, e.g.:
    # "bacanie-169",
    # "fructe-si-legume-170",
    # "lactate-171",
]

# ============================================================================
# AUTHENTICATION (Reused from save_all_categories.py)
# ============================================================================

def get_authenticated_session():
    """
    Get or create an authenticated Bringo session.
    Uses local JSON file cache to avoid re-authentication.
    Returns PHPSESSID cookie value.
    """
    from datetime import datetime
    
    session_file = Path(__file__).parent / "bringo_session.json"
    
    logger.info("🔐 Checking for existing authentication...")
    
    # Try to load from local JSON cache first
    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            phpsessid = session_data.get('phpsessid')
            expires_at = session_data.get('expires_at')
            username = session_data.get('username')
            
            if phpsessid and expires_at:
                # Parse expiration time
                expiration = datetime.fromisoformat(expires_at)
                now = datetime.now()
                
                if now < expiration:
                    time_remaining = expiration - now
                    logger.info(f"📦 Found valid cached session for: {username}")
                    logger.info(f"⏰ Session valid for: {time_remaining}")
                    logger.info(f"✅ Using cached PHPSESSID from: {session_file.name}")
                    return phpsessid
                else:
                    logger.info(f"⏰ Cached session expired at: {expires_at}")
                    logger.info("🔄 Re-authenticating...")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load cached session: {e}")
    
    # No valid cached session, need to authenticate
    logger.info("⚠️ No valid cached session. Authenticating with credentials...")
    
    # Get credentials from settings
    username = settings.BRINGO_USERNAME
    password = settings.BRINGO_PASSWORD
    store = settings.BRINGO_STORE
    
    if not username or not password:
        raise Exception("BRINGO_USERNAME and BRINGO_PASSWORD must be set in .env file")
    
    # Authenticate using Selenium
    logger.info(f"🚀 Starting Selenium authentication for: {username}")
    auth_result = json.loads(authenticate_with_credentials(username, password, store))
    
    if auth_result.get('status') != 'success':
        error_msg = auth_result.get('message', 'Unknown error')
        raise Exception(f"Authentication failed: {error_msg}")
    
    phpsessid = auth_result.get('phpsessid')
    expires_at = auth_result.get('expires_at')
    
    # Save to local JSON cache
    session_data = {
        'phpsessid': phpsessid,
        'expires_at': expires_at,
        'username': username,
        'authenticated_at': datetime.now().isoformat()
    }
    
    with open(session_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    logger.info(f"✅ Authentication successful! Session expires at: {expires_at}")
    logger.info(f"💾 Saved session to: {session_file.name}")
    
    return phpsessid

# ============================================================================
# PRODUCT EXTRACTION (Adapted from bringo_products_v2.py)
# ============================================================================

def clean_price(price_text):
    """Extract numeric price from text."""
    if not price_text:
        return None
    price_match = re.search(r'([0-9]+[,.][0-9]+)', price_text)
    if price_match:
        return float(price_match.group(1).replace(',', '.'))
    return None

def extract_discount(original_price, current_price):
    """Calculate discount percentage from prices."""
    if original_price and current_price and original_price > current_price:
        return round(((original_price - current_price) / original_price) * 100)
    return 0

async def extract_products_from_category(
    session: aiohttp.ClientSession,
    phpsessid: str,
    category_slug: str,
    store: str,
    max_products: Optional[int] = None,
    fetch_details: bool = False
) -> List[Dict]:
    """
    Extract all products from a single category with pagination.
    
    Args:
        session: aiohttp session
        phpsessid: Valid PHPSESSID cookie (currently unused - testing without auth)
        category_slug: Category slug (e.g., "bacanie-169")
        store: Store slug (e.g., "carrefour_park_lake")
        max_products: Maximum products to extract (None = all)
        fetch_details: Whether to fetch detailed product info
    
    Returns:
        List of product dictionaries
    """
    base_url = f"https://www.bringo.ro/ro/store/{store}/{category_slug}"
    products = []
    page = 1
    
    # Headers WITHOUT authentication (testing like bringo_products_v2.py)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.bringo.ro/',
        # NOTE: Removed PHPSESSID cookie to test if it works without auth
        # 'Cookie': f'PHPSESSID={phpsessid}'
    }
    
    while True:
        # Build paginated URL
        current_url = f"{base_url}?limit=100&page={page}"
        logger.info(f"  📄 Fetching page {page}: {current_url}")
        
        try:
            async with session.get(current_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"  ❌ Page {page} failed with status {response.status}")
                    break
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find all product boxes
                product_boxes = soup.find_all('div', class_='box-product')
                
                if not product_boxes:
                    logger.info(f"  ℹ️ No products on page {page}. End of category.")
                    break
                
                page_products = []
                
                for product_box in product_boxes:
                    # Check if we've reached the limit
                    if max_products and len(products) + len(page_products) >= max_products:
                        break
                    
                    try:
                        # Extract product name and URL
                        product_name_tag = product_box.find('a', class_='bringo-product-name')
                        if not product_name_tag:
                            continue
                        
                        product_name = product_name_tag.get_text(strip=True)
                        product_url = urljoin("https://www.bringo.ro", product_name_tag.get('href', ''))
                        
                        # Extract product ID from URL
                        product_id = None
                        url_match = re.search(r'/products/[^/]*/(\\d+)$', product_url)
                        if url_match:
                            product_id = int(url_match.group(1))
                        
                        if not product_id:
                            logger.debug(f"  ⏭️ Skipping product '{product_name}' - no Product ID")
                            continue
                        
                        # Extract variant ID
                        variant_id = None
                        variant_input = product_box.find('input', {'name': 'sylius_add_to_cart[cartItem][variant]'})
                        if variant_input:
                            variant_id = variant_input.get('value')
                        
                        # Extract prices from ecommerce data
                        price = None
                        original_price = None
                        
                        ecommerce_a = product_box.find('a', onclick=re.compile(r'ecommerce_item'))
                        if ecommerce_a:
                            try:
                                onclick_attr = ecommerce_a.get('onclick')
                                match = re.search(r'ecommerce_item\((.*?),\s*[\'"]select_item[\'"]\)', onclick_attr)
                                if match:
                                    json_str = match.group(1).replace('&quot;', '"')
                                    ecommerce_data = json.loads(json_str)
                                    price = ecommerce_data.get('price', 0) / 100
                                    original_price = ecommerce_data.get('initial_price', 0) / 100
                            except Exception as e:
                                logger.debug(f"  ⚠️ Failed to parse ecommerce data: {e}")
                        
                        # Fallback to price tag
                        if price is None:
                            price_tag = product_box.find('div', class_='bringo-product-price')
                            if price_tag:
                                price = clean_price(price_tag.get_text(strip=True))
                                original_price = price
                        
                        # Calculate discount
                        discount_percentage = extract_discount(original_price, price)
                        
                        # Extract image
                        img_tag = product_box.find('img', class_='image-product')
                        image_url = img_tag.get('src', '') if img_tag else None
                        if image_url:
                            image_url = re.sub(r'/web/cache/[^/]+/', '/web/cache/sylius_shop_product_original/', image_url)
                        
                        # Build product data
                        product_data = {
                            'product_name': product_name,
                            'product_url': product_url,
                            'product_id': product_id,
                            'variant_id': variant_id,
                            'price_ron': price,
                            'original_price_ron': original_price,
                            'discount_percentage': discount_percentage,
                            'category': category_slug,
                            'image_url': image_url,
                            'in_stock': True,
                            'store': store,
                            'description': None,
                            'producer': None,
                            'product_number': None,
                            'sgr_fee': None,
                            'country_origin': None,
                            'ingredients': None,
                            'nutritional_info': None
                        }
                        
                        page_products.append(product_data)
                    
                    except Exception as e:
                        logger.error(f"  ⚠️ Error processing product: {e}")
                
                if not page_products:
                    logger.info(f"  ℹ️ No valid products on page {page}. Stopping.")
                    break
                
                products.extend(page_products)
                logger.info(f"  ✅ Page {page}: Extracted {len(page_products)} products. Total so far: {len(products)}")
                
                # Check if we've reached the limit
                if max_products and len(products) >= max_products:
                    logger.info(f"  🎯 Reached max products limit ({max_products}). Stopping.")
                    break
                
                page += 1
        
        except Exception as e:
            logger.error(f"  ❌ Error fetching page {page}: {e}")
            break
    
    return products

# ============================================================================
# CATEGORY INPUT PARSING
# ============================================================================

def load_categories_from_json(file_path: str) -> List[str]:
    """Load categories from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'categories' in data:
                return data['categories']
            elif isinstance(data, list):
                return data
            else:
                raise ValueError("JSON must be a list or dict with 'categories' key")
    except Exception as e:
        logger.error(f"Failed to load categories from {file_path}: {e}")
        raise

def parse_category_input(
    cli_categories: Optional[str],
    file_path: Optional[str],
    default_categories: List[str]
) -> List[str]:
    """
    Parse category input from multiple sources (priority order).
    
    Priority:
    1. CLI --categories argument (comma-separated)
    2. JSON file via --categories-file
    3. DEFAULT_CATEGORIES list in script
    """
    if cli_categories:
        categories = [c.strip() for c in cli_categories.split(',') if c.strip()]
        logger.info(f"📋 Using {len(categories)} categories from CLI arguments")
        return categories
    
    if file_path:
        categories = load_categories_from_json(file_path)
        logger.info(f"📋 Using {len(categories)} categories from file: {file_path}")
        return categories
    
    if default_categories:
        logger.info(f"📋 Using {len(default_categories)} categories from DEFAULT_CATEGORIES")
        return default_categories
    
    raise ValueError("No categories specified. Use --categories, --categories-file, or edit DEFAULT_CATEGORIES in script.")

# ============================================================================
# OUTPUT FILE GENERATION
# ============================================================================

def save_category_json(products: List[Dict], category_slug: str, output_dir: Path):
    """Save products for a single category to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"products_{category_slug}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    logger.info(f"  💾 Saved {len(products)} products to: {output_file.name}")

def save_combined_csv(all_products: List[Dict], output_dir: Path):
    """Save all products to a combined CSV file."""
    if not all_products:
        logger.warning("No products to save to CSV")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"all_products_{timestamp}.csv"
    
    # Convert to DataFrame for CSV export
    df = pd.DataFrame(all_products)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    logger.info(f"📊 Saved {len(all_products)} total products to: {output_file.name}")
    return output_file

# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main(
    categories: List[str],
    store: str,
    output_dir: Path,
    max_products: Optional[int] = None,
    fetch_details: bool = False,
    use_bigquery: bool = False
):
    """
    Main execution flow.
    
    Args:
        categories: List of category slugs
        store: Store slug
        output_dir: Output directory
        max_products: Max products per category
        fetch_details: Whether to fetch detailed info
        use_bigquery: Whether to use BigQuery integration
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("🚀 BRINGO MULTI-CATEGORY PRODUCT SCRAPER")
    logger.info("=" * 80)
    logger.info(f"📦 Store: {store}")
    logger.info(f"📋 Categories: {len(categories)}")
    logger.info(f"📁 Output Directory: {output_dir}")
    logger.info(f"🔢 Max Products per Category: {max_products or 'Unlimited'}")
    logger.info(f"📝 Fetch Details: {fetch_details}")
    logger.info(f"💾 BigQuery Integration: {use_bigquery}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Get authenticated session
        phpsessid = get_authenticated_session()
        
        # Step 2: Create SSL context and session
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        all_products = []
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Step 3: Process each category
            for idx, category_slug in enumerate(categories, 1):
                logger.info("")
                logger.info(f"{'=' * 80}")
                logger.info(f"📂 Processing Category {idx}/{len(categories)}: {category_slug}")
                logger.info(f"{'=' * 80}")
                
                try:
                    products = await extract_products_from_category(
                        session=session,
                        phpsessid=phpsessid,
                        category_slug=category_slug,
                        store=store,
                        max_products=max_products,
                        fetch_details=fetch_details
                    )
                    
                    if products:
                        # Save per-category JSON
                        save_category_json(products, category_slug, output_dir)
                        all_products.extend(products)
                        logger.info(f"  ✅ Category complete: {len(products)} products extracted")
                    else:
                        logger.warning(f"  ⚠️ No products found for category: {category_slug}")
                
                except Exception as e:
                    logger.error(f"  ❌ Failed to process category {category_slug}: {e}", exc_info=True)
        
        # Step 4: Save combined CSV
        if all_products:
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 GENERATING COMBINED OUTPUT")
            logger.info("=" * 80)
            csv_file = save_combined_csv(all_products, output_dir)
            
            # Step 5: BigQuery integration (optional)
            if use_bigquery:
                logger.info("")
                logger.info("💾 BIGQUERY INTEGRATION")
                logger.info("-" * 80)
                try:
                    from data.bigquery_client import BigQueryClient
                    bq_client = BigQueryClient()
                    existing_ids = bq_client.get_existing_product_ids()
                    
                    # Filter out existing products
                    df = pd.DataFrame(all_products)
                    df['_pid_str'] = df['product_id'].astype(str)
                    new_products = df[~df['_pid_str'].isin(existing_ids)].copy()
                    new_products.drop(columns=['_pid_str'], inplace=True)
                    
                    if not new_products.empty:
                        logger.info(f"  📤 Inserting {len(new_products)} new products to BigQuery...")
                        bq_client.insert_products_df(new_products)
                        logger.info(f"  ✅ BigQuery sync complete")
                    else:
                        logger.info(f"  ℹ️ All products already exist in BigQuery. Skipping insertion.")
                except Exception as e:
                    logger.error(f"  ❌ BigQuery integration failed: {e}")
        
        # Step 6: Summary
        elapsed = datetime.now() - start_time
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ SCRAPING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 Total Products Extracted: {len(all_products)}")
        logger.info(f"📂 Categories Processed: {len(categories)}")
        logger.info(f"⏱️ Time Elapsed: {elapsed}")
        logger.info(f"📁 Output Directory: {output_dir}")
        logger.info("=" * 80)
        
        return len(all_products)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 0

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract products from specific Bringo categories using authenticated sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CATEGORY INPUT METHODS (priority order):
  1. --categories "slug1,slug2,slug3"    CLI comma-separated list
  2. --categories-file path/to/file.json JSON file with categories array
  3. Edit DEFAULT_CATEGORIES in script    Direct script modification

EXAMPLES:
  # Extract from specific categories (CLI)
  python save_products_by_categories.py \\
      --categories "bacanie-169,fructe-si-legume-170"
  
  # Extract from JSON file with limit
  python save_products_by_categories.py \\
      --categories-file my_categories.json \\
      --max-products 50
  
  # Edit DEFAULT_CATEGORIES in script and run
  python save_products_by_categories.py

REQUIREMENTS:
  - BRINGO_USERNAME and BRINGO_PASSWORD in .env file
  - ChromeDriver (auto-installed by Selenium Manager)
        """
    )
    
    # Category input
    parser.add_argument('--categories', type=str, help='Comma-separated category slugs (e.g., "bacanie-169,lactate-171")')
    parser.add_argument('--categories-file', type=str, help='Path to JSON file with categories array')
    
    # Configuration
    parser.add_argument('--store', type=str, default='carrefour_park_lake', help='Store slug (default: carrefour_park_lake)')
    parser.add_argument('--output-dir', type=str, default='.', help='Output directory (default: current directory)')
    parser.add_argument('--max-products', type=int, help='Max products per category (for testing)')
    parser.add_argument('--fetch-details', action='store_true', help='Fetch detailed product info (slower)')
    parser.add_argument('--use-bigquery', action='store_true', help='Enable BigQuery integration for deduplication')
    
    args = parser.parse_args()
    
    try:
        # Parse category input
        categories = parse_category_input(
            cli_categories=args.categories,
            file_path=args.categories_file,
            default_categories=DEFAULT_CATEGORIES
        )
        
        # Run main execution
        output_dir = Path(args.output_dir)
        total_products = asyncio.run(main(
            categories=categories,
            store=args.store,
            output_dir=output_dir,
            max_products=args.max_products,
            fetch_details=args.fetch_details,
            use_bigquery=args.use_bigquery
        ))
        
        sys.exit(0 if total_products > 0 else 1)
    
    except Exception as e:
        logger.error(f"❌ Script failed: {e}", exc_info=True)
        sys.exit(1)
