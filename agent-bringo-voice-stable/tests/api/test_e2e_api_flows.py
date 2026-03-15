import requests
import sys
import os
import time
import pandas as pd
import subprocess
import json
from pathlib import Path

# Add parent directory to path to reach project modules
current_file = Path(__file__).resolve()
base_dir = current_file.parent.parent
if str(base_dir) not in sys.path:
    sys.path.append(str(base_dir))

from data.bigquery_client import BigQueryClient

# Configuration
API_URL = "http://localhost:8080/api/v1"  # Default to local for dev
API_AUTH_KEY = "bringo_secure_shield_2026"
HEADERS = {"X-API-KEY": API_AUTH_KEY, "Content-Type": "application/json"}

def print_banner(title):
    print("\n" + "="*80)
    print(f"🚀 {title}")
    print("="*80)

def test_connectivity():
    print_banner("STAGE 1: Connectivity & Health check")
    health_url = API_URL.replace("/api/v1", "/health")
    print(f"Pinging: {health_url}")
    
    try:
        response = requests.get(health_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Backend status: {data.get('status')}")
            print(f"📊 Components: {data.get('components')}")
            return True
        else:
            print(f"❌ Error: Received status code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

def test_search_flow(product_name):
    print_banner(f"STAGE 2: Similarity Search Flow")
    print(f"Targeting: {product_name}")
    
    endpoint = f"{API_URL}/search"
    payload = {
        "product_name": product_name,
        "top_k": 5, 
        "use_ranking": True, 
        "in_stock_only": False
    }
    
    try:
        print(f"📡 Request: POST {endpoint}")
        start_time = time.time()
        response = requests.post(endpoint, json=payload, headers=HEADERS)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('similar_products', [])
            print(f"✅ Received {len(results)} matches in {latency:.0f}ms")
            print(f"   Method: {data.get('search_method')}")
            
            for i, prod in enumerate(results, 1):
                img = prod.get('image_url', 'N/A')
                print(f"   {i}. [{prod.get('product_id')}] {prod['product_name'][:40]}...")
                print(f"      💰 Price: {prod.get('price')} RON | Score: {prod.get('ranking_score', 0):.4f}")
            return True
        else:
            print(f"❌ API Search Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Search flow exception: {e}")
        return False

def test_substitution_flow(product_name):
    print_banner(f"STAGE 3: Intelligent Substitution")
    print(f"Targeting Missing Product: {product_name}")
    
    endpoint = f"{API_URL}/search" # Use unified search endpoint
    
    # Use search endpoint with substitution parameters
    payload = {
        "product_name": product_name,
        "top_k": 5,
        "in_stock_only": True,  # Critical for substitution
        "use_ranking": True
    }
    
    try:
        print(f"📡 Request: POST {endpoint}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        start_time = time.time()
        response = requests.post(endpoint, json=payload, headers=HEADERS)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            subs = data.get('similar_products', [])
            print(f"✅ Completed in {latency:.0f}ms. Got {len(subs)} in-stock suggestions.")
            
            for i, prod in enumerate(subs, 1):
                print(f"\n--- Suggestion #{i} ---")
                print(f"Product: {prod['product_name']}")
                print(f"In Stock: {prod.get('in_stock')}")
                if prod.get('price_difference') is not None:
                    diff = prod['price_difference']
                    print(f"Price Diff: {'+' if diff > 0 else ''}{diff:.2f} RON")
            return True
        else:
            print(f"❌ Substitution Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Substitution flow exception: {e}")
        return False

def run_all_tests():
    print_banner("STARTING E2E INTEGRATION TEST SUITE")
    print(f"Endpoints: {API_URL}")
    
    if not test_connectivity():
        print("\n❌ ABORTING: Cannot reach backend.")
        return

    # Check if API is running locally or we need simple test logic
    # Just run search flow check
    
    test_prod = "Lapte Zuzu 3.5% 1L"
    search_ok = test_search_flow(test_prod)
    sub_ok = test_substitution_flow(test_prod)
    
    print_banner("TEST SUMMARY")
    print(f"Connectivity:   ✅")
    print(f"Search Flow:    {'✅ PASS' if search_ok else '❌ FAIL'}")
    print(f"Substitution:   {'✅ PASS' if sub_ok else '❌ FAIL'}")
    print("="*80)

if __name__ == "__main__":
    run_all_tests()
