import asyncio
import logging
import sys
import time
from pathlib import Path

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.routes.similarity import search_similar_products
from api.models import SearchRequest
from api import dependencies

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_live_search():
    logger.info("Starting Live Search Verification...")
    
    # Ensure dependencies are initialized (or allow them to init on first call)
    # Ideally, we might want to preload them to separate init time from search time in logs
    try:
        logger.info("Initializing dependencies...")
        dependencies.get_search_engine()
        dependencies.get_feature_server()
        dependencies.get_bq_client() # Fallback
        logger.info("Dependencies initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {e}")
        return

    # Test Query: "lapte" (Milk) - should return many results
    query = "lapte"
    request = SearchRequest(query_text=query, top_k=5)
    
    logger.info(f"\n--- Searching for '{query}' ---")
    start_time = time.time()
    
    try:
        response = await search_similar_products(request)
        elapsed = time.time() - start_time
        
        logger.info(f"Search completed in {elapsed:.2f}s")
        logger.info(f"Found {len(response.similar_products)} products")
        
        if not response.similar_products:
            logger.warning("No products found! Check if Vector Search or Feature Store is empty.")
        else:
            logger.info("Top 5 Results:")
            for i, p in enumerate(response.similar_products):
                logger.info(f"  {i+1}. [{p.product_id}] {p.product_name} - {p.price} RON (Score: {p.similarity_score})")
                
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_live_search())
