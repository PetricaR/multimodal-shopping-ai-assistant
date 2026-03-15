
import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("find_store")

# Load environment
load_dotenv()

# Add current directory to path
sys.path.append(os.getcwd())

from services.store_service import StoreService

def find_store():
    address = "Strada Fetești 52, București"
    logger.info(f"🔎 Find stores for: {address}")
    
    try:
        result = StoreService.scrape_stores_at_address(address)
        if result.get("status") == "success":
            stores = result.get("stores", [])
            logger.info(f"✅ Found {len(stores)} stores:")
            for s in stores:
                logger.info(f" - {s['name']} (ID: {s['store_id']}) - URL: {s['url']}")
        else:
            logger.error(f"❌ Failed: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    find_store()
