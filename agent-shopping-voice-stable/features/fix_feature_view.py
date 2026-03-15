#!/usr/bin/env python3
"""
Fix Feature View: Delete and recreate bringo_feature_store
pointing to the correct BigQuery table (bringo_products_native).
"""
import os
import sys
import logging
from dotenv import load_dotenv
from google.cloud import aiplatform_v1
from google.api_core import client_options

load_dotenv()

PROJECT_ID = "formare-ai"
REGION = "europe-west1"
FEATURE_ONLINE_STORE_ID = "bringo_realtime_features"
FEATURE_VIEW_ID = "bringo_product_metadata"
BQ_SOURCE_URI = "bq://formare-ai.bringo_products_data.bringo_products_native"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_admin_client():
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    return aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options=client_options.ClientOptions(api_endpoint=api_endpoint)
    )


def delete_feature_view():
    """Delete the existing feature view."""
    client = get_admin_client()
    feature_view_name = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_ONLINE_STORE_ID}/"
        f"featureViews/{FEATURE_VIEW_ID}"
    )

    logger.info(f"Deleting Feature View: {FEATURE_VIEW_ID}")
    try:
        operation = client.delete_feature_view(name=feature_view_name)
        logger.info("Waiting for deletion to complete...")
        operation.result()
        logger.info(f"✅ Deleted Feature View: {FEATURE_VIEW_ID}")
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            logger.info(f"Feature View {FEATURE_VIEW_ID} does not exist, skipping delete")
        else:
            raise


def create_feature_view():
    """Create the feature view pointing to the correct BigQuery table."""
    client = get_admin_client()
    parent = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_ONLINE_STORE_ID}"
    )

    logger.info(f"Creating Feature View: {FEATURE_VIEW_ID}")
    logger.info(f"  Source: {BQ_SOURCE_URI}")

    feature_view = aiplatform_v1.FeatureView(
        big_query_source=aiplatform_v1.FeatureView.BigQuerySource(
            uri=BQ_SOURCE_URI,
            entity_id_columns=["product_id"],
        ),
        sync_config=aiplatform_v1.FeatureView.SyncConfig(
            cron="0 * * * *"  # Hourly
        ),
    )

    operation = client.create_feature_view(
        parent=parent,
        feature_view=feature_view,
        feature_view_id=FEATURE_VIEW_ID,
    )

    logger.info("Waiting for creation to complete...")
    result = operation.result()
    logger.info(f"✅ Created Feature View: {result.name}")
    logger.info(f"   Source: {BQ_SOURCE_URI}")
    logger.info(f"   Entity ID column: product_id")
    logger.info(f"   Sync: Hourly")
    return result


def trigger_sync():
    """Trigger an immediate sync after creation."""
    client = get_admin_client()
    feature_view_name = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_ONLINE_STORE_ID}/"
        f"featureViews/{FEATURE_VIEW_ID}"
    )

    logger.info("Triggering initial sync...")
    operation = client.sync_feature_view(request={"feature_view": feature_view_name})
    op_name = getattr(operation, "operation", None) or getattr(operation, "name", None)
    logger.info(f"✅ Sync initiated: {op_name}")
    logger.info("   Sync runs in the background. Wait a few minutes, then re-run tests.")


def main():
    logger.info("=" * 80)
    logger.info("FIX FEATURE VIEW — Point to bringo_products_native")
    logger.info("=" * 80)

    logger.info("\nStep 1: Delete old Feature View")
    delete_feature_view()

    logger.info("\nStep 2: Create new Feature View")
    create_feature_view()

    logger.info("\nStep 3: Trigger initial sync")
    trigger_sync()

    logger.info("\n" + "=" * 80)
    logger.info("✅ DONE. Wait a few minutes for sync to complete, then run:")
    logger.info("   python tests/test_feature_store.py")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
