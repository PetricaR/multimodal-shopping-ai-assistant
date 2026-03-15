# 🧠 Embedding Engine: Multimedia Logic

The Embedding Engine is the bridge between raw product assets (images/text) and the mathematical space used for similarity search. It implements strict image normalization and rate-limiting to ensure production stability.

---

## 📄 `embeddings/generator.py`: Asset Transformation

This script manages the lower-level interaction with **Vertex AI `multimodalembedding@001`**.

### 1. Robust Image Preprocessing Pipeline

To satisfy the requirements of the Vertex AI Vision model, every product image goes through a 4-step transformation (`download_and_process_image`):

1. **Download & Cache**: Fetches images via HTTP with custom `User-Agent` headers. It calculates an **MD5 hash** of the URL to check a local `/tmp/` cache, preventing multiple downloads of the same asset.
2. **Alpha Channel Removal**: The model requires 3-channel (RGB) input. We check the PIL image mode; if it's `RGBA` or `LA` (transparency), we composite it onto a **Solid White Background** before conversion.
3. **Lanczos Resizing**: Images are resized to **512x512 pixels**. We use the `LANCZOS` resampling filter (higher quality than `NEAREST` or `BILINEAR`) to preserve fine textual details on product labels (e.g., "Organic" or brand names).
4. **JPEG Optimization**: Processed images are saved as JPEGs with `quality=85` to maintain the balance between visual fidelity and input payload size.

### 2. The Multimodal Fusion Call

The logic in `generate_embedding` implements a "Best Effort" multimodal strategy:

* **Ideal Case**: Sends both `image` and `contextual_text`. It returns the `image_embedding`, which Google confirms is **fused**—meaning the vector positions are influenced by both the visual look and the text description.
* **Fallback 1 (Text-only)**: If the image URL is dead or download fails, it automatically switches to a `text_embedding` call.
* **Fallback 2 (Error Safety)**: If all else fails, it returns a zeroed vector, preventing the entire search batch from crashing due to one bad product asset.

---

## 📄 `embeddings/batch_processor.py`: Scale Orchestration

Generating 10,000 embeddings is a high-volume operation that must respect Google’s API limits.

### 1. Rate Limiting Logic

By default, Vertex AI projects have a 120 requests/minute quota.

* The processor implements a **precise wait timer** (lines 114-120): `elapsed = time.time() - last_request_time`.
* It ensures a minimum of 0.5 seconds between every request.
* With 2 workers, this results in a stable throughput that stays ~20% below the quota limit to account for network jitter and prevent `429 Too Many Requests` errors.

### 2. The JSONL Vector Schema

The processor outputs data in the specific **JSONL (Newline-delimited JSON)** format required by Vertex Vector Search:

```json
{
  "id": "product_id_string",
  "embedding": [0.1, 0.2, ... (512 values)],
  "restricts": [
    {"namespace": "category", "allow": ["Teas"]},
    {"namespace": "in_stock", "allow": ["true"]}
  ],
  "crowding_tag": "category_string"
}
```

* **Crowding Tags**: Used to ensure results aren't dominated by a single category when searching broadly.
* **Restricts**: Enables the "Hard Filtering" feature in the search engine (e.g., "Only show me in-stock items").

### 3. GCS Streaming

Instead of keeping 10k vectors in memory (which could consume GBs of RAM), the processor can be configured to stream or upload chunks to GCS, ensuring it can run on small containers/machines.
