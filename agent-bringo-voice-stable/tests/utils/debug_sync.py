
from google.cloud import bigquery
import logging
import sys
import os

# Add the project root to sys.path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
    # Also add the app dir to allow 'features', 'config' imports
    app_dir = os.path.dirname(current_dir)
    if app_dir not in sys.path:
        sys.path.append(app_dir)

from features.realtime_server import RealTimeFeatureServer
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_data")

def check_sync_status():
    """
    1. Get sample IDs from BigQuery Native Table (Source)
    2. Try to fetch them from Feature Store (Destination)
    3. Report sync status
    """
    print(f"\n🔍 DEBUGGING FEATURE STORE DATA SYNC")
    print(f"===================================")
    
    # 1. Query BigQuery
    bq_client = bigquery.Client(project=settings.PROJECT_ID)
    table_id = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.{settings.BQ_TABLE}"
    
    print(f"\n1️⃣  Checking Source: BigQuery Table ({table_id})")
    try:
        query = f"SELECT product_id FROM `{table_id}` LIMIT 5"
        query_job = bq_client.query(query)
        bq_ids = [str(row.product_id) for row in query_job]
        
        if not bq_ids:
            print("   ❌ Source table is EMPTY! Run the creation SQL query first.")
            return
            
        print(f"   ✓ Found {len(bq_ids)} sample IDs in BigQuery: {bq_ids}")
        
    except Exception as e:
        print(f"   ❌ BigQuery Error: {e}")
        return

    # 2. Check Feature Store
    print(f"\n2️⃣  Checking Destination: Feature Store View (product_metadata_names)")
    fs_server = RealTimeFeatureServer()
    
    found_count = 0
    for pid in bq_ids:
        print(f"   ➤ Inspecting {pid}...")
        try:
            # Use private method to see raw response
            response = fs_server._fetch_single_product(pid, fs_server.metadata_view)
            
            if response is None:
                print(f"      ❌ Product NOT FOUND in Feature Store")
                continue

            # Print Raw Response for debugging structure
            print(f"      ✓ Raw response received")
            
            # Try to parse securely
            # key_values.features is the list
            try:
                if hasattr(response, 'key_values') and response.key_values:
                    features_list = response.key_values.features
                    if features_list:
                        print(f"      ✓ Features found: {[f.name for f in features_list]}") 
                        found_count += 1
                    else:
                        print(f"      ❌ Empty Features List")
                else:
                    print(f"      ❌ Invalid response structure (missing key_values)")
            except Exception as e:
                print(f"      ❌ Parsing Error: {e}")
                    
        except Exception as e:
            print(f"      ❌ Exception during fetch: {e}")
            
    print(f"\n📊 Summary")
    print(f"   - Source IDs: {len(bq_ids)}")
    print(f"   - Synced IDs: {found_count}")
    
    if found_count == 0:
        print("\n⚠️  ACTION REQUIRED: Feature View is empty.")
        print("   -> Go to Cloud Console > Vertex AI > Feature Store")
        print("   -> Select 'product_metadata_view' and click 'SYNC NOW'")
    elif found_count < len(bq_ids):
        print("\n⚠️  Sync is partial or in progress.")
    else:
        print("\n✅ Sync is COMPLETE! Endpoints should work.")

if __name__ == "__main__":
    check_sync_status()
