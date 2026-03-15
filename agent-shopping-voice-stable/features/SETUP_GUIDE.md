# Vertex AI Feature Store Setup Guide

## ⚠️ Important: Google Sheets Source Issue

If your BigQuery table is an **external table linked to Google Sheets**, you MUST create a native table copy first for reliable Feature Store performance.

### Why?

- Google Sheets queries are 10-30 seconds vs <1 second for native tables
- Feature Store hourly syncs may timeout with Sheets
- Risk of data inconsistency during manual Sheet edits

### Solution: Create Native Table

```bash
# Run in BigQuery Console (https://console.cloud.google.com/bigquery?project=formare-ai)
CREATE OR REPLACE TABLE `formare-ai.bringo_products_data.bringo_products_native`
AS
SELECT *
FROM `formare-ai.bringo_products_data.bringo_products`
WHERE product_name IS NOT NULL;
```

**Then use `bringo_products_native` as your Feature View source.**

---

## Step 1: Create Feature Online Store (Cloud Console)

1. Go to: <https://console.cloud.google.com/vertex-ai/feature-store?project=formare-ai>
2. Click **"Create Feature Online Store"**
3. Configure:
   - **Name**: `bringo-realtime-features`
   - **Region**: `europe-west1`
   - **Type**: **Optimized** (for <2ms latency)
   - **Labels**: `environment=production`, `use_case=product_similarity`
4. Click **Create**

---

## Step 2: Create Feature View

1. Click **"Create Feature View"**
2. Configure:
   - **Name**: `product_metadata_view`
   - **BigQuery Source**: `formare-ai.bringo_products_data.bringo_products_native`
   - **Entity ID Column**: `product_id`
   - **Sync Mode**: Manual (or Scheduled with `0 * * * *` for hourly)
   - **Labels**: `data_type=metadata`
3. Click **Create**

---

## Step 3: Trigger Manual Sync

### Option A: Cloud Console

If you set **Sync Mode** to "Scheduled", a **"Sync Now"** button will appear in the Feature View page.

### Option B: REST API (Works for Manual or Scheduled mode)

```bash
# Get your project number and feature view name from the Console
# Resource name format: projects/PROJECT_NUMBER/locations/REGION/featureOnlineStores/STORE_ID/featureViews/VIEW_ID

ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -X POST \
  "https://europe-west1-aiplatform.googleapis.com/v1/projects/845266575866/locations/europe-west1/featureOnlineStores/bringo_realtime_features/featureViews/product_metadata_view:sync" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json"
```

**Note**: Replace `845266575866` with your project number (visible in Console resource name)

**Success**: No output = sync triggered successfully

---

## ✅ Verify Sync Status

1. **Refresh** the Feature View page in Cloud Console
2. **Check the sync table** at bottom:
   - Status should show "Running" → "Success"
   - Length of data transfer shows row count when complete
   - First sync takes 5-10 minutes

---

## � Setup Automatic Hourly Sync

**Recommended for production:**

1. Edit Feature View
2. Change Sync config to **Scheduled**
3. Set cron: `0 * * * *` (every hour)
4. Save

This keeps your Feature Store automatically updated with fresh BigQuery data!

---

## 🧪 Test Feature Serving

After sync completes:

```python
python features/test_realtime_server.py
```

Your `realtime_server.py` will now fetch features with <2ms latency!
