# Quick Start Guide - Bringo Product Similarity (Multimodal)

## Prerequisites (5 minutes)

```bash
# 1. GCP Authentication
gcloud auth application-default login
gcloud config set project formare-ai

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings
```

## Step-by-Step Setup

### Step 1: Generate Embeddings (2-4 hours, automated)

```bash
python scripts/generate_embeddings.py
```

**What happens**:
- Fetches products from BigQuery
- Downloads product images (with caching)
- Generates 512D multimodal embeddings (image + text)
- Saves to GCS in JSONL format
- Progress bar shows: ~10,000 products/hour

**Output**: `gs://formare-ai-vector-search/embeddings/bringo_products.jsonl`

### Step 2: Create Vector Search Index (45-90 minutes, automated)

```bash
python scripts/create_index.py
```

**What happens**:
- Creates TreeAH index (COSINE_DISTANCE, 512D)
- Builds search structure (approximateNeighbors=150)
- Deploys to public endpoint with auto-scaling
- Progress monitoring included

**Output**: Index deployed and ready to query

### Step 3: Start API Server (instant)

```bash
python -m api.main
```

**Access**: http://localhost:8080/docs

### Step 4: Test Product Similarity

```python
import requests

# Find similar products
response = requests.post(
    "http://localhost:8080/api/v1/search",
    json={
        "product_id": "12345",  # Your product ID
        "top_k": 20,
        "use_ranking": True      # Enable Ranking API
    }
)

results = response.json()
print(f"Found {len(results['similar_products'])} similar products")

# Top result
top = results['similar_products'][0]
print(f"#{1}: {top['product_name']}")
print(f"   Similarity: {top['similarity_score']:.3f}")
print(f"   Relevance: {top['ranking_score']:.3f}")
```

## Architecture Flow

```
1. Input Product → 
2. Fetch from BigQuery → 
3. Generate Multimodal Embedding (image+text, 512D) → 
4. Vector Search (retrieve 150 similar candidates) → 
5. Ranking API (rerank top 20 by relevance) → 
6. Return Results
```

## Troubleshooting

### "Image download failed"
→ Check image_url column in BigQuery
→ Review logs: `tail -f logs/embedding_generation.log`

### "Index build takes too long"
→ Normal for first time (45-90 min)
→ Monitor: `gcloud ai index-endpoints list --region=europe-west1`

### "Ranking API error"
→ Ensure Discovery Engine API is enabled
→ Check quota: 1000 requests/day (default)

## Performance Expectations

| Metric | Expected Value |
|--------|----------------|
| Embedding generation | ~10K products/hour |
| Index build time | 45-90 minutes |
| Query latency (P99) | <300ms |
| Recall@20 | >95% |

## Cost Estimate

**Setup** (one-time): $3-5  
**Monthly** (10K products, 100K queries): $55-85

## Next Steps

1. ✅ Verify embeddings quality: `python scripts/validate_embeddings.py`
2. ✅ Test search accuracy: Compare results with manual curation
3. ✅ Monitor performance: Set up logging and metrics
4. ✅ Production deployment: Use Cloud Run or GKE

## Support

- Review logs in `logs/` directory
- Enable debug: Set `LOG_LEVEL=DEBUG` in .env
- Check Google docs: https://cloud.google.com/vertex-ai/docs
