
from google.cloud import aiplatform_v1
from google.cloud.aiplatform_v1.types import feature_online_store_service

print(dir(feature_online_store_service.FetchFeatureValuesRequest))
print("\n__init__ annotations:")
try:
    print(feature_online_store_service.FetchFeatureValuesRequest.__init__.__annotations__)
except:
    pass
