#!/usr/bin/env python3
"""
Test Vector Search component.

Verifies:
1. Search Engine initializes and connects to the endpoint
2. Text query produces embeddings and returns results
3. Results contain numeric product IDs with similarity scores
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_vector_search")


def test_search_engine_init():
    """Test that the Search Engine initializes and finds the endpoint."""
    logger.info("=" * 80)
    logger.info("TEST 1: Search Engine Initialization")
    logger.info("=" * 80)

    try:
        from api import dependencies
        from config.settings import settings
        search_engine = dependencies.get_search_engine()

        logger.info(f"  Endpoint: {search_engine.endpoint.display_name}")
        logger.info(f"  Embedding model: {settings.EMBEDDING_MODEL}")
        logger.info("\n✅ PASS: Search Engine initialized")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAIL: Could not initialize Search Engine: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_text_search():
    """Test that a text query returns results from Vector Search."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Text Search Query")
    logger.info("=" * 80)

    from api import dependencies

    search_engine = dependencies.get_search_engine()
    query = "cafea"
    logger.info(f"  Query: '{query}'")

    results = search_engine.search_by_text(query_text=query, num_neighbors=5)

    if not results:
        logger.error("\n❌ FAIL: No results returned for query")
        return False

    logger.info(f"  Results returned: {len(results)}")

    for i, r in enumerate(results):
        logger.info(
            f"  [{i+1}] id={r.get('id')}  "
            f"similarity={r.get('similarity_score', 0):.4f}  "
            f"name={r.get('product_name', 'N/A')}"
        )

    logger.info(f"\n✅ PASS: Search returned {len(results)} results")
    return True


def test_result_format():
    """Test that results have the expected fields and numeric IDs."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Result Format Validation")
    logger.info("=" * 80)

    from api import dependencies

    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="lapte", num_neighbors=3)

    if not results:
        logger.error("\n❌ FAIL: No results to validate")
        return False

    passed = True
    first = results[0]

    # Check required fields
    required = ['id', 'distance', 'similarity_score', 'product_id']
    missing = [f for f in required if f not in first]
    if missing:
        logger.error(f"  Missing fields: {missing}")
        passed = False
    else:
        logger.info(f"  Required fields present: {required}")

    # Check numeric ID
    pid = str(first.get('id', ''))
    if pid.isdigit():
        logger.info(f"  Product ID '{pid}' is numeric")
    else:
        logger.error(f"  Product ID '{pid}' is NOT numeric — index may use product names")
        passed = False

    # Check similarity score range
    score = first.get('similarity_score', -1)
    if 0 <= score <= 1:
        logger.info(f"  Similarity score {score:.4f} is in valid range [0, 1]")
    else:
        logger.error(f"  Similarity score {score} is out of range")
        passed = False

    if passed:
        logger.info(f"\n✅ PASS: Result format is correct")
    else:
        logger.error(f"\n❌ FAIL: Result format issues detected")
    return passed


def main():
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 22 + "VECTOR SEARCH TEST" + " " * 38 + "║")
    logger.info("╚" + "=" * 78 + "╝")

    tests = [
        ("Search Engine Init", test_search_engine_init),
        ("Text Search Query", test_text_search),
        ("Result Format", test_result_format),
    ]

    results = {}
    for name, func in tests:
        try:
            results[name] = func()
        except Exception as e:
            logger.error(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        logger.info(f"  {status}: {name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
