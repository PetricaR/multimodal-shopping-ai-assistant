"""
Cart management tools
Uses the robust CartService for reliable basket operations.
"""

import logging
import json
from typing import Dict, Optional, List, Any
from services.cart_service import CartService

logger = logging.getLogger("cart_tools")

def extract_product_details_from_url(product_url: str, phpsessid: str, cookies: Dict[str, str]) -> str:
    """
    REAL ACTION: Extract product details (variant_id) from product URL using robust CartService.
    """
    logger.info(f"🔍 [TOOL] Extracting product details from URL: {product_url}")
    try:
        cart_service = CartService()
        result = cart_service.extract_product_details_from_url(
            product_url=product_url,
            phpsessid=phpsessid,
            cookies=cookies
        )
        return result
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return json.dumps({'status': 'error', 'message': str(e)})

def add_product_to_cart(product_id: str, variant_id: str, quantity: int, phpsessid: str, cookies: Dict[str, str], store: str = "carrefour_park_lake") -> str:
    """
    REAL ACTION: Add product to Bringo cart using robust CartService.
    """
    logger.info(f"🛒 [TOOL] Adding product {product_id} (variant: {variant_id}) to cart")
    try:
        cart_service = CartService()
        result = cart_service.add_product_to_cart(
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity,
            phpsessid=phpsessid,
            cookies=cookies,
            store=store
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Add to cart failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def get_cart_summary(phpsessid: str, cookies: Dict[str, str]) -> str:
    """REAL ACTION: Get cart summary using robust CartService."""
    try:
        cart_service = CartService()
        result = cart_service.get_cart_summary(phpsessid=phpsessid, cookies=cookies)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def batch_add_to_cart(products_json: str, phpsessid: str, cookies: Dict[str, str], store_id: str = "carrefour_park_lake") -> str:
    """
    REAL ACTION: Add multiple products to the cart in a single batch operation.
    
    CRITICAL INSTRUCTION: ALWAYS use this tool when adding more than one product.
    Do NOT call 'add_product_to_cart' in a loop. Use this batch tool for speed and reliability.
    It automatically handles variant resolution and parallel requests.
    
    Args:
        products_json: JSON string of list of dicts: [{"product_id": "123", "quantity": 1}, ...]
    """
    try:
        items = json.loads(products_json) if isinstance(products_json, str) else products_json
        logger.info(f"🛒 [TOOL] Batch adding {len(items)} products...")
        
        cart_service = CartService()
        result = cart_service.add_products_batch(
            items=items,
            store_id=store_id,
            phpsessid=phpsessid,
            cookies=cookies
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Batch add failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def remove_from_cart(product_id: str, phpsessid: str, cookies: Dict[str, str]) -> str:
    """
    REAL ACTION: Remove a specific product from the Bringo cart.
    
    Args:
        product_id: The ID of the product to remove (e.g., "1234567").
    """
    logger.info(f"🗑️ [TOOL] Removing product {product_id} from cart")
    try:
        cart_service = CartService()
        result = cart_service.remove_item_from_cart(
            product_id=product_id,
            phpsessid=phpsessid,
            cookies=cookies
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Remove from cart failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})

