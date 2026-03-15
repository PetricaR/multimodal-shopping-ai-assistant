"""
Generate multimodal embeddings for all products
Following Google best practices (validated January 2026)

This is Step 1 of the deployment process.
Expected time: 2-4 hours for 10,000 products
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import BigQueryClient
from embeddings import BatchEmbeddingProcessor
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embedding_generation.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Main embedding generation pipeline
    
    Google Best Practices:
    - 512 dimensions (optimal for production)
    - Multimodal (image + text combined)
    - NO task types (not supported for multimodal)
    - Use image_embedding (incorporates both modalities)
    - Rate limiting: 120 req/min
    - Batch size: 25 (optimal for multimodal)
    """
    logger.info("=" * 80)
    logger.info("BRINGO PRODUCT SIMILARITY - EMBEDDING GENERATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"  Dimensions: {settings.EMBEDDING_DIMENSION} (512 = optimal)")
    logger.info(f"  Multimodal: {settings.USE_MULTIMODAL}")
    logger.info(f"  Rate limit: {settings.EMBEDDING_RATE_LIMIT} req/min")
    logger.info(f"  Batch size: {settings.BATCH_SIZE}")
    logger.info("")
    
    try:
        # Step 1: Fetch products from BigQuery
        logger.info("Step 1: Fetching products from BigQuery...")
        bq_client = BigQueryClient()
        
        # Fetch all products (or use limit for testing)
        # df = bq_client.fetch_products(limit=50)  # Testing - Limited to 50 for validation
        df = bq_client.fetch_products()  # Production
        
        logger.info(f"✓ Fetched {len(df)} products")
        logger.info("")
        
        # Step 2: Prepare for embedding
        logger.info("Step 2: Preparing products for embedding...")
        products = bq_client.prepare_for_embedding(df)
        logger.info(f"✓ Prepared {len(products)} products")
        logger.info("")
        
        # Step 3: Generate embeddings
        logger.info("Step 3: Generating multimodal embeddings...")
        logger.info(f"Expected time: ~{len(products)/10000*60:.1f} minutes")
        logger.info("")
        
        processor = BatchEmbeddingProcessor()
        gcs_uri = processor.process_and_save(
            products=products,
            filename="bringo_products_embeddings.json"
        )
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ EMBEDDING GENERATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Embeddings saved to: {gcs_uri}")
        logger.info(f"Total products: {len(products)}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run: python scripts/create_index.py")
        logger.info("2. Wait for index creation (45-90 minutes)")
        logger.info("3. Deploy endpoint and start API")
        logger.info("")
    
    except Exception as e:
        logger.error(f"FAILED: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
