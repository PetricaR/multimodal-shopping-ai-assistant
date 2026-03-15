#!/usr/bin/env python3
"""
Test Feature Store Flow (After Fix Completes)

This test verifies the complete flow:
1. Vector Search returns numeric product_id
2. Feature Store enriches with metadata
3. Cart API adds product successfully

Run this AFTER embeddings regeneration and index rebuild complete.
"""
import os
import logging
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_fs_flow")


def test_vector_search():
    """Test that Vector Search returns numeric product_ids"""
    logger.info("=" * 80)
    logger.info("TEST 1: Vector Search Returns Numeric Product IDs")
    logger.info("=" * 80)

    from api import dependencies

    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=3)

    if not results:
        logger.error("❌ No results returned!")
        return False

    # Check first result
    first_id = results[0].get('id', '')
    is_numeric = str(first_id).isdigit()

    logger.info(f"\nFirst result ID: {first_id}")
    logger.info(f"Is numeric: {is_numeric}")
    logger.info(f"Type: {type(first_id).__name__}")

    if is_numeric:
        logger.info("\n✅ PASS: Vector Search returns numeric product_id")
        return True
    else:
        logger.error("\n❌ FAIL: Vector Search still returns product names")
        logger.error("   → Index rebuild may not be complete yet")
        logger.error("   → Run: python diagnose_index.py to check status")
        return False


def test_feature_store_enrichment():
    """Test that Feature Store enriches results with metadata"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Feature Store Enrichment")
    logger.info("=" * 80)

    from api import dependencies

    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=3)

    if not results:
        logger.error("❌ No results!")
        return False

    product = results[0]

    # Check required fields
    required_fields = {
        'product_id': 'Numeric product ID',
        'product_name': 'Product name',
        'variant_id': 'Variant ID (for cart)',
        'price': 'Price in RON'
    }

    logger.info("\nEnriched product data:")
    logger.info(f"  Product: {product.get('product_name', 'MISSING')}")
    logger.info(f"  ID: {product.get('product_id', 'MISSING')}")
    logger.info(f"  Variant: {product.get('variant_id', 'MISSING')}")
    logger.info(f"  Price: {product.get('price', 'MISSING')} RON")
    logger.info(f"  Category: {product.get('category', 'N/A')}")
    logger.info(f"  In Stock: {product.get('in_stock', 'N/A')}")
    logger.info(f"  Similarity: {product.get('similarity_score', 0):.1%}")

    # Verify required fields
    missing_fields = []
    for field, description in required_fields.items():
        if not product.get(field):
            missing_fields.append(f"{field} ({description})")

    if missing_fields:
        logger.error(f"\n❌ FAIL: Missing required fields:")
        for field in missing_fields:
            logger.error(f"   - {field}")
        logger.error("\n   → Feature Store may not be synced yet")
        logger.error("   → Run: python features/sync_feature_store.py")
        return False
    else:
        logger.info("\n✅ PASS: Feature Store enrichment complete")
        return True


def test_cart_integration():
    """Test adding product to cart with enriched data"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Cart Integration")
    logger.info("=" * 80)

    from api import dependencies
    from services.cart_service import CartService
    from api.tools.shared import db

    # Get auth
    creds = db.get_credentials()
    if not creds or not creds.get('session_cookie'):
        logger.error("❌ No active session found!")
        logger.error("   → Run: python test_auth.py first")
        return False

    phpsessid = creds['session_cookie']
    logger.info(f"✓ Authenticated as: {creds.get('username')}")

    # Search for product
    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=1)

    if not results:
        logger.error("❌ No products found!")
        return False

    product = results[0]

    # Verify we have required fields
    product_id = product.get('product_id')
    variant_id = product.get('variant_id')

    if not product_id:
        logger.error("❌ Missing product_id!")
        return False

    if not variant_id:
        logger.error("❌ Missing variant_id!")
        return False

    logger.info(f"\nAdding to cart:")
    logger.info(f"  Product: {product.get('product_name')}")
    logger.info(f"  ID: {product_id}")
    logger.info(f"  Variant: {variant_id}")

    # Add to cart
    result = CartService.add_product_to_cart(
        product_id=product_id,
        variant_id=variant_id,
        quantity=1,
        phpsessid=phpsessid,
        cookies={'PHPSESSID': phpsessid},
        store="carrefour_park_lake"
    )

    if result['status'] == 'success':
        logger.info(f"\n✅ PASS: Cart integration successful")
        logger.info(f"   Message: {result['message']}")
        return True
    else:
        logger.error(f"\n❌ FAIL: Cart operation failed")
        logger.error(f"   Error: {result['message']}")
        return False


def test_complete_flow():
    """Test the complete agent flow end-to-end"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Complete Agent Flow (Search → Rank → Enrich → Cart)")
    logger.info("=" * 80)

    from api import dependencies
    from ranking.reranker import SemanticReranker
    from features.realtime_server import get_feature_server
    from services.cart_service import CartService
    from api.tools.shared import db

    try:
        # 1. Auth
        creds = db.get_credentials()
        if not creds:
            logger.error("❌ Not authenticated")
            return False

        phpsessid = creds['session_cookie']

        # 2. Vector Search
        logger.info("\n1️⃣  Vector Search...")
        search_engine = dependencies.get_search_engine()
        candidates = search_engine.search_by_text("cafea", num_neighbors=150)
        logger.info(f"   ✓ Found {len(candidates)} candidates")

        # 3. Ranking
        logger.info("\n2️⃣  Ranking API...")
        reranker = SemanticReranker()
        ranked = reranker.rerank("cafea", candidates, top_n=5)
        logger.info(f"   ✓ Ranked top {len(ranked)} results")

        # 4. Feature Store enrichment
        logger.info("\n3️⃣  Feature Store enrichment...")
        feature_server = get_feature_server()
        product_ids = [r['id'] for r in ranked]
        metadata = feature_server.get_product_metadata(product_ids)

        # Enrich
        for result in ranked:
            if result['id'] in metadata:
                result.update(metadata[result['id']])

        logger.info(f"   ✓ Enriched {len(metadata)} products")

        # Display top result
        best = ranked[0]
        logger.info(f"\n   🎯 Best match:")
        logger.info(f"      {best.get('product_name')}")
        logger.info(f"      Score: {best.get('similarity_score', 0):.1%}")
        logger.info(f"      Price: {best.get('price')} RON")

        # 5. Add to cart
        logger.info("\n4️⃣  Adding to cart...")
        result = CartService.add_product_to_cart(
            product_id=best['product_id'],
            variant_id=best['variant_id'],
            quantity=1,
            phpsessid=phpsessid,
            cookies={'PHPSESSID': phpsessid},
            store="carrefour_park_lake"
        )

        if result['status'] == 'success':
            logger.info(f"   ✓ {result['message']}")
            logger.info("\n✅ PASS: Complete flow successful!")
            return True
        else:
            logger.error(f"   ✗ {result['message']}")
            return False

    except Exception as e:
        logger.error(f"\n❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "FEATURE STORE FLOW TEST" + " " * 35 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\nThis tests the complete flow after embeddings fix completes.\n")

    tests = [
        ("Vector Search", test_vector_search),
        ("Feature Store Enrichment", test_feature_store_enrichment),
        ("Cart Integration", test_cart_integration),
        ("Complete Flow", test_complete_flow),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! Flow is ready for production.")
        return 0
    else:
        logger.error(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
