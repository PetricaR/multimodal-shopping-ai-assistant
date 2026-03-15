#!/usr/bin/env python3
"""
Test Feature Store component.

Verifies:
1. Feature Store client initializes and connects
2. Product metadata can be fetched by ID
3. Returned metadata contains fields needed by the agent
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
logger = logging.getLogger("test_feature_store")


def test_feature_server_init():
    """Test that the Feature Store client initializes without error."""
    logger.info("=" * 80)
    logger.info("TEST 1: Feature Server Initialization")
    logger.info("=" * 80)

    try:
        from features.realtime_server import get_feature_server
        server = get_feature_server()

        logger.info(f"  Feature Store: {server.feature_online_store}")
        logger.info(f"  Metadata view: {server.metadata_view}")
        logger.info(f"\n✅ PASS: Feature Server initialized")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAIL: Could not initialize Feature Server: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_metadata():
    """Test fetching metadata for products returned by Vector Search."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Fetch Product Metadata")
    logger.info("=" * 80)

    # Get real product IDs from Vector Search
    from api import dependencies

    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=3)

    if not results:
        logger.error("❌ Vector Search returned no results — cannot test Feature Store")
        return False

    product_ids = [r.get('id') for r in results if r.get('id')]
    logger.info(f"  Product IDs from search: {product_ids}")

    from features.realtime_server import get_feature_server
    server = get_feature_server()
    metadata = server.get_product_metadata(product_ids)

    logger.info(f"  Metadata returned for {len(metadata)}/{len(product_ids)} products")

    if not metadata:
        logger.error("\n❌ FAIL: Feature Store returned no metadata")
        logger.error("   Possible causes:")
        logger.error("   - Feature Store not synced (run: python features/sync_feature_store.py)")
        logger.error("   - Entity IDs don't match between index and Feature Store")
        logger.error(f"   - Queried IDs: {product_ids}")
        return False

    # Log sample metadata
    first_pid = next(iter(metadata))
    logger.info(f"\n  Sample metadata for product {first_pid}:")
    for key, value in metadata[first_pid].items():
        logger.info(f"    {key}: {value}")

    logger.info(f"\n✅ PASS: Retrieved metadata for {len(metadata)} product(s)")
    return True


def test_metadata_fields():
    """Test that metadata contains the fields needed for cart operations."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Required Metadata Fields")
    logger.info("=" * 80)

    from api import dependencies
    from features.realtime_server import get_feature_server

    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(query_text="cafea", num_neighbors=1)

    if not results:
        logger.error("❌ No search results")
        return False

    product_id = results[0].get('id')
    if not product_id:
        logger.error("❌ Search result missing 'id'")
        return False

    server = get_feature_server()
    metadata = server.get_product_metadata([product_id])

    if product_id not in metadata:
        logger.error(f"❌ No metadata for product {product_id}")
        logger.error("   Feature Store data may not be synced")
        return False

    data = metadata[product_id]
    logger.info(f"  Available fields: {list(data.keys())}")

    # Fields the agent needs for cart operations
    expected = {
        'product_name': 'Product display name',
        'variant_id': 'Required for add-to-cart API',
        'price': 'Price in RON',
    }

    missing = []
    for field, desc in expected.items():
        val = data.get(field)
        if val:
            logger.info(f"  ✓ {field}: {val}")
        else:
            # Also check alternate field names
            alt = data.get('price_ron') if field == 'price' else None
            if alt:
                logger.info(f"  ✓ {field} (as price_ron): {alt}")
            else:
                logger.warning(f"  ✗ {field} — {desc}")
                missing.append(field)

    if missing:
        logger.error(f"\n❌ FAIL: Missing required fields: {missing}")
        return False

    logger.info(f"\n✅ PASS: All required fields present")
    return True


def main():
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 22 + "FEATURE STORE TEST" + " " * 38 + "║")
    logger.info("╚" + "=" * 78 + "╝")

    tests = [
        ("Feature Server Init", test_feature_server_init),
        ("Fetch Product Metadata", test_fetch_metadata),
        ("Required Metadata Fields", test_metadata_fields),
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
