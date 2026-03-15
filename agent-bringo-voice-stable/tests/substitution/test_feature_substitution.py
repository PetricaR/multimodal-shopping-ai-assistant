import sys
import os
import requests
import time
import json
from pathlib import Path

# Add project root and app root to sys.path
current_file = Path(__file__).resolve()
base_dir = current_file.parent.parent 

if str(base_dir) not in sys.path:
    sys.path.append(str(base_dir))

from config.settings import settings

def test_feature_store_substitution():
    """
    Test the unified substitution flow via search endpoint
    """
    print("\n" + "="*60)
    print("🚀 TEST: FEATURE STORE SUBSTITUTION via UNIFIED ENDPOINT")
    print("="*60)
    
    API_URL = "http://localhost:8080/api/v1/search"
    AUTH_KEY = "bringo_secure_shield_2026"
    
    # Product: Dr.Oetker Gelatina Foi 10g (Sample)
    product_name = "Dr.Oetker Gelatina Foi 10g"
    
    payload = {
        "product_name": product_name,
        "top_k": 5,
        "in_stock_only": True,  # Enables substitution logic
        "use_ranking": True
    }
    
    headers = {
        "X-API-KEY": AUTH_KEY,
        "Content-Type": "application/json"
    }

    print(f"\n1️⃣  Calling Unified Search API: {API_URL}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_call = time.time()
        response = requests.post(API_URL, json=payload, headers=headers)
        call_duration = (time.time() - start_call) * 1000
        
        if response.status_code == 200:
            data = response.json()
            suggestions = data.get('similar_products', [])
            
            print(f"✅ Success! Received {len(suggestions)} suggestions")
            print(f"   ⏱️  Total Test Latency: {call_duration:.1f}ms")
            print(f"   ⏱️  API Internal Time: {data.get('query_time_ms', 0):.1f}ms")
            print(f"   Method: {data.get('search_method')}")
            
            print("\n✨ TOP RECOMMENDED SUBSTITUTES:")
            print("-" * 60)
            for i, prod in enumerate(suggestions, 1):
                print(f"{i}. {prod['product_name']}")
                print(f"   ID: {prod.get('product_id')} | Price: {prod.get('price')} RON")
                if prod.get('price_difference') is not None:
                    print(f"   Price Diff: {prod['price_difference']:.2f} RON")
                print("-" * 30)
        else:
            print(f"❌ API Error ({response.status_code}):")
            print(f"   {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Failed! is the API running?")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    test_feature_store_substitution()
