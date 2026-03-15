#!/usr/bin/env python3
"""
End-to-End Test for Product Name Search
Validates the complete workflow from API endpoint through ranking
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import requests
import time
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
API_KEY = os.getenv("API_KEY", "bringo_secure_shield_2026")


def test_endpoint(product_name: str, top_k: int = 5, use_ranking: bool = True):
    """
    Test the unified search endpoint
    """
    logger.info(f"\nTesting: '{product_name}'")
    logger.info("-" * 70)

    url = f"{API_BASE_URL}/api/v1/search"
    headers = {"X-API-KEY": API_KEY}
    
    # Unified payload
    payload = {
        "product_name": product_name,
        "top_k": top_k,
        "use_ranking": use_ranking
    }

    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload)
    total_time = (time.time() - start_time) * 1000

    if response.status_code == 200:
        data = response.json()
        logger.info(f"✅ Success!")
        logger.info(f"   Total latency: {total_time:.1f}ms")
        logger.info(f"   API reported time: {data['query_time_ms']:.1f}ms")
        logger.info(f"   Search method: {data['search_method']}")
        logger.info(f"   Candidates retrieved: {data['candidates_retrieved']}")
        
        # Display query product
        if data.get('query_product'):
            qp = data['query_product']
            logger.info(f"\n   Query Product:")
            logger.info(f"      {qp['product_name']}")
            logger.info(f"      ID: {qp.get('product_id')}, Price: {qp.get('price', 'N/A')} RON")

        # Display top results
        logger.info(f"\n   Top {min(3, len(data['similar_products']))} Similar Products:")
        for i, product in enumerate(data['similar_products'][:3], 1):
            score_str = ""
            if product.get('similarity_score'):
                score_str = f"sim: {product['similarity_score']:.3f}"
            if product.get('ranking_score'):
                score_str += f", rank: {product['ranking_score']:.3f}"

            logger.info(f"      {i}. {product['product_name'][:60]}")
            if score_str:
                logger.info(f"         ({score_str})")

        return data
    else:
        logger.error(f"❌ Error: {response.status_code}")
        logger.error(f"   {response.text}")
        return None


def test_voice_scenarios():
    """Test scenarios specific to voice agents (text query fallback)"""

    logger.info("\n" + "=" * 70)
    logger.info("VOICE AGENT SCENARIOS (Text Search)")
    logger.info("=" * 70)

    voice_tests = [
        ("lapte", "Common product"),
        ("milk", "English synonym"),
        ("paine", "Romanian word"),
    ]

    results = []

    for query, description in voice_tests:
        logger.info(f"\n{description}: '{query}'")

        # Use query_text for these tests
        url = f"{API_BASE_URL}/api/v1/search"
        headers = {"X-API-KEY": API_KEY}
        payload = {
            "query_text": query, 
            "top_k": 3,
            "use_ranking": True
        }

        start = time.time()
        response = requests.post(url, headers=headers, json=payload)
        total_time = (time.time() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            results.append({
                'query': query,
                'found': True,
                'latency': total_time,
                'search_method': data.get('search_method')
            })
            logger.info(f"✅ Found {len(data['similar_products'])} results in {total_time:.1f}ms")
        else:
            results.append({
                'query': query,
                'found': False,
                'latency': total_time
            })
            logger.info(f"❌ Failed: {response.text}")

    return results


def main():
    """Run all tests"""
    logger.info("=" * 70)
    logger.info("END-TO-END UNIFIED SEARCH TEST")
    logger.info("=" * 70)
    
    # Test 1: Product Name Search
    test_endpoint("Lapte Zuzu 3.5% 1L", top_k=5)
    
    # Test 2: Voice Scenarios
    test_voice_scenarios()

if __name__ == "__main__":
    main()
