# Feature Store API Endpoints - Quick Reference

## 📍 New Endpoints Created

### 1. Feature Store + Gemini (Full AI Pipeline)

```
POST /api/v1/feature-store/substitution/with-gemini
```

**Performance**: ~634ms

- Feature Store: 2ms
- Vector Search: 150ms  
- Ranking API: 80ms
- Gemini: 400ms

**Use Case**: Best substitution quality with context-aware reasoning

---

### 2. Feature Store Only (No Gemini)

```
POST /api/v1/feature-store/substitution/no-gemini
```

**Performance**: ~234ms (63% faster!)

- Feature Store: 2ms
- Vector Search: 150ms
- Ranking API: 80ms

**Use Case**: When speed is critical and basic similarity is sufficient

---

## 🧪 Testing

```bash
# Test with Gemini
curl -X POST "http://localhost:8000/api/v1/feature-store/substitution/with-gemini" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "missing_product_id": "12345",
    "top_k": 10,
    "current_basket": [],
    "user_history": []
  }'

# Test without Gemini (faster)
curl -X POST "http://localhost:8000/api/v1/feature-store/substitution/no-gemini" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "missing_product_id": "12345",
    "top_k": 10
  }'
```

---

## 📊 Response Format

Both endpoints return:

```json
{
  "missing_product": {
    "product_name": "...",
    "category": "...",
    "price_ron": 15.99,
    "in_stock": false
  },
  "suggestions": [
    {
      "id": "67890",
      "product_name": "...",
      "confidence": 0.95,
      "reasoning": "...",
      "price_difference": 2.50
    }
  ],
  "query_time_ms": 234.56,
  "method": "feature_store_vector_ranking",
  "metadata": {
    "step_1_feature_store_ms": 1.8,
    "step_2_vector_search_ms": 152.3,
    "step_3_feature_store_ms": 1.9,
    "step_4_ranking_ms": 78.5,
    "gemini_used": false
  }
}
```

---

## ⚙️ Files Created

1. **`api/feature_store_helpers.py`** - Feature Server initialization
2. **`api/feature_store_endpoints.py`** - Two new endpoints
3. **`api/main.py`** - Updated to register new endpoints

---

## 🚀 Starting the Server

```bash
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-final
python -m api.main
```

Visit: <http://localhost:8000/docs> to see both new endpoints!
