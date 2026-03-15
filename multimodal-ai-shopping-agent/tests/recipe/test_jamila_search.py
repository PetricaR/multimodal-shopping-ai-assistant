
import sys
import os
import logging
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.recipe_service import RecipeService

logging.basicConfig(level=logging.INFO)

def test_search(query):
    print(f"\n🔍 Testing search for: {query}")
    result = RecipeService.search_recipe(query)
    if result.get("success"):
        print(f"✅ Success!")
        print(f"   Recipe: {result.get('recipe_name')}")
        print(f"   URL: {result.get('url')}")
        print(f"   Ingredients: {len(result.get('ingredients', []))} items")
        print(f"   Instructions: {len(result.get('instructions', []))} steps")
    else:
        print(f"❌ Failed!")
        print(f"   Error: {result.get('error')}")

if __name__ == "__main__":
    queries = ["papanasi", "sarmale", "pizza"]
    for q in queries:
        test_search(q)
