from google.cloud import aiplatform
from google.cloud.aiplatform_v1 import MatchServiceClient, FindNeighborsRequest, IndexDatapoint
import sys
import random
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

def debug_query():
    print("🐛 RAW DEBUG QUERY")
    print(f"Endpoint: {settings.VS_ENDPOINT_NAME}")
    
    # 1. Get Endpoint
    aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)
    endpoints = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{settings.VS_ENDPOINT_NAME}"'
    )
    if not endpoints:
        print("No endpoint found")
        return
    endpoint = endpoints[0]
    
    # 2. Setup Client
    public_domain = endpoint.public_endpoint_domain_name
    print(f"Domain: {public_domain}")
    
    client = MatchServiceClient(
        client_options={
            "api_endpoint": f"{public_domain}:443"
        }
    )
    
    # 3. Create Random Vector
    vector = [random.random() for _ in range(512)]
    
    # 4. Request
    request = FindNeighborsRequest(
        index_endpoint=endpoint.resource_name,
        deployed_index_id=settings.VS_DEPLOYED_INDEX_ID,
        queries=[FindNeighborsRequest.Query(
            datapoint=IndexDatapoint(feature_vector=vector),
            neighbor_count=5
        )],
        return_full_datapoint=False
    )
    
    try:
        response = client.find_neighbors(request)
        print(f"Response count: {len(response.nearest_neighbors)}")
        if response.nearest_neighbors:
            print("Found neighbors:")
            for n in response.nearest_neighbors[0].neighbors:
                print(f" - ID: {n.datapoint.datapoint_id}, Dist: {n.distance}")
        else:
            print("❌ ZERO RESULTS")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_query()
