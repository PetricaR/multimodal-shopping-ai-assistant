"""
Recipe Routes
Endpoints for recipe discovery
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from services.recipe_service import RecipeService
from api import models

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recipes"])

@router.post("/api/v1/recipes/search", response_model=models.RecipeResponse)
async def search_recipes(request: models.RecipeSearchRequest):
    """
    Search for recipes
    """
    try:
        # Blocking operation
        import asyncio
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            RecipeService.search_recipe,
            request.food_name
        )
        
        if not result.get("success"):
             return models.RecipeResponse(
                 status="error",
                 found=False,
                 error=result.get("error")
             )
             
        return models.RecipeResponse(
            status="success",
            found=True,
            recipe=models.RecipeInfo(
                recipe_name=result.get("recipe_name", ""),
                url=result.get("url", ""),
                image_url=result.get("image_url", ""),
                prep_time=result.get("prep_time"),
                cook_time=result.get("cook_time"),
                servings=result.get("servings"),
                ingredients=result.get("ingredients", []),
                formatted_summary=result.get("formatted_summary")
            )
        )
            
    except Exception as e:
        logger.error(f"Recipe search route error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/recipes/ingredients", response_model=models.RecipeIngredientsResponse)
async def get_ingredients(request: models.RecipeSearchRequest):
    """
    Get ingredients for a recipe as a shopping list
    """
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            RecipeService.get_recipe_ingredients_for_shopping,
            request.food_name
        )
        
        if not result.get("success"):
            return models.RecipeIngredientsResponse(
                status="error",
                message=result.get("error")
            )
            
        return models.RecipeIngredientsResponse(
            status="success",
            recipe_name=result.get("recipe_name"),
            servings=result.get("servings"),
            ingredients=result.get("ingredients", []),
            ingredient_groups=result.get("ingredient_groups", {}),
            shopping_list=result.get("shopping_list"),
            url=result.get("url")
        )
            
    except Exception as e:
        logger.error(f"Recipe ingredients route error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
