"""
Recipe Search Routes
Endpoints for finding recipes and ingredients
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import logging

from api.models import RecipeSearchRequest, RecipeResponse, RecipeInfo
from api.tools import recipe_search

router = APIRouter(prefix="/recipes", tags=["Recipes"])
logger = logging.getLogger("recipe_router")

@router.get("/search", response_model=RecipeResponse)
async def search_recipes(q: str = Query(..., description="Food name (e.g. 'sarmale')")):
    """Search for a recipe by name"""
    try:
        result = recipe_search.search_recipe(q)
        
        if result.get("success"):
            recipe_data = result
            return RecipeResponse(
                status="success",
                found=True,
                recipe=RecipeInfo(
                    recipe_name=recipe_data["recipe_name"],
                    url=recipe_data["url"],
                    description=recipe_data.get("description"),
                    prep_time=recipe_data.get("prep_time"),
                    cook_time=recipe_data.get("cook_time"),
                    servings=recipe_data.get("servings"),
                    ingredients=recipe_data.get("ingredients", []),
                    formatted_summary=recipe_data.get("formatted_summary")
                )
            )
        else:
            return RecipeResponse(
                status="success",
                found=False,
                error=result.get("error"),
                suggestions=[result.get("suggestion")] if result.get("suggestion") else None
            )
            
    except Exception as e:
        logger.error(f"Recipe search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ingredients", response_model=RecipeResponse)
async def get_ingredients(q: str = Query(..., description="Food name")):
    """Get just the ingredients shopping list for a recipe"""
    try:
        result = recipe_search.get_recipe_ingredients_for_shopping(q)
        
        if result.get("success"):
            return RecipeResponse(
                status="success",
                found=True,
                recipe=RecipeInfo(
                    recipe_name=result["recipe_name"],
                    url=result["url"],
                    servings=result.get("servings"),
                    ingredients=result.get("ingredients", []),
                    shopping_list=result.get("shopping_list")
                )
            )
        else:
            return RecipeResponse(
                status="success",
                found=False,
                error=result.get("error")
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggest", response_model=RecipeResponse)
async def suggest_recipes(ingredients: List[str] = Query(..., description="List of available ingredients")):
    """Suggest recipes based on ingredients"""
    try:
        result = recipe_search.suggest_recipe_by_ingredients(ingredients)
        
        return RecipeResponse(
            status="success",
            found=result.get("success", False),
            suggestions=result.get("suggestions", []),
            error=result.get("message")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
