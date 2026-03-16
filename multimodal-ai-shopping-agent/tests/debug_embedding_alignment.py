import sys
from pathlib import Path
import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from data.bigquery_client import BigQueryClient
from embeddings.generator import MultimodalEmbeddingGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_alignment():
    bq = BigQueryClient()
    gen = MultimodalEmbeddingGenerator()
    
    # 1. Fetch Products
    logger.info("Fetching products...")
    # Use explicit names we likely have
    
    # Product A: Coffee
    products_a = bq.get_products_by_name("Doncafe", limit=1)
    if not products_a:
        logger.error("Could not find Doncafe")
        return
    prod_a = products_a[0]
    
    # Product B: Milk (Lapte) or something distinct
    # Try searching widely
    products_b = bq.get_products_by_name("Zuzu", limit=1) # Likely milk
    if not products_b:
        # Fallback
        products_b = bq.get_products_by_name("Apa", limit=1) # Water
    
    if not products_b:
        logger.error("Could not find comparison product (Zuzu/Apa)")
        return
    prod_b = products_b[0]
    
    logger.info(f"Product A: {prod_a['metadata']['product_name']}")
    logger.info(f"Product B: {prod_b['metadata']['product_name']}")
    
    # 2. Generate Product Embeddings (Multimodal)
    logger.info("Generating Multimodal Embeddings (Image + Text)...")
    
    vec_a, type_a = gen.generate_embedding(prod_a['combined_text'], prod_a['image_url'])
    logger.info(f"Vector A Type: {type_a}")
    
    vec_b, type_b = gen.generate_embedding(prod_b['combined_text'], prod_b['image_url'])
    logger.info(f"Vector B Type: {type_b}")
    
    # 3. Generate Query Embedding (Text Only)
    query_text = "cafea"
    logger.info(f"Generating Query Embedding for: '{query_text}'")
    
    vec_q, type_q = gen.generate_embedding(query_text, None)
    logger.info(f"Vector Q Type: {type_q}")
    
    # 4. Compare
    # Reshape for sklearn
    va = np.array(vec_a).reshape(1, -1)
    vb = np.array(vec_b).reshape(1, -1)
    vq = np.array(vec_q).reshape(1, -1)
    
    sim_a = cosine_similarity(vq, va)[0][0]
    sim_b = cosine_similarity(vq, vb)[0][0]
    
    logger.info("-" * 40)
    logger.info(f"Query: '{query_text}'")
    logger.info(f"Similarity to A (Coffee): {sim_a:.4f}")
    logger.info(f"Similarity to B (Other):  {sim_b:.4f}")
    logger.info("-" * 40)
    
    if sim_a > sim_b:
        logger.info("✅ SUCCESS: Query matches Coffee better.")
        if sim_a < 0.6:
            logger.warning("⚠️  BUT score is low (< 0.6). Alignment might be weak.")
    else:
        logger.error("❌ FAILURE: Query matches Other better! Embedding space mismatch.")

if __name__ == "__main__":
    debug_alignment()
