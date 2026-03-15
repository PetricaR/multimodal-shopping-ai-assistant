
from google.cloud import aiplatform_v1
from google.api_core import client_options
from config.settings import settings

def inspect_store():
    # Correct Endpoint for Admin operations is regional aiplatform
    api_endpoint = f"{settings.LOCATION}-aiplatform.googleapis.com"
    
    # Use Admin Client for Get/List operations
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options=client_options.ClientOptions(api_endpoint=api_endpoint)
    )
    
    name = f"projects/{settings.PROJECT_ID}/locations/{settings.LOCATION}/featureOnlineStores/bringo_realtime_features"
    
    print(f"🔍 Inspecting Store: {name}")
    try:
        store = client.get_feature_online_store(name=name)
        print("\n✅ Store Details:")
        print(f"   Name: {store.name}")
        print(f"   State: {store.state}")
        
        print("\n🌐 Connectivity:")
        # Check dedicated serving endpoint
        if store.dedicated_serving_endpoint:
             print(f"   Dedicated Endpoint (Public): {store.dedicated_serving_endpoint.public_endpoint_domain_name}")
             print(f"   Private Service Connect: {store.dedicated_serving_endpoint.service_attachment}")
             
             if not store.dedicated_serving_endpoint.public_endpoint_domain_name:
                 print("\n⚠️  WARNING: Public Endpoint is EMPTY. Access might be restricted to VPC.")
        else:
             print("   No Dedicated Endpoint info found (might be Bigtable serving or legacy).")
             
    except Exception as e:
        print(f"❌ Error getting store info: {e}")

if __name__ == "__main__":
    inspect_store()
