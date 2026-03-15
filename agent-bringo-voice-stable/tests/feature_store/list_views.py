
from google.cloud import aiplatform_v1
import logging
import os
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_views():
    PROJECT_ID = "formare-ai"
    REGION = "europe-west1"
    STORE_ID = "bringo_realtime_features"
    
    api_endpoint = f"{REGION}-aiplatform.googleapis.com"
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": api_endpoint}
    )
    
    parent = f"projects/{PROJECT_ID}/locations/{REGION}/featureOnlineStores/{STORE_ID}"
    
    logger.info(f"Listing views for {parent}...")
    try:
        views = client.list_feature_views(parent=parent)
        for view in views:
            print(f"VIEW: {view.name}")
            # print(f"  Source: {view.big_query_source}")
            # print(f"  Entity IDs: {view.big_query_source.entity_id_columns}")
    except Exception as e:
        logger.error(f"Failed to list views: {e}")

if __name__ == "__main__":
    list_views()
