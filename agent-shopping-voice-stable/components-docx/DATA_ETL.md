# 📊 Data & ETL: Implementation Details

The Data layer is responsible for translating raw database rows into "AI-ready" context objects and managing the high-speed retrieval of product metadata.

---

## 📄 `data/bigquery_client.py`: The BigQuery Gateway

This file implements the `BigQueryClient` class, which serves as the interface between the application and the product catalog stored in Google BigQuery.

### 1. The Context Fusion Algorithm (`_combine_text_fields`)

The effectiveness of the Multimodal Embedding depends on the quality of the text context. This function (lines 44-65) performs a deterministic "fusion" of product attributes:

* **Priority 1: Product Name**: Placed at the very top of the string.
* **Priority 2: Fixed Attributes**: Explicitly labeled strings like `Categorie: {cat}` and `Producător: {producer}`. This labels-based approach helps the LLM/Embedding model understand specific facets.
* **Priority 3: Ingredients & Origin**: Added only if not null.
* **Constraint Management**: The final string is capped at **1000 characters**. This is critical because the Vertex AI `contextual_text` parameter has a hard 1024-token limit. Truncation ensures the API call never errors out due to long manufacturer descriptions.

### 2. High-Performance Metadata Retrieval

* **Batched Retrieval (`get_products_by_ids`)**: When the Vector Search returns 150 candidate IDs, this function is called.
  * **The Problem**: Searching for 150 IDs using 150 `SELECT` statements is extremely slow.
  * **The Solution**: We use a single query with an `UNNEST` parameter:
      `SELECT * FROM TABLE WHERE product_id IN UNNEST(@product_ids)`.
  * This reduces the round-trip time from BigQuery to a few hundred milliseconds, regardless of the list size.
* **In-Memory Caching**:
  * The client maintains a `_cache` dictionary (lines 33, 37-42).
  * Every product fetched by ID is automatically stored.
  * This is highly effective for "Similar To This" features where the same query product is fetched repeatedly by different users in a short window.

### 3. Authentication & External Tables

The client is initialized with **specific OAuth scopes**:

```python
SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/drive.readonly",
]
```

* **Why?**: Retailer datasets often link BigQuery external tables to files on Google Drive (e.g., promotional spreadsheets). Without the `drive.readonly` scope, the client would fail to read those tables even with service account permissions.

---

## 🏗️ Data Flow for Search

1. **Request**: API asks for metadata for IDs `[A, B, C]`.
2. **Lookup**: `BigQueryClient` checks the local cache for `A, B, C`.
3. **Query**: If missing, it constructs one `UNNEST` query for the missing IDs.
4. **Processing**: It runs `_combine_text_fields` on the results.
5. **Response**: Returns a dictionary mapping IDs to `ProductInfo` compatible objects.

---

## 🚀 4. Feature Store Sync (Real-Time Substitution)

For the **Substitution API**, we bypass the direct BigQuery client in favor of **Vertex AI Feature Store**.

* **Mechanism**: A `FeatureView` (`product_metadata_view`) automatically syncs data from BigQuery to the Online Store (Bigtable-backed).
* **Frequency**: Syncs run hourly (cron: `0 * * * *`).
* **Latency**: Reduces fetching time from ~100ms (BigQuery) to **<2ms** (Feature Store).
* **Consistency**: ensuring the mobile app always sees the latest `in_stock` status without hitting BigQuery quota limits.
