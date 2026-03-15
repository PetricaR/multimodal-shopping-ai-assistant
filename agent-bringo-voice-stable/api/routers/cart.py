"""
Cart Management Routes
Endpoints for viewing and modifying the shopping cart
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
import json
import logging

from api.models import CartItemRequest, CartOperationResponse
from api.tools import cart_management
from api.routers.auth import auth_status

router = APIRouter(prefix="/cart", tags=["Cart"])
logger = logging.getLogger("cart_router")

async def get_session_cookies(phpsessid: Optional[str] = Header(None)):
    """Dependency to get session cookies"""
    if phpsessid:
        return phpsessid, {}
    
    # Validation fallback? For now rely on client providing header or we fetch from DB?
    # Better to allow client to pass it.
    # But for seamless integration, maybe fetch from DB if header missing?
    # Let's enforce header for API purity, or optional DB lookup.
    return None, {}

@router.get("/summary", response_model=CartOperationResponse)
async def get_cart(phpsessid: str = Header(..., description="Bringo PHPSESSID")):
    """Get current cart summary"""
    try:
        result_json = cart_management.get_cart_summary(phpsessid, {})
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            return CartOperationResponse(
                status="success",
                message="Cart summary retrieved",
                cart_count=result.get("cart_count")
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add", response_model=CartOperationResponse)
async def add_to_cart(
    item: CartItemRequest,
    phpsessid: str = Header(..., description="Bringo PHPSESSID")
):
    """
    Add item to cart.
    Requires variant_id (fast) OR product_url (slow, will scrape).
    """
    try:
        pid = item.product_id
        vid = item.variant_id
        qty = item.quantity
        url = item.product_url
        
        if not vid:
            if not url:
                raise HTTPException(status_code=400, detail="Either variant_id or product_url is required")
            
            # Scrape to get variant_id
            details_json = cart_management.extract_product_details_from_url(url, phpsessid, {})
            details = json.loads(details_json)
            
            if details.get("status") != "success":
                raise HTTPException(status_code=400, detail=f"Failed to extract product details: {details.get('message')}")
            
            vid = details.get("variant_id")
            if not vid:
                raise HTTPException(status_code=400, detail="Could not find variant_id for product")
                
        # Proceed to add
        result_json = cart_management.add_product_to_cart(pid, vid, qty, phpsessid, {})
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            return CartOperationResponse(
                status="success",
                message=result.get("message"),
                items_added=[{"product_id": pid, "quantity": qty}]
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add to cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-batch", response_model=CartOperationResponse)
async def add_batch_to_cart(
    items: List[CartItemRequest],
    phpsessid: str = Header(..., description="Bringo PHPSESSID")
):
    """Add multiple items to cart in parallel"""
    try:
        # Convert Pydantic models to dicts for tool
        products_list = [item.dict() for item in items]
        
        result_json = cart_management.add_multiple_products_to_cart_parallel(
            products_json=products_list,
            phpsessid=phpsessid,
            cookies={}
        )
        result = json.loads(result_json)
        
        return CartOperationResponse(
            status=result.get("status", "error"),
            message=f"Batch operation completed. Success: {result.get('successful', 0)}/{result.get('total', 0)}",
            items_added=[r for r in result.get("results", []) if r.get("status") == "success"],
            failed_items=[r for r in result.get("results", []) if r.get("status") != "success"]
        )
    except Exception as e:
        logger.error(f"Batch add error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
