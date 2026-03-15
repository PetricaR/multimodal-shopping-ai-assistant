#!/usr/bin/env python3
"""
Quick check: Is the fix complete and ready to use?

Run this to see if:
1. Index rebuild is done
2. Feature Store works
3. Complete flow is ready

Usage:
    python check_if_ready.py
"""
import logging

logging.basicConfig(level=logging.WARNING)  # Suppress info logs

def test_flow():
    """Quick test to see if everything works"""
    try:
        from api import dependencies

        # Test search
        search_engine = dependencies.get_search_engine()
        results = search_engine.search_by_text("cafea", num_neighbors=1)

        if not results:
            print("❌ No search results")
            return False

        product = results[0]
        product_id = product.get('id', '')
        has_metadata = bool(product.get('product_id') and product.get('variant_id'))

        # Check if using numeric IDs
        is_numeric = str(product_id).isdigit()

        print("\n" + "="*60)
        print("QUICK STATUS CHECK")
        print("="*60)

        print(f"\n1. Index Status:")
        if is_numeric:
            print(f"   ✅ Index returns numeric product_id: {product_id}")
        else:
            print(f"   ⏳ Index still returns product names: {product_id[:50]}...")
            print(f"   → Index rebuild in progress (45-90 min)")
            return False

        print(f"\n2. Feature Store:")
        if has_metadata:
            print(f"   ✅ Enrichment working")
            print(f"   → Product: {product.get('product_name')}")
            print(f"   → Variant: {product.get('variant_id')}")
        else:
            print(f"   ⏳ Enrichment not working")
            print(f"   → Need to sync: python features/sync_feature_store.py")
            return False

        print(f"\n3. Complete Flow:")
        print(f"   ✅ READY TO USE!")
        print(f"\nNext steps:")
        print(f"  1. Run full test: python test_feature_store_flow.py")
        print(f"  2. Integrate into agent")
        print(f"  3. Deploy to production")
        print()

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    ready = test_flow()
    sys.exit(0 if ready else 1)
