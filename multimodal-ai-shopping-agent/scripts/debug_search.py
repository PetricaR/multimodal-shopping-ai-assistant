
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
from vector_search.search_engine import SearchEngine

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    query = "ulei unirea"
    logger.info(f"Testing search for: '{query}'")
    
    try:
        engine = SearchEngine()
        results = engine.search_by_text(query, num_neighbors=5)
        
        print("\n=== Search Results ===")
        found = False
        for res in results:
            # Check if name contains 'Unirea' (case insensitive)
            name = res.get('product_name', 'Unknown')
            pid = res.get('id', 'N/A')
            score = res.get('similarity_score', 0)
            
            print(f"- [{pid}] {name} (Score: {score:.4f})")
            
            if 'unirea' in name.lower() and 'ulei' in name.lower():
                found = True
                
        if found:
            print("\n✅ SUCCESS: Found 'Ulei Unirea' in results.")
        else:
            print("\n❌ WARNING: 'Ulei Unirea' NOT found in top 5 results.")
            
    except Exception as e:
        logger.error(f"Search failed: {e}")

if __name__ == "__main__":
    main()
