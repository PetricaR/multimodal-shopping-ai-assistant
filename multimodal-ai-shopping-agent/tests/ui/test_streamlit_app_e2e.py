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
from substitution.test_data import get_generic_baskets, get_user_profiles

# Configuration (Mirrors Streamlit App)
API_URL = "http://34.78.177.35/api/v1"
API_AUTH_KEY = "bringo_secure_shield_2026"
HEADERS = {"X-API-KEY": API_AUTH_KEY, "Content-Type": "application/json"}

def print_banner(title):
    print("\n" + "="*80)
    print(f"🚀 {title}")
    print("="*80)

def get_kubernetes_logs(lines=10):
    """Fetch the latest logs from the GKE backend pod"""
    print(f"\n☁️  [K8S LOGS] Fetching latest {lines} lines from GKE...")
    try:
        # Find the pod name first
        cmd_find = "kubectl get pods -l app=bringo-multimodal-api -n default -o jsonpath='{.items[0].metadata.name}'"
        pod_name = subprocess.check_output(cmd_find, shell=True, text=True).strip()
        
        if not pod_name:
            print("⚠️  No GKE pods found for app=bringo-multimodal-api")
            return
            
        # Get logs
        cmd_logs = f"kubectl logs {pod_name} -n default --tail={lines}"
        logs = subprocess.check_output(cmd_logs, shell=True, text=True)
        
        print("-" * 40)
        print(logs)
        print("-" * 40)
    except Exception as e:
        print(f"⚠️  Failed to fetch K8S logs: {e}")

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
            get_kubernetes_logs(5)
            return True
        else:
            print(f"❌ Error: Received status code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return False

def test_data_loading():
    print_banner("STAGE 2: Data Loading (BigQuery)")
    try:
        bq = BigQueryClient()
        print("Fetching top 100 products for testing...")
        df = bq.fetch_products(limit=100)
        if not df.empty:
            print(f"✅ Loaded {len(df)} products successfully.")
            return df
        else:
            print("❌ No products found in BigQuery.")
            return None
    except Exception as e:
        print(f"❌ BigQuery Error: {e}")
        return None

def test_search_flow(test_product):
    print_banner(f"STAGE 3: Similarity Search Flow")
    pid = test_product['product_id']
    name = test_product['product_name']
    
    print(f"Targeting: {name} (ID: {pid})")
    
    endpoint = f"{API_URL}/product/{pid}/similar"
    params = {"top_k": 5, "use_ranking": True, "in_stock_only": False}
    
    try:
        print(f"📡 Request: GET {endpoint}")
        start_time = time.time()
        response = requests.get(endpoint, params=params, headers=HEADERS)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('similar_products', [])
            print(f"✅ Received {len(results)} matches in {latency:.0f}ms")
            
            for i, prod in enumerate(results, 1):
                img = prod.get('image_url', 'N/A')
                is_absolute = img.startswith('http') if img != 'N/A' else True
                img_status = "✅ Absolute" if is_absolute else "❌ Relative (Error!)"
                
                print(f"   {i}. [{prod['product_id']}] {prod['product_name'][:40]}...")
                print(f"      💰 Price: {prod.get('price')} RON | Score: {prod.get('ranking_score', 0):.4f}")
                print(f"      📸 Image: {img[:50]}... ({img_status})")
            
            get_kubernetes_logs(15)
            return True
        else:
            print(f"❌ API Search Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Search flow exception: {e}")
        return False

def test_substitution_flow(test_product):
    print_banner(f"STAGE 4: Intelligent Substitution (Gemini)")
    pid = test_product['product_id']
    
    # Setup context
    profiles = get_user_profiles()
    baskets = get_generic_baskets()
    
    # Pick a sample context
    profile_key = list(profiles.keys())[0] # Usually 'fan_bio'
    basket_key = 'cina_italiana'
    
    print(f"Context: Profile '{profile_key}' | Basket '{basket_key}'")
    
    payload = {
        "missing_product_id": str(pid),
        "current_basket": baskets[basket_key],
        "user_history": profiles[profile_key]["history"]
    }
    
    endpoint = f"{API_URL}/substitution/suggest"
    
    try:
        print(f"📡 Request: POST {endpoint}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        print("Waiting for Gemini reasoning...")
        start_time = time.time()
        response = requests.post(endpoint, json=payload, headers=HEADERS)
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            subs = data.get('suggestions', [])
            print(f"✅ Gemini completed in {latency:.0f}ms. Got {len(subs)} suggestions.")
            
            for i, prod in enumerate(subs, 1):
                print(f"\n--- Suggestion #{i} ---")
                print(f"Product: {prod['product_name']}")
                print(f"Confidence: {prod.get('gemini_confidence', 0)*100:.0f}%")
                print(f"Reasoning: {prod.get('substitution_reason', 'N/A')}")
                diff = prod.get('price_difference', 0)
                print(f"Price Diff: {'+' if diff > 0 else ''}{diff:.2f} RON")
            
            get_kubernetes_logs(20)
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
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not test_connectivity():
        print("\n❌ ABORTING: Cannot reach backend.")
        return

    products_df = test_data_loading()
    if products_df is None or products_df.empty:
        return

    # Select specific product to test with as requested by user
    print(f"\n🎯 Target Test Product: Dr.Oetker Gelatina Foi 10g (ID: 499385)")
    sample_product = {
        'product_id': '499385',
        'product_name': 'Dr.Oetker Gelatina Foi 10g',
        'category': 'Zahar si ingrediente patiserie',
        'price': 7.93
    }
    
    search_ok = test_search_flow(sample_product)
    sub_ok = test_substitution_flow(sample_product)
    
    print_banner("TEST SUMMARY")
    print(f"Connectivity:   ✅")
    print(f"Data Loading:   ✅")
    print(f"Search Flow:    {'✅ PASS' if search_ok else '❌ FAIL'}")
    print(f"Substitution:   {'✅ PASS' if sub_ok else '❌ FAIL'}")
    print("="*80)

if __name__ == "__main__":
    run_all_tests()
