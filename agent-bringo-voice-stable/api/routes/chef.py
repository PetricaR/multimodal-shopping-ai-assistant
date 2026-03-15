from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

from api import models
from services.chef_flow_service import ChefFlowService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chef", tags=["chef-ai"])

@router.get("/plan/propose", response_model=Dict[str, Any])
async def propose_plan(user_id: str = "default_user"):
    """Step 1: Get a meal plan proposal based on profile and context (BR09)"""
    try:
        return ChefFlowService.propose_daily_plan(user_id)
    except Exception as e:
        logger.error(f"Error proposing plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate plan proposal")

@router.post("/plan/details", response_model=Dict[str, Any])
async def get_plan_details(request: Dict[str, str], user_id: str = "default_user"):
    """Step 3: Generate full recipe details for a chosen plan (BR09)"""
    try:
        # request is { "breakfast": "Recipe Name", ... }
        return ChefFlowService.generate_full_plan_details(request, user_id)
    except Exception as e:
        logger.error(f"Error generating plan details: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate plan details")

@router.post("/optimize", response_model=models.OptimizationResult)
async def optimize_chef_cart(request: models.OptimizationRequest):
    """Step 4: Optimize the final shopping list for budget/quality (BR09)"""
    try:
        return ChefFlowService.finalize_and_optimize(request.cache_key, request.budget_ron)
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail="Failed to optimize shopping list")
