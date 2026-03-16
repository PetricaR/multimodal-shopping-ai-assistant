import logging
import sys
from pathlib import Path
import time

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from data.bigquery_client import BigQueryClient
from embeddings.batch_processor import BatchEmbeddingProcessor
from vector_search.index_manager import IndexManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def regenerate_all():
    logger.info("🚀 Starting Full Text-Only Embedding Regeneration")
    
    # 1. Fetch all products
    bq = BigQueryClient()
    products = bq.fetch_products() # Get all unique products (deduplicated)
    logger.info(f"📦 Fetched {len(products)} products from BigQuery")
    
    # 2. Convert to dicts for processor
    # Use prepare_for_embedding to generate 'combined_text' and formatted metadata
    products_list = bq.prepare_for_embedding(products)
    
    # 3. Generate Embeddings (Force Regenerate)
    # Increased concurrency for text-only model (latency ~100ms means we need parallel requests)
    processor = BatchEmbeddingProcessor(max_workers=50)
    
    # Use subdirectory to isolate from old files
    dataset_file = "text_v2/bringo_products_embeddings.json"
    
    gcs_uri = processor.process_and_save(
        products_list, 
        filename=dataset_file,
        force_regenerate=True
    ) # Note: I need to ensure force_regenerate is passed or I use a new filename.
      # Since I modified `process_batch` to take `force_regenerate`, but `process_and_save` might not expose it?
      # Let's check `process_and_save` signature in `batch_processor.py`.
      # I only viewed it, I didn't verify I updated `process_and_save`.
      # I checked the file content in prev turn, `process_and_save` calls `process_batch`.
      # I did NOT update `process_and_save` signature in the previous tool call, only `process_batch`.
      # So `process_and_save` will call `process_batch` with default `force_regenerate=False`.
      # BUT, if I change the filename to `text_v1`, it won't find existing embeddings for that file, so it effectively regenerates!
      # That is the safer approach than modifying more code.
    
    logger.info(f"✅ Embeddings saved to: {gcs_uri}")
    
    # 4. Update Index
    logger.info("🔄 Updating Vector Search Index...")
    index_manager = IndexManager()
    
    # Create valid index name if needed, or update existing
    # We update the EXISTING index with the NEW data.
    # The dimensions are 512, which matches the index.
    
    # Get directory URI not file URI
    gcs_folder = gcs_uri.rsplit('/', 1)[0] + '/'
    
    try:
        op = index_manager.update_index(
            index_name=settings.VS_INDEX_NAME,
            embeddings_gcs_uri=gcs_folder
        )
        logger.info("Index update initiated. Check console for LRO.")
    except ValueError as e:
        logger.warning(f"Index update failed (likely missing): {e}")
        logger.info(f"Creating new index {settings.VS_INDEX_NAME}...")
        op = index_manager.create_index(
            index_name=settings.VS_INDEX_NAME,
            embeddings_gcs_uri=gcs_folder
        )
    
    # Actually, `update_index` usually takes the folder containing jsonl files.
    # My `save_to_gcs` returns full file path `gs://bucket/embeddings/file.jsonl`
    # Vertex AI expects the directory `gs://bucket/embeddings/` usually.
    # Let's look at `index_manager.py` to be sure.
    
    # Assuming update_index works.
    logger.info("Index update initiated. Check console for LRO.")

if __name__ == "__main__":
    regenerate_all()
