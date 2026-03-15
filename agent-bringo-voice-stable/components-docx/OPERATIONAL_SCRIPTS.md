# 🚀 Operational & Automation Scripts: Execution Guide

These scripts are the tools for deploying, maintaining, and observing the Multimodal Similarity engine. They are designed to be run from the command line during the setup and maintenance phases.

---

## 📝 1. `generate_embeddings.py` (The ETL Runner)

This script is the first step of the entire system. It extracts data from BigQuery and converts it into GCS vectors.

### Workflow Details

1. **BigQuery Fetch**: Pulls all products with a valid name.
2. **Multimodal Generation**: For each product, it downloads the image, resizes it, and sends it to Vertex AI along with the text context.
3. **JSONL Streaming**: It builds the JSONL lines one-by-one and uploads the final aggregate to: `gs://{STAGING_BUCKET}/embeddings/retailer_products.jsonl`.
4. **Audit Logs**: Every success and failure is recorded in `logs/embedding_generation.log`. Check this after a run to see how many images failed the download process (~5% is normal).

---

## 📝 2. `create_index.py` (The Builder)

This script instructs Vertex AI to build the high-scale search infrastructure.

### Execution Parameters

* **TreeAH Algorithm**: Configured for `leafNodesToSearchPercent: 7`.
* **Metadata**: Links the GCS URI generated in Step 1 to the Index.
* **Time Notice**: This script initiates a **Long-Running Operation (LRO)**. It will output a Cloud URL where you can monitor the 45–90 minute build progress.
* **Usage**: `python scripts/create_index.py`

---

## 📝 3. `deploy_index.py` & `update_index.py` (Lifecycle)

* **Deploy**: Once the build from Step 2 is complete, run this to attach the index to an endpoint. It configures the machine type (`e2-standard-2`) and auto-scaling ranges (1–3 replicas).
* **Update**: Run this whenever the product catalog changes significantly. It performs a **Batch Update** of the embeddings, refreshing the search tree without needing to delete and recreate the endpoint.

---

## 📝 4. Diagnostic & Utility Scripts

* **`test_vector_search.py`**:
  * **The Problem**: Searching via the API involves many layers (API -> Enrich -> Ranking).
  * **The Utility**: This script queries the gRPC endpoint **Directly**.
  * **Value**: Used to diagnose networking issues or "Empty Results" errors in the raw index.
* **`rename_file.py`**: A utility script used to ensure metadata consistency across the GCS bucket during migrations.
* **`example_usage.py`**: This is a production-simulated search client.
  * Sends real JSON payloads to `localhost:8080`.
  * Demonstrates how to handle the `query_time_ms` and `ranking_score` in a real application.
  * **Usage**: `python example_usage.py` (Ensure the API is started first).

---

## 📝 5. Feature Store Management (Real-Time)

Scripts for managing the low-latency serving layer:

* **`features/setup_feature_store.py`**:
  * Creates the **Optimized Online Store** and Feature Views.
  * Run once during initial setup.
* **`features/inspect_store.py`**:
  * **Critical**: Queries the Admin API to find the **Dedicated Public Endpoint**.
  * Run this to populate `FS_PUBLIC_ENDPOINT` in `settings.py`.
* **`features/debug_sync.py`**:
  * **Diagnostic**: Verifies if data has successfully synced from BigQuery to the Online Store.
  * Use this if the API returns "Product Not Found".

---

## 📁 Log Directory Structure

Scripts output to the `logs/` folder for production auditing:

* `embedding_generation.log`: Tracks rate-limiting hits and image corruption.
* `index_creation.log`: Stores gcloud operation IDs for disaster recovery.
* `reranker_debug.log`: (Optional) Stores raw payloads sent to the Ranking API for precision tuning.
