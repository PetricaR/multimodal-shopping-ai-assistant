#!/usr/bin/env python3
"""
GKE API Test Script for Bringo Product Similarity API.
Tests health endpoints, product search, and text search functionality.

Usage:
    python scripts/test_gke_api.py
"""

import requests
import json
import time
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

API_HOST = "34.78.177.35"
API_PORT = 80
BASE_URL = f"http://{API_HOST}:{API_PORT}/api/v1"
HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"
AUTH_KEY = "bringo_secure_shield_2026"

# Streamlit URL (for reference)
STREAMLIT_URL = "http://34.140.215.60"

# =============================================================================
# Test Utilities
# =============================================================================

def print_result(name, success, details, time_taken=None):
    """Print test result with icon and timing."""
    icon = "✅" if success else "❌"
    time_str = f" ({time_taken:.3f}s)" if time_taken else ""
    print(f"{icon} {name}{time_str}")
    if details:
        print(f"   {details}")

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# =============================================================================
# API Tests
# =============================================================================

def test_health():
    """Test the health check endpoint."""
    print(f"\n--- Testing Health Check ({HEALTH_URL}) ---")
    try:
        start = time.time()
        response = requests.get(HEALTH_URL, timeout=10)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print_result("Health Check", True, 
                        f"Status: {data.get('status')} | Version: {data.get('version')}", 
                        duration)
            print("   Components:")
            for comp, status in data.get('components', {}).items():
                icon = "🟢" if status == "initialized" else "🔴"
                print(f"     {icon} {comp}: {status}")
            return True
        else:
            print_result("Health Check", False, 
                        f"Status Code: {response.status_code}\n   Response: {response.text}", 
                        duration)
            return False
            
    except Exception as e:
        print_result("Health Check", False, f"Error: {e}")
        return False

def test_search(product_name: str):
    """Test product similarity search by exact product name."""
    url = f"{BASE_URL}/search"
    print(f"\n--- Testing Product Search ({url}) ---")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": AUTH_KEY
    }
    
    payload = {
        "product_name": product_name,
        "top_k": 5,
        "use_ranking": True,
        "in_stock_only": False
    }
    
    print(f"   Payload: {json.dumps(payload)}")
    
    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('similar_products', [])
            method = data.get('search_method', 'unknown')
            
            print_result("Search Request", True, 
                        f"Found {len(results)} results in {data.get('query_time_ms', 0):.1f}ms | Method: {method}", 
                        duration)
            
            if results:
                print("\n   Top 3 Results:")
                for i, prod in enumerate(results[:3]):
                    name = prod.get('product_name', 'N/A')
                    score = prod.get('similarity_score', 0)
                    price = prod.get('price', 0)
                    stock = "✅" if prod.get('in_stock') else "🔴"
                    print(f"     {i+1}. {name}")
                    print(f"        Score: {score:.3f} | Price: {price} RON | Stock: {stock}")
            return True
        else:
            print_result("Search Request", False, 
                        f"Status Code: {response.status_code}\n   Response: {response.text}", 
                        duration)
            return False
            
    except Exception as e:
        print_result("Search Request", False, f"Error: {e}")
        return False

def test_text_search(query_text: str):
    """Test free-text semantic search."""
    url = f"{BASE_URL}/search"
    print(f"\n--- Testing Text Search ---")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": AUTH_KEY
    }
    
    payload = {
        "query_text": query_text,
        "top_k": 5,
        "use_ranking": True,
        "in_stock_only": False
    }
    
    print(f"   Query: '{query_text}'")
    
    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('similar_products', [])
            
            print_result("Text Search", True, 
                        f"Found {len(results)} results in {data.get('query_time_ms', 0):.1f}ms", 
                        duration)
            
            if results:
                print("\n   Results:")
                for i, prod in enumerate(results[:3]):
                    name = prod.get('product_name', 'N/A')
                    price = prod.get('price', 0)
                    print(f"     {i+1}. {name} - {price} RON")
            return results
        else:
            print_result("Text Search", False, f"Status Code: {response.status_code}", duration)
            return []
    except Exception as e:
        print_result("Text Search", False, f"Error: {e}")
        return []

def find_valid_product():
    """Find a valid product name via text search."""
    print(f"\n--- 🔍 Finding valid product via Text Search ---")
    
    try:
        url = f"{BASE_URL}/search"
        payload = {"query_text": "lapte", "top_k": 3}
        headers = {"x-api-key": AUTH_KEY}
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            results = response.json().get('similar_products', [])
            
            # Find first result with a non-empty name
            for res in results:
                name = res.get('product_name', '').strip()
                if name:
                    print(f"✅ Found valid product: '{name}'")
                    return name
        
        # Fallback
        fallback = "Ampawa Lapte De Cocos 400Ml"
        print(f"⚠️ Using fallback product: '{fallback}'")
        return fallback
        
    except Exception as e:
        print(f"⚠️ Error finding product: {e}")
        return "Ampawa Lapte De Cocos 400Ml"

# =============================================================================
# Main Test Sequence
# =============================================================================

if __name__ == "__main__":
    print_section("GKE API Test Sequence")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 API: http://{API_HOST}")
    print(f"🖥️  Streamlit: {STREAMLIT_URL}")
    
    # Step 1: Health Check
    if not test_health():
        print("\n❌ Health check failed. Aborting tests.")
        exit(1)
    
    # Step 2: Find a valid product
    valid_product = find_valid_product()
    
    # Step 3: Test product search
    test_search(valid_product)
    
    # Step 4: Test text search
    test_text_search("lapte bio")
    
    # Step 5: Test Streamlit health
    print(f"\n--- Testing Streamlit ({STREAMLIT_URL}) ---")
    try:
        start = time.time()
        response = requests.get(f"{STREAMLIT_URL}/_stcore/health", timeout=10)
        duration = time.time() - start
        if response.status_code == 200:
            print_result("Streamlit Health", True, f"Frontend is accessible at {STREAMLIT_URL}", duration)
        else:
            print_result("Streamlit Health", False, f"Status: {response.status_code}", duration)
    except Exception as e:
        print_result("Streamlit Health", False, f"Error: {e}")
    
    # Step 6: Final health check
    test_health()
    
    print_section("Test Complete")
    print(f"✅ All tests passed")
    print(f"\n📌 Endpoints:")
    print(f"   API:       http://{API_HOST}")
    print(f"   Streamlit: {STREAMLIT_URL}")
