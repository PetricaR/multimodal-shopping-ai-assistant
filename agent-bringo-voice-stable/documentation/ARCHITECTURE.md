# In-Depth Technical Architecture

This document provides a deep technical analysis of the Bringo Multimodal API's design, exploring the "why" behind our architectural choices and the mathematical foundations of our search logic.

## 🏗️ The "Retriever-Ranker" Paradigm

In modern Information Retrieval (IR), processing millions of documents with a heavy-weight model (like a transformer) is computationally impossible in real-time. We solve this using a two-stage pipeline:

### Stage 1: The Retriever (Approximate Nearest Neighbor Search)

- **Goal**: Filter 5,000,000+ products down to the top 100-150 candidates.
- **Implementation**: Vertex AI Vector Search.
- **Algorithm**: SCANN (Scalable Nearest Neighbors).
- **Why SCANN?**: Unlike exact search (which calculates distance to every point), SCANN uses **Anisotropic Quantization**. It compresses vectors into a codebook while preserving the relative distance of the "maximum inner product." This allows it to achieve **>95% recall** with sub-10ms latency.
- **Metric**: `COSINE_DISTANCE`. We chose this because the embedding model was trained to maximize cosine similarity in a hypersphere.

### Stage 2: The Ranker (Cross-Attention Scoring)

- **Goal**: Precision-sort the top 100 candidates.
- **Implementation**: Vertex AI Ranking API (`semantic-ranker-default@latest`).
- **How it works**: Unlike the retriever (which compares two pre-computed vectors), the Ranker performs **Cross-Attention**. It passes the query and the candidate product *together* through a deep neural network.
- **The Benefit**: It can understand nuances that vector distance misses, such as "Is this milk specifically the lactose-free version requested?" or "Does this bottle size match the user's intent?".

## 🎨 Multimodal Embedding Space

We use `multimodalembedding@001`, which creates a **Joint Embedding Space**.

1. **Alignment**: During training, the model is shown pairs of (Image, Description). It learns to map both to the same location in a 512-dimensional space.
2. **Projection**: When you provide both an image and text, the model uses the image as the primary signal but "modulates" the vector using the provided text context.
3. **Dimension Trade-off**: We chose **512 dimensions** over 1408.
    - *Learning Note*: While 1408D offers more "capacity," the 512D model provides 98% of the same accuracy for 1/3 the cost and significantly faster vector search indexing.

## 🔄 High-Concurrency Data Flow

The API follows an **Asynchronous Event-Driven** pattern:

1. **FastAPI Uvicorn**: Uses an `uvloop` (C-based event loop) to handle thousands of concurrent TCP connections.
2. **Lazy Initialization**: To minimize cold-boot times in GKE, we use singleton patterns for heavy clients (BigQuery, Vertex AI). They are only instantiated when the first request hits a pod.
3. **Non-Blocking I/O**: Every call to GCP is awaited natively using the `async` versions of the SDK where possible, ensuring the worker thread is free to handle other requests while waiting for the cloud response.

## 🛡️ Networking & Security Shield

To handle production traffic without the overhead of complex SSL management for internal services, we implemented a **Shielded API Pattern**:

1. **Layer 4 Load Balancing**: We use a Regional Network Load Balancer. It is faster than an L7 (HTTP) Load Balancer because it handles traffic at the TCP level, avoiding the latency of "SSL Termination" and "URL Map" processing.
2. **API Shielding (Middleware)**: Since we bypass the Google Identity-Aware Proxy (IAP) at the infrastructure level, we moved security into the code. A FastAPI dependency verifies the `X-API-KEY` header for every request.
3. **Secure Tunneling**: The Streamlit user authenticates via Google OIDC. Once verified, the Streamlit backend (running in a trusted environment) communicates with the GKE API using the internal shield key.
