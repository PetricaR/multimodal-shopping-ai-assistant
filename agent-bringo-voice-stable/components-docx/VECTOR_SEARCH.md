# ⚡ Vector Search: Infrastructure & Querying

The Vector Search component handles the "Heavy Lifting" of the search process. It uses **Vertex AI Vector Search (TreeAH)** to find neighbors among millions of vectors in milliseconds.

---

## 📄 `vector_search/index_manager.py`: Infrastructure Lifecycle

This script uses the **AI Platform SDK** to manage the cloud-side search engine.

### 1. The TreeAH Algorithm (Search Tree)

We use the **Tree-based Asymmetric Hashing (TreeAH)** algorithm.

* **Leaf Counting**: We configure `leafNodeEmbeddingCount: 500`. This controls how many vectors are stored in each "bucket" at the end of the search tree.
* **Search Depth**: `leafNodesToSearchPercent: 7`. During a search, the system doesn't check every bucket; it checks 7% of the most likely buckets. This is the secret to getting sub-200ms latency even at massive scale while maintaining >95% recall accuracy.

### 2. Auto-scaling Endpoints

The deployment logic (`deploy_index`, lines 143-184) ensures the Retailer's budget is protected:

* **Machine Type**: `e2-standard-2` (Optimal for most retail search loads).
* **Replicas**: Set to `min_replica: 1` and `max_replica: 3`. The index will automatically spin up more machines if traffic spikes, and scale back down to 1 machine at night to save costs.
* **Index Updates**: The `update_index` function (lines 228-254) allows for **Delta Updates**. When new products are added, we only upload the *new* embeddings to GCS and call `update_embeddings`. The system will re-build the tree in the background without taking the search API offline.

---

## 📄 `vector_search/search_engine.py`: High-Performance Retrieval

This is the runtime engine used by the FastAPI service.

### 1. Robust Connection Logic (`MatchServiceClient`)

While the Vertex SDK is easy to use, it can be slow for high-concurrency production queries. We implement the **Low-level `MatchServiceClient`** (lines 68-119):

* **Public Point Access**: We query the index endpoint via its **Public Domain Name** (e.g., `{ip}.europe-west1.vdb.vertexai.goog`).
* **gRPC Protocol**: This client uses gRPC over HTTP, which is significantly faster and more resource-efficient than standard REST APIs.

### 2. Multi-Faceted Filtering (`restricts`)

The `search_by_embedding` function supports **Boolean Hard Filters**:

* If `filter_in_stock` is passed as `True`, the search engine doesn't just find the nearest neighbors; it finds the nearest neighbors **that also satisfy** the `in_stock: true` property index.
* These filters are applied *during* the vector scan, meaning there is zero performance penalty for filtering.

### 3. Symmetric vs Non-Symmetric Search

The system supports three search patterns:

1. **Symmetric (Product-to-Product)**: Uses a full multimodal vector to find items that "look and feel" like the query item.
2. **Asymmetric (Text-to-Product)**: Uses a text-only embedding of the user's keywords (e.g., "blue bio tea") to find relevant items.
3. **Exclusion Search**: `search_by_product_id` automatically retrieves `N+1` results and **removes the original product ID** from the list (line 158). This ensures that a similarity search on item A doesn't just return item A as the first result.
