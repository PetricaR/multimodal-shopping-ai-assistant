import sys
from pathlib import Path
import logging
from google.cloud import aiplatform_v1
from google.cloud.aiplatform_v1.types import feature_online_store_service
from google.api_core import client_options

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_feature_store():
    print("🔍 TESTING FEATURE STORE CONNECTION")
    print("-" * 50)
    
    project = settings.PROJECT_ID
    location = settings.LOCATION
    feature_view_resource = f"projects/{project}/locations/{location}/featureOnlineStores/bringo_realtime_features/featureViews/product_metadata_names"
    
    print(f"Target Resource: {feature_view_resource}")
    
    # 1. Initialize Client
    api_endpoint = settings.FS_PUBLIC_ENDPOINT or f"{location}-aiplatform.googleapis.com"
    client = aiplatform_v1.FeatureOnlineStoreServiceClient(
        client_options=client_options.ClientOptions(api_endpoint=api_endpoint)
    )
    
    product_id = "Lapte Zuzu 3.5% 1L"
    print(f"\n1. Fetching Metadata for ID: '{product_id}'...")
    
    try:
        data_key = feature_online_store_service.FeatureViewDataKey(key=str(product_id))
        request = feature_online_store_service.FetchFeatureValuesRequest(
            feature_view=feature_view_resource,
            data_key=data_key
        )
        
        response = client.fetch_feature_values(request=request)
        
        print("\n✅ RESPONSE RECEIVED:")
        # Dump response
        print(response)
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        # Detect if 404
        if "404" in str(e) or "Not Found" in str(e):
            print("\n🚨 DIAGNOSIS: The Feature View does not exist. You likely need to run 'create_feature_store.py'.")

if __name__ == "__main__":
    test_feature_store()
