
from google.cloud import aiplatform_v1
from google.cloud.aiplatform_v1.types import feature_online_store_service

try:
    key = feature_online_store_service.FeatureViewDataKey(key="test")
    req = feature_online_store_service.FetchFeatureValuesRequest(
        feature_view="test",
        data_key=key
    )
    print("SUCCESS: data_key argument is valid")
except Exception as e:
    print(f"FAILED: {e}")
