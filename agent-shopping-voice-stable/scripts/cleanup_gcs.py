import sys
from pathlib import Path
import logging
from google.cloud import storage

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_embeddings_folder(keep_file: str = "bringo_products_embeddings.json"):
    """
    Remove all files in embeddings/ except the target file.
    This prevents Vector Search from ingesting duplicates or stale data.
    """
    logger.info(f"Checking GCS bucket: {settings.STAGING_BUCKET}/embeddings/")
    
    client = storage.Client(project=settings.PROJECT_ID)
    bucket = client.bucket(settings.STAGING_BUCKET)
    
    blobs = list(bucket.list_blobs(prefix="embeddings/"))
    
    deleted_count = 0
    kept_count = 0
    
    for blob in blobs:
        # Check if it matches the target filename
        if blob.name.endswith(keep_file):
            logger.info(f"✅ Keeping: {blob.name} ({blob.size / 1024:.1f} KB)")
            kept_count += 1
        else:
            # It's a different file (e.g. .jsonl or temp)
            if blob.name.endswith("/"): # Virtual folder
                continue
                
            logger.info(f"🗑️ Deleting stale file: {blob.name}")
            try:
                blob.delete()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {blob.name}: {e}")
    
    logger.info("-" * 40)
    logger.info(f"Cleanup complete. Kept: {kept_count}, Deleted: {deleted_count}")

if __name__ == "__main__":
    cleanup_embeddings_folder()
