import asyncio
import aiohttp
import ssl
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
from urllib.parse import urljoin
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to automatically extract categories from any category page's navigation
async def extract_categories_from_page(session, store, sample_category_url=None):
    """
    Extracts all available categories by scraping the category navigation
    from any product category page.
    
    Args:
        session: aiohttp session
        store: store slug
        sample_category_url: Optional URL to a known category page to extract nav from
    
    Returns:
        dict: Dictionary with category names as keys and slugs as values
    """
    # If no sample URL provided, try a commonly available category
    if not sample_category_url:
        sample_category_url = f"https://www.bringo.ro/ro/store/{store}/bacanie-169"
    
    try:
        logger.info(f"Fetching category navigation from: {sample_category_url}")
        
        # Add browser-like headers to avoid redirects
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        async with session.get(sample_category_url, headers=headers, allow_redirects=True) as response:
            if response.status == 200:
                html_content = await response.text()
                
                # Save for debugging
                debug_file = "debug_category_page.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Saved category page HTML to {debug_file}")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                categories = {}
                
                # Method 1: Try to find left sidebar navigation (common pattern)
                sidebar_links = soup.find_all('a', href=re.compile(r'/ro/store/[^/]+/[\w-]+'))
                
                if sidebar_links:
                    logger.info(f"Found {len(sidebar_links)} potential category links")
                    for link in sidebar_links:
                        href = link.get('href', '')
                        match = re.search(r'/ro/store/[^/]+/([\w-]+(?:-\d+)?)$', href)
                        if match:
                            slug = match.group(1)
                            # Extract category name from link text or nearby element
                            name = link.get_text(strip=True) or slug.replace('-', ' ').title()
                            if name and slug and len(name) > 1:  # Basic validation
                                categories[name] = slug
                    
                    if categories:
                        # Remove duplicates by slug
                        unique_cats = {}
                        for name, slug in categories.items():
                            if slug not in unique_cats.values():
                                unique_cats[name] = slug
                        
                        logger.info(f"Successfully extracted {len(unique_cats)} unique categories")
                        return unique_cats
                
                logger.warning("Could not extract categories from navigation")
                return {}
            else:
                logger.error(f"Failed to fetch category page. Status: {response.status}")
                return {}
                
    except Exception as e:
        logger.error(f"Error extracting categories: {e}")
        return {}

# Define a function to build the URL dynamically based on store and category
def build_url(store, category_slug):
    base_url = f"https://www.bringo.ro/ro/store/{store}/{category_slug}"
    return base_url

# Helper function to clean prices
def clean_price(price_text):
    if not price_text:
        return None
    # Extract just the digits and decimal point
    price_match = re.search(r'([0-9]+[,.][0-9]+)', price_text)
    if price_match:
        # Return the price as a float, replacing comma with dot if necessary
        return float(price_match.group(1).replace(',', '.'))
    return None

# Helper function to extract discount percentage
def extract_discount(discount_text):
    if not discount_text:
        return None
    discount_match = re.search(r'-([0-9]+)%', discount_text)
    if discount_match:
        return int(discount_match.group(1))
    return None

# Schema mapping for BigQuery (shared across functions)
SCHEMA_MAPPING = {
    'Product Name': ('product_name', str),
    'Product URL': ('product_url', str),
    'Product ID': ('product_id', lambda x: int(x) if x and str(x).isdigit() else None),
    'Variant ID': ('variant_id', str),
    'Price (RON)': ('price_ron', float),
    'Original Price (RON)': ('original_price_ron', float),
    'Discount (%)': ('discount_', lambda x: int(x) if x is not None else 0),
    'Category': ('category', str),
    'Brand': ('brand', str),
    'Image URL': ('image_url', str),
    'In Stock': ('in_stock', bool),
    'Store': ('store', str),
    'Description': ('description', str),
    'Producer': ('producer', str),
    'Product_Number': ('product_number', lambda x: int(x) if x and str(x).isdigit() else None),
    'SGR_Fee': ('sgr_fee', str),
    'Country_Origin': ('country_origin', str),
    'Ingredients': ('ingredients', str),
    'Nutritional_Info': ('nutritional_info', str) 
}

def transform_products_for_bq(products_list):
    """Transform scraped product dicts to BigQuery schema format"""
    final_data = []
    for row in products_list:
        new_row = {}
        for scraped_col, (bq_col, type_func) in SCHEMA_MAPPING.items():
            if scraped_col in row:
                raw_val = row[scraped_col]
                try:
                    if pd.isna(raw_val) or raw_val == '':
                        new_row[bq_col] = None
                    else:
                        new_row[bq_col] = type_func(raw_val)
                except Exception:
                    new_row[bq_col] = None
        final_data.append(new_row)
    return pd.DataFrame(final_data)

# Define a function to extract product data from the given URL (handling pagination)
async def extract_product_data(session, base_url, category_name, store, fetch_details=False, max_products=None, semaphore=None, bq_client=None, existing_ids=None):
    """
    Extracts products from a category, handling pagination automatically.
    Optionally saves each page to BigQuery immediately for crash resilience.
    
    Args:
        session: aiohttp session
        base_url (str): The base URL of the category
        category_name (str): The name of the category
        store (str): The store slug
        fetch_details (bool): Whether to fetch detailed product info (slower)
        max_products (int): Maximum number of products to extract
        semaphore: asyncio.Semaphore for concurrency control
        bq_client: Optional BigQueryClient for per-page saves
        existing_ids: Set of existing product IDs to skip
        
    Returns:
        pd.DataFrame: DataFrame containing product data
    """
    all_products_list = []
    seen_product_ids = set()  # Track seen product IDs to detect duplicates
    page = 1
    
    while True:
        # Construct URL for the current page
        # If it's the first page, we can use the base URL (or append ?page=1 explicitly)
        # Bringo seems to use ?page=n
        if "?" in base_url:
            current_url = f"{base_url}&limit=100&page={page}"
        else:
            current_url = f"{base_url}?limit=100&page={page}"
            
        logger.info(f"Fetching data from: {current_url}")
        
        try:
            async with session.get(current_url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    page_products_list = []
                    detail_tasks = []
                    new_products_on_page = 0  # Track new (non-duplicate) products
                    
                    # Find all product boxes
                    product_boxes = soup.find_all('div', class_='box-product')
                    
                    if not product_boxes:
                        logger.info(f"No products found on page {page}. Stopping pagination for this category.")
                        break
                    
                    for product_box in product_boxes:
                        # Check if we've reached the limit
                        if max_products and len(all_products_list) + len(page_products_list) >= max_products:
                            break
                            
                        try:
                            # Extract product details
                            product_name_tag = product_box.find('a', class_='bringo-product-name')
                            if not product_name_tag:
                                continue
                                
                            product_name = product_name_tag.get_text(strip=True)
                            product_url = urljoin("https://www.bringo.ro", product_name_tag.get('href', ''))
                            
                            # Extract product ID and variant ID from data attributes or URL
                            product_id = None
                            variant_id = None
                            
                            # Try to extract from URL
                            url_match = re.search(r'/products/[^/]*/(\d+)$', product_url)
                            if url_match:
                                product_id = url_match.group(1)
                            
                            # Try to find variant ID
                            variant_input = product_box.find('input', {'name': 'sylius_add_to_cart[cartItem][variant]'})
                            if variant_input:
                                variant_id = variant_input.get('value', None)
                            
                            # Initialize price variables
                            price = None
                            original_price = None
                            
                            # Extract price and original price from ecommerce data if available
                            ecommerce_a = product_box.find('a', onclick=re.compile(r'ecommerce_item'))
                            if ecommerce_a:
                                try:
                                    onclick_attr = ecommerce_a.get('onclick')
                                    match = re.search(r'ecommerce_item\((.*?),\s*[\'"]select_item[\'"]\)', onclick_attr)
                                    if match:
                                        json_str = match.group(1).replace('&quot;', '"')
                                        ecommerce_data = json.loads(json_str)
                                        
                                        # Prices are usually in cents/bani (integer)
                                        price = ecommerce_data.get('price', 0) / 100
                                        original_price = ecommerce_data.get('initial_price', 0) / 100
                                except Exception as e:
                                    logger.warning(f"Failed to parse ecommerce data: {e}")
                            
                            # Fallback to existing extraction if price is still None
                            if price is None:
                                price_tag = product_box.find('div', class_='bringo-product-price')
                                if price_tag:
                                    price = clean_price(price_tag.get_text(strip=True))
                                original_price = price
                            
                            # Calculate discount from price difference
                            discount_percentage = 0
                            if original_price and price and original_price > price:
                                discount_percentage = round(((original_price - price) / original_price) * 100)
                            
                            # Extract product image
                            img_tag = product_box.find('img', class_='image-product')
                            image_url = img_tag.get('src', '') if img_tag else None
                            
                            # Convert to full size image URL if present
                            if image_url:
                                image_url = re.sub(r'/web/cache/[^/]+/', '/web/cache/sylius_shop_product_original/', image_url)
                            
                            # Extract brand (N/A default)
                            brand = "N/A"
                            
                            # Extract if product is in stock
                            in_stock = True
                            
                            # Only proceed if we have a valid product ID
                            if not product_id:
                                logger.debug(f"Skipping product '{product_name}' - no Product ID found")
                                continue
                            
                            # Check for duplicates (Bringo returns same products on pages beyond last real page)
                            if product_id in seen_product_ids:
                                logger.debug(f"Skipping duplicate product ID: {product_id}")
                                continue
                            
                            seen_product_ids.add(product_id)
                            new_products_on_page += 1

                            # Create product data dictionary
                            product_data = {
                                'Product Name': product_name,
                                'Product URL': product_url,
                                'Product ID': product_id,
                                'Variant ID': variant_id,
                                'Price (RON)': price,
                                'Original Price (RON)': original_price,
                                'Discount (%)': discount_percentage,
                                'Category': category_name,
                                'Brand': brand,
                                'Image URL': image_url,
                                'In Stock': in_stock,
                                'Store': store,
                                'Description': None,
                                'Producer': None,
                                'Product_Number': None,
                                'SGR_Fee': None,
                                'Country_Origin': None,
                                'Ingredients': None,
                                'Nutritional_Info': None
                            }
                            
                            # Queue detailed info fetch if requested
                            if fetch_details and product_url and semaphore:
                                detail_tasks.append(fetch_product_details(session, product_url, semaphore))
                            
                            page_products_list.append(product_data)

                        except Exception as e:
                            logger.error(f"Error processing product: {e}", exc_info=True)
                    
                    # Execute all detail fetch tasks in parallel for this page
                    if detail_tasks:
                        logger.info(f"Fetching details for {len(detail_tasks)} products from page {page}...")
                        detail_results = await asyncio.gather(*detail_tasks)
                        
                        # Create a map of url -> details for easy lookup
                        details_map = {res[0]: res[1] for res in detail_results if res and res[1]}
                        
                        # Update products with fetched details
                        for product in page_products_list:
                            url = product['Product URL']
                            if url in details_map:
                                details = details_map[url]
                                product['Description'] = details.get('Description')
                                product['Producer'] = details.get('Producer')
                                product['Product_Number'] = details.get('Product_Number')
                                product['SGR_Fee'] = details.get('SGR_Fee')
                                product['Country_Origin'] = details.get('Country_Origin')
                                product['Ingredients'] = details.get('Ingredients')
                                product['Nutritional_Info'] = details.get('Nutritional_Info')

                    if not page_products_list:
                        logger.info(f"No valid products extracted on page {page}. Stopping.")
                        break
                    
                    # Check if all products on this page were duplicates (we've gone past the real last page)
                    if new_products_on_page == 0:
                        logger.info(f"All products on page {page} were duplicates. Reached end of unique products.")
                        break

                    # --- PER-PAGE BIGQUERY SAVE ---
                    if bq_client and page_products_list:
                        # Transform and filter for this page's products
                        page_df = transform_products_for_bq(page_products_list)
                        
                        # Filter out existing products if we have existing_ids
                        if existing_ids:
                            page_df['_pid_str'] = page_df['product_id'].astype(str)
                            new_products_df = page_df[~page_df['_pid_str'].isin(existing_ids)].copy()
                            if '_pid_str' in new_products_df.columns:
                                new_products_df.drop(columns=['_pid_str'], inplace=True)
                            skipped = len(page_df) - len(new_products_df)
                            if skipped > 0:
                                logger.info(f"Page {page}: Skipped {skipped} existing products")
                        else:
                            new_products_df = page_df
                        
                        # Save to BigQuery immediately
                        if not new_products_df.empty:
                            logger.info(f"Page {page}: Saving {len(new_products_df)} new products to BigQuery...")
                            bq_client.insert_products_df(new_products_df)
                            logger.info(f"Page {page}: ✓ Saved to BigQuery")
                            
                            # Add newly saved IDs to existing_ids to prevent duplicates in subsequent pages
                            if existing_ids is not None:
                                new_ids = set(new_products_df['product_id'].astype(str).tolist())
                                existing_ids.update(new_ids)
                    # --- END PER-PAGE SAVE ---

                    all_products_list.extend(page_products_list)
                    logger.info(f"Page {page}: Extracted {len(page_products_list)} new products. Total so far: {len(all_products_list)}")
                    
                    # Check global limit again just in case
                    if max_products and len(all_products_list) >= max_products:
                        logger.info(f"Reached max products limit ({max_products}). Stopping.")
                        break
                        
                    page += 1
                else:
                    logger.error(f"Failed to retrieve page {page}. Status code: {response.status}")
                    break
        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            break
            
    return pd.DataFrame(all_products_list)

# Define an async function to iterate over all categories and extract product data
async def extract_all_categories_data(store, max_categories=None, fetch_details=False, max_products_per_category=None, semaphore=None, category_filter=None):
    """
    Orchestrates the scraping process across multiple categories.
    
    Args:
        store (str): Store slug
        max_categories (int): Limit number of categories to scrape
        fetch_details (bool): Whether to fetch detailed info
        max_products_per_category (int): Max products per category
        semaphore: asyncio.Semaphore
        category_filter (str): Component of category name/slug to filter by
        
    Returns:
        pd.DataFrame: Combined DataFrame of all products
    """
    all_product_data = []  # List to store product data for all categories
    
    # Create SSL context to bypass certificate verification
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Create connector with SSL context
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Automatically extract categories from a sample category page
        category_slugs = await extract_categories_from_page(session, store)
        
        if not category_slugs:
            logger.error("No categories found. Exiting.")
            return pd.DataFrame()
        
        tasks = []  # List to store the tasks (HTTP requests)
        
        # Use a subset of categories for testing if max_categories is set
        category_items = list(category_slugs.items())
        
        # Apply Category Filter if provided
        if category_filter:
            logger.info(f"Applying category filter: '{category_filter}'")
            category_items = [
                (name, slug) for name, slug in category_items 
                if category_filter.lower() in name.lower() or category_filter.lower() in slug.lower()
            ]
            if not category_items:
                logger.warning(f"No categories found matching filter '{category_filter}'. Available: {list(category_slugs.keys())[:5]}...")
                return pd.DataFrame()
                
        if max_categories:
            category_items = category_items[:max_categories]
        
        # Iterate over each category
        for category_name, category_slug in category_items:
            url = build_url(store, category_slug)
            tasks.append(extract_product_data(session, url, category_name, store, fetch_details, max_products_per_category, semaphore))
        
        logger.info(f"Sending {len(tasks)} requests for categories")
        results = await asyncio.gather(*tasks)
        
        # Combine all dataframes
        for df in results:
            if not df.empty:
                all_product_data.append(df)
        
        # Concatenate all data into one DataFrame
        if all_product_data:
            all_products_df = pd.concat(all_product_data, ignore_index=True)
            return all_products_df
        else:
            logger.warning("No product data was extracted")
            return pd.DataFrame()

# Function to fetch detailed product information
async def fetch_product_details(session, product_url, semaphore):
    """
    Fetches detailed information for a single product.
    
    Args:
        session: aiohttp session
        product_url (str): URL of the product
        semaphore: asyncio.Semaphore
        
    Returns:
        tuple: (url, details_dict)
    """
    if not product_url:
        return (product_url, None)
        
    try:
        async with semaphore:
            async with session.get(product_url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    details = {}
                    
                         # Extract SGR Fee
                    sgr_div = soup.find('div', class_='sgr-price-details')
                    if sgr_div:
                        strong_tags = sgr_div.find_all('strong')
                        if strong_tags:
                            details['SGR_Fee'] = strong_tags[0].get_text(strip=True)

                    # Extract details from tab
                    details_tab = soup.find('div', {'id': 'details', 'role': 'tabpanel'})
                    
                    if details_tab:
                        # Extract producer/manufacturer
                        producer_tag = details_tab.find('strong', string='Producator:')
                        if producer_tag and producer_tag.parent:
                            producer_text = producer_tag.parent.get_text(strip=True)
                            details['Producer'] = producer_text.replace('Producator:', '').strip()
                        
                        # Extract product number
                        product_num_tag = details_tab.find('strong', string='Numar produs:')
                        if product_num_tag and product_num_tag.parent:
                            product_num_text = product_num_tag.parent.get_text(strip=True)
                            details['Product_Number'] = product_num_text.replace('Numar produs:', '').strip()
                        
                        # Extract main description text
                        description_div = details_tab.find('div')
                        full_text = ""
                        if description_div:
                            full_text = description_div.get_text(separator=' ', strip=True)
                        else:
                            full_text = details_tab.get_text(separator=' ', strip=True)
                            
                        details['Description'] = full_text

                        # Parse description for specific fields
                        if full_text:
                            # Country of Origin
                            origin_match = re.search(r'Tara de origine:\s*([^.<]+)', full_text, re.IGNORECASE)
                            if origin_match:
                                details['Country_Origin'] = origin_match.group(1).strip()
                            
                            # Ingredients
                            ingred_match = re.search(r'Ingrediente:\s*(.*?)(?=(?:Alergeni|Valori nutritionale|Conditii|$))', full_text, re.IGNORECASE | re.DOTALL)
                            if ingred_match:
                                details['Ingredients'] = ingred_match.group(1).strip().lstrip(':-').strip()

                            # Nutritional Values
                            nutri_match = re.search(r'Valori nutritionale\s*(.*?)(?=(?:Conditii|Tara de origine|$))', full_text, re.IGNORECASE | re.DOTALL)
                            if nutri_match:
                                # Clean leading punctuation (colon, dash) from the value
                                details['Nutritional_Info'] = nutri_match.group(1).strip().lstrip(':-').strip()
                    
                    return (product_url, details)
                else:
                    logger.debug(f"Failed to retrieve product details from {product_url}. Status code: {response.status}")
                    return (product_url, {})
    except Exception as e:
        logger.debug(f"Error fetching product details from {product_url}: {e}")
        return (product_url, {})

# Main function for single category extraction
async def main_single_category(store, category_slug, category_name, output_file, fetch_details=False, max_products=None, existing_ids=None):
    """
    Extract all products from a specific category.
    
    Args:
        store (str): Store slug (e.g., 'carrefour_park_lake')
        category_slug (str): Category slug (e.g., 'bacanie-169', 'lactate-oua-190')
        category_name (str): Friendly name for the category
        output_file (str): Output CSV file path
        fetch_details (bool): Whether to fetch detailed product info
        max_products (int): Maximum number of products to extract
        existing_ids (set): Set of existing product IDs to skip (optional)
        
    Returns:
        int: Number of new products inserted into BigQuery
    """
    logger.info(f"="*60)
    logger.info(f"SINGLE CATEGORY EXTRACTION")
    logger.info(f"Store: {store}")
    logger.info(f"Category: {category_name} ({category_slug})")
    
    # --- BigQuery Integration ---
    try:
        import sys
        from pathlib import Path
        
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
            
        from data.bigquery_client import BigQueryClient
        bq_client = BigQueryClient()
        
        # Only fetch existing IDs if not provided
        if existing_ids is None:
            existing_ids = bq_client.get_existing_product_ids()
            logger.info(f"Fetched {len(existing_ids)} existing products from BigQuery.")
        else:
            logger.info(f"Using provided set of {len(existing_ids)} existing product IDs.")
            
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        return None
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    semaphore = asyncio.Semaphore(50)
    
    total_saved = 0
    async with aiohttp.ClientSession(connector=connector) as session:
        # Build URL directly from the category slug
        base_url = build_url(store, category_slug)
        logger.info(f"Scraping category URL: {base_url}")
        logger.info(f"Mode: Per-page BigQuery saves enabled")
        
        # Extract products from this single category with per-page saves
        product_data = await extract_product_data(
            session=session,
            base_url=base_url,
            category_name=category_name,
            store=store,
            fetch_details=fetch_details,
            max_products=max_products,
            semaphore=semaphore,
            bq_client=bq_client,        # Enable per-page saves
            existing_ids=existing_ids   # Pass existing IDs for dedup
        )
    
    if product_data.empty:
        logger.warning(f"No products found in category '{category_name}'")
        return 0
    
    # Products are already saved per-page, so just log final stats
    logger.info(f"="*60)
    logger.info(f"EXTRACTION COMPLETE")
    logger.info(f"Total products extracted: {len(product_data)}")
    logger.info(f"All products were saved to BigQuery during extraction")
    logger.info(f"="*60)
    
    # Save CSV for reference
    if not product_data.empty:
        csv_df = transform_products_for_bq(product_data.to_dict('records'))
        csv_df.to_csv(output_file, index=False)
        logger.info(f"Saved {len(csv_df)} products to {output_file}")
    
    return len(product_data)


# Main function to run the scraping process (multi-category)
async def main(store, output_file, max_categories=None, fetch_details=False, max_products_per_category=None, category_filter=None):
    logger.info(f"Starting scraping process for store: {store}")
    
    # --- BigQuery Integration ---
    try:
        # Import here to avoid circular dependencies if run from root
        import sys
        from pathlib import Path
        
        # Add project root to sys.path
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
            
        from data.bigquery_client import BigQueryClient
        bq_client = BigQueryClient()
        existing_ids = bq_client.get_existing_product_ids()
        logger.info(f"Found {len(existing_ids)} existing products in BigQuery. They will be skipped.")
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        return None
    # ---------------------------

    if fetch_details:
        logger.info("Detailed product information will be fetched (this will take longer)")
    if max_products_per_category:
        logger.info(f"Limiting to {max_products_per_category} products per category for testing")
    
    # Create a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(50)  # Adjust limit as needed
    
    all_product_data = await extract_all_categories_data(store, max_categories, fetch_details, max_products_per_category, semaphore, category_filter)
    
    if not all_product_data.empty:
        # Define strict mapping from Scraped keys to BigQuery Schema keys
        # Format: {'Scraped Column': ('bq_column_name', type_function)}
        schema_mapping = {
            'Product Name': ('product_name', str),
            'Product URL': ('product_url', str),
            'Product ID': ('product_id', lambda x: int(x) if x and str(x).isdigit() else None),
            'Variant ID': ('variant_id', str),
            'Price (RON)': ('price_ron', float),
            'Original Price (RON)': ('original_price_ron', float),
            'Discount (%)': ('discount_', lambda x: int(x) if x is not None else 0), # Note: dictionary key 'discount_'
            'Category': ('category', str),
            'Brand': ('brand', str), # Not in schema provided by user, but common? User schema didn't showing 'brand'. 
                                     # User schema: product_name, product_url, product_id, variant_id, price_ron, 
                                     # original_price_ron, discount_, category, image_url, in_stock, store, 
                                     # description, producer, product_number, sgr_fee, country_origin, 
                                     # ingredients, nutritional_info.
                                     # Missing 'brand' in user schema. Will drop or map to something else if needed.
                                     # Assuming 'brand' is not in target schema based on user request.
            'Image URL': ('image_url', str),
            'In Stock': ('in_stock', bool),
            'Store': ('store', str),
            'Description': ('description', str),
            'Producer': ('producer', str),
            'Product_Number': ('product_number', lambda x: int(x) if x and str(x).isdigit() else None),
            'SGR_Fee': ('sgr_fee', str),
            'Country_Origin': ('country_origin', str),
            'Ingredients': ('ingredients', str),
            'Nutritional_Info': ('nutritional_info', str) 
        }

        # Rename and Transform
        final_data = []
        for index, row in all_product_data.iterrows():
            new_row = {}
            for scraped_col, (bq_col, type_func) in schema_mapping.items():
                if scraped_col in row:
                    raw_val = row[scraped_col]
                    try:
                        if pd.isna(raw_val) or raw_val == '':
                            new_row[bq_col] = None
                        else:
                            new_row[bq_col] = type_func(raw_val)
                    except Exception as e:
                        # logger.warning(f"Type conversion failed for {bq_col} value {raw_val}: {e}")
                        new_row[bq_col] = None
            final_data.append(new_row)
        
        all_product_data = pd.DataFrame(final_data)
        
        # Ensure product_id is string ONLY for existing check comparison (BQ returns ints usually, need robust match)
        # BigQueryClient.get_existing_product_ids() returns set of strings.
        # But for insertion, we want to maintain the specific schema types (product_id=INTEGER).
        
        # Filter existing
        # Convert to string just for the .isin check
        all_product_data['_pid_str'] = all_product_data['product_id'].astype(str)
        
        # Deduplicate
        initial_count = len(all_product_data)
        new_products = all_product_data[~all_product_data['_pid_str'].isin(existing_ids)].copy()
        
        # Drop helper column
        if '_pid_str' in new_products.columns:
            new_products.drop(columns=['_pid_str'], inplace=True)
            
        skipped_count = initial_count - len(new_products)
        
        logger.info(f"Scraped {initial_count} items. Skipped {skipped_count} existing items.")
        
        if not new_products.empty:
            logger.info(f"Schema aligned. Inserting {len(new_products)} new items into BigQuery...")
            bq_client.insert_products_df(new_products)
            logger.info("Sync to BigQuery complete.")
        else:
            logger.info("No new products to insert.")
            
        return len(new_products)
    else:
        logger.warning("No data extracted")
        return 0

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Bringo Products Scraper - Extract products from specific categories')
    parser.add_argument('--store', type=str, default="carrefour_park_lake", help='Store slug (e.g., carrefour_park_lake)')
    parser.add_argument('--output', type=str, default="carrefour_products_enhanced.csv", help='Output CSV file path')
    parser.add_argument('--max-categories', type=int, default=None, help='Limit number of categories to scrape (for testing)')
    parser.add_argument('--max-products', type=int, default=None, help='Limit products per category (for testing)')
    parser.add_argument('--no-details', action='store_true', help='Disable detailed product info fetching (faster)')
    
    # Category filtering options
    parser.add_argument('--category', type=str, help='Filter to specific category (partial match on name or slug)')
    parser.add_argument('--category-slug', type=str, dest='category_slug',
                        help='Exact category slug to scrape (e.g., "bacanie-169", "lactate-oua-190"). '
                             'When provided, skips category discovery and scrapes directly from this category.')
    parser.add_argument('--category-name', type=str, dest='category_name', default=None,
                        help='Friendly name for the category (used in output). Defaults to slug if not provided.')
    
    args = parser.parse_args()
    
    fetch_details = not args.no_details
    
    # If exact category slug is provided, use direct single-category extraction
    if args.category_slug:
        category_name = args.category_name or args.category_slug.replace('-', ' ').title()
        asyncio.run(main_single_category(
            store=args.store,
            category_slug=args.category_slug,
            category_name=category_name,
            output_file=args.output,
            fetch_details=fetch_details,
            max_products=args.max_products
        ))
    else:
        # Multi-category extraction (original behavior)
        asyncio.run(main(args.store, args.output, args.max_categories, fetch_details, args.max_products, args.category))