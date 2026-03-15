#!/usr/bin/env python3
"""
Test Ranking API component.

Verifies:
1. Reranker client initializes and connects
2. Reranking produces scored results from Vector Search candidates
3. Ranking scores are valid and ordering is correct
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
logger = logging.getLogger("test_ranking")


def test_reranker_init():
    """Test that the Reranker client initializes without error."""
    logger.info("=" * 80)
    logger.info("TEST 1: Reranker Initialization")
    logger.info("=" * 80)

    try:
        from ranking.reranker import Reranker
        reranker = Reranker()

        logger.info(f"  Model: {reranker.model}")
        logger.info(f"  Ranking config: {reranker.ranking_config}")
        logger.info(f"\n✅ PASS: Reranker initialized")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAIL: Could not initialize Reranker: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rerank_candidates():
    """Test reranking Vector Search candidates."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Rerank Vector Search Candidates")
    logger.info("=" * 80)

    from api import dependencies
    from ranking.reranker import Reranker

    # Get candidates from Vector Search
    search_engine = dependencies.get_search_engine()
    query = "cafea"
    candidates = search_engine.search_by_text(query_text=query, num_neighbors=150)

    if not candidates:
        logger.error("❌ Vector Search returned no candidates — cannot test ranking")
        return False

    logger.info(f"  Candidates from Vector Search: {len(candidates)}")

    # Rerank
    reranker = Reranker()
    top_n = 5
    ranked = reranker.rerank(query=query, candidates=candidates, top_n=top_n)

    if not ranked:
        logger.error("\n❌ FAIL: Reranker returned no results")
        return False

    logger.info(f"  Ranked results: {len(ranked)}")

    for i, r in enumerate(ranked):
        logger.info(
            f"  [{i+1}] id={r.get('id')}  "
            f"ranking_score={r.get('ranking_score', 'N/A')}  "
            f"similarity={r.get('similarity_score', 0):.4f}  "
            f"name={r.get('product_name', 'N/A')}"
        )

    logger.info(f"\n✅ PASS: Reranked to {len(ranked)} results")
    return True


def test_ranking_scores():
    """Test that ranking scores are valid and properly ordered."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Ranking Score Validation")
    logger.info("=" * 80)

    from api import dependencies
    from ranking.reranker import Reranker

    search_engine = dependencies.get_search_engine()
    query = "lapte"
    candidates = search_engine.search_by_text(query_text=query, num_neighbors=150)

    if not candidates:
        logger.error("❌ No candidates")
        return False

    reranker = Reranker()
    ranked = reranker.rerank(query=query, candidates=candidates, top_n=10)

    if not ranked:
        logger.error("❌ No ranked results")
        return False

    passed = True

    # Check that ranking_score exists on results
    scores = [r.get('ranking_score') for r in ranked]
    if any(s is None for s in scores):
        logger.error(f"  Some results missing ranking_score: {scores}")
        passed = False
    else:
        logger.info(f"  All {len(ranked)} results have ranking_score")

    # Check score range (Ranking API returns 0-1)
    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        min_s, max_s = min(valid_scores), max(valid_scores)
        logger.info(f"  Score range: [{min_s:.4f}, {max_s:.4f}]")
        if min_s < 0 or max_s > 1:
            logger.warning(f"  Scores outside expected [0, 1] range")

    # Check descending order
    if valid_scores == sorted(valid_scores, reverse=True):
        logger.info(f"  Scores are in descending order")
    else:
        logger.error(f"  Scores are NOT in descending order")
        passed = False

    # Check that ranking changed the order vs vector search
    original_ids = [c.get('id') for c in candidates[:len(ranked)]]
    ranked_ids = [r.get('id') for r in ranked]
    if original_ids != ranked_ids:
        logger.info(f"  Ranking reordered results (different from Vector Search order)")
    else:
        logger.info(f"  Ranking kept same order as Vector Search")

    if passed:
        logger.info(f"\n✅ PASS: Ranking scores are valid")
    else:
        logger.error(f"\n❌ FAIL: Ranking score issues detected")
    return passed


def main():
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 25 + "RANKING TEST" + " " * 41 + "║")
    logger.info("╚" + "=" * 78 + "╝")

    tests = [
        ("Reranker Init", test_reranker_init),
        ("Rerank Candidates", test_rerank_candidates),
        ("Ranking Scores", test_ranking_scores),
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
