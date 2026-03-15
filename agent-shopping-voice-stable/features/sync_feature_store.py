#!/usr/bin/env python3
"""
Trigger Feature View Sync
Uses FeatureOnlineStoreAdminServiceClient for reliable sync triggering
"""

import os
import logging
import sys
from dotenv import load_dotenv
from google.cloud import aiplatform_v1

# Load .env if present
load_dotenv()

# Configuration (can be overridden via environment variables)
PROJECT_ID = os.getenv("PROJECT_ID", "formare-ai")
REGION = os.getenv("REGION", "europe-west1")
FEATURE_ONLINE_STORE_ID = os.getenv("FEATURE_ONLINE_STORE_ID", "bringo_realtime_features")
FEATURE_VIEW_ID = os.getenv("FEATURE_VIEW_ID", "bringo_product_metadata")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def trigger_sync():
    """Trigger sync using the Low-level Admin Service Client"""
    
    # Endpoint format: region-aiplatform.googleapis.com
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    
    logger.info(f"Connecting to Vertex AI Admin Service ({api_endpoint})...")
    
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )
    
    # Construct resource name
    feature_view_name = (
        f"projects/{PROJECT_ID}/locations/{REGION}/"
        f"featureOnlineStores/{FEATURE_ONLINE_STORE_ID}/"
        f"featureViews/{FEATURE_VIEW_ID}"
    )
    
    logger.info(f"Targeting Feature View: {FEATURE_VIEW_ID}")
    logger.info(f"Resource Name: {feature_view_name}")
    
    try:
        # Trigger Sync
        logger.info("Initiating Sync...")

        # The SDK expects 'feature_view' not 'name' for this request
        operation = client.sync_feature_view(request={"feature_view": feature_view_name})

        # The call returns a long-running operation. Log operation details (name, metadata) and do not block.
        op_name = getattr(operation, "operation", None) or getattr(operation, "name", None) or getattr(operation, "_operation", None)
        if op_name:
            logger.info(f"✅ Sync initiated successfully. Operation: {op_name}")
        else:
            # Fallback: print the operation repr
            logger.info(f"✅ Sync initiated successfully. Operation repr: {operation}")

        # If metadata is available, show a short summary
        try:
            metadata = getattr(operation, "metadata", None)
            if metadata:
                logger.info(f"   Operation metadata: {metadata}")
        except Exception:
            pass

        logger.info("   The sync is running in the background. Use the operation name to track progress if needed.")

    except Exception as e:
        logger.error(f"❌ Failed to trigger sync: {e}")
        sys.exit(1)

if __name__ == "__main__":
    trigger_sync()
