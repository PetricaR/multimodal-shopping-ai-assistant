# Vector Search Fix - Complete Guide

## Problem Diagnosis

Your Vector Search index is using **product names** as datapoint IDs instead of **numeric product_ids**:

```
❌ CURRENT STATE:
Vector Search returns: "Cafea Boabe Dallmayr Espresso 1Kg"
test_cart.py expects: "2388" (numeric product ID)
```

**Root Cause:** The embeddings file (`bringo_products_embeddings.json`) was generated with product names as IDs instead of numeric product_ids.

## Solution

You need to:
1. **Regenerate embeddings** with correct numeric product_id format
2. **Rebuild the vector index** with the new embeddings

## How to Fix

### Option 1: Automated Fix (Recommended)

Run the automated fix script:

```bash
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-live
python fix_vector_search_auto.py
```

**Time required:**
- Embedding generation: ~13 minutes (1550 products ÷ 120 req/min)
- Index rebuild: 45-90 minutes
- **Total: ~1-2 hours**

### Option 2: Manual Fix (Step by Step)

If you want more control:

1. **Regenerate embeddings:**
   ```bash
   python scripts/generate_embeddings.py
   ```

2. **Rebuild the index:**
   ```bash
   python scripts/update_index.py
   ```

## What Changed

### Before (Incorrect):
```json
{
  "id": "Cafea Boabe Dallmayr Espresso 1Kg",
  "embedding": [0.123, 0.456, ...],
  ...
}
```

### After (Correct):
```json
{
  "id": "2388",
  "embedding": [0.123, 0.456, ...],
  ...
}
```

## Verification

After the fix completes (wait for index rebuild to finish):

### 1. Check Index IDs

```bash
python diagnose_index.py
```

**Expected output:**
```
✅ Index is using NUMERIC product_id (CORRECT)
ID from vector search: 2388
Product ID (numeric): 2388
ID is numeric: True
```

### 2. Test Cart Functionality

```bash
python test_cart.py
```

**Expected output:**
```
✅ Resolved numeric id from field 'id': 2388
✅ Extracted variant_id: vsp-2-343-2403
✅ Add to Cart SUCCESS!
```

## Monitoring Progress

Monitor the index rebuild progress in Google Cloud Console:
```
https://console.cloud.google.com/vertex-ai/matching-engine/indexes?project=formare-ai
```

Look for the index `bringo-product-index-multimodal` - it should show status "UPDATING" and eventually "DEPLOYED".

## Files Modified

The fix will create/update these files:
- `gs://formare-ai-vector-search/embeddings/bringo_products_embeddings.jsonl` (new format)
- Vector Search Index: `bringo-product-index-multimodal` (rebuilt)

## Rollback (If Needed)

If something goes wrong, the old embeddings file is still available:
```
gs://formare-ai-vector-search/embeddings/bringo_products_embeddings.json
```

You can restore it by renaming back to `.jsonl` and rebuilding the index.

## Why This Happened

The embeddings were likely generated using an older version of the code that used product names as IDs. The correct implementation is in [batch_processor.py:70](embeddings/batch_processor.py#L70):

```python
return {
    'id': str(product['product_id']),  # ✅ Correct: uses numeric product_id
    'embedding': embedding,
    ...
}
```

## Next Steps

After verification succeeds:
1. Remove the temporary workaround from `test_cart.py` (lines 54-65)
2. Update any other code that depends on vector search results
3. The issue should be permanently fixed
