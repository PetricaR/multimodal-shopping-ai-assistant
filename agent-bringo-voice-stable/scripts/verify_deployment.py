import sys
from pathlib import Path
import random
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)

from vector_search.search_engine import SearchEngine

def verify_index_content():
    print("🔍 VERIFYING INDEX CONTENT (Using SearchEngine)")
    print("-" * 50)
    
    try:
        # 1. Initialize Engine (auto-finds endpoint)
        print("1. Initializing Search Engine...")
        engine = SearchEngine()
        
        # 2. Test with a text query
        query = "lapte si miere"
        print(f"\n2. Running Test Search Query: '{query}'...")
        
        results = engine.search_by_text(
            query_text=query,
            num_neighbors=5,
            filter_in_stock=False
        )
        
        # 3. Analyze Results
        if not results:
            print("\n❌ Query returned NO results. The index might be empty.")
        else:
            print(f"\n✅ Query SUCCESS! Found {len(results)} neighbors:")
            for i, res in enumerate(results):
                print(f"   {i+1}. ID: {res['id']}")
                print(f"      Distance: {res['distance']:.4f}")
                print(f"      Similarity: {res['similarity_score']:.4f}")
            
            print("\n🎉 CONCLUSION: The Index HAS DATA and is SEARCHABLE.")
            
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_index_content()
