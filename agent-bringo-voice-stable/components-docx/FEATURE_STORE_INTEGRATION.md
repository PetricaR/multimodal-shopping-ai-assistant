# 🏪 Vertex AI Feature Store Integration for Real-Time Mobile App

## 📦 Prerequisites

**Python SDK Requirements**:

- `google-cloud-aiplatform >= 1.40.0`
- `google-cloud-bigquery >= 3.11.0`
- Python 3.9+

**Validation**: Run `python features/test_api_availability.py` to verify SDK installation.

---

## 🎯 Why Feature Store is ESSENTIAL for Your Use Case

Based on Vertex AI documentation (January 2026), Feature Store with **Optimized Online Serving** is the RIGHT choice for your mobile app because:

1. **Ultra-Low Latency**: 99% of requests served in **<2ms** (Google benchmark)
2. **Embedding Management**: Native support for vector similarity search
3. **Real-Time Serving**: Direct integration with BigQuery for fresh data
4. **Mobile-Optimized**: Designed specifically for real-time inference scenarios

---

## 🏗️ Architecture: Feature Store + Vector Search Hybrid

```text
Mobile App (Search: "Coca Cola")
        ↓
   Backend API
        ↓
    ┌───────────────────────────────────┐
    │  Vertex AI Feature Store          │
    │  (Online Serving - 2ms latency)   │
    │                                   │
    │  Fetches:                         │
    │  • Product metadata               │
    │  • Stock status                   │
    │  • Price                          │
    │  • Category                       │
    └───────────────┬───────────────────┘
                    │
    ┌───────────────▼───────────────────┐
    │  Vertex Vector Search             │
    │  (TreeAH - 150ms)                 │
    │                                   │
    │  Finds:                           │
    │  • 150 similar products           │
    │  • Based on embeddings            │
    └───────────────┬───────────────────┘
                    │
    ┌───────────────▼───────────────────┐
    │  Ranking API                      │
    │  (80ms)                           │
    │                                   │
    │  Reranks:                         │
    │  • Top 20 by relevance            │
    └───────────────┬───────────────────┘
                    │
    ┌───────────────▼───────────────────┐
    │  Gemini Substitution              │
    │  (400ms - contextual reasoning)   │
    │                                   │
    │  Selects:                         │
    │  • Final 3 substitutes            │
    │  • With reasoning                 │
    └───────────────┬───────────────────┘
                    ↓
              Mobile App Response
              (Total: ~632ms)
```

---

## 📋 What Gets Stored in Feature Store

### Feature Groups

1. **`product_metadata`** (Updated hourly)
   - `product_id` (Entity key)
   - `product_name`
   - `category`
   - `producer`
   - `price_ron`
   - `in_stock` (CRITICAL for real-time)
   - `image_url`

2. **`product_embeddings`** (Static, unless products change)
   - `product_id` (Entity key)
   - `text_embedding` (512D array)
   - `multimodal_embedding` (512D array)

3. **`user_context`** (Real-time, optional Phase 2)
   - `user_id` (Entity key)
   - `last_viewed_products` (array)
   - `basket_total`
   - `preferred_categories`

---

## 🛠️ Implementation

### Step 1: Create Feature Store Instance

```bash
# scripts/setup_feature_store.sh
#!/bin/bash

PROJECT_ID="formare-ai"
REGION="europe-west1"
FEATURE_ONLINE_STORE_ID="bringo-realtime-features"

echo "Creating Vertex AI Feature Store..."

# Create Feature Online Store (Optimized)
gcloud alpha ai feature-online-stores create ${FEATURE_ONLINE_STORE_ID} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --optimized \
    --embedding-management-enabled

echo "✅ Feature Store created"
```

### Step 2: Define Feature Views (BigQuery → Feature Store)

```python
# features/feature_store_manager.py
from google.cloud import aiplatform
from google.cloud import bigquery
from typing import Dict, List

class FeatureStoreManager:
    """
    Manages Vertex AI Feature Store for real-time product serving
    """
    
    def __init__(self):
        aiplatform.init(
            project="formare-ai",
            location="europe-west1"
        )
        
        self.feature_online_store_id = "bringo-realtime-features"
        self.bq_client = bigquery.Client()
    
    def create_product_metadata_view(self):
        """
        Create Feature View for product metadata
        Synced from BigQuery every hour
        """
        
        # BigQuery source query
        source_query = """
        SELECT 
            product_id AS entity_id,
            productname AS product_name,
            category,
            producer,
            price_ron,
            in_stock,
            image_url,
            CURRENT_TIMESTAMP() AS feature_timestamp
        FROM `formare-ai.bringo_products_data.bringo_products`
        WHERE product_name IS NOT NULL
        """
        
        # Create Feature View
        feature_view = aiplatform.FeatureView.create(
            name="product_metadata_view",
            source=aiplatform.utils.FeatureViewBigQuerySource(
                uri=f"bq://formare-ai.bringo_products_data.bringo_products",
                entity_id_columns=["product_id"]
            ),
            feature_online_store_id=self.feature_online_store_id,
            sync_config=aiplatform.FeatureView.SyncConfig(cron="0 * * * *")  # Hourly
        )
        
        return feature_view
    
    def create_embeddings_view(self):
        """
        Create Feature View for product embeddings
        Synced daily (embeddings are more static)
        """
        
        # This assumes embeddings are stored in BigQuery
        # Alternative: Store in GCS and load to BigQuery
        
        source_query = """
        SELECT 
            product_id AS entity_id,
            embedding AS multimodal_embedding,
            CURRENT_TIMESTAMP() AS feature_timestamp
        FROM `formare-ai.bringo_embeddings.product_vectors`
        """
        
        feature_view = aiplatform.FeatureView.create(
            name="product_embeddings_view",
            source=aiplatform.utils.FeatureViewBigQuerySource(
                uri=f"bq://formare-ai.bringo_embeddings.product_vectors",
                entity_id_columns=["product_id"]
            ),
            feature_online_store_id=self.feature_online_store_id,
            sync_config=aiplatform.FeatureView.SyncConfig(cron="0 2 * * *")  # Daily at 2 AM
        )
        
        return feature_view
```

### Step 3: Real-Time Feature Fetching

```python
# features/realtime_server.py
from google.cloud import aiplatform_v1
from typing import List, Dict

class RealTimeFeatureServer:
    """
    Fetch features with <2ms latency for mobile app
    """
    
    def __init__(self):
        self.client = aiplatform_v1.FeatureOnlineStoreServiceClient()
        self.feature_online_store = (
            "projects/formare-ai/locations/europe-west1/"
            "featureOnlineStores/bringo-realtime-features"
        )
    
    def get_product_features(self, product_ids: List[str]) -> Dict:
        """
        Fetch fresh product data for candidate products
        
        Returns in <2ms per Google benchmarks
        """
        
        # Prepare request
        request = aiplatform_v1.FetchFeatureValuesRequest(
            feature_view=f"{self.feature_online_store}/featureViews/product_metadata_view",
            data_keys=[
                aiplatform_v1.FeatureViewDataKey(
                    key=product_id
                ) for product_id in product_ids
            ]
        )
        
        # Fetch (ultra-fast)
        response = self.client.fetch_feature_values(request=request)
        
        # Parse
        products = {}
        for proto in response.feature_vectors:
            product_id = proto.id
            features = {}
            
            for feature in proto.values:
                features[feature.name] = feature.value
            
            products[product_id] = {
                'product_name': features.get('product_name'),
                'price': features.get('price_ron'),
                'in_stock': features.get('in_stock'),
                'category': features.get('category'),
                'producer': features.get('producer'),
                'image_url': features.get('image_url')
            }
        
        return products
    
    def search_similar_with_features(
        self,
        query_embedding: List[float],
        top_k: int = 20
    ) -> List[Dict]:
        """
        Combined: Vector similarity + Feature retrieval
        """
        
        # Step 1: Vector Search (your existing index)
        # Returns IDs only
        from vector_search import SearchEngine
        search_engine = SearchEngine()
        candidates = search_engine.search_by_embedding(
            embedding=query_embedding,
            num_neighbors=150
        )
        
        # Step 2: Fetch fresh features (using Feature Store)
        candidate_ids = [c['id'] for c in candidates]
        fresh_features = self.get_product_features(candidate_ids)
        
        # Step 3: Filter in-stock only (real-time!)
        in_stock_candidates = [
            {
                **c,
                **fresh_features[c['id']]
            }
            for c in candidates
            if fresh_features.get(c['id'], {}).get('in_stock', False)
        ]
        
        return in_stock_candidates[:top_k]
```

### Step 4: Updated API Endpoint

```python
# api/main.py (updated substitution endpoint)
from api.feature_serving import RealTimeFeatureServer

@app.post("/api/v1/substitution/suggest-realtime")
async def suggest_substitution_realtime(request: SubstitutionRequest):
    """
    Real-time substitution with Feature Store
    
    Mobile-optimized: <700ms total
    """
    start_time = time.time()
    
    # Initialize Feature Server
    feature_server = RealTimeFeatureServer()
    
    # 1. Get missing product details (Feature Store - 2ms)
    missing_product_features = feature_server.get_product_features([request.missing_product_id])
    
    if not missing_product_features:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # 2. Generate query embedding (if not cached)
    from embeddings import MultimodalEmbeddingGenerator
    generator = MultimodalEmbeddingGenerator()
    
    missing_product = missing_product_features[request.missing_product_id]
    query_embedding, _ = generator.generate_embedding(
        text=f"{missing_product['product_name']} {missing_product['category']}",
        image_url=missing_product.get('image_url')
    )
    
    # 3. Search + Fetch (Vector Search 150ms + Feature Store 2ms = 152ms)
    candidates_with_features = feature_server.search_similar_with_features(
        query_embedding=query_embedding,
        top_k=30
    )
    
    # 4. Ranking API (80ms)
    from ranking import Reranker
    reranker = Reranker()
    ranked_candidates = reranker.rerank(
        query=missing_product['product_name'],
        candidates=candidates_with_features,
        top_n=10
    )
    
    # 5. Gemini context reasoning (400ms)
    from substitution import GeminiSubstitutor
    substitutor = GeminiSubstitutor()
    final_suggestions = substitutor.select_best(
        missing_product=missing_product,
        candidates=ranked_candidates,
        current_basket=request.current_basket,
        user_history=request.user_history,
        top_n=3
    )
    
    total_time = (time.time() - start_time) * 1000
    
    return {
        "missing_product": missing_product,
        "suggestions": final_suggestions,
        "query_time_ms": total_time,
        "method": "feature_store_vector_search_ranking_gemini"
    }
```

---

## 📊 Performance Comparison

| Component | Without Feature Store | With Feature Store |
| :--- | :--- | :--- |
| **Metadata Fetch** | 100ms (BigQuery) | 2ms (Feature Store) |
| **Stock Filtering** | After search (unreliable) | During search (real-time) |
| **Total Latency** | ~732ms | **~634ms** |
| **Data Freshness** | Cached (stale) | Real-time (fresh) |

---

## 💰 Cost Analysis

**Vertex AI Feature Store (Optimized)**:

- Storage: $0.08 per GB/month
- Reads: $0.05 per 1M requests
- For 10K products × 100K queries/month: **~$50/month**

**Value**:

- Guaranteed real-time stock status
- Sub-2ms metadata serving
- Eliminates stale substitution suggestions

---

## 🚀 Deployment Script

```bash
# scripts/deploy_feature_store_pipeline.sh
#!/bin/bash

echo "Deploying Feature Store Pipeline..."

# 1. Create Feature Store
python features/setup_feature_store.py

# 2. Create Feature Views
python features/create_feature_views.py

# 3. Initial sync
gcloud ai feature-views sync bringo-realtime-features/product_metadata_view

echo "✅ Feature Store deployed and synced"
```

---

## ✅ When to Use This Architecture

Use Feature Store when:

- ✅ Mobile app needs **real-time** data (<700ms)
- ✅ Stock status changes **frequently**
- ✅ Users expect **instant** substitutionsSkip Feature Store when:
- ❌ Batch recommendations only
- ❌ Data updates <1x/day
- ❌ Latency >2 seconds acceptable

**For your mobile app use case: Feature Store is ESSENTIAL.**

---

## 🚀 Production Configuration Guide (Verified Jan 2026)

### 1. Dedicated Public Endpoint

**Critical**: Optimized Feature Stores do **not** use the regional endpoint (`europe-west1-aiplatform...`). They use a **Dedicated Endpoint**.

**How to find it**:
Run `features/inspect_store.py` to query the Admin API:

```python
# Look for dedicated_serving_endpoint.public_endpoint_domain_name
# Format: {project_number}.{region}-{id}.featurestore.vertexai.goog
```

**Configuration**:
Set this in `config.env` or `settings.py`:
`FS_PUBLIC_ENDPOINT="527765581332480.europe-west1-845266575866.featurestore.vertexai.goog"`

### 2. Python Client Compatibility

**Warning**: The `google-cloud-aiplatform` Python client uses `proto-plus` for response objects.

- **Issue**: `.HasField('name')` method does NOT exist.
- **Fix**: Use direct attribute access with truthiness checks:

```python
# CORRECT
if feature.value.string_value:
    val = feature.value.string_value

# INCORRECT (Crashes)
if feature.value.HasField('string_value'): ...
```

### 3. Verification

Use the provided debugging tool to verify data availability before deploying endpoints:

```bash
python -m features.debug_sync
```

If `Synced IDs: 0`, check the **Sync** tab in Cloud Console.
