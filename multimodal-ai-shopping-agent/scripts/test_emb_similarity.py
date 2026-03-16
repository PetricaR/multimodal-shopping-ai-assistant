
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import settings and generator
from config.settings import settings
from embeddings.generator import MultimodalEmbeddingGenerator
from vector_search.search_engine import SearchEngine
import numpy as np

def test_live_search():
    generator = MultimodalEmbeddingGenerator()
    search_engine = SearchEngine()
    
    query_text = "“Ardealul” - Pasta Vegetala Cu Ceapa Verde 100 G"
    
    print(f"--- Local Model Verification ---")
    print(f"Model: {generator.model}, Dimension: {generator.dimension}")
    emb_q, _ = generator.generate_embedding(query_text, task_type="RETRIEVAL_QUERY")
    print(f"Query Vector (first 5): {emb_q[:5]}")
    
    print(f"\n--- Live Vector Search Verification ---")
    print(f"Searching index: {settings.VS_INDEX_NAME}")
    print(f"Endpoint: {settings.VS_ENDPOINT_NAME}")
    
    try:
        results = search_engine.search_by_text(query_text, num_neighbors=10)
        
        print(f"\nResults Found: {len(results)}")
        for i, res in enumerate(results):
            print(f"{i+1}. ID: {res['id']}, Score: {res.get('similarity_score', 'N/A')}")
            print(f"   Name: {res.get('product_name', 'Unknown')}")
            print(f"   Category: {res.get('category', 'N/A')}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    test_live_search()
