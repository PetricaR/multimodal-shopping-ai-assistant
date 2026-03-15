#!/usr/bin/env python3
"""
Monitor Embeddings Regeneration & Index Rebuild Progress

Checks:
1. Embeddings file status in GCS
2. Vector Search index status
3. Whether fix is complete and ready to test

Run this periodically to check progress:
    python monitor_fix_progress.py

Or run in watch mode:
    watch -n 60 python monitor_fix_progress.py
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import storage, aiplatform
from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_embeddings_file():
    """Check embeddings file status in GCS"""
    logger.info("=" * 80)
    logger.info("1. EMBEDDINGS FILE STATUS")
    logger.info("=" * 80)

    try:
        storage_client = storage.Client(project=settings.PROJECT_ID)
        bucket = storage_client.bucket(settings.STAGING_BUCKET)

        # Check for new embeddings file (.jsonl)
        new_blob = bucket.blob('embeddings/bringo_products_embeddings.jsonl')
        old_blob = bucket.blob('embeddings/bringo_products_embeddings.json')

        new_exists = new_blob.exists()
        old_exists = old_blob.exists()

        if new_exists:
            new_blob.reload()
            size_mb = new_blob.size / 1024 / 1024
            updated = new_blob.updated

            logger.info(f"\n✅ New embeddings file found:")
            logger.info(f"   Path: gs://{settings.STAGING_BUCKET}/embeddings/bringo_products_embeddings.jsonl")
            logger.info(f"   Size: {size_mb:.2f} MB")
            logger.info(f"   Updated: {updated}")

            # Check format
            content = new_blob.download_as_text()
            lines = content.strip().split('\n')
            sample = eval(lines[0]) if lines else {}
            sample_id = sample.get('id', '')

            logger.info(f"   Records: ~{len(lines)}")
            logger.info(f"   Sample ID: {sample_id}")
            logger.info(f"   ID is numeric: {str(sample_id).isdigit()}")

            if str(sample_id).isdigit():
                logger.info("\n   🎉 Embeddings use NUMERIC product_id (CORRECT!)")
                return "ready"
            else:
                logger.info("\n   ⚠️  Embeddings still use product names (regeneration incomplete)")
                return "in_progress"

        elif old_exists:
            old_blob.reload()
            logger.info(f"\n⏳ Old embeddings file still in use:")
            logger.info(f"   Path: gs://{settings.STAGING_BUCKET}/embeddings/bringo_products_embeddings.json")
            logger.info(f"   Size: {old_blob.size / 1024 / 1024:.2f} MB")
            logger.info(f"\n   Regeneration has not started or is in early stages.")
            return "not_started"

        else:
            logger.error("\n❌ No embeddings file found!")
            return "missing"

    except Exception as e:
        logger.error(f"\n❌ Error checking embeddings: {e}")
        return "error"


def check_index_status():
    """Check Vector Search index rebuild status"""
    logger.info("\n" + "=" * 80)
    logger.info("2. VECTOR SEARCH INDEX STATUS")
    logger.info("=" * 80)

    try:
        aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)

        # Get index
        indexes = aiplatform.MatchingEngineIndex.list(
            filter=f'display_name="{settings.VS_INDEX_NAME}"'
        )

        if not indexes:
            logger.error(f"\n❌ Index not found: {settings.VS_INDEX_NAME}")
            return "not_found"

        index = indexes[0]

        logger.info(f"\nIndex: {index.display_name}")
        logger.info(f"Resource: {index.resource_name}")

        # Check state (this might not be directly accessible, but we can try)
        # The state is usually in the metadata or we need to check for update operations

        logger.info(f"\n✓ Index exists and is accessible")
        logger.info(f"  To check rebuild status, visit:")
        logger.info(f"  https://console.cloud.google.com/vertex-ai/matching-engine/indexes?project={settings.PROJECT_ID}")

        return "check_console"

    except Exception as e:
        logger.error(f"\n❌ Error checking index: {e}")
        return "error"


def check_background_process():
    """Check if background regeneration process is still running"""
    logger.info("\n" + "=" * 80)
    logger.info("3. BACKGROUND PROCESS STATUS")
    logger.info("=" * 80)

    output_file = "/private/tmp/claude-501/-Users-radanpetrica-PFA-agents-agents-adk-mcp/tasks/b0f873f.output"

    try:
        with open(output_file, 'r') as f:
            content = f.read()

        # Check for completion markers
        if "✓ Index update initiated" in content:
            logger.info("\n✅ Process reached index rebuild stage!")
            logger.info("   Embeddings regeneration complete.")
            logger.info("   Index rebuild initiated (runs in background on GCP).")
            return "rebuilding_index"

        elif "Generating Embeddings" in content:
            # Extract progress
            lines = content.split('\n')
            progress_lines = [l for l in lines if 'Generating Embeddings' in l]
            if progress_lines:
                last_progress = progress_lines[-1]
                logger.info(f"\n⏳ Embeddings regeneration in progress:")
                logger.info(f"   {last_progress.split('Generating Embeddings')[1].strip()}")
            return "generating"

        else:
            logger.info("\n⏳ Process is running...")
            return "running"

    except FileNotFoundError:
        logger.info("\n⚠️  Background process output file not found")
        logger.info("   Process may have completed or been stopped.")
        return "unknown"
    except Exception as e:
        logger.error(f"\n❌ Error reading process output: {e}")
        return "error"


def test_current_flow():
    """Quick test to see if flow is working"""
    logger.info("\n" + "=" * 80)
    logger.info("4. QUICK FLOW TEST")
    logger.info("=" * 80)

    try:
        from api import dependencies

        search_engine = dependencies.get_search_engine()
        results = search_engine.search_by_text("cafea", num_neighbors=1)

        if not results:
            logger.error("\n❌ No search results")
            return "failed"

        first_id = results[0].get('id', '')
        product_name = results[0].get('product_name', 'N/A')
        product_id = results[0].get('product_id')
        variant_id = results[0].get('variant_id')

        logger.info(f"\nSearch result:")
        logger.info(f"  ID from index: {first_id}")
        logger.info(f"  Product name: {product_name}")
        logger.info(f"  Product ID: {product_id}")
        logger.info(f"  Variant ID: {variant_id}")

        is_numeric = str(first_id).isdigit()
        has_enrichment = product_id and variant_id

        if is_numeric and has_enrichment:
            logger.info("\n✅ Flow is working correctly!")
            logger.info("   - Index returns numeric product_id")
            logger.info("   - Feature Store enrichment successful")
            return "working"
        elif is_numeric:
            logger.info("\n⚠️  Index is fixed but Feature Store needs sync")
            logger.info("   - Index returns numeric product_id ✓")
            logger.info("   - Feature Store enrichment failed ✗")
            logger.info("\n   Next step: python features/sync_feature_store.py")
            return "needs_sync"
        else:
            logger.info("\n⏳ Still using old index")
            logger.info("   - Index returns product names (old format)")
            logger.info("   - Need to wait for index rebuild to complete")
            return "old_index"

    except Exception as e:
        logger.error(f"\n❌ Flow test failed: {e}")
        return "error"


def main():
    """Run all checks and provide summary"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 25 + "FIX PROGRESS MONITOR" + " " * 33 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Run checks
    embeddings_status = check_embeddings_file()
    index_status = check_index_status()
    process_status = check_background_process()
    flow_status = test_current_flow()

    # Overall summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    if flow_status == "working":
        logger.info("\n🎉 FIX COMPLETE! Flow is ready to use.")
        logger.info("\nNext steps:")
        logger.info("  1. Run comprehensive test: python test_feature_store_flow.py")
        logger.info("  2. Verify ranking integration works")
        logger.info("  3. Deploy to production")

    elif flow_status == "needs_sync":
        logger.info("\n⏳ Almost ready! Just need to sync Feature Store.")
        logger.info("\nNext steps:")
        logger.info("  1. Sync Feature Store: python features/sync_feature_store.py")
        logger.info("  2. Run test: python test_feature_store_flow.py")

    elif embeddings_status == "ready" and process_status == "rebuilding_index":
        logger.info("\n⏳ Index is rebuilding (45-90 minutes).")
        logger.info("\nWhat's happening:")
        logger.info("  - Embeddings: ✅ Complete with numeric IDs")
        logger.info("  - Index: ⏳ Rebuilding in background on GCP")
        logger.info("\nNext steps:")
        logger.info("  - Wait for index rebuild to complete")
        logger.info("  - Monitor: Check GCP Console or run this script again")

    elif process_status in ["generating", "running"]:
        logger.info("\n⏳ Embeddings are still being regenerated.")
        logger.info("\nWhat's happening:")
        logger.info("  - Background process is running")
        logger.info("  - May be hitting quota limits (normal)")
        logger.info("\nNext steps:")
        logger.info("  - Wait for regeneration to complete")
        logger.info("  - Monitor: Run this script periodically")

    else:
        logger.info("\n⏳ Fix is in progress.")
        logger.info("\nCurrent status:")
        logger.info(f"  - Embeddings: {embeddings_status}")
        logger.info(f"  - Index: {index_status}")
        logger.info(f"  - Process: {process_status}")
        logger.info(f"  - Flow: {flow_status}")

    logger.info("\n" + "=" * 80)
    logger.info("\nTo monitor continuously:")
    logger.info("  watch -n 60 python monitor_fix_progress.py")
    logger.info("\nTo check background process output:")
    logger.info("  tail -f /private/tmp/claude-501/-Users-radanpetrica-PFA-agents-agents-adk-mcp/tasks/b0f873f.output")
    logger.info("\n")


if __name__ == "__main__":
    main()
