import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.recipe_service import RecipeService
from services.user_profile_service import UserProfileService
from services.external_data_service import ExternalDataService
from services.search_service import SearchService

logger = logging.getLogger(__name__)

class ChefFlowService:
    """
    Orchestrates the intelligent meal planning flows (BR08, BR09)
    """

    @staticmethod
    def propose_daily_plan(user_id: str = "default_user") -> Dict[str, Any]:
        """Step 1: Agent makes a proposal daily plan (BR09)"""
        profile = UserProfileService.get_profile(user_id)
        weather = ExternalDataService.get_weather_context()
        holidays = ExternalDataService.get_upcoming_holidays()
        produce = ExternalDataService.get_seasonal_produce()
        
        # Determine theme based on context
        theme = "standard"
        if weather.get("is_cold"): theme = "comfort food"
        if holidays: theme = holidays[0]["name"]
        
        # Select meal types from profile
        meal_types = profile.get("preferences", {}).get("meal_types", ["breakfast", "lunch", "dinner"])
        
        proposal = {
            "status": "proposal",
            "user_id": user_id,
            "theme": theme,
            "seasonal_produce": produce,
            "meals": {}
        }
        
        # Mock selection of recipes (In reality, search via RecipeService)
        # We simulate 3 simple options as per BR09 example
        recipes = {
            "breakfast": "Omletă cu bacon și ardei",
            "lunch": "Burger de vită cu cartofi noi",
            "dinner": "Paste cu sos de roșii și busuioc"
        }
        
        for mtype in meal_types:
            if mtype in recipes:
                proposal["meals"][mtype] = recipes[mtype]
                
        return proposal

    @staticmethod
    def generate_full_plan_details(meal_plan: Dict[str, str], user_id: str = "default_user") -> Dict[str, Any]:
        """Step 3: Generate actual daily plan with details (BR09) using real recipes"""
        profile = UserProfileService.get_profile(user_id)
        budget = profile.get("finance", {}).get("budget_ron_month", 400) / 30 # Daily budget approx
        
        full_plan = {
            "status": "detailed",
            "meals": []
        }
        
        total_estimated_price = 0
        
        for mtype, recipe_name in meal_plan.items():
            # Real fetch from RecipeService
            recipe_data = RecipeService.search_recipe(recipe_name)
            
            if recipe_data.get('success'):
                recipe_details = {
                    "meal_type": mtype,
                    "recipe_name": recipe_data['recipe_name'],
                    "ingredients": recipe_data['ingredients'],
                    "instructions": recipe_data['instructions'],
                    "calories": recipe_data.get('labels', {}).get('calories', 500), # Mock cal if missing in labels
                    "servings": recipe_data.get('servings', 2),
                    "estimated_price": recipe_data.get('labels', {}).get('estimated_price_ron', 18.5), # Mock price if missing
                    "image_url": recipe_data.get('image_url')
                }
            else:
                # Fallback to simple details if recipe not found
                recipe_details = {
                    "meal_type": mtype,
                    "recipe_name": recipe_name,
                    "ingredients": ["Vă rugăm selectați alte produse"],
                    "instructions": "Rețeta nu a putut fi încărcată.",
                    "calories": 0,
                    "servings": 0,
                    "estimated_price": 0,
                    "image_url": None
                }
                
            full_plan["meals"].append(recipe_details)
            total_estimated_price += recipe_details["estimated_price"]
            
        full_plan["total_estimated"] = total_estimated_price
        full_plan["budget_fit"] = total_estimated_price <= (budget * 1.5) # Allow some margin
        
        return full_plan

    @staticmethod
    def finalize_and_optimize(cache_key: str, budget_ron: float) -> Dict[str, Any]:
        """Step 4: Use SearchService logic to optimize the shopping list"""
        # This is essentially what we implemented in services/search_service.py
        return SearchService.optimize_budget_for_quality(cache_key, budget_ron)
