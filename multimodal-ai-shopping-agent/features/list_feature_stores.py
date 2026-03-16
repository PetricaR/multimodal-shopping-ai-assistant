#!/usr/bin/env python3
"""
List Existing Feature Online Stores
Uses FeatureOnlineStoreAdminServiceClient
"""

from google.cloud import aiplatform_v1
import logging
import sys

# Configuration
PROJECT_ID = "formare-ai"
REGION = "europe-west1"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_stores():
    """List all Feature Online Stores in the region"""
    
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    
    logger.info(f"Connecting to Admin Service ({api_endpoint})...")
    
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )
    
    logger.info(f"Listing stores in: {parent}")
    
    try:
        stores = client.list_feature_online_stores(parent=parent)
        
        count = 0
        for store in stores:
            count += 1
            logger.info(f"✅ Found Store: {store.name}")
            logger.info(f"   State: {store.state}")
            
            # List views in this store
            logger.info(f"   Listing views...")
            views = client.list_feature_views(parent=store.name)
            for view in views:
                logger.info(f"      - View: {view.name}")
            
        if count == 0:
            logger.info("❌ No Feature Online Stores found.")
            
    except Exception as e:
        logger.error(f"❌ Failed to list stores: {e}")
        sys.exit(1)

if __name__ == "__main__":
    list_stores()
