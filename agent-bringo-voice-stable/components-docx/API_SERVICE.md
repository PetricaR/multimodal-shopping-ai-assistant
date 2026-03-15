# 🌐 API Service: Deep-Dive Documentation

The API Service is the central nervous system of the Multimodal Product Similarity engine. Built with **FastAPI**, it serves as the orchestration layer between the client applications and the three distinct layers of Google Vertex AI.

---

## 📄 `api/main.py`: The Orchestration Core

This script manages the high-concurrency lifecycle of search requests. It is designed to be stateless, scalable, and highly observable.

### 1. High-Performance Design

* **Asynchronous Endpoints**: Every endpoint (`/search`, `/suggest`) is `async`, allowing the server to handle multiple requests simultaneously while waiting for I/O from Vertex AI or BigQuery.
* **Lazy Component Loading**:
  * To ensure lightning-fast cold starts (crucial for Cloud Run/Kubernetes), components like `SearchEngine`, `Reranker`, and `BigQueryClient` are not initialized until the first request hits an endpoint.
  * This is managed via global `_variable` checks and `get_component()` functions (lines 66-96).
* **CORS & Middleware**:
  * Includes a `CORSMiddleware` configured to allow cross-origin requests from web frontends.
  * Features a custom `verify_api_key` dependency (lines 52-58) that secures the API using a header check (`X-API-Key`). If `API_AUTH_KEY` is not set in the environment, it defaults to a permissive mode.

### 2. Search Pipeline Logic (`/api/v1/search`)

The `/search` endpoint implements the optimized **"Retrieve-and-Rank"** pattern:

1. **Step 1: Embedding Conversion**: Converts the query (text or product image) into a 512D vector via `generator.py`.
2. **Step 2: TreeAH Retrieval**: Queries the Vector Search Endpoint to find 150 candidates. If filtering by stock is enabled, it applies a `MatchServiceClient` restrict set (line 160).
3. **Step 3: Metadata Enrichment**: Uses a **batched query** in BigQuery to fetch full product details (name, category, price) for the 150 candidate IDs (lines 191-208).
4. **Step 4: Semantic Reranking**: Sends candidates to the Ranking API. This stage corrects "approximate" matches by comparing the query text against the candidate's rich description.
5. **Step 5: Pydantic Serialization**: Maps the internal dictionaries to the `SearchResponse` model, ensuring strict Type safety and clean JSON output.

---

## 📄 `api/models.py`: The Data Contract

This file defines the strict JSON schemas that the API accepts and returns. It uses **Pydantic v2** for validation.

### 1. Input Validation (`SearchRequest`)

* `product_id`: Optional string. If provided, the API performs multimodal search (Image + Text).
* `query_text`: Optional string. If provided, the API performs semantic text search.
* `top_k`: Integer (range 1-100). Defaults to 20.
* `use_ranking`: Boolean. Controls whether the +80ms Ranking API stage is activated.

### 2. Output Richness (`ProductInfo`)

The response doesn't just return IDs; it provides a comprehensive product profile:

* **Core Metadata**: Name, Category, Producer, Image URL, Price, Stock Status.
* **AI Metrics**:
  * `similarity_score`: Visual/Semantic closeness from Vector Search (0.0 to 1.0).
  * `ranking_score`: Fine-grained relevance from Ranking API (0.0 to 1.0).
  * `gemini_confidence`: Reasoning reliability score (only for substitutions).

---

## ⚖️ Error Handling & Observability

* **HTTP Exceptions**: Custom handlers manage common failures:
  * `400 Bad Request`: Missing both ID and Text.
  * `404 Not Found`: Query Product ID does not exist in BigQuery.
  * `500 Internal Error`: Vertex AI service unavailability (with detailed logging).
* **Latency Logging**: Every request logs 5 distinct millisecond metrics: `Components Init`, `Product Fetch`, `Vector Search`, `Enrichment`, and `Ranking`. This allows SREs to pinpoint bottlenecks in the pipeline.

---

## ⚡ Feature Store Endpoints (`/api/v1/feature-store`)

New in v2.0, these endpoints leverage **Vertex AI Feature Store** for sub-millisecond data retrieval.

### POST `/substitution/no-gemini`

**High-Speed Substitution** (Latency: ~230ms)

* **Use Case**: Real-time "Out of Stock" replacements on listing pages.
* **Flow**:
  1. **Feature Store**: Fetch missing product metadata (2ms).
  2. **Vector Search**: Find 150 candidates.
  3. **Feature Store**: Fetch metadata for candidates + Filter In-Stock (2ms).
  4. **Ranking API**: Rerank top 20.
  5. **Return**: Top 3 suggestions.

### POST `/substitution/with-gemini`

**Reasoned Substitution** (Latency: ~600ms)

* **Use Case**: Checkout/Cart page where explanation matters.
* **Flow**:
  * Steps 1-4 same as above.
  * **Step 5**: **Gemini 1.5 Pro** analyzes candidates vs user history/basket.
  * **Return**: Suggestions with `substitution_reason` and `confidence_score`.
