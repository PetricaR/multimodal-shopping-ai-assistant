# Complete Agent Search & Cart Flow with Ranking

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  AI AGENT                                                        │
│  "Add cafea to my cart"                                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 1. Search query: "cafea"
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  VECTOR SEARCH (Approximate Nearest Neighbor)                   │
│  • Generate embedding for "cafea"                                │
│  • Find ~150 similar products (fast but approximate)             │
│  • Returns: [{id, distance, similarity_score}, ...]              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 2. Top 150 candidates
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  RANKING API (Semantic Ranker)                                  │
│  • Re-rank top 150 results for precision                         │
│  • Uses: semantic-ranker-default@latest                          │
│  • Returns: Top N most relevant (sorted by relevance)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 3. Top N ranked results
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FEATURE STORE ENRICHMENT                                        │
│  • Batch fetch metadata for top N products                       │
│  • Adds: product_id, variant_id, price, category, in_stock      │
│  • <2ms latency per product                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 4. Enriched + Ranked products
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  ENRICHED RESULTS                                                │
│  [                                                               │
│    {                                                             │
│      "product_name": "Cafea Boabe Dallmayr Espresso 1Kg",       │
│      "product_id": "6112937",        ← From Feature Store        │
│      "variant_id": "vsp-2-343-...",  ← From Feature Store        │
│      "price": 45.99,                 ← From Feature Store        │
│      "category": "Coffee",           ← From Feature Store        │
│      "in_stock": true,               ← From Feature Store        │
│      "similarity_score": 0.95,       ← From Ranking API          │
│      "rank": 1                       ← From Ranking API          │
│    },                                                            │
│    ...                                                           │
│  ]                                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 5. Agent selects best match
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  CART API                                                        │
│  POST /ro/ajax/cart/add-item/{product_id}                       │
│  Body: {variant_id, quantity, store}                            │
│  Returns: success/error                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation

### Step 1: Vector Search (Fast, Approximate)

```python
from api import dependencies

search_engine = dependencies.get_search_engine()

# Get ~150 approximate matches
candidates = search_engine.search_by_text(
    query_text="cafea",
    num_neighbors=150  # Standard: retrieve 150 for ranking
)
```

**Output:**
```python
[
    {'id': '6112937', 'distance': 0.22, 'similarity_score': 0.78},
    {'id': '22743581', 'distance': 0.26, 'similarity_score': 0.74},
    # ... 148 more candidates
]
```

### Step 2: Ranking API (Precise Re-ranking)

```python
from ranking.reranker import SemanticReranker

reranker = SemanticReranker()

# Re-rank candidates for precision
ranked_results = reranker.rerank(
    query_text="cafea",
    candidates=candidates,
    top_n=5  # Return top 5 most relevant
)
```

**Output:**
```python
[
    {'id': '6112937', 'similarity_score': 0.95, 'rank': 1},
    {'id': '22743581', 'similarity_score': 0.89, 'rank': 2},
    # ... top 5 ranked by relevance
]
```

### Step 3: Feature Store Enrichment

```python
from features.realtime_server import get_feature_server

feature_server = get_feature_server()

# Get product IDs from ranked results
product_ids = [r['id'] for r in ranked_results]

# Batch fetch metadata (<2ms per product)
metadata = feature_server.get_product_metadata(product_ids)

# Enrich results
for result in ranked_results:
    pid = result['id']
    if pid in metadata:
        result.update(metadata[pid])
```

**Output:**
```python
[
    {
        'id': '6112937',
        'product_name': 'Cafea Boabe Dallmayr Espresso 1Kg',
        'product_id': '6112937',
        'variant_id': 'vsp-2-343-225255',
        'price': 45.99,
        'category': 'Coffee',
        'in_stock': True,
        'similarity_score': 0.95,
        'rank': 1
    },
    # ... enriched top 5
]
```

### Step 4: Add to Cart

```python
from services.cart_service import CartService
from api.tools.shared import db

# Get authentication
creds = db.get_credentials()

# Select best match
product = ranked_results[0]

# Add to cart
result = CartService.add_product_to_cart(
    product_id=product['product_id'],
    variant_id=product['variant_id'],
    quantity=1,
    phpsessid=creds['session_cookie'],
    cookies={'PHPSESSID': creds['session_cookie']},
    store="carrefour_park_lake"
)
```

## Complete Integration (All Steps)

```python
#!/usr/bin/env python3
"""
Complete Agent Flow: Search → Rank → Enrich → Add to Cart
"""
from api import dependencies
from ranking.reranker import SemanticReranker
from features.realtime_server import get_feature_server
from services.cart_service import CartService
from api.tools.shared import db
import logging

logger = logging.getLogger(__name__)


def agent_search_and_add_to_cart(query: str, quantity: int = 1):
    """
    Complete flow: Vector Search → Ranking → Feature Store → Cart

    Args:
        query: Search query (e.g., "cafea", "lapte")
        quantity: Number of items to add

    Returns:
        dict: Result with status and product info
    """

    # 0. Get authentication
    creds = db.get_credentials()
    if not creds:
        return {"error": "Not authenticated"}

    phpsessid = creds['session_cookie']

    # 1. VECTOR SEARCH: Get ~150 candidates (fast, approximate)
    logger.info(f"🔍 Searching for: {query}")
    search_engine = dependencies.get_search_engine()

    candidates = search_engine.search_by_text(
        query_text=query,
        num_neighbors=150  # Standard for ranking
    )

    if not candidates:
        return {"error": f"No products found for '{query}'"}

    logger.info(f"✓ Vector Search: {len(candidates)} candidates")

    # 2. RANKING API: Re-rank top candidates (precise)
    logger.info("📊 Re-ranking with Semantic Ranker...")
    reranker = SemanticReranker()

    ranked_results = reranker.rerank(
        query_text=query,
        candidates=candidates,
        top_n=5  # Get top 5 most relevant
    )

    logger.info(f"✓ Ranking API: Top {len(ranked_results)} ranked")

    # 3. FEATURE STORE: Enrich with metadata
    logger.info("💎 Enriching with Feature Store...")
    feature_server = get_feature_server()

    product_ids = [r['id'] for r in ranked_results]
    metadata = feature_server.get_product_metadata(product_ids)

    # Enrich results
    for result in ranked_results:
        pid = result['id']
        if pid in metadata:
            result.update(metadata[pid])
            result['product_id'] = pid

    logger.info(f"✓ Feature Store: {len(metadata)} products enriched")

    # Select best match
    product = ranked_results[0]

    logger.info(f"\n🎯 Best Match (Rank #{product.get('rank', 1)}):")
    logger.info(f"   {product['product_name']}")
    logger.info(f"   Similarity: {product.get('similarity_score', 0):.1%}")
    logger.info(f"   Price: {product.get('price', 'N/A')} RON")

    # Verify required fields
    if not product.get('product_id'):
        return {"error": "Missing product_id"}

    if not product.get('variant_id'):
        return {"error": "Missing variant_id"}

    # 4. ADD TO CART
    logger.info("🛒 Adding to cart...")
    result = CartService.add_product_to_cart(
        product_id=product['product_id'],
        variant_id=product['variant_id'],
        quantity=quantity,
        phpsessid=phpsessid,
        cookies={'PHPSESSID': phpsessid},
        store="carrefour_park_lake"
    )

    if result['status'] == 'success':
        logger.info(f"✅ SUCCESS: {result['message']}")
    else:
        logger.error(f"❌ FAILED: {result['message']}")

    return {
        "status": result['status'],
        "message": result['message'],
        "product": {
            "name": product['product_name'],
            "id": product['product_id'],
            "variant": product['variant_id'],
            "price": product.get('price'),
            "rank": product.get('rank'),
            "similarity": product.get('similarity_score')
        }
    }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    result = agent_search_and_add_to_cart("cafea", quantity=1)
    print(f"\nResult: {result}")
```

## Performance Metrics

| Step | Time | Description |
|------|------|-------------|
| Vector Search | ~2-3s | Find 150 candidates |
| Ranking API | ~0.5-1s | Re-rank to top 5 |
| Feature Store | <0.01s | Enrich 5 products |
| **Total** | **~3-4s** | Complete search |

## After Fix Completes

Once the embeddings regeneration finishes, the flow becomes even cleaner:

### Before (Current - Temporary)
```
Vector Search → Returns product names
→ Need BigQuery lookup for product_id
→ Then Feature Store for rest
```

### After (Fixed - Permanent)
```
Vector Search → Returns numeric product_id directly
→ Feature Store enriches immediately
→ No BigQuery lookup needed
```

**Performance improvement:** ~1 second faster

## Testing

### Test the complete flow
```bash
# Create test file
cat > test_complete_flow.py << 'EOF'
from api import dependencies
from ranking.reranker import SemanticReranker
from features.realtime_server import get_feature_server

# 1. Vector Search
search_engine = dependencies.get_search_engine()
candidates = search_engine.search_by_text("cafea", num_neighbors=150)
print(f"✓ Vector Search: {len(candidates)} candidates")

# 2. Ranking
reranker = SemanticReranker()
ranked = reranker.rerank("cafea", candidates, top_n=5)
print(f"✓ Ranking: Top {len(ranked)} results")

# 3. Feature Store
feature_server = get_feature_server()
ids = [r['id'] for r in ranked]
metadata = feature_server.get_product_metadata(ids)
print(f"✓ Feature Store: {len(metadata)} enriched")

# Display results
for i, r in enumerate(ranked, 1):
    pid = r['id']
    meta = metadata.get(pid, {})
    print(f"\n{i}. {meta.get('product_name', pid)}")
    print(f"   Score: {r.get('similarity_score', 0):.2f}")
    print(f"   Price: {meta.get('price', 'N/A')} RON")
EOF

python test_complete_flow.py
```

## Next Steps

1. **Wait for embeddings** (~13 minutes remaining)
2. **Sync Feature Store** with new data
3. **Test complete flow** with ranking
4. **Verify performance** meets requirements
5. **Deploy to production**

## Monitoring

### Check embeddings progress
```bash
tail -f /private/tmp/claude-501/-Users-radanpetrica-PFA-agents-agents-adk-mcp/tasks/b0f873f.output
```

### Check Feature Store sync
```bash
python features/debug_sync.py
```

### Test ranking API
```bash
python scripts/debug_ranking.py
```
