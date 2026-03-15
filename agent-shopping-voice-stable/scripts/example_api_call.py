#!/usr/bin/env python3
"""
Simple example script for calling the Bringo Similarity Search API.

Usage:
    python scripts/example_api_call.py
"""

import requests
import json

# =============================================================================
# Configuration
# =============================================================================

# Choose your API endpoint
API_URL = "http://34.78.177.35/api/v1"  # Cloud (GKE)
# API_URL = "http://localhost:8080/api/v1"  # Local development

API_KEY = "bringo_secure_shield_2026"

# =============================================================================
# Example: Search by Product Name
# =============================================================================

def search_by_product_name(product_name: str, top_k: int = 5):
    """Search for products similar to a given product name."""
    
    url = f"{API_URL}/search"
    
    payload = {
        "product_name": product_name,
        "top_k": top_k,
        "use_ranking": True,
        "in_stock_only": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    
    print(f"🔍 Searching for products similar to: '{product_name}'")
    print(f"   URL: {url}")
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    print()
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✅ Success! Found {len(data['similar_products'])} results")
        print(f"   Search Method: {data['search_method']}")
        print(f"   Query Time: {data['query_time_ms']:.1f}ms")
        print()
        
        print("📦 Results:")
        print("-" * 60)
        
        for i, product in enumerate(data['similar_products'], 1):
            print(f"{i}. {product['product_name']}")
            print(f"   Price: {product['price']} RON | Stock: {'✅' if product['in_stock'] else '🔴'}")
            print(f"   Score: {product['similarity_score']:.3f}")
            print()
        
        return data
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   {response.text}")
        return None


# =============================================================================
# Example: Text-based Search
# =============================================================================

def search_by_text(query: str, top_k: int = 5):
    """Search for products using free-text query."""
    
    url = f"{API_URL}/search"
    
    payload = {
        "query_text": query,
        "top_k": top_k,
        "use_ranking": True,
        "in_stock_only": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    
    print(f"🔍 Text search: '{query}'")
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {len(data['similar_products'])} results in {data['query_time_ms']:.1f}ms")
        
        for i, product in enumerate(data['similar_products'], 1):
            print(f"  {i}. {product['product_name']} - {product['price']} RON")
        
        return data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Bringo Similarity Search API - Example")
    print("=" * 60)
    print()
    
    # Example 1: Search by product name
    search_by_product_name("Ampawa Lapte De Cocos 400Ml", top_k=5)
    
    print()
    print("=" * 60)
    print()
    
    # Example 2: Text search
    search_by_text("lapte bio", top_k=3)
