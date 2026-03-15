"""
Recipe Search Services
Integrates Jamila Cuisine scraper for recipe discovery
"""
import logging
from typing import Dict, Any, List, Optional

from services.jamila_scraper import JamilaRecipeScraper, Recipe
from services.search_service import SearchService
from google import genai
from config.settings import settings
import os
import json

logger = logging.getLogger(__name__)

# Initialize global scraper instance
_scraper = None

class RecipeService:
    @staticmethod
    def get_scraper() -> JamilaRecipeScraper:
        """Get or create scraper instance"""
        global _scraper
        if _scraper is None:
            _scraper = JamilaRecipeScraper(delay=1.0)
        return _scraper

    @staticmethod
    def search_recipe(food_name: str) -> Dict[str, Any]:
        """
        Search for a recipe by food name and return detailed recipe information.
        """
        try:
            scraper = RecipeService.get_scraper()
            recipe = scraper.get_recipe(food_name)
            
            if recipe and recipe.name != "Error":
                # Generate formatted summary
                summary = RecipeService._format_recipe_summary(recipe)
                
                return {
                    'success': True,
                    'recipe_name': recipe.name,
                    'url': recipe.url,
                    'description': recipe.description,
                    'prep_time': recipe.prep_time,
                    'cook_time': recipe.cook_time,
                    'total_time': recipe.total_time,
                    'servings': recipe.servings,
                    'ingredients': recipe.ingredients,
                    'instructions': recipe.instructions,
                    'nutrition_info': recipe.nutrition_info,
                    'tags': recipe.tags,
                    'image_url': recipe.image_url,
                    'video_url': recipe.video_url,
                    'formatted_summary': summary,
                    'scraped_at': recipe.scraped_at,
                    'labels': RecipeService.get_recipe_labels(recipe)
                }
            else:
                return {
                    'success': False,
                    'error': f'Nu am găsit rețetă pentru "{food_name}"',
                    'suggestion': 'Încearcă să reformulezi căutarea sau caută un alt fel de mâncare.',
                    'formatted_summary': f"Nu-i nimic, poftă bună în continuare! Nu am găsit rețetă pentru {food_name}"
                }
                
        except Exception as e:
            logger.error(f"Recipe search error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Eroare la căutarea rețetei: {str(e)}',
                'suggestion': 'Te rog încearcă din nou mai târziu.'
            }

    @staticmethod
    def _format_recipe_summary(recipe: Recipe) -> str:
        """Format recipe as human-readable summary"""
        lines = []
        
        lines.append(f"🍽️  **{recipe.name}**")
        lines.append(f"🔗 {recipe.url}")
        lines.append("")
        
        if recipe.description:
            lines.append(f"📝 {recipe.description[:200]}{'...' if len(recipe.description) > 200 else ''}")
            lines.append("")
        
        # Timing info
        timing = []
        if recipe.prep_time:
            timing.append(f"⏱️  Prep: {recipe.prep_time}")
        if recipe.cook_time:
            timing.append(f"🔥 Cook: {recipe.cook_time}")
        if recipe.total_time:
            timing.append(f"⏰ Total: {recipe.total_time}")
        if recipe.servings:
            timing.append(f"👥 Porții: {recipe.servings}")
        
        if timing:
            lines.append(" | ".join(timing))
            lines.append("")
        
        # Ingredients
        if recipe.ingredients:
            lines.append(f"🥘 **INGREDIENTE** ({len(recipe.ingredients)} items):")
            for ingredient in recipe.ingredients[:15]:  # First 15
                if ingredient.startswith('#'):
                    lines.append(f"   **{ingredient[1:].strip()}:**")
                else:
                    lines.append(f"   • {ingredient}")
            
            if len(recipe.ingredients) > 15:
                lines.append(f"   ... și încă {len(recipe.ingredients) - 15} ingrediente")
            lines.append("")
        
        # Instructions
        if recipe.instructions:
            lines.append(f"📋 **MOD DE PREPARARE** ({len(recipe.instructions)} pași):")
            for i, instruction in enumerate(recipe.instructions[:3], 1):
                lines.append(f"   {i}. {instruction[:150]}{'...' if len(instruction) > 150 else ''}")
            
            if len(recipe.instructions) > 3:
                lines.append(f"   ... și încă {len(recipe.instructions) - 3} pași")
            lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def get_recipe_ingredients_for_shopping(food_name: str) -> Dict[str, Any]:
        """
        Get recipe ingredients formatted as a shopping list.
        """
        try:
            scraper = RecipeService.get_scraper()
            recipe = scraper.get_recipe(food_name)
            
            if recipe and recipe.name != "Error":
                # Group ingredients by category (if groups exist)
                ingredient_groups = {}
                current_group = "Ingrediente"
                ingredient_groups[current_group] = []
                
                for ingredient in recipe.ingredients:
                    if ingredient.startswith('#'):
                        # New group header
                        current_group = ingredient[1:].strip()
                        ingredient_groups[current_group] = []
                    else:
                        ingredient_groups[current_group].append(ingredient)
                
                # Format shopping list
                shopping_list = RecipeService._format_shopping_list(recipe.name, recipe.servings, ingredient_groups)
                
                return {
                    'success': True,
                    'recipe_name': recipe.name,
                    'servings': recipe.servings,
                    'ingredients': recipe.ingredients,
                    'ingredient_groups': ingredient_groups,
                    'shopping_list': shopping_list,
                    'url': recipe.url
                }
            else:
                return {
                    'success': False,
                    'error': f'Nu am găsit rețetă pentru "{food_name}"'
                }
                
        except Exception as e:
            logger.error(f"Recipe ingredients error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Eroare: {str(e)}'
            }

    @staticmethod
    def _format_shopping_list(recipe_name: str, servings: Optional[str], ingredient_groups: Dict[str, List[str]]) -> str:
        """Format ingredients as human-readable shopping list"""
        lines = []
        lines.append(f"🛒 **LISTA DE CUMPĂRĂTURI**")
        lines.append(f"📝 Pentru: {recipe_name}")
        if servings:
            lines.append(f"👥 Porții: {servings}")
        lines.append("")
        lines.append("=" * 30)
        
        for group_name, ingredients in ingredient_groups.items():
            if ingredients:
                lines.append(f"\n**{group_name}:**")
                for ingredient in ingredients:
                    lines.append(f"  ☐ {ingredient}")
        
        lines.append("\n" + "=" * 30)
        return "\n".join(lines)

    @staticmethod
    def match_ingredients_to_products(ingredients: List[str], store_id: str = "729792") -> Dict[str, Any]:
        """
        Search for products for each ingredient in parallel.
        Returns a mapping of original ingredients to their best-matched product.
        """
        try:
            # 1. Clean ingredients to get searchable names
            search_map = {} # cleaned_name -> [original_ingredients]
            for ing in ingredients:
                if ing.startswith('#'): continue # Skip group headers
                
                clean_name = SearchService.clean_ingredient_for_search(ing)
                if not clean_name: continue
                
                if clean_name not in search_map:
                    search_map[clean_name] = []
                search_map[clean_name].append(ing)
            
            clean_queries = list(search_map.keys())
            if not clean_queries:
                return {"success": False, "error": "No valid ingredients to search"}
            
            # 2. Perform parallel search across stores
            # Using store_id as primary, but we'll treat it as a single-store search for now
            # by providing only one store in the list for search_multi_store logic.
            stores = [{"store_id": store_id, "store_name": "Selected Store"}]
            search_results = SearchService.search_multi_store(clean_queries, stores)
            
            if search_results.get("status") != "success":
                return {"success": False, "error": "Search failed"}
                
            # 3. Match best products and build result map
            matches = []
            results_data = search_results.get("results", {})
            
            for clean_query, q_data in results_data.items():
                products = q_data.get("products", [])
                original_ings = search_map.get(clean_query, [])
                
                best_match = None
                if products:
                    # Score and compare products to find best match
                    scored = SearchService.compare_products(products)
                    best_match = scored[0] if scored else None
                
                for orig_ing in original_ings:
                    matches.append({
                        "ingredient": orig_ing,
                        "search_query": clean_query,
                        "best_match": best_match,
                        "found": best_match is not None
                    })
            
            return {
                "success": True,
                "matches": matches,
                "elapsed_seconds": search_results.get("elapsed_seconds"),
                "store_id": store_id
            }
            
        except Exception as e:
            logger.error(f"Ingredient matching error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_recipe_labels(recipe: Recipe) -> Dict[str, Any]:
        """
        Use GenAI to label the recipe with metadata for BR05 retrieval.
        """
        try:
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                return {}

            # Handle potential SecretStr or plain string
            if hasattr(api_key, 'get_secret_value'):
                api_key_str = api_key.get_secret_value()
            else:
                api_key_str = str(api_key)
                
            client = genai.Client(api_key=api_key_str)
            
            prompt = f"""
            Analyze the following Romanian recipe and provide metadata in JSON format.
            Recipe Name: {recipe.name}
            Description: {recipe.description}
            Ingredients: {", ".join(recipe.ingredients)}
            
            Return JSON with these fields:
            - diet_type: List[str] (choices: vegan, keto, vegetarian, mediterranean, paleo, gluten-free)
            - complexity: str (novice, basic, intermediate, advanced)
            - meal_category: str (breakfast, lunch, dinner, snack)
            - kid_friendly: bool
            - nutritional_focus: List[str] (high-protein, weight-loss, low-carb, healthy)
            - season: str (winter, spring, summer, autumn)
            - estimated_budget: str (low, medium, high)
            
            JSON:
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"GenAI labeling error: {e}")
            return {}
