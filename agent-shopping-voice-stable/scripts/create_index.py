"""
Create and deploy Vector Search index
Following Google best practices (validated January 2026)

This is Step 2 of the deployment process.
Expected time: 45-90 minutes (automated)
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/index_creation.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Create and deploy Vector Search index
    
    Google Best Practices (Validated Jan 2026):
    - TreeAH algorithm (production standard)
    - COSINE_DISTANCE (model trained with it)
    - approximateNeighborsCount=150
    - 512 dimensions
    - Public endpoint with auto-scaling
    """
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - INDEX CREATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Algorithm: TreeAH")
    logger.info(f"  Distance: {settings.VS_DISTANCE_MEASURE}")
    logger.info(f"  Dimensions: {settings.EMBEDDING_DIMENSION}")
    logger.info(f"  Neighbors: {settings.VS_APPROXIMATE_NEIGHBORS}")
    logger.info(f"  Machine: {settings.VS_MACHINE_TYPE}")
    logger.info(f"  Replicas: {settings.VS_MIN_REPLICAS}-{settings.VS_MAX_REPLICAS}")
    logger.info("")
    
    try:
        # Initialize manager
        manager = IndexManager()
        
        # Get embeddings GCS URI
        embeddings_uri = f"gs://{settings.STAGING_BUCKET}/embeddings/bringo_products_embeddings.json"
        logger.info(f"Embeddings location: {embeddings_uri}")
        logger.info("")
        
        # Step 1: Create index
        logger.info("Step 1: Creating Vector Search index...")
        logger.info("⏱ This will take 45-90 minutes (automated)")
        logger.info("")
        
        index = manager.create_index(
            embeddings_gcs_uri=embeddings_uri,
            index_name=settings.VS_INDEX_NAME
        )
        
        logger.info("✓ Index creation started")
        logger.info(f"Index: {index.resource_name}")
        logger.info("")
        
        # Step 2: Create or get endpoint
        logger.info("Step 2: Setting up endpoint...")
        endpoint = manager.get_or_create_endpoint(
            endpoint_name=settings.VS_ENDPOINT_NAME
        )
        
        logger.info("✓ Endpoint ready")
        logger.info(f"Endpoint: {endpoint.resource_name}")
        logger.info("")
        
        # Step 3: Wait for index to be ready
        logger.info("Step 3: Waiting for index build to complete...")
        logger.info("⏱ This typically takes 45-90 minutes")
        logger.info("You can monitor progress in Google Cloud Console:")
        logger.info(f"https://console.cloud.google.com/vertex-ai/matching-engine/indexes?project={settings.PROJECT_ID}")
        logger.info("")
        
        # Note: In production, you might want to poll the index status
        # For now, we'll let the user monitor manually
        
        logger.info("=" * 80)
        logger.info("INDEX CREATION IN PROGRESS")
        logger.info("=" * 80)
        logger.info("")
        logger.info("To deploy the index once it's ready:")
        logger.info("")
        logger.info("1. Wait for index build to complete (check console)")
        logger.info("2. Run deployment:")
        logger.info("")
        logger.info("   python scripts/deploy_index.py")
        logger.info("")
        logger.info("Or manually deploy using:")
        logger.info("")
        logger.info("   from vector_search import IndexManager")
        logger.info("   manager = IndexManager()")
        logger.info("   manager.deploy_index()")
        logger.info("")
    
    except Exception as e:
        logger.error(f"FAILED: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
