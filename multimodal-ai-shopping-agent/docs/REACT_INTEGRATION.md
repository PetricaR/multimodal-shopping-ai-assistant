# Bringo API Integration Guide for React

This guide explains how to integrate the Bringo Product Similarity API into a React application.

## API Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| **API** | `http://34.78.177.35/api/v1` | Product similarity search |
| **Streamlit** | `http://34.140.215.60` | Demo frontend |

---

## Authentication

All API requests require the `x-api-key` header:

```javascript
const API_KEY = "bringo_secure_shield_2026";
const API_BASE = "http://34.78.177.35/api/v1";
```

---

## API Endpoints

### 1. Health Check

```javascript
// GET /health
const checkHealth = async () => {
  const response = await fetch("http://34.78.177.35/health");
  return response.json();
};

// Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "vector_search": "initialized",
    "ranking_api": "initialized",
    "bigquery": "initialized"
  }
}
```

### 2. Product Similarity Search

```javascript
// POST /api/v1/search
const searchProducts = async (productName, options = {}) => {
  const { topK = 10, useRanking = true, inStockOnly = false } = options;
  
  const response = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      product_name: productName,
      top_k: topK,
      use_ranking: useRanking,
      in_stock_only: inStockOnly,
    }),
  });
  
  return response.json();
};
```

### 3. Text Search (Semantic)

```javascript
// POST /api/v1/search with query_text
const textSearch = async (query, topK = 10) => {
  const response = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      query_text: query,
      top_k: topK,
      use_ranking: true,
    }),
  });
  
  return response.json();
};
```

---

## Response Structure

```typescript
interface SearchResponse {
  query_product: string;
  similar_products: Product[];
  search_method: string;       // "feature_store_vector_ranking"
  candidates_retrieved: number;
  candidates_ranked: number;
  query_time_ms: number;
}

interface Product {
  product_id: string;
  product_name: string;
  category: string;
  producer: string;
  image_url: string;
  price: number;
  in_stock: boolean;
  similarity_score: number;    // 0-1 (higher = more similar)
  ranking_score: number;       // 0-1 (AI reranking score)
}
```

---

## React Integration Examples

### Custom Hook

```jsx
// hooks/useProductSearch.js
import { useState, useCallback } from "react";

const API_BASE = "http://34.78.177.35/api/v1";
const API_KEY = "bringo_secure_shield_2026";

export function useProductSearch() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (productName, options = {}) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": API_KEY,
        },
        body: JSON.stringify({
          product_name: productName,
          top_k: options.topK || 12,
          use_ranking: options.useRanking ?? true,
          in_stock_only: options.inStockOnly || false,
        }),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.similar_products || []);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, loading, error, search };
}
```

### Product Card Component

```jsx
// components/ProductCard.jsx
import React from "react";
import "./ProductCard.css";

export function ProductCard({ product }) {
  const { 
    product_name, 
    price, 
    image_url, 
    in_stock, 
    similarity_score,
    ranking_score 
  } = product;

  const matchPercent = Math.round((ranking_score || similarity_score) * 100);

  return (
    <div className="product-card">
      <div className="product-image">
        {image_url ? (
          <img src={image_url} alt={product_name} loading="lazy" />
        ) : (
          <div className="no-image">🖼️</div>
        )}
      </div>
      
      <div className="product-info">
        <h3 className="product-name">{product_name}</h3>
        
        <div className="product-meta">
          <span className="price">{price.toFixed(2)} RON</span>
          <span className={`stock ${in_stock ? "in-stock" : "out-of-stock"}`}>
            {in_stock ? "✅" : "🔴"}
          </span>
          <span className="match">{matchPercent}% Match</span>
        </div>
      </div>
    </div>
  );
}
```

### Product Card CSS

```css
/* components/ProductCard.css */
.product-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
}

.product-image {
  height: 180px;
  overflow: hidden;
  background: #f3f4f6;
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-image {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
  color: #9ca3af;
}

.product-info {
  padding: 1rem;
}

.product-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: #374151;
  margin: 0 0 0.5rem 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 2.5rem;
}

.product-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.5rem;
  border-top: 1px solid #f3f4f6;
}

.price {
  color: #059669;
  font-weight: 700;
  font-size: 1.1rem;
}

.match {
  color: #6b7280;
  font-size: 0.8rem;
}

.stock.in-stock { color: #10b981; }
.stock.out-of-stock { color: #ef4444; }
```

### Search Results Grid

```jsx
// components/SearchResults.jsx
import React from "react";
import { ProductCard } from "./ProductCard";
import "./SearchResults.css";

export function SearchResults({ products, loading, error }) {
  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Searching products...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error">
        <p>❌ {error}</p>
      </div>
    );
  }

  if (!products.length) {
    return (
      <div className="empty">
        <p>No products found. Try a different search.</p>
      </div>
    );
  }

  return (
    <div className="results-grid">
      {products.map((product, index) => (
        <ProductCard key={product.product_id || index} product={product} />
      ))}
    </div>
  );
}
```

### Search Results CSS

```css
/* components/SearchResults.css */
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  padding: 1rem 0;
}

.loading, .error, .empty {
  text-align: center;
  padding: 3rem;
  color: #6b7280;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error {
  color: #ef4444;
}
```

### Full Page Example

```jsx
// App.jsx
import React, { useState } from "react";
import { useProductSearch } from "./hooks/useProductSearch";
import { SearchResults } from "./components/SearchResults";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const { results, loading, error, search } = useProductSearch();

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      search(query, { topK: 12, useRanking: true });
    }
  };

  return (
    <div className="app">
      <header>
        <h1>🛒 Bringo Product Search</h1>
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products..."
            className="search-input"
          />
          <button type="submit" disabled={loading} className="search-button">
            {loading ? "⏳" : "🔍"} Search
          </button>
        </form>
      </header>

      <main>
        <SearchResults products={results} loading={loading} error={error} />
      </main>
    </div>
  );
}

export default App;
```

---

## Error Handling

```javascript
const handleApiError = (response) => {
  switch (response.status) {
    case 401:
      throw new Error("Invalid API key");
    case 400:
      throw new Error("Bad request - check your parameters");
    case 500:
      throw new Error("Server error - try again later");
    default:
      throw new Error(`API Error: ${response.status}`);
  }
};
```

---

## Performance Tips

1. **Debounce search input** to avoid excessive API calls
2. **Cache results** for recently searched products
3. **Use `loading="lazy"`** on images
4. **Limit `top_k`** to 12-20 for optimal UX

---

## Quick Start

```bash
# 1. Test API directly
curl -X POST "http://34.78.177.35/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "x-api-key: bringo_secure_shield_2026" \
  -d '{"product_name": "Lapte", "top_k": 5}'

# 2. Check health
curl http://34.78.177.35/health
```
