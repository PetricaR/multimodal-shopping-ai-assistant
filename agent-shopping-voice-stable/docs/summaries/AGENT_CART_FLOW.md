# Complete Agent Cart Flow - Implementation Guide

## Overview

This document describes the complete flow for an AI agent to search for products and add them to the shopping cart using the Bringo API.

## Current Status

### ✅ What's Working NOW (Temporary Solution)

The flow works with BigQuery enrichment:

```
1. Agent searches: "cafea"
2. Vector Search returns: product names as IDs
3. BigQuery enrichment adds: product_id, variant_id
4. Agent receives: complete product data
5. Agent adds to cart: using product_id and variant_id
```

**Test it:**
```bash
python test_cart.py
```

### 🔧 Long-Term Fix (In Progress)

Regenerating embeddings with numeric product_ids as datapoint IDs:

```
1. Embeddings use numeric product_id (e.g., "6112937")
2. Vector Search returns product_id directly
3. Enrichment adds remaining metadata
4. Faster and cleaner flow
```

**Monitor progress:**
```bash
# Check if embeddings are being generated
python -c "
from google.cloud import storage
from config.settings import settings

client = storage.Client(project=settings.PROJECT_ID)
bucket = client.bucket(settings.STAGING_BUCKET)

blob = bucket.blob('embeddings/bringo_products_embeddings.jsonl')
if blob.exists():
    blob.reload()
    print(f'✓ Embeddings file: {blob.size / 1024 / 1024:.2f} MB')
    print(f'  Updated: {blob.updated}')
else:
    print('⏳ Embeddings still generating...')
"
```

## Complete Flow Architecture

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  AI AGENT                                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ 1. Search by text: "cafea"
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  VECTOR SEARCH (search_engine.py)                           │
│  • Generate query embedding                                  │
│  • Find similar products (ANN search)                        │
│  • Returns: product IDs + similarity scores                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ 2. Enrich results
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  BIGQUERY ENRICHMENT (search_engine._enrich_with_metadata)  │
│  • Fetch metadata by product_id or product_name             │
│  • Add: product_id, variant_id, price, category, etc.       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ 3. Returns enriched products
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  ENRICHED RESULTS                                            │
│  {                                                           │
│    "product_name": "Cafea Boabe Dallmayr Espresso 1Kg",     │
│    "product_id": "6112937",         ← Numeric ID             │
│    "variant_id": "vsp-2-343-225255", ← Required for cart     │
│    "similarity_score": 0.777,                                │
│    "price": 45.99,                                           │
│    "category": "Coffee",                                     │
│    "in_stock": true                                          │
│  }                                                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ 4. Agent selects product
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  CART SERVICE (cart_service.py)                             │
│  • POST /ro/ajax/cart/add-item/{product_id}                 │
│  • Body: {variant_id, quantity, store}                      │
│  • Returns: success/error                                    │
└─────────────────────────────────────────────────────────────┘
```

## API Integration Points

### 1. Search Products

```python
from api import dependencies

# Initialize search engine
search_engine = dependencies.get_search_engine()

# Search by text
results = search_engine.search_by_text(
    query_text="cafea",
    num_neighbors=5
)

# Results are already enriched with complete metadata
for product in results:
    print(f"Product: {product['product_name']}")
    print(f"  ID: {product['product_id']}")
    print(f"  Variant: {product['variant_id']}")
    print(f"  Price: {product['price']} RON")
    print(f"  Similarity: {product['similarity_score']:.2f}")
```

### 2. Add to Cart

```python
from services.cart_service import CartService

# Get authentication
from api.tools.shared import db
creds = db.get_credentials()
phpsessid = creds['session_cookie']

# Add product to cart
result = CartService.add_product_to_cart(
    product_id=product['product_id'],      # Numeric ID
    variant_id=product['variant_id'],       # Required
    quantity=1,
    phpsessid=phpsessid,
    cookies={'PHPSESSID': phpsessid},
    store="carrefour_park_lake"
)

if result['status'] == 'success':
    print(f"✅ Added to cart: {result['message']}")
else:
    print(f"❌ Failed: {result['message']}")
```

## Complete Agent Implementation Example

```python
#!/usr/bin/env python3
"""
Example: AI Agent adding products to cart
"""
from api import dependencies
from services.cart_service import CartService
from api.tools.shared import db

def agent_add_to_cart(search_query: str, quantity: int = 1):
    """
    Agent flow: Search and add to cart

    Args:
        search_query: What to search for (e.g., "cafea", "lapte")
        quantity: How many to add
    """
    # 1. Get authentication
    creds = db.get_credentials()
    if not creds:
        return {"error": "Not authenticated"}

    phpsessid = creds['session_cookie']

    # 2. Search for products
    search_engine = dependencies.get_search_engine()
    results = search_engine.search_by_text(
        query_text=search_query,
        num_neighbors=5
    )

    if not results:
        return {"error": f"No products found for '{search_query}'"}

    # 3. Select best match (highest similarity)
    product = results[0]

    print(f"\n🔍 Found: {product['product_name']}")
    print(f"   Similarity: {product['similarity_score']:.1%}")
    print(f"   Price: {product.get('price', 'N/A')} RON")

    # 4. Verify we have required fields
    if not product.get('product_id'):
        return {"error": "Missing product_id"}

    if not product.get('variant_id'):
        return {"error": "Missing variant_id"}

    # 5. Add to cart
    result = CartService.add_product_to_cart(
        product_id=product['product_id'],
        variant_id=product['variant_id'],
        quantity=quantity,
        phpsessid=phpsessid,
        cookies={'PHPSESSID': phpsessid},
        store="carrefour_park_lake"
    )

    return {
        "status": result['status'],
        "message": result['message'],
        "product": {
            "name": product['product_name'],
            "id": product['product_id'],
            "variant": product['variant_id'],
            "price": product.get('price')
        }
    }

# Example usage
if __name__ == "__main__":
    result = agent_add_to_cart("cafea", quantity=1)
    print(f"\n{result}")
```

## Required Fields

### For Search (Input)
- `query_text`: Search query in Romanian (e.g., "cafea", "lapte")

### For Cart (Output from Search)
- ✅ `product_id`: Numeric product ID (e.g., "6112937")
- ✅ `variant_id`: Variant identifier (e.g., "vsp-2-343-225255")
- `product_name`: Human-readable name
- `similarity_score`: How well it matches (0-1)
- `price`: Price in RON (optional but useful)
- `in_stock`: Availability (optional but useful)

### For API Call
- `phpsessid`: Authentication cookie
- `product_id`: Numeric ID
- `variant_id`: Variant ID
- `quantity`: Number of items
- `store`: Store identifier (e.g., "carrefour_park_lake")

## Error Handling

```python
# Check search results
if not results:
    # No products found
    return "No products match your search"

# Check required fields
product = results[0]
if not product.get('product_id'):
    # Missing product_id - enrichment failed
    # Fallback or retry
    pass

if not product.get('variant_id'):
    # Missing variant_id - may need to fetch from URL
    # Or use different product
    pass

# Check cart API response
if result['status'] == 'error':
    if 'alt magazin' in result.get('response_text', ''):
        # Products from another store - clear cart first
        CartService.clear_cart(phpsessid, cookies)
        # Retry add
    else:
        # Other error - handle appropriately
        pass
```

## Performance Optimizations

### Current Performance
- Vector search: ~2-3 seconds
- BigQuery enrichment: ~1 second
- Total search: ~3-4 seconds

### After Fix (with numeric IDs)
- Vector search: ~2-3 seconds
- Minimal enrichment: <0.5 seconds
- Total search: ~2.5-3.5 seconds

### Caching
The system uses multiple cache layers:
1. **Product cache DB**: Stores product_id → variant_id mappings
2. **BigQuery cache**: In-memory cache for frequently accessed products
3. **Search results**: Can be cached at application level

## Testing

### Test the complete flow
```bash
python test_cart.py
```

### Test just the search
```bash
python -c "
from api import dependencies

search_engine = dependencies.get_search_engine()
results = search_engine.search_by_text('cafea', num_neighbors=3)

for r in results:
    print(f'{r[\"product_name\"]}: {r.get(\"product_id\", \"MISSING\")}, {r.get(\"variant_id\", \"MISSING\")}')
"
```

### Verify enrichment
```bash
python diagnose_index.py
```

## Troubleshooting

### Problem: No product_id in results
**Solution:**
- Check if enrichment is working: `python diagnose_index.py`
- Verify BigQuery permissions
- Run the fix: `python fix_vector_search_auto.py`

### Problem: No variant_id in results
**Solution:**
- BigQuery table may be missing variant_id column
- Fallback: Fetch from product URL (slower)
- Check table schema

### Problem: BigQuery permissions error
**Solution:**
- The table uses Google Sheets external source
- Need Drive API permissions
- Alternative: Use native BigQuery table

### Problem: Cart API fails
**Solution:**
- Check authentication (PHPSESSID)
- Verify store_id is correct
- Check if cart has products from another store

## Next Steps

1. **Wait for embeddings regeneration** (~13 minutes)
2. **Wait for index rebuild** (~45-90 minutes)
3. **Verify fix**: `python diagnose_index.py`
4. **Test complete flow**: `python test_cart.py`
5. **Deploy to production**

## Files Reference

- **Search Engine**: [vector_search/search_engine.py](vector_search/search_engine.py)
- **Cart Service**: [services/cart_service.py](services/cart_service.py)
- **BigQuery Client**: [data/bigquery_client.py](data/bigquery_client.py)
- **Test Script**: [test_cart.py](test_cart.py)
- **Diagnostic**: [diagnose_index.py](diagnose_index.py)
- **Fix Script**: [fix_vector_search_auto.py](fix_vector_search_auto.py)
