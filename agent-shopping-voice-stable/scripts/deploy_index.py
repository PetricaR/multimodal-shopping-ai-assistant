"""
Deploy Vector Search index to endpoint
Following Google best practices (validated January 2026)

This is Step 3 of the deployment process.
Run this after the index build completes (45-90 minutes after create_index.py)
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
        logging.FileHandler('logs/index_deployment.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Deploy Vector Search index to endpoint
    
    Prerequisites:
    - Index must be built and ready (check Google Cloud Console)
    - Endpoint must exist (created by create_index.py)
    
    Deployment takes 10-20 minutes.
    """
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - INDEX DEPLOYMENT")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Index: {settings.VS_INDEX_NAME}")
    logger.info(f"  Endpoint: {settings.VS_ENDPOINT_NAME}")
    logger.info(f"  Deployed ID: {settings.VS_DEPLOYED_INDEX_ID}")
    logger.info(f"  Machine: {settings.VS_MACHINE_TYPE}")
    logger.info(f"  Replicas: {settings.VS_MIN_REPLICAS}-{settings.VS_MAX_REPLICAS}")
    logger.info("")
    
    try:
        # Initialize manager
        manager = IndexManager()
        
        # Step 1: Get existing index
        logger.info("Step 1: Finding existing index...")
        try:
            index = manager.get_existing_index(settings.VS_INDEX_NAME)
            logger.info(f"✓ Found index: {index.display_name}")
            logger.info(f"  Resource: {index.resource_name}")
        except ValueError as e:
            logger.error(f"Index not found: {settings.VS_INDEX_NAME}")
            logger.error("Make sure create_index.py completed successfully.")
            logger.error("Check: https://console.cloud.google.com/vertex-ai/matching-engine/indexes")
            sys.exit(1)
        
        # Step 2: Get existing endpoint
        logger.info("")
        logger.info("Step 2: Finding existing endpoint...")
        try:
            endpoint = manager.get_existing_endpoint(settings.VS_ENDPOINT_NAME)
            logger.info(f"✓ Found endpoint: {endpoint.display_name}")
            logger.info(f"  Resource: {endpoint.resource_name}")
        except ValueError as e:
            logger.error(f"Endpoint not found: {settings.VS_ENDPOINT_NAME}")
            logger.error("Make sure create_index.py completed successfully.")
            sys.exit(1)
        
        # Step 3: Deploy index to endpoint
        logger.info("")
        logger.info("Step 3: Deploying index to endpoint...")
        logger.info("⏱ This will take 10-20 minutes")
        logger.info("")
        
        manager.deploy_index(
            index=index,
            endpoint=endpoint,
            deployed_index_id=settings.VS_DEPLOYED_INDEX_ID
        )
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ DEPLOYMENT STARTED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Deployment is in progress (10-20 minutes).")
        logger.info("Monitor at:")
        logger.info(f"https://console.cloud.google.com/vertex-ai/matching-engine/index-endpoints?project={settings.PROJECT_ID}")
        logger.info("")
        logger.info("Once deployed, start the API:")
        logger.info("")
        logger.info("   python -m api.main")
        logger.info("")
        logger.info("Or use the example:")
        logger.info("")
        logger.info("   python example_usage.py")
        logger.info("")
    
    except Exception as e:
        logger.error(f"FAILED: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
