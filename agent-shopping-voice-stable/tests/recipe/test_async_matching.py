
import sys
import os
import logging
import time
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.recipe_service import RecipeService
from services.search_service import SearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cleaning():
    print("\n--- 🧹 Testing Ingredient Cleaning ---")
    test_cases = [
        "500g branza de vaci bine scursa",
        "200ml smantana grasa",
        "3 oua",
        "o lingura de gris",
        "un pachet de unt",
        "sare si piper dupa gust",
        "o legatura de patrunjel"
    ]
    
    for tc in test_cases:
        cleaned = SearchService.clean_ingredient_for_search(tc)
        print(f"Original: {tc}")
        print(f"Cleaned:  {cleaned}")
        print("-" * 20)

def test_async_matching():
    print("\n--- ⚡ Testing Async Ingredient Matching ---")
    ingredients = [
        "500g branza de vaci",
        "200g smantana",
        "3 oua",
        "100g gris",
        "esenta de vanilie"
    ]
    
    start_time = time.time()
    result = RecipeService.match_ingredients_to_products(ingredients)
    end_time = time.time()
    
    if result.get("success"):
        print(f"✅ Success! Matched {len(result['matches'])} ingredients in {result['elapsed_seconds']:.2f}s")
        print(f"Total real time: {end_time - start_time:.2f}s")
        
        for m in result['matches']:
            status = "✅" if m['found'] else "❌"
            prod_name = m['best_match']['name'] if m['found'] else "N/A"
            prod_price = f"{m['best_match']['price']} RON" if m['found'] else ""
            print(f"{status} {m['ingredient']} -> {prod_name} ({prod_price})")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_cleaning()
    test_async_matching()
