from bs4 import BeautifulSoup
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    with open("debug_nav_root.html", "r", encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check for bringo-category-list-box
    grid_box = soup.find('div', class_='bringo-category-list-box')
    if grid_box:
        logger.info("Found 'bringo-category-list-box'!")
        links = grid_box.find_all('a', href=True)
        logger.info(f"Links in box: {len(links)}")
    else:
        logger.error("Did NOT find 'bringo-category-list-box'")
        
    # Check all links
    all_links = soup.find_all('a', href=True)
    logger.info(f"Total links in file: {len(all_links)}")
    
    # Print first few links containing 'store'
    count = 0
    for link in all_links:
        if "/ro/store/" in link['href']:
            logger.info(f"Sample link: {link['href']}")
            count += 1
            if count > 5: break
            
except Exception as e:
    logger.error(f"Error: {e}")
