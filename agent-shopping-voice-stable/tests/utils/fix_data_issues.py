#!/usr/bin/env python3
"""
Fix Feature Store Data Issues
1. Creates a deduplicated BigQuery View (unique product_name)
2. Updates Feature View to use this new source
3. Triggers Sync
"""

from google.cloud import bigquery
from google.cloud import aiplatform_v1
from google.api_core import operations_v1
import logging
import sys
import time

from config.settings import settings

# Configuration
PROJECT_ID = settings.PROJECT_ID
REGION = settings.LOCATION
DATASET = settings.BQ_DATASET
SOURCE_TABLE = settings.BQ_TABLE
NEW_VIEW = "bringo_products_unique_ids_view"

FEATURE_STORE_ID = "bringo_realtime_features"
FEATURE_VIEW_ID = settings.FS_METADATA_VIEW

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_deduplicated_view():
    """Create a BigQuery View that ensures product_id uniqueness"""
    client = bigquery.Client(project=PROJECT_ID)
    
    view_id = f"{PROJECT_ID}.{DATASET}.{NEW_VIEW}"
    source_id = f"{PROJECT_ID}.{DATASET}.{SOURCE_TABLE}"
    
    logger.info(f"Creating/Updating View: {view_id}")
    
    # Logic: Partition by product_id, take the latest one
    query = f"""
    CREATE OR REPLACE VIEW `{view_id}` AS
    SELECT * EXCEPT(row_num)
    FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY product_id ORDER BY product_id DESC) as row_num
        FROM `{source_id}`
        WHERE product_id IS NOT NULL
    )
    WHERE row_num = 1
    """
    
    try:
        job = client.query(query)
        job.result()  # Wait for completion
        logger.info(f"✅ Deduplicated View created successfully!")
        return view_id
    except Exception as e:
        logger.error(f"❌ Failed to create view: {e}")
        sys.exit(1)

def update_feature_view_source():
    """Update Feature View to point to the new unique view"""
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )
    
    feature_view_name = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_STORE_ID}/"
        f"featureViews/{FEATURE_VIEW_ID}"
    )
    
    logger.info(f"Updating Feature View Source: {feature_view_name}")
    
    # New source URI
    new_bq_uri = f"bq://{PROJECT_ID}.{DATASET}.{NEW_VIEW}"
    
    try:
        # Construct update request
        feature_view = aiplatform_v1.FeatureView(
            name=feature_view_name,
            big_query_source=aiplatform_v1.FeatureView.BigQuerySource(
                uri=new_bq_uri,
                entity_id_columns=["product_id"]
            )
        )
        
        # We only want to update the big_query_source field
        update_mask = {"paths": ["big_query_source.uri"]}
        
        operation = client.update_feature_view(
            feature_view=feature_view,
            update_mask=update_mask
        )
        
        logger.info("Update operation started. Waiting for completion...")
        response = operation.result()
        logger.info("✅ Feature View source updated!")
        return response
        
    except Exception as e:
        logger.error(f"❌ Failed to update Feature View: {e}")
        sys.exit(1)

def trigger_sync():
    """Trigger sync on the updated view"""
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )
    
    feature_view_name = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_STORE_ID}/"
        f"featureViews/{FEATURE_VIEW_ID}"
    )
    
    logger.info("Triggering new sync...")
    try:
        response = client.sync_feature_view(feature_view=feature_view_name)
        logger.info("✅ Sync initiated successfully!")
        logger.info(f"   Resource: {response.feature_view_sync}")
        
    except Exception as e:
        # Ignore "sync already running" errors if it picked up immediately
        if "400" in str(e) and "running" in str(e):
             logger.info("⚠️  Sync already running (likely auto-triggered by update).")
        else:
            logger.error(f"❌ Sync trigger failed: {e}")

def main():
    logger.info("=== FIXING FEATURE STORE DATA ISSUES ===")
    
    # 1. Create View
    create_deduplicated_view()
    
    # 2. Update Feature Store Source
    update_feature_view_source()
    
    # 3. Trigger Sync
    trigger_sync()
    
    logger.info("\n✅ All fixes applied. Please check GCP Console for sync progress.")

if __name__ == "__main__":
    main()
