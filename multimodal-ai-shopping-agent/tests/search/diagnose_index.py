#!/usr/bin/env python3
"""
Diagnose Vector Search Index - Check what IDs are being used
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api import dependencies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("=== DIAGNOSING VECTOR SEARCH INDEX ===\n")

    # Get search engine
    search_engine = dependencies.get_search_engine()

    # Search for a common product
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=5)

    logger.info(f"\n📊 Search Results Analysis:")
    logger.info(f"   Total results: {len(results)}\n")

    for i, result in enumerate(results, 1):
        result_id = result.get('id', 'N/A')
        product_name = result.get('product_name', 'N/A')
        product_id = result.get('product_id', 'NOT FOUND')
        similarity = result.get('similarity_score', 0)

        logger.info(f"   Result #{i}:")
        logger.info(f"      ID from vector search: {result_id}")
        logger.info(f"      Product name: {product_name}")
        logger.info(f"      Product ID (numeric): {product_id}")
        logger.info(f"      Similarity: {similarity:.3f}")
        logger.info(f"      ID type: {type(result_id).__name__}")
        logger.info(f"      ID is numeric: {str(result_id).isdigit()}")
        logger.info("")

    # Diagnosis
    logger.info("\n🔍 DIAGNOSIS:")
    first_id = results[0].get('id', '') if results else ''

    if str(first_id).isdigit():
        logger.info("   ✅ Index is using NUMERIC product_id (CORRECT)")
        logger.info("   → No action needed. Index is properly configured.")
    else:
        logger.info("   ❌ Index is using PRODUCT NAMES as IDs (INCORRECT)")
        logger.info("   → This causes the warning in test_cart.py")
        logger.info("")
        logger.info("   📋 TO FIX:")
        logger.info("   1. Check embeddings file format:")
        logger.info("      gsutil cat gs://formare-ai-vector-search/embeddings/bringo_products_embeddings.jsonl | head -3")
        logger.info("")
        logger.info("   2. If embeddings have numeric IDs but index doesn't, rebuild index:")
        logger.info("      python scripts/update_index.py")
        logger.info("")
        logger.info("   3. If embeddings also have product names, regenerate embeddings:")
        logger.info("      python scripts/generate_embeddings.py")
        logger.info("      python scripts/update_index.py")

if __name__ == "__main__":
    main()
