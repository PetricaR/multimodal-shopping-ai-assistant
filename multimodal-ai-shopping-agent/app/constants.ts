// API Configuration is in services/api.ts (uses VITE_API_URL env var)
// Do NOT define API_BASE_URL or API_KEY here — they are managed centrally in api.ts

// Matches Streamlit "Generic Baskets" structure
export const DEFAULT_BASKET = [
  { "product_id": "111", "name": "Organic Milk" },
  { "product_id": "222", "name": "Whole Grain Bread" }
];

// Matches Streamlit "User Profiles" structure
export const DEFAULT_USER_HISTORY = [
  { "product_id": "333", "name": "Greek Yogurt", "frequency": 5 },
  { "product_id": "882341", "name": "Butter", "frequency": 2 }
];