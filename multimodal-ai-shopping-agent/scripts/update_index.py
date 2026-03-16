"""
Update Vector Search index with new embeddings
Following Google best practices

This script forces an update of the existing index with the new embeddings 
generated in GCS.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_search import IndexManager
from config.settings import settings

# Configure logging
Path(__file__).parent.parent.joinpath('logs').mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(Path(__file__).parent.parent / 'logs' / 'index_update.log'))
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Update Vector Search index
    """
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - INDEX UPDATE")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Index: {settings.VS_INDEX_NAME}")
    logger.info(f"  Bucket: {settings.STAGING_BUCKET}")
    logger.info("")
    
    try:
        # Initialize manager
        manager = IndexManager()
        
        # Vertex AI expects a flat DIRECTORY uri
        embeddings_uri = f"gs://{settings.STAGING_BUCKET}/embeddings/"
        logger.info(f"Embeddings location: {embeddings_uri}")
        logger.info("")
        
        # Update index
        logger.info("Starting index update...")
        logger.info("⏱ This will take 45-90 minutes")
        logger.info("")
        
        operation = manager.update_index(
            index_name=settings.VS_INDEX_NAME,
            embeddings_gcs_uri=embeddings_uri
        )
        
        logger.info("✓ Index update operation started")
        logger.info(f"Operation: {operation.operation.name}")
        logger.info("")
        logger.info("You can monitor progress in Google Cloud Console:")
        logger.info(f"https://console.cloud.google.com/vertex-ai/matching-engine/indexes?project={settings.PROJECT_ID}")
        logger.info("")
        
    except Exception as e:
        logger.error(f"FAILED: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
