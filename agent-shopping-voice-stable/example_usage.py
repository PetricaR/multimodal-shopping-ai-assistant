"""
Example usage of Bringo Product Similarity API
Test the complete multimodal similarity search
"""
import requests
import json
from substitution.test_data import get_generic_baskets, get_user_profiles

# API base URL
BASE_URL = "http://localhost:8080"

def test_health_check():
    """Test API health check"""
    print("=" * 80)
    print("TEST 1: Health Check")
    print("=" * 80)
    
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_product_similarity(product_id: str = "4347506"):
    """Test finding similar products by product ID"""
    print("=" * 80)
    print(f"TEST 2: Find Similar Products (Product ID: {product_id})")
    print("=" * 80)
    
    payload = {
        "product_id": product_id,
        "top_k": 10,
        "use_ranking": True,  # Enable Ranking API for precision
        "in_stock_only": False
    }
    
    print(f"Request: {json.dumps(payload, indent=2)}")
    print()
    
    response = requests.post(
        f"{BASE_URL}/api/v1/search",
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Query time: {result['query_time_ms']:.1f}ms")
        print(f"Search method: {result['search_method']}")
        print(f"Candidates retrieved: {result['candidates_retrieved']}")
        print(f"Candidates ranked: {result['candidates_ranked']}")
        print()
        
        if result['query_product']:
            print("Query Product:")
            qp = result['query_product']
            print(f"  ID: {qp['product_id']}")
            print(f"  Name: {qp['product_name']}")
            print(f"  Category: {qp['category']}")
            print()
        
        print(f"Similar Products ({len(result['similar_products'])}):")
        print()
        
        for i, product in enumerate(result['similar_products'][:5], 1):
            print(f"{i}. {product['product_name']}")
            print(f"   ID: {product['product_id']}")
            print(f"   Category: {product['category']}")
            print(f"   Producer: {product['producer']}")
            if product.get('similarity_score'):
                print(f"   Similarity: {product['similarity_score']:.3f}")
            if product.get('ranking_score'):
                print(f"   Relevance: {product['ranking_score']:.3f}")
            print(f"   In stock: {product['in_stock']}")
            print()
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
    print()

def test_text_search(query: str = "ceai verde bio"):
    """Test text-based product search"""
    print("=" * 80)
    print(f"TEST 3: Text Search (Query: '{query}')")
    print("=" * 80)
    
    payload = {
        "query_text": query,
        "top_k": 5,
        "use_ranking": True,
        "in_stock_only": False
    }
    
    print(f"Request: {json.dumps(payload, indent=2)}")
    print()
    
    response = requests.post(
        f"{BASE_URL}/api/v1/search",
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Query time: {result['query_time_ms']:.1f}ms")
        print(f"Results: {len(result['similar_products'])}")
        print()
        
        for i, product in enumerate(result['similar_products'], 1):
            print(f"{i}. {product['product_name']}")
            print(f"   Category: {product['category']}")
            if product.get('ranking_score'):
                print(f"   Relevance: {product['ranking_score']:.3f}")
            print()
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
    print()

def test_simplified_endpoint(product_id: str = "12345"):
    """Test simplified GET endpoint"""
    print("=" * 80)
    print(f"TEST 4: Simplified Endpoint (Product ID: {product_id})")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/product/{product_id}/similar?top_k=5&use_ranking=true"
    print(f"URL: {url}")
    print()
    
    response = requests.get(url)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Found {len(result['similar_products'])} similar products")
        print()
        
        for i, product in enumerate(result['similar_products'], 1):
            print(f"{i}. {product['product_name']}")
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
    print()

def test_substitution(product_id: str = "4347506"):
    """Test product substitution suggestion"""
    print("=" * 80)
    print(f"TEST 5: Product Substitution Suggestion (ID: {product_id})")
    print("=" * 80)
    
    # Get test data
    baskets = get_generic_baskets()
    profiles = get_user_profiles()
    
    # Use "mic_dejun_sanatos" basket and "fan_bio" profile
    payload = {
        "missing_product_id": product_id,
        "current_basket": baskets["mic_dejun_sanatos"],
        "user_history": profiles["fan_bio"]["history"]
    }
    
    print(f"Request: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print()
    
    response = requests.post(
        f"{BASE_URL}/api/v1/substitution/suggest",
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Query time: {result['query_time_ms']:.1f}ms")
        print()
        
        print(f"Missing Product: {result['missing_product']['product_name']}")
        print(f"Substitutes Found: {len(result['suggestions'])}")
        print()
        
        for i, product in enumerate(result['suggestions'], 1):
            print(f"{i}. {product['product_name']}")
            print(f"   ID: {product['product_id']}")
            print(f"   Price: {product['price']} RON (Diff: {product.get('price_difference', 0):+.2f} RON)")
            print(f"   Confidence: {product.get('gemini_confidence', 0):.2f}")
            if product.get('image_url'):
                print(f"   Image: {product['image_url']}")
            print(f"   Reason: {product.get('substitution_reason', 'N/A')}")
            print()
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
    print()

if __name__ == "__main__":
    print("BRINGO PRODUCT SIMILARITY - API TESTING")
    print()
    
    try:
        # Test 1: Health check
        test_health_check()
        
        # Test 2: Product similarity (you'll need to replace with actual product ID)
        # test_product_similarity("12345")
        
        # Test 3: Text search
        test_text_search("ceai verde bio")
        
        # Test 4: Simplified endpoint
        # test_simplified_endpoint("12345")

        # Test 5: Substitution
        test_substitution("4347506")
        
        print("=" * 80)
        print("TESTING COMPLETE")
        print("=" * 80)
        print()
        print("Notes:")
        print("- Uncomment test functions with actual product IDs")
        print("- Ensure API server is running: python -m api.main")
        print("- Check logs for detailed information")
        print()
    
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to API server")
        print("Make sure the API is running: python -m api.main")
    except Exception as e:
        print(f"ERROR: {e}")
