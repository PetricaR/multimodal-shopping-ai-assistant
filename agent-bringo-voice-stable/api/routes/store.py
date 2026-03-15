"""
Store Routes
Endpoints for store searching and selection
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from services.store_service import StoreService
from api import models

logger = logging.getLogger(__name__)
router = APIRouter(tags=["store"])

class StoreSearchRequest(BaseModel):
    address: str

class StoreSelectRequest(BaseModel):
    store_id: str

@router.post("/api/v1/store/search", response_model=models.StoreListResponse)
async def search_stores(request: StoreSearchRequest):
    """
    Search for stores at a specific address
    """
    try:
        # Blocking operation
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            StoreService.scrape_stores_at_address, 
            request.address
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        stores = []
        for s in result.get("stores", []):
            stores.append(models.StoreInfo(
                store_id=s.get("store_id", "") or "unknown",
                name=s.get("name", ""),
                category=s.get("category", ""),
                url=s.get("url", ""),
                status=s.get("status", ""),
                schedule=s.get("schedule")
            ))
            
        return models.StoreListResponse(
            status="success",
            stores=stores,
            count=result.get("stores_count", 0)
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/store/current")
async def get_current_store():
    """
    Get the currently configured/selected store
    """
    try:
        result = StoreService.get_configured_store()
        return result
    except Exception as e:
        logger.error(f"Get current store error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
