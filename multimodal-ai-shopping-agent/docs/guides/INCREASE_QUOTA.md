# How to Increase Vertex AI Quotas

## Current Quota Issue

**Error:** `429 Quota exceeded for aiplatform.googleapis.com/online_prediction_requests_per_base_model`

**Model:** `multimodalembedding@001`

This limits how fast you can generate embeddings.

## Increase Quota (2 Methods)

### Method 1: Google Cloud Console (Recommended)

1. **Go to Quotas Page:**
   ```
   https://console.cloud.google.com/iam-admin/quotas?project=formare-ai
   ```

2. **Search for Quota:**
   - In the search box, type: `Vertex AI API`
   - Filter by: `multimodalembedding` or `online prediction`

3. **Find the Right Quota:**
   Look for:
   - **Name:** "Online prediction requests per base model per minute"
   - **Service:** Vertex AI API
   - **Dimensions:** `base_model:multimodalembedding`

4. **Request Increase:**
   - Click the checkbox next to the quota
   - Click "EDIT QUOTAS" button (top of page)
   - Enter new limit (e.g., `300` or `600` requests per minute)
   - Add business justification: "Generating embeddings for product search system"
   - Submit request

5. **Wait for Approval:**
   - Usually approved within 24-48 hours
   - You'll get email notification

### Method 2: gcloud CLI

```bash
# Set your project
gcloud config set project formare-ai

# List current quotas
gcloud compute project-info describe --project=formare-ai

# Request quota increase (example)
gcloud alpha services quota update \
  --service=aiplatform.googleapis.com \
  --consumer=projects/formare-ai \
  --metric=aiplatform.googleapis.com/online_prediction_requests_per_base_model \
  --unit=1/min/{base_model} \
  --dimensions=base_model=multimodalembedding \
  --value=300
```

## Current Quota Limits

Based on the errors, your current limits are approximately:

| Quota | Current | Recommended |
|-------|---------|-------------|
| Requests per minute | ~120 | 300-600 |
| Requests per day | Unknown | 50,000+ |

## Why Increase?

**Current Performance:**
- 120 requests/min = ~2 requests/sec
- 1557 products ÷ 120 req/min = ~13 minutes
- But with quota errors: 30+ minutes

**After Increase (300 req/min):**
- 300 requests/min = ~5 requests/sec
- 1557 products ÷ 300 req/min = ~5 minutes
- Much faster regeneration

## Alternative: Use Batch Processing

If quota increase is denied or takes too long:

```python
# Modify batch_processor.py to use slower rate
EMBEDDING_RATE_LIMIT = 100  # Reduce from 120 to 100

# Or add exponential backoff for quota errors
# (Already implemented in the code)
```

## Check Current Quota Usage

```bash
# View quota usage
gcloud logging read \
  'protoPayload.methodName="google.cloud.aiplatform.v1.PredictionService.Predict"' \
  --limit=100 \
  --format=json \
  --project=formare-ai
```

## Status After Quota Increase

Once approved:
- Embeddings will generate 2-3x faster
- Less quota errors during regeneration
- Smoother pipeline operation

## Links

- **Quota Console:** https://console.cloud.google.com/iam-admin/quotas?project=formare-ai
- **Vertex AI Quotas Docs:** https://cloud.google.com/vertex-ai/docs/quotas
- **Request Form:** In console (Edit Quotas button)
