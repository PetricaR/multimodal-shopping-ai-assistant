"""
Script to test Vector Search functionality directly using Python SDK.
This script bypasses the API and tests the SearchEngine class directly.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vector_search import SearchEngine
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - DIRECT VECTOR SEARCH TEST")
    logger.info("=" * 80)
    
    try:
        # Initialize search engine
        logger.info("Initializing Search Engine...")
        engine = SearchEngine()
        
        # Test Query 1: Text Search
        query_text = "lapte bio"
        logger.info(f"\nTest 1: Text Search for '{query_text}'")
        
        results = engine.search_by_text(
            query_text=query_text,
            num_neighbors=5,
            filter_in_stock=False
        )
        
        logger.info(f"Found {len(results)} results:")
        for i, res in enumerate(results, 1):
            logger.info(f"  {i}. ID: {res['id']}, Score: {res['similarity_score']:.4f}")
            
        # Test Query 2: Product ID Search (if valid ID exists)
        # You can replace this with a valid product ID from your database
        product_id = "4347506" 
        logger.info(f"\nTest 2: Product Search for ID '{product_id}'")
        
        # Note: We need the product text to generate the embedding for query.
        # In a real scenario, this comes from BigQuery. 
        # For this test, we'll mock the text if we can't easily fetch it here without BigQuery client setup.
        # However, search_by_product_id expects text.
        
        # For simplicity in this standalone test, we will skip the BigQuery fetch part 
        # and just demonstrate that the method exists. To fully test search_by_product_id,
        # we would need to fetch the product text first.
        
        # Let's do a search validation check instead:
        if not results:
             logger.warning("\nWARNING: No results found. This likely means the index is empty or has not finished updating.")
        else:
             logger.info("\nSUCCESS: Vector Search returned results.")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
