# Core Features & User Guide

This guide explains how to interact with the Bringo Multimodal API and the logic behind its core capabilities.

## 🔍 Multimodal Similarity Search

The search engine doesn't just look for keywords (lexical search); it understands the **visual and semantic concepts** of products.

### How it works

1. **Input**: You provide a product name or image.
2. **Context**: The system uses `multimodalembedding@001` to capture properties like "Gluten-Free," "Organic," or "Plastic Packaging."
3. **Cross-Product Matching**: It can find "Lactose-Free Milk" when searching for "Regular Milk" because they are semantically similar even if the names don't match exactly.

### API Usage

**Endpoint**: `GET /api/v1/product/{product_id}/similar`
**Key Parameter**: `use_ranking=True`

- Set to `True` for maximum quality (recommended for production).
- Set to `False` for maximum speed (useful for background processing).

---

## 🍎 Intelligent Product Substitution

When a product is unavailable, the system uses **Gemini 1.5 Flash** to act as a "Personal Concierge."

### The Multi-Step Flow

1. **Candidate Selection**: Find the top products that are similar to the missing one.
2. **Persona Injection**: Gemini is instructed to act as a Bringo shopper Expert.
3. **Data Analysis**: Gemini looks at:
    - User's Basket (e.g., "User is buying many organic vegetables").
    - History (e.g., "User strictly buys low-fat products").
    - Substitution Logic (e.g., "Replacing 500g with 250g x 2").
4. **Decision**: Gemini picks the single best replacement and provides a human-readable reason.

### API Usage

**Endpoint**: `POST /api/v1/substitution/suggest`
**Payload Example**:

```json
{
  "product_id": "12345",
  "basket_items": ["apple", "cheese"],
  "user_history": ["low-fat yogurt", "skim milk"]
}
```

---

## 🔐 Security & Access

The Bringo platform is secured at two levels:

### 1. Web Portal Access (Streamlit)

The frontend requires a **Google Account** login. Only emails authorized in the Google Cloud Console "Test Users" or the Identity-Aware Proxy list will be granted access.

### 2. Direct API Access

If you are calling the API from a backend script or Postman, you **must** include the API Shield key in the headers:

- **Header**: `X-API-KEY`
- **Value**: Your secure key (found in `config.env`)

---

## 📊 Semantic Health Check

You can monitor the status of all underlying AI services by visiting the health endpoint:

`GET /health`

It verifies connectivity to:

- **Vector Search**: Checks if the Index Endpoint is reachable.
- **Ranking API**: Checks if the Discovery Engine client is ready.
- **BigQuery**: Verifies table permissions.
