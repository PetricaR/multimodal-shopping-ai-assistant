"""
Live Search Routes
Endpoints for real-time product search
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import logging

from services.search_service import SearchService
from services.store_service import StoreService
from api import models
from api.models import LiveSearchRequest # Import directly for signature
from security.guardrails import check_input

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/live_search", tags=["live-search"])

@router.post("/search")
async def live_search(request: LiveSearchRequest):
    """
    Search for products across multiple stores
    """
    try:
        # --- Guardrails: validate user-supplied queries ---
        for text in (request.queries or []):
            guard = await check_input(text)
            if not guard.allowed:
                logger.warning(f"Guardrails blocked live_search (reason={guard.reason}): '{text[:80]}'")
                raise HTTPException(
                    status_code=400,
                    detail="Pot să te ajut doar cu produse din catalogul Bringo/Carrefour. Ce produs cauți?",
                )
        # --------------------------------------------------

        # Determine stores
        stores = request.stores
        if not stores:
            if request.address:
                # Scrape stores from address
                store_result = await asyncio.to_thread(
                    StoreService.scrape_stores_at_address,
                    request.address
                )
                if store_result.get("status") == "success":
                    stores = [
                        {"store_id": s["store_id"], "store_name": s["name"]}
                        for s in store_result.get("stores", [])[:5] # Limit to top 5
                    ]
            else:
                # Default store? Or error?
                # For now let's error if no stores/address
                raise HTTPException(status_code=400, detail="Must provide stores or address")
        
        if not stores:
             raise HTTPException(status_code=404, detail="No stores found")

        # Execute search
        result = await asyncio.to_thread(
            SearchService.search_multi_store,
            request.queries,
            stores
        )
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Live search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize_cart")
async def optimize_cart(request: models.OptimizationRequest):
    """
    Optimize cart based on previous search results (Single Store vs Mixed)
    """
    try:
        result = SearchService.optimize_cart(request.cache_key)
        if result.get("status") == "error":
             raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cart optimization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize_budget", response_model=models.OptimizationResult)
async def optimize_budget(request: models.OptimizationRequest):
    """
    Optimize shopping list for budget while maximizing quality
    """
    try:
        result = SearchService.optimize_budget_for_quality(request.cache_key, request.budget_ron)
        if result.get("status") == "error":
             raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Budget optimization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
