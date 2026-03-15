"""
Update Vector Search index with new products
Run this after adding new products to BigQuery and running generate_embeddings.py

Workflow:
1. Generate new embeddings (handled by generate_embeddings.py)
2. Run this script to update the index with the new embeddings
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_search import IndexManager
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - INDEX UPDATE")
    logger.info("=" * 80)
    
    try:
        manager = IndexManager()
        
        # Vertex AI requires a DIRECTORY uri for update_embeddings
        embeddings_uri = f"gs://{settings.STAGING_BUCKET}/embeddings/"
        
        logger.info(f"Updating index {settings.VS_INDEX_NAME}")
        logger.info(f"Using embeddings from: {embeddings_uri}")
        logger.info("NOTE: This performs a full index update (overwrite)")
        
        operation = manager.update_index(
            index_name=settings.VS_INDEX_NAME,
            embeddings_gcs_uri=embeddings_uri
        )
        
        logger.info("")
        logger.info("✓ Update operation started successfully")
        # logger.info(f"Operation: {operation.operation.name}")
        logger.info("")
        logger.info("The index update runs in the background.")
        logger.info("You check status in the Google Cloud Console.")
        
    except Exception as e:
        logger.error(f"Failed to update index: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
