# 📂 Deep Technical Documentation Repository

This directory contains the "Bible" of the Multimodal Similarity engine. Every document here provides 100% architectural and implementation clarity for developers and engineers.

---

## 📑 Core Documentation Modules

### 1. [🌐 API Service](API_SERVICE.md)

* Detailed async FastAPI workflows, lazy-loading component logic, and latency tracking.
* *Key Files*: `api/main.py`, `api/models.py`.

### 2. [📊 Data & ETL](DATA_ETL.md)

* BigQuery merging strategy, `UNNEST` query optimization, and Drive-based authentication.
* *Key Files*: `data/bigquery_client.py`.

### 3. [🧠 Embedding Engine](EMBEDDING_ENGINE.md)

* Multimodal fusion logic, image normalization (Alpha channel removal), and throughput rate-limiting.
* *Key Files*: `embeddings/generator.py`, `embeddings/batch_processor.py`.

### 4. [⚡ Vector Search](VECTOR_SEARCH.md)

* TreeAH index parameters, auto-scaling replica logic, and low-level gRPC `MatchServiceClient` implementation.
* *Key Files*: `vector_search/index_manager.py`, `vector_search/search_engine.py`.

### 5. [⚖️ Ranking & Substitution](RANKING_SUBSTITUTION.md)

* Semantic re-ordering precision logic and Gemini-powered context-aware reasoning for product replacements.
* *Key Files*: `ranking/reranker.py`, `substitution/gemini_substitutor.py`.

### 6. [🚀 Operational Scripts](OPERATIONAL_SCRIPTS.md)

* Comprehensive guide for Step 1 (Embedding), Step 2 (Indexing), and Step 3 (Deployment/Testing).
* *Key Files*: `scripts/*.py`.

---

## 🏗️ Architectural Mantra: The 3-Layer Funnel

When maintaining this codebase, remember the **funnel priority**:

1. **Retrieve (Scale)**: Use Vector Search to cut millions down to 150 candidates as fast as possible.
2. **Rerank (Precision)**: Use Ranking API to order those 150 based on fine-grained text nuances.
3. **Reason (Context)**: Use Gemini to pick the final 3 substitutes by "understanding" the human context of the basket.

---
**Status**: 🚀 Operational Excellence Achieved
**Standard**: Google Cloud Validated (January 2026)
