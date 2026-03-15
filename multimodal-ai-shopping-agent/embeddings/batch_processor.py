"""
Batch processing for multimodal embeddings
Optimized for Speed with Multithreading & Rate Limiting
"""
import json
import logging
import time
import threading
from typing import List, Dict
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import storage
from config.settings import settings
from embeddings.generator import MultimodalEmbeddingGenerator

logger = logging.getLogger(__name__)

class RateLimiter:
    """Thread-safe Rate Limiter"""
    def __init__(self, requests_per_minute: int):
        self.interval = 60.0 / requests_per_minute
        self.lock = threading.Lock()
        self.last_request_time = 0

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_request_time = time.time()

class BatchEmbeddingProcessor:
    """
    Process products in batches to generate multimodal embeddings
    Optimized for Speed with Multithreading & Rate Limiting
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize with thread pool support.
        
        Args:
            max_workers: Number of concurrent threads (4-8 is usually optimal for 2 QPS)
        """
        self.generator = MultimodalEmbeddingGenerator()
        self.storage_client = storage.Client(project=settings.PROJECT_ID)
        self.bucket = self.storage_client.bucket(settings.STAGING_BUCKET)
        
        # Enforce quota globally across threads
        self.limiter = RateLimiter(requests_per_minute=settings.EMBEDDING_RATE_LIMIT)
        self.max_workers = max_workers
        
        logger.info(f"✓ Initialized batch processor (Threaded)")
        logger.info(f"  - Workers: {self.max_workers}")
        logger.info(f"  - Rate Limit: {settings.EMBEDDING_RATE_LIMIT} req/min")
    
    def _process_single_product(self, product: Dict) -> Dict:
        """Thread worker function"""
        # Global Rate Limit check (blocks thread)
        self.limiter.wait()
        
        try:
            embedding, emb_type = self.generator.generate_embedding(
                text=product['combined_text'],
                image_url=product.get('image_url')
            )
            
            return {
                'id': str(product['product_id']),
                'embedding': embedding,
                'restricts': [
                    {'namespace': 'category', 'allow': [product['metadata'].get('category', '')]},
                    {'namespace': 'in_stock', 'allow': ['true' if product['metadata'].get('in_stock') else 'false']}
                ],
                'crowding_tag': product['metadata'].get('category', 'unknown'),
            }
        except Exception as e:
            logger.error(f"Failed to process product {product.get('product_id')}: {e}")
            return None
    
    def process_batch(self, products: List[Dict], target_filename: str = None, show_progress: bool = True) -> List[Dict]:
        """
        Process products using ThreadPoolExecutor for speed
        Skips products that already have embeddings (Primitive caching)
        """
        logger.info(f"Processing batch. Target cache file: {target_filename}")
        
        existing_ids = set()
        existing_data = []
        
        # Load existing embeddings from GCS if filename provided
        if target_filename:
            blob_path = f"embeddings/{target_filename}"
            try:
                blob = self.bucket.blob(blob_path)
                if blob.exists():
                    logger.info(f"Checking existing embeddings in: {blob_path}")
                    # Download as bytes and decode to avoid encoding issues, or stream
                    content = blob.download_as_text()
                    count = 0
                    for line in content.splitlines():
                        if line.strip():
                            try:
                                record = json.loads(line)
                                rid = str(record.get('id', ''))
                                # Self-healing: Only keep records with numeric IDs
                                if rid and rid.isdigit():
                                    existing_ids.add(rid)
                                    existing_data.append(record)
                                    count += 1
                                elif rid:
                                    logger.warning(f"Skipping legacy non-numeric ID: {rid}")
                            except json.JSONDecodeError:
                                pass
                    logger.info(f"✓ Loaded {count} valid numeric embeddings from GCS.")
            except Exception as e:
                logger.warning(f"Could not load existing embeddings from {blob_path}: {e}")
            
        # Filter products
        # 'id' in embedding record corresponds to 'product_id'
        products_to_process = [p for p in products if str(p['product_id']) not in existing_ids]
        
        if not products_to_process:
            logger.info("All products already have embeddings. Skipping generation.")
            return existing_data
            
        logger.info(f"Processing {len(products_to_process)} NEW products (Skipped {len(existing_ids)} existing)...")
        
        new_embeddings = []
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_prod = {executor.submit(self._process_single_product, p): p for p in products_to_process}
            
            # Monitor progress
            iterator = as_completed(future_to_prod)
            if show_progress:
                iterator = tqdm(iterator, total=len(products_to_process), desc="Generating Embeddings (Threaded)")
                
            for future in iterator:
                try:
                    result = future.result()
                    if result:
                        new_embeddings.append(result)
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Thread exception: {e}")
                    failed_count += 1
        
        self.generator.print_stats()
        logger.info(f"✓ Generated {len(new_embeddings)} new embeddings")
        logger.info(f"✗ Failed: {failed_count}")
        
        # Combined result
        combined_embeddings = existing_data + new_embeddings
        return combined_embeddings

    def save_to_gcs(self, embeddings_data: List[Dict], filename: str = "bringo_products_embeddings.jsonl") -> str:
        """Save to GCS"""
        jsonl_content = "\n".join([json.dumps(record) for record in embeddings_data])
        blob_path = f"embeddings/{filename}"
        blob = self.bucket.blob(blob_path)
        
        logger.info(f"Uploading {len(embeddings_data)} embeddings to gs://{settings.STAGING_BUCKET}/{blob_path}")
        blob.upload_from_string(jsonl_content, content_type='application/json')
        return f"gs://{settings.STAGING_BUCKET}/{blob_path}"

    def process_and_save(self, products: List[Dict], filename: str = "bringo_products_embeddings.jsonl") -> str:
        # Pass filename to allow caching check
        embeddings_data = self.process_batch(products, target_filename=filename, show_progress=True)
        return self.save_to_gcs(embeddings_data, filename)
