import logging
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_search.search_engine import SearchEngine
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search():
    logger.info("Initializing SearchEngine...")
    try:
        engine = SearchEngine()
    except Exception as e:
        logger.error(f"Failed to init engine: {e}")
        return

    query = "brânză"
    logger.info(f"Searching for '{query}'...")
    
    start = time.time()
    try:
        results = engine.search_by_text(query, num_neighbors=5)
        elapsed = time.time() - start
        logger.info(f"Search completed in {elapsed:.2f}s")
        logger.info(f"Found {len(results)} results")
        for r in results:
            logger.info(f" - {r['id']} (score: {r['similarity_score']:.4f})")
            
    except Exception as e:
        logger.error(f"Search failed: {e}")

if __name__ == "__main__":
    test_search()
