"""
Extract ALL categories from Bringo using authenticated session.
Leverages existing Selenium-based authentication system.
"""
import asyncio
import aiohttp
import ssl
import json
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Add parent directory to path to import authentication module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.tools.authentication import authenticate_with_credentials, get_authentication_from_state, validate_session
from api.tools.shared import db
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_authenticated_session():
    """
    Get or create an authenticated Bringo session using existing auth system.
    Validates existing sessions and re-authenticates if expired.
    Returns PHPSESSID cookie value.
    """
    logger.info("🔐 Checking for existing authentication...")
    
    # First, check if we have a session in the database
    auth_state = json.loads(get_authentication_from_state())
    
    if auth_state.get('status') == 'authenticated':
        phpsessid = auth_state.get('session_cookie')
        username = auth_state.get('username')
        logger.info(f"📦 Found existing session for user: {username}")
        
        # Validate the session is still active
        logger.info("🔍 Validating session with Bringo server...")
        validation_result = json.loads(validate_session(phpsessid))
        
        if validation_result.get('status') == 'valid':
            logger.info("✅ Session is valid! Using existing session.")
            return phpsessid
        else:
            logger.warning(f"⚠️ Session validation failed: {validation_result.get('message')}")
            logger.info("🔄 Session expired, re-authenticating...")
    
    # No valid session, need to authenticate
    logger.info("⚠️ No valid session found. Authenticating with credentials...")
    
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
    
    logger.info(f"✅ Authentication successful! Session expires at: {auth_result.get('expires_at')}")
    return auth_result.get('phpsessid')

async def fetch_categories_with_session(phpsessid: str, store: str = "carrefour_park_lake"):
    """
    Fetch ALL categories from Bringo using authenticated PHPSESSID.
    
    Args:
        phpsessid: Valid PHPSESSID session cookie
        store: Store slug (e.g., 'carrefour_park_lake')
    
    Returns:
        Dict of {category_name: category_slug}
    """
    base_url = f"https://www.bringo.ro/ro/store-details/{store}"
    
    logger.info(f"🏪 Targeting Store: {store}")
    logger.info(f"🔗 URL: {base_url}")

    # Headers that look like a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.bringo.ro/',
        'Cookie': f'PHPSESSID={phpsessid}'  # Use authenticated session
    }

    # SSL Context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(base_url, headers=headers) as response:
            
            # Check for redirect (means session is invalid)
            final_url = str(response.url)
            if final_url == "https://www.bringo.ro/ro/" or final_url == "https://www.bringo.ro/":
                logger.error("=" * 60)
                logger.error("❌ FAIL: Redirected to Homepage!")
                logger.error("Session is invalid or expired.")
                logger.error("Try re-authenticating with Selenium.")
                logger.error("=" * 60)
                return {}

            if response.status != 200:
                logger.error(f"❌ Failed to fetch page. Status: {response.status}")
                return {}
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            # Find the category container
            grid_box = soup.find('div', class_='bringo-category-list-box')
            
            if not grid_box:
                logger.error("❌ Could not find 'bringo-category-list-box'.")
                logger.error("Possible reasons:")
                logger.error("  - Session expired")
                logger.error("  - Delivery address not set")
                logger.error("  - Website structure changed")
                return {}

            # Extract all category links
            links = grid_box.find_all('a', class_='box-inner')
            categories = {}
            
            logger.info(f"✅ Success! Found {len(links)} categories.")

            for link in links:
                href = link.get('href')
                
                # Extract name from <h4> tag
                h4_tag = link.find('h4')
                name = h4_tag.get_text(strip=True) if h4_tag else link.get_text(strip=True)
                
                # Extract slug from URL
                # Format: /ro/store/carrefour_park_lake/category-slug-123
                if href:
                    slug = href.strip('/').split('/')[-1]
                    if name and slug:
                        categories[name] = slug
                        logger.debug(f"  ✓ {name}: {slug}")

            return categories

def save_categories(categories: dict, output_dir: Path):
    """Save categories dict to JSON file."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_file = path / "bringo_categories.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"✅ [SUCCESS] Saved {len(categories)} categories to:")
    print(f"📄 {output_file}")
    print(f"{'=' * 60}")
    
    # Print preview
    print("\n📋 Preview (first 5 categories):")
    print("-" * 40)
    for name, slug in list(categories.items())[:5]:
        print(f"  • {name}: {slug}")
    if len(categories) > 5:
        print(f"  ... and {len(categories) - 5} more")
    print("-" * 40)

async def main(store: str = "carrefour_park_lake"):
    """Main execution flow."""
    try:
        # Step 1: Get authenticated session
        phpsessid = get_authenticated_session()
        
        # Step 2: Fetch categories with authenticated session
        categories = await fetch_categories_with_session(phpsessid, store)
        
        # Step 3: Save categories
        if categories:
            output_dir = Path(__file__).parent
            save_categories(categories, output_dir)
            return True
        else:
            logger.error("\n❌ No categories extracted. Check errors above.")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Extract ALL Bringo Categories using authenticated session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script uses the existing Selenium-based authentication system.

Requirements:
1. Set BRINGO_USERNAME and BRINGO_PASSWORD in .env file
2. Ensure ChromeDriver is installed (handled automatically by Selenium Manager)
3. Run from the bringo_catalog directory

Example:
    python save_all_categories.py
    python save_all_categories.py --store carrefour_park_lake
        """
    )
    parser.add_argument("--store", default="carrefour_park_lake", 
                       help="Store slug (e.g., carrefour_park_lake)")
    args = parser.parse_args()
    
    # Run the async main function
    success = asyncio.run(main(args.store))
    sys.exit(0 if success else 1)
