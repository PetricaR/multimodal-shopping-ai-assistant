"""
Cart Routes
Endpoints for managing the shopping cart
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import logging

from services.cart_service import CartService
from services.auth_service import AuthService
from services.store_service import StoreService
from config.settings import settings
from api import models
from api import dependencies

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cart"])


@router.get("/api/v1/cart")
async def view_cart(auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """Get current cart status"""
    try:
        cookies = {
            'PHPSESSID': auth.get("session_cookie")
        }
        
        result = CartService.get_cart_summary(auth.get("session_cookie"), cookies)
        
        return models.CartOperationResponse(
            status=result.get("status"),
            message="Cart summary retrieved",
            cart_count=result.get("cart_count")
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View cart error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/cart/add")
@router.post("/api/v1/cart/items")
async def add_item(request: models.CartItemRequest, auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """Add item to cart"""
    try:
        cookies = {'PHPSESSID': auth.get("session_cookie")}
        phpsessid = auth.get("session_cookie")
        
        # Determine store
        store_id = request.store_id
        if not store_id:
             # Try to get from settings or auth
             store_id = settings.BRINGO_STORE
        
        # Build product_url if not provided
        product_url = request.product_url
        if not product_url:
            product_url = f"{settings.BRINGO_BASE_URL}/ro/{store_id}/products/product-{request.product_id}"

        # Blocking operation in thread pool
        result = await asyncio.to_thread(
            CartService.add_product_optimized,
            request.product_id,
            store_id,
            product_url,
            request.quantity,
            phpsessid,
            cookies,
            request.product_name
        )
        
        if result.get("status") == "error":
             raise HTTPException(status_code=400, detail=result.get("message"))
             
        return models.CartOperationResponse(
            status="success",
            message=result.get("message", "Item added"),
            items_added=[result]
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/cart/add-batch")
async def add_items_batch(request: models.CartBatchRequest, auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """
    Add multiple items to cart concurrently (async + multi-threading).

    Uses ThreadPoolExecutor internally:
    - Phase 1: Resolve all variant_ids concurrently (cache -> Feature Store -> scrape)
    - Phase 2: Add resolved products to cart concurrently
    """
    try:
        cookies = {'PHPSESSID': auth.get("session_cookie")}
        phpsessid = auth.get("session_cookie")

        store_id = request.store_id
        if not store_id:
            store_id = settings.BRINGO_STORE

        items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "product_name": item.product_name,
                "variant_id": item.variant_id,
                "product_url": item.product_url
            }
            for item in request.items
        ]

        result = await asyncio.to_thread(
            CartService.add_products_batch,
            items,
            store_id,
            phpsessid,
            cookies
        )

        return models.CartOperationResponse(
            status=result.get("status"),
            message=result.get("message", "Batch operation complete"),
            items_added=result.get("items_added"),
            failed_items=result.get("failed_items"),
            timing_ms=result.get("timing_ms")
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch add error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/v1/cart/items/{product_id}")
async def delete_item(product_id: str, auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """Remove item from cart"""
    try:
        cookies = {'PHPSESSID': auth.get("session_cookie")}
        phpsessid = auth.get("session_cookie")
        
        result = await asyncio.to_thread(
            CartService.remove_item_from_cart,
            product_id,
            phpsessid,
            cookies
        )
        
        if result.get("status") == "error":
             raise HTTPException(status_code=400, detail=result.get("message"))
             
        return models.CartOperationResponse(
            status="success",
            message=result.get("message", "Item removed")
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.patch("/api/v1/cart/items/{product_id}")
async def update_item_qty(product_id: str, request: models.CartItemRequest, auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """Update item quantity in cart"""
    try:
        cookies = {'PHPSESSID': auth.get("session_cookie")}
        phpsessid = auth.get("session_cookie")
        
        result = await asyncio.to_thread(
            CartService.update_item_quantity,
            product_id,
            request.quantity,
            phpsessid,
            cookies
        )
        
        if result.get("status") == "error":
             raise HTTPException(status_code=400, detail=result.get("message"))
             
        return models.CartOperationResponse(
            status="success",
            message=result.get("message", "Quantity updated"),
            quantity=result.get("quantity")
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/api/v1/cart")
async def clear_cart_endpoint(auth: Dict[str, Any] = Depends(dependencies.get_authenticated_user)):
    """Clear all items from cart"""
    try:
        cookies = {'PHPSESSID': auth.get("session_cookie")}
        phpsessid = auth.get("session_cookie")
        
        result = await asyncio.to_thread(
            CartService.clear_cart,
            phpsessid,
            cookies
        )
        
        if result.get("status") == "error":
             raise HTTPException(status_code=400, detail=result.get("message"))
             
        return models.CartOperationResponse(
            status="success",
            message=result.get("message", "Cart cleared"),
            cart_count=0
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear cart error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
