import logging
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.realtime_server import get_feature_server
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fs():
    logger.info("Initializing Feature Server...")
    try:
        server = get_feature_server()
    except Exception as e:
        logger.error(f"Failed to init server: {e}")
        return

    # Use a known product or just a random ID to check connectivity
    # 'lapte' is a query, not an ID. IDs are usually strings.
    # Let's try to fetch a known ID if we had one.
    # Or just use the get_product_metadata with a dummy ID and see if it returns (even empty).
    
    test_ids = ["test_product_id_123", "Greek Land Crema balsamica rose 250 ML"] # Using a name seen in previous output as ID?
    # In batch_processor, we saw we use product_name as metadata product_name, 
    # but ID logic in scraping uses names or numbers?
    # The scraping logic wasn't fully inspected for ID generation, but index_manager uses what's in GCS.
    
    logger.info(f"Fetching metadata for {test_ids}...")
    
    start = time.time()
    try:
        data = server.get_product_metadata(test_ids)
        elapsed = time.time() - start
        logger.info(f"FS Fetch completed in {elapsed:.2f}s")
        logger.info(f"Result: {data}")
            
    except Exception as e:
        logger.error(f"FS Fetch failed: {e}")

if __name__ == "__main__":
    test_fs()
