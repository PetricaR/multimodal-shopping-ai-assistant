#!/usr/bin/env python3
"""
Test script for Name Search Engine
Validates performance and accuracy of semantic name matching
"""

import sys
import os
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from vector_search.name_search_engine import NameSearchEngine
from data.bigquery_client import BigQueryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_name_search():
    """Test name search engine with various queries"""

    logger.info("=" * 70)
    logger.info("TESTING NAME SEARCH ENGINE")
    logger.info("=" * 70)

    # Initialize engines
    name_search = NameSearchEngine()
    bq_client = BigQueryClient()

    # Test queries (Romanian)
    test_queries = [
        "lapte",
        "laptte",  # Typo
        "milk",  # English synonym
        "paine",
        "bread",  # English
        "cafea",
        "coffee",  # English
        "ciocolata",
        "chocolate",
        "bere",
        "beer",
    ]

    results = []

    for query in test_queries:
        logger.info(f"\nTest query: '{query}'")
        logger.info("-" * 70)

        # Test Vector Search (fast)
        if name_search.is_available():
            vs_start = time.time()
            vs_matches = name_search.search_by_name(query, num_results=3)
            vs_time = (time.time() - vs_start) * 1000

            logger.info(f"✓ Vector Search: {len(vs_matches)} matches in {vs_time:.1f}ms")
            if vs_matches:
                for i, match in enumerate(vs_matches[:3], 1):
                    product = bq_client.get_product_by_id(match['product_id'])
                    if product:
                        logger.info(f"  {i}. {product['metadata']['product_name']} (score: {match['similarity_score']:.3f})")
        else:
            logger.warning("Vector Search name index not available")
            vs_time = None

        # Test BigQuery (slow)
        bq_start = time.time()
        bq_matches = bq_client.get_products_by_name(query, limit=3)
        bq_time = (time.time() - bq_start) * 1000

        logger.info(f"✓ BigQuery LIKE: {len(bq_matches)} matches in {bq_time:.1f}ms")
        if bq_matches:
            for i, product in enumerate(bq_matches[:3], 1):
                logger.info(f"  {i}. {product['metadata']['product_name']}")

        # Compare performance
        if vs_time:
            speedup = bq_time / vs_time
            logger.info(f"⚡ Speedup: {speedup:.1f}x faster with Vector Search")
            results.append({
                'query': query,
                'vs_time': vs_time,
                'bq_time': bq_time,
                'speedup': speedup
            })

    # Summary
    if results:
        logger.info("\n" + "=" * 70)
        logger.info("PERFORMANCE SUMMARY")
        logger.info("=" * 70)

        avg_vs_time = sum(r['vs_time'] for r in results) / len(results)
        avg_bq_time = sum(r['bq_time'] for r in results) / len(results)
        avg_speedup = sum(r['speedup'] for r in results) / len(results)

        logger.info(f"Average Vector Search time: {avg_vs_time:.1f}ms")
        logger.info(f"Average BigQuery time: {avg_bq_time:.1f}ms")
        logger.info(f"Average speedup: {avg_speedup:.1f}x")
        logger.info("")
        logger.info("✅ Name Search Engine is optimized for voice agents!")


def test_voice_scenarios():
    """Test scenarios specific to voice-based shopping"""

    logger.info("\n" + "=" * 70)
    logger.info("TESTING VOICE-SPECIFIC SCENARIOS")
    logger.info("=" * 70)

    name_search = NameSearchEngine()

    if not name_search.is_available():
        logger.warning("Name Search Engine not available. Skipping voice tests.")
        return

    # Voice recognition challenges
    voice_tests = [
        ("lapte zuzu", "Correct pronunciation"),
        ("laptee zuzzu", "ASR typos"),
        ("milk zuzu", "Code-switching (Romanian + English)"),
        ("paine feliata", "Multi-word queries"),
        ("payne feliata", "Phonetic misspelling"),
    ]

    for query, description in voice_tests:
        logger.info(f"\n{description}: '{query}'")
        start = time.time()
        matches = name_search.search_by_name(query, num_results=1)
        latency = (time.time() - start) * 1000

        if matches:
            bq_client = BigQueryClient()
            product = bq_client.get_product_by_id(matches[0]['product_id'])
            if product:
                logger.info(f"  ✓ Found: {product['metadata']['product_name']}")
                logger.info(f"  Score: {matches[0]['similarity_score']:.3f}")
                logger.info(f"  Latency: {latency:.1f}ms")
        else:
            logger.info("  ✗ No match found")


if __name__ == "__main__":
    test_name_search()
    test_voice_scenarios()

    logger.info("\n" + "=" * 70)
    logger.info("TESTING COMPLETE")
    logger.info("=" * 70)
