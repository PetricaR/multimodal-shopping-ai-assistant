# 🚀 Redis Caching Layer for Product Metadata

## Why Redis Instead of Feature Store?

For your use case (product similarity search), a **Redis cache** provides the perfect balance:

- **Sub-millisecond latency** for repeated product lookups
- **No infrastructure complexity** of a Feature Store
- **Cost-effective** (~$20/month for Cloud Memorystore)
- **Drop-in replacement** for your existing BigQuery caching

---

## Architecture Enhancement

```
Current Flow:
API → BigQuery (100ms) → Vector Search (150ms) → Ranking (80ms) = 330ms

With Redis:
API → Redis (2ms) → Vector Search (150ms) → Ranking (80ms) = 232ms
     ↓ (on cache miss)
   BigQuery (100ms)
```

---

## Implementation

### 1. Cloud Memorystore Setup (Redis)

```bash
# Create a Redis instance
gcloud redis instances create product-metadata-cache \
    --size=1 \
    --region=europe-west1 \
    --redis-version=redis_7_0 \
    --tier=basic
```

### 2. Updated BigQuery Client with Redis

```python
# data/redis_cache_client.py
import redis
import json
from typing import Dict, Optional, List
from config.settings import settings

class ProductMetadataCache:
    """
    Redis-backed cache for product metadata
    Reduces BigQuery latency from ~100ms to ~2ms for cache hits
    """
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True
        )
        self.ttl = 3600  # 1 hour cache TTL
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get product from cache"""
        cached = self.redis_client.get(f"product:{product_id}")
        if cached:
            return json.loads(cached)
        return None
    
    def set_product(self, product_id: str, product_data: Dict):
        """Cache product data"""
        self.redis_client.setex(
            f"product:{product_id}",
            self.ttl,
            json.dumps(product_data)
        )
    
    def get_products_batch(self, product_ids: List[str]) -> Dict[str, Dict]:
        """Batch get with pipeline for efficiency"""
        pipeline = self.redis_client.pipeline()
        for pid in product_ids:
            pipeline.get(f"product:{pid}")
        
        results = pipeline.execute()
        
        cached_products = {}
        for pid, cached in zip(product_ids, results):
            if cached:
                cached_products[pid] = json.loads(cached)
        
        return cached_products
    
    def set_products_batch(self, products: Dict[str, Dict]):
        """Batch set with pipeline"""
        pipeline = self.redis_client.pipeline()
        for pid, product_data in products.items():
            pipeline.setex(
                f"product:{pid}",
                self.ttl,
                json.dumps(product_data)
            )
        pipeline.execute()
```

### 3. Enhanced BigQuery Client

```python
# data/bigquery_client.py (updated)
from data.redis_cache_client import ProductMetadataCache

class BigQueryClient:
    def __init__(self):
        # ... existing init ...
        self.cache = ProductMetadataCache()  # Redis cache
    
    def get_products_by_ids(self, product_ids: List[str]) -> Dict[str, Dict]:
        """
        Enhanced with Redis caching
        Cache hit: ~2ms
        Cache miss: ~100ms (BigQuery) + cache write
        """
        if not product_ids:
            return {}
        
        # Step 1: Check Redis
        cached_products = self.cache.get_products_batch(product_ids)
        missing_ids = [pid for pid in product_ids if pid not in cached_products]
        
        logger.info(f"Redis cache hit: {len(cached_products)}/{len(product_ids)}")
        
        # Step 2: Fetch missing from BigQuery
        if missing_ids:
            query = f"SELECT * FROM `{self.table}` WHERE product_id IN UNNEST(@product_ids)"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("product_ids", "INT64", 
                                                [int(pid) for pid in missing_ids])
                ]
            )
            df = self.client.query(query, job_config=job_config).to_dataframe()
            
            # Step 3: Process and cache new results
            fresh_products = {}
            for _, row in df.iterrows():
                product = {
                    'product_id': str(row['product_id']),
                    'combined_text': self._combine_text_fields(row),
                    'image_url': row.get('image_url'),
                    'metadata': {
                        'product_name': str(row.get('product_name', '')),
                        'category': str(row.get('category', '')),
                        'producer': str(row.get('producer', '')),
                        'in_stock': bool(row.get('in_stock', False)),
                        'price': float(row.get('price_ron', 0.0)) if pd.notna(row.get('price_ron')) else None,
                    }
                }
                fresh_products[product['product_id']] = product
            
            # Cache the new products
            if fresh_products:
                self.cache.set_products_batch(fresh_products)
            
            # Merge with cached results
            cached_products.update(fresh_products)
        
        return cached_products
```

---

## Configuration

Add to `config/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Redis Cache Settings
    REDIS_HOST: str = "10.0.0.3"  # From Cloud Memorystore
    REDIS_PORT: int = 6379
    REDIS_CACHE_TTL: int = 3600  # 1 hour
```

---

## Performance Impact

| Scenario | Before (BigQuery) | After (Redis) | Improvement |
|:---------|:------------------|:--------------|:------------|
| **Cold Start** | 100ms | 100ms | 0% (first query) |
| **Warm Cache (80% hit rate)** | 100ms | 22ms | **78% faster** |
| **Hot Product (100% hit)** | 100ms | 2ms | **98% faster** |

### Real-World Example

- **Search for popular product** (e.g., "Coca Cola"):
  - OLD: 330ms total
  - NEW: **234ms total** (96ms saved)

---

## Cost Analysis

**Cloud Memorystore (Redis)**:

- Tier: Basic
- Size: 1GB
- Cost: ~$25/month
- QPS: >10,000

**Vertex AI Feature Store (Alternative)**:

- Online serving: ~$100/month (minimum)
- Complexity: High (requires sync pipelines)
- Latency: Similar to Redis (~2ms)

**Verdict**: Redis saves **75% cost** with zero complexity.

---

## Deployment

```bash
# 1. Create Redis instance
./scripts/setup_redis_cache.sh

# 2. Update dependencies
pip install redis

# 3. Deploy updated API
gcloud run deploy product-similarity-api \
    --set-env-vars REDIS_HOST=10.0.0.3
```

---

## When to Graduate to Feature Store

Migrate to Vertex AI Feature Store when:

1. You add **>50 dynamic features** (user behavior, real-time stats)
2. You need **feature versioning** for A/B tests
3. You have **multiple ML models** sharing features
4. You need **training-serving consistency** guarantees

For your current product similarity use case, **Redis is the optimal choice**.
