import logging
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ranking.reranker import Reranker
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ranking():
    logger.info("Initializing Reranker...")
    try:
        reranker = Reranker()
    except Exception as e:
        logger.error(f"Failed to init reranker: {e}")
        return

    # Mock candidates (usually come from Vector Search)
    candidates = [
        {"id": "test_1", "product_name": "Lapte 1.5%", "combined_text": "Lapte UHT 1.5% grasime"},
        {"id": "test_2", "product_name": "Iaurt", "combined_text": "Iaurt cremos"},
        {"id": "test_3", "product_name": "Branza", "combined_text": "Branza proaspata de vaci"},
        {"id": "test_4", "product_name": "Apa", "combined_text": "Apa minerala"},
    ]
    query = "branza"
    
    logger.info(f"Reranking {len(candidates)} candidates for query '{query}'...")
    
    start = time.time()
    try:
        results = reranker.rerank(query, candidates, top_n=2)
        elapsed = time.time() - start
        logger.info(f"Rerank completed in {elapsed:.2f}s")
        for r in results:
            logger.info(f" - {r['product_name']} (score: {r.get('ranking_score', 0):.4f})")
            
    except Exception as e:
        logger.error(f"Rerank failed: {e}")

if __name__ == "__main__":
    test_ranking()
