# Performance Deep-Dive & Low-Level Optimization

This document explains the high-performance engineering techniques used to achieve enterprise-grade latency in a multimodal pipeline.

## 🚀 The BigQuery Storage Read API (gRPC/Arrow)

Traditional REST APIs for database retrieval involve heavy overhead:

1. **JSON Serialization**: The database converts rows to JSON strings (expensive).
2. **HTTP Overhead**: Standard request/response cycles.
3. **Deserialization**: Python parses the large JSON string back into objects (slow).

### Our Solution: Apache Arrow & gRPC

We bypass the REST layer using the **BigQuery Storage API**:

- **Binary Format**: Data is transmitted using **Apache Arrow**, a columnar memory format.
- **Zero-Copy**: Arrow data is read directly into memory buffers that Pandas can understand without re-parsing every field.
- **Parallel Streams**: For large fetches, the API can open multiple gRPC streams to pull data in parallel across multiple CPU cores.
- **Result**: Metadata retrieval for 100 products dropped from **1.2s to <400ms**.

## 🧠 Multimodal Embedding Logic & Latency

Embedding generation is the most expensive part of the "Retriever" stage.

### Image Preprocessing Optimization

Before sending an image to Vertex AI, we perform localized processing in `embeddings/generator.py`:

- **LANCZOS Resampling**: High-quality downsampling to 512x512.
- **Alpha-Channel Flattening**: Converting RGBA to RGB on a white background (required by the model).
- **Caching**: We use an MD5 hash of the Image URL to cache processed images locally. This avoids redownloading the same image multiple times across different user sessions.

### In-Memory Vector Cache

Generating a multimodal vector takes ~800ms-1200ms.

- **Implementation**: A bounded dictionary stores the resulting lists.
- **Key**: `hash(text + image_url)`.
- **Benefit**: Frequent searches (e.g., repeating a search for the same product ID) become nearly instantaneous (<10ms).

## ⚡ The Reranking Bottleneck

The **Ranking API** is the most latent component (~1-2s).

- **Learning Purpose**: Why is it slow? Because it's not a distance calculation; it's a full-pass inference through a transformer model for every query-candidate pair.
- **Optimization**: We mitigate this by only sending the **Top 100** candidates.
- **Trade-off**: Increasing candidates to 200 would improve quality by ~1-2% but would double the latency to 4s. 100 is the "Golden Ratio" for production search.

## 📈 Resource Management in GKE

### CPU vs. Memory

- **CPU-Bound**: Image processing and Arrow deserialization are spikes in CPU usage.
- **Memory-Bound**: The embedding cache and the product metadata cache grow over time.
- **Autoscaling Strategy**: We scale on **CPU (70% target)**. This ensures that when search traffic spikes, new pods are spun up before the image processing logic starts queuing requests.
