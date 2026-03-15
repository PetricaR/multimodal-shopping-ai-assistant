"""
Store Selection Routes
Endpoints for finding and selecting stores
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import logging

from api.models import StoreSearchRequest, StoreListResponse, StoreInfo
from api.tools import store_selection

router = APIRouter(prefix="/stores", tags=["Stores"])
logger = logging.getLogger("store_router")

@router.post("/find", response_model=StoreListResponse)
async def find_stores(request: StoreSearchRequest):
    """
    Find stores at a specific address (scrapes if not found)
    """
    try:
        # Check DB first? The tool does scraping which saves to DB.
        # Ideally we'd check DB first, but for now rely on tool logic.
        # The tool scrape_stores_at_address does the heavy lifting.
        
        result_json = store_selection.scrape_stores_at_address(request.address)
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            return StoreListResponse(
                status="success",
                count=result.get("stores_count", 0),
                stores=result.get("stores", [])
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Failed to find stores"))
            
    except Exception as e:
        logger.error(f"Store search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=StoreListResponse)
async def list_stores(
    categories: Optional[List[str]] = Query(None),
    status: str = "Open"
):
    """
    Get stores from database, optionally filtered by category
    """
    try:
        cat_str = json.dumps(categories) if categories else ""
        result_json = store_selection.get_stores_from_database(cat_str, status)
        result = json.loads(result_json)
        
        return StoreListResponse(
            status="success",
            count=result.get("stores_count", 0),
            stores=result.get("stores", [])
        )
    except Exception as e:
        logger.error(f"List stores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
