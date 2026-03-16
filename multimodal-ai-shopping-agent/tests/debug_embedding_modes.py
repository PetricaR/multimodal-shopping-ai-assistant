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

def debug_modes():
    bq = BigQueryClient()
    gen = MultimodalEmbeddingGenerator()
    
    # Fetch Product (Coffee)
    products = bq.get_products_by_name("Doncafe", limit=1)
    if not products:
        logger.error("Product not found")
        return
    product = products[0]
    
    logger.info(f"Product: {product['metadata']['product_name']}")
    text = product['combined_text']
    image_url = product['image_url']
    
    # Generate Variables
    logger.info("Generating Variations...")
    
    # 1. Text Only Product
    vec_p_text, _ = gen.generate_embedding(text, None)
    
    # 2. Image Only Product
    settings.USE_MULTIMODAL = True # Ensure enabled
    vec_p_image_only = None
    # Force image only by suppressing text? No, generator doesn't allow standard api for that easily without hacking.
    # Actually generator handles it: if text is None.
    try:
        # Use underlying model directly to avoid 'Either text or image' check if we pass text=None
        img_obj = gen.download_and_process_image(image_url)
        v_img = gen.model.get_embeddings(image=img_obj, dimension=512)
        vec_p_image_only = v_img.image_embedding
    except Exception as e:
        logger.error(f"Image only failed: {e}")

    # 3. Multimodal (Current Pipeline)
    vec_p_multi, _ = gen.generate_embedding(text, image_url)
    
    # 4. Query
    query = "cafea"
    vec_q, _ = gen.generate_embedding(query, None)
    
    # Compare
    def sim(v1, v2):
        if v1 is None or v2 is None: return 0.0
        return cosine_similarity(np.array(v1).reshape(1, -1), np.array(v2).reshape(1, -1))[0][0]

    logger.info("=" * 40)
    logger.info(f"Query: '{query}'")
    logger.info("-" * 40)
    logger.info(f"vs Product (Text Only):  {sim(vec_q, vec_p_text):.4f}")
    logger.info(f"vs Product (Image Only): {sim(vec_q, vec_p_image_only):.4f}")
    logger.info(f"vs Product (Multimodal): {sim(vec_q, vec_p_multi):.4f}")
    logger.info("=" * 40)

if __name__ == "__main__":
    debug_modes()
