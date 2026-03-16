/**
 * Bringo API Service
 * 
 * Strict implementation of:
 * curl -X 'POST' \
 *   'http://localhost:8080/api/v1/search' \
 *   -H 'accept: application/json' \
 *   -H 'x-api-key: bringo_secure_shield_2026' \
 *   -H 'Content-Type: application/json' \
 *   -d '{ "in_stock_only": false, "query_text": "...", "top_k": 20, "use_ranking": true }'
 */

import { Product } from '../types';

// =============================================================================
// Configuration
// =============================================================================

// Use environment variable for API host, fallback to localhost for development
const env = (import.meta as any).env;
export const API_HOST = (env && env.VITE_API_URL) || "http://localhost:8080";
export const API_KEY = "bringo_secure_shield_2026";

// Standard Title-Case headers
const HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
    "Accept": "application/json"
};

// =============================================================================
// Logging
// =============================================================================

let apiLogger: ((msg: string) => void) | null = null;

export const setApiLogger = (logger: (msg: string) => void) => {
    apiLogger = logger;
};

const log = (msg: string, data?: any) => {
    let logData = '';
    if (data) {
        if (data instanceof Error) {
            logData = ` ${data.message}`;
        } else {
            logData = ` ${JSON.stringify(data)}`;
        }
    }
    console.log(`[API Service] ${msg}${logData}`);
    if (apiLogger) apiLogger(`${msg}${logData}`);
};

// =============================================================================
// Image Utilities
// =============================================================================

const resolveImageUrl = (url: string | undefined, seedName: string = 'product'): string => {
    if (!url || url === 'N/A' || url === 'http://...' || url === '') {
        return `https://placehold.co/400x400/1f2937/ffffff?text=${encodeURIComponent(seedName.substring(0, 15))}`;
    }
    return url;
};

// =============================================================================
// Data Mapping
// =============================================================================

const mapApiProduct = (p: any): Product => {
    let images: string[] = [];

    if (Array.isArray(p.images) && p.images.length > 0) {
        images = p.images.map((img: string) => resolveImageUrl(img, p.product_name));
    } else if (p.image_url) {
        images = [resolveImageUrl(p.image_url, p.product_name)];
    } else {
        images = [resolveImageUrl(undefined, p.product_name)];
    }

    const producer = (p.producer && p.producer !== 'None') ? p.producer : 'Unknown';

    return {
        product_id: p.product_id || p.id || '',
        product_name: p.product_name || 'Unknown Product',
        category: p.category || '',
        producer,
        price: typeof p.price === 'string' ? parseFloat(p.price) : (p.price ?? p.price_ron ?? 0),
        images,
        in_stock: p.in_stock !== undefined ? p.in_stock : true,
        url: p.url || undefined,
        variant_id: p.variant_id || undefined,
        store_id: p.store_id || undefined,
        store_name: p.store_name || undefined,
        ranking_score: p.ranking_score ?? 0,
        similarity_score: p.similarity_score ?? 0,
        gemini_confidence: p.gemini_confidence,
        substitution_reason: p.substitution_reason,
        price_difference: p.price_difference,
    };
};

// =============================================================================
// Fallback Data
// =============================================================================

const DEMO_DB: Product[] = [
    { product_id: "coff1", product_name: "Cafea Macinata Jacobs Kronung 500g", category: "coffee", producer: "Jacobs", price: 24.50, images: ["https://placehold.co/400?text=Jacobs+Kronung"], ranking_score: 0.99, similarity_score: 0.99, in_stock: true },
    { product_id: "d1", product_name: "Lapte Zuzu 3.5% 1L", category: "dairy", producer: "Albalact", price: 8.50, images: ["https://placehold.co/400?text=Lapte+Zuzu"], ranking_score: 0.98, similarity_score: 0.98, in_stock: true },
];

// =============================================================================
// HTTP Client
// =============================================================================

const fetchWithTimeout = async (
    url: string,
    options: RequestInit,
    timeoutMs: number = 60000
): Promise<Response> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        // Ensure error is propagated clearly
        throw error;
    }
};

// =============================================================================
// API Functions
// =============================================================================

export const checkHealth = async (): Promise<boolean> => {
    try {
        const url = `${API_HOST}/health`;
        log(`[REQUEST] GET ${url}`);
        const response = await fetchWithTimeout(url, { method: 'GET' }, 5000);
        log(`[RESPONSE] ${url} - ${response.status} ${response.statusText}`);
        return response.ok;
    } catch (error) {
        log(`[ERROR] Health check failed:`, error);
        return false;
    }
};

export interface SystemConfig {
    google_api_key?: string;
    status: string;
    version: string;
}

export const getSystemConfig = async (): Promise<SystemConfig | null> => {
    try {
        const url = `${API_HOST}/api/v1/config`;
        log(`[REQUEST] GET ${url}`);
        const response = await fetchWithTimeout(url, { method: 'GET' }, 5000);
        if (!response.ok) return null;
        const data = await response.json();
        log(`[RESPONSE] Config loaded: ${data.status}`);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to load system config:`, error);
        return null;
    }
};

/**
 * Perform Search matching strictly:
 * curl -X 'POST' 'http://localhost:8080/api/v1/search' ... -d '{ "in_stock_only": false, "query_text": "...", "top_k": 20, "use_ranking": true }'
 */
export const searchProducts = async (query: string | string[], multiStore: boolean = false, topK: number = 20): Promise<Product[]> => {
    const payload: any = {
        "in_stock_only": false,
        "top_k": topK,
        "use_ranking": true,
        "multi_store": multiStore
    };

    if (Array.isArray(query)) {
        if (query.length === 1 && !multiStore) {
            payload.query_text = query[0];
        } else {
            payload.queries = query;
        }
    } else {
        payload.query_text = query;
    }

    const url = `${API_HOST}/api/v1/search`;

    // Logging headers to prove API Key presence
    log(`[REQUEST] POST ${url}`, { headers: HEADERS, body: payload });

    const MAX_RETRIES = 2;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
            const response = await fetchWithTimeout(
                url,
                {
                    method: 'POST',
                    headers: HEADERS,
                    body: JSON.stringify(payload),
                }
            );

            if (!response.ok) {
                const txt = await response.text();
                log(`[ERROR] ${response.status}`, txt);
                throw new Error(`${response.status}: ${txt}`);
            }

            const data = await response.json();
            log(`[RESPONSE] ${response.status}`, data);

            const products = data.similar_products || [];
            return products.map(mapApiProduct);

        } catch (error) {
            log(`[EXCEPTION] Search failed (attempt ${attempt + 1}/${MAX_RETRIES + 1}):`, error);
            if (attempt < MAX_RETRIES) {
                log(`[RETRY] Retrying in ${(attempt + 1) * 2}s...`);
                await new Promise(r => setTimeout(r, (attempt + 1) * 2000));
            } else {
                return fallbackSearch(Array.isArray(query) ? query[0] : query);
            }
        }
    }
    return fallbackSearch(Array.isArray(query) ? query[0] : query);
};

/**
 * Get ingredients for a recipe using Gemini AI directly (no backend scraper needed).
 * Falls back to backend if no API key is available.
 */
export const getRecipeIngredients = async (foodName: string, apiKey?: string): Promise<any> => {
    const resolvedKey = apiKey || (env && env.VITE_GOOGLE_API_KEY);

    if (resolvedKey) {
        log(`[GEMINI] Fetching recipe for "${foodName}" via Gemini AI`);
        try {
            const { GoogleGenAI } = await import('@google/genai');
            const ai = new GoogleGenAI({ apiKey: resolvedKey });

            const prompt = `You are a culinary expert. Provide a detailed recipe for "${foodName}".
Return ONLY a valid JSON object (no markdown, no extra text) with this exact structure:
{
  "recipe_name": "Full recipe name",
  "servings": "4 servings",
  "ingredients": ["200g flour", "3 eggs", "..."],
  "ingredient_groups": {
    "Main": ["200g flour", "3 eggs"],
    "Sauce": ["2 tbsp olive oil"]
  },
  "shopping_list": "- 200g flour\\n- 3 eggs\\n..."
}`;

            const response = await ai.models.generateContent({
                model: 'gemini-2.0-flash',
                contents: [{ role: 'user', parts: [{ text: prompt }] }],
                config: { responseMimeType: 'application/json' }
            });

            const text = response.text ?? '';
            const jsonMatch = text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const data = JSON.parse(jsonMatch[0]);
                log(`[GEMINI] Recipe fetched: ${data.recipe_name}, ${data.ingredients?.length} ingredients`);
                return {
                    status: 'success',
                    recipe_name: data.recipe_name || foodName,
                    servings: data.servings || '4 servings',
                    ingredients: data.ingredients || [],
                    ingredient_groups: data.ingredient_groups || {},
                    shopping_list: data.shopping_list || (data.ingredients || []).map((i: string) => `- ${i}`).join('\n'),
                };
            }
            throw new Error('Could not parse Gemini JSON response');
        } catch (error) {
            log(`[WARN] Gemini recipe fetch failed, falling back to backend:`, error);
        }
    }

    // Fallback: backend scraper
    const url = `${API_HOST}/api/v1/recipes/ingredients`;
    const payload = { food_name: foodName };
    log(`[REQUEST] POST ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Recipe ingredients:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to get recipe ingredients:`, error);
        throw error;
    }
};

/**
 * Optimize budget for identified products
 */
export const optimizeBudget = async (cacheKey: string, budget: number): Promise<any> => {
    const url = `${API_HOST}/api/v1/live_search/optimize_budget`;
    const payload = { cache_key: cacheKey, budget_ron: budget };
    log(`[REQUEST] POST ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Budget optimization:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to optimize budget:`, error);
        throw error;
    }
};

export const optimizeCart = async (cacheKey: string): Promise<any> => {
    const url = `${API_HOST}/api/v1/live_search/optimize_cart`;
    const payload = { cache_key: cacheKey };
    log(`[REQUEST] POST ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Cart optimization:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to optimize cart:`, error);
        throw error;
    }
};

// --- Chef AI & Personalization ---

export const getUserProfile = async (): Promise<any> => {
    const url = `${API_HOST}/api/v1/user/profile`;
    log(`[REQUEST] GET ${url}`);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'GET',
            headers: { "x-api-key": API_KEY, "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] User profile loaded`);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to get user profile:`, error);
        throw error;
    }
};

export const updateUserProfile = async (profileUpdate: any): Promise<any> => {
    const url = `${API_HOST}/api/v1/user/profile`;
    const payload = profileUpdate;
    log(`[REQUEST] POST ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] User profile updated`);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to update user profile:`, error);
        throw error;
    }
};

export const proposeMealPlan = async (): Promise<any> => {
    const url = `${API_HOST}/api/v1/chef/plan/propose`;
    log(`[REQUEST] GET ${url}`);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'GET',
            headers: { "x-api-key": API_KEY, "Accept": "application/json" }
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Meal plan proposed:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to propose meal plan:`, error);
        throw error;
    }
};

export const getMealPlanDetails = async (mealPlan: Record<string, string>): Promise<any> => {
    const url = `${API_HOST}/api/v1/chef/plan/details`;
    const payload = mealPlan;
    log(`[REQUEST] POST ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Meal plan details:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to get meal plan details:`, error);
        throw error;
    }
};

/**
 * For substitutions, we also use the proven query_text endpoint since it works reliably.
 * We pass the productName as the query_text.
 */
export const searchByProductName = async (productName: string, topK: number = 20, inStock: boolean = false): Promise<Product[]> => {
    const payload = {
        "in_stock_only": inStock,
        "query_text": productName,
        "top_k": topK,
        "use_ranking": true
    };

    const url = `${API_HOST}/api/v1/search`;

    log(`[REQUEST] POST ${url}`, { headers: HEADERS, body: payload });

    try {
        const response = await fetchWithTimeout(
            url,
            {
                method: 'POST',
                headers: HEADERS,
                body: JSON.stringify(payload),
            }
        );

        if (!response.ok) {
            const txt = await response.text();
            log(`[ERROR] ${response.status}`, txt);
            throw new Error(`${response.status}: ${txt}`);
        }

        const data = await response.json();
        log(`[RESPONSE] ${response.status}`, data);

        const products = data.similar_products || [];
        return products.map(mapApiProduct);

    } catch (error) {
        log(`[EXCEPTION] Search failed:`, error);
        return fallbackSearch(productName);
    }
};

export const addToCart = async (productId: string, quantity: number, productUrl?: string, productName?: string): Promise<any> => {
    const payload = {
        product_id: productId,
        quantity: quantity,
        product_url: productUrl,
        product_name: productName
    };

    const url = `${API_HOST}/api/v1/cart/add`;

    // Attempt to get session first?
    // For now we assume session is managed by backend or not needed for this demo, 
    // BUT the backend endpoint REQUIRES `phpsessid` header.
    // We will check auth status first to get the session ID.

    let phpsessid = "";
    try {
        const statusResp = await fetch(`${API_HOST}/api/v1/auth/status`);
        if (statusResp.ok) {
            const statusData = await statusResp.json();
            if (statusData.status === "authenticated") {
                phpsessid = statusData.phpsessid;
            }
        }
    } catch (e) {
        log(`[WARN] Failed to check auth status:`, e);
    }

    const headers = { ...HEADERS, ...(phpsessid ? { "phpsessid": phpsessid } : {}) };

    log(`[REQUEST] POST ${url}`, { headers, body: payload });

    try {
        const response = await fetchWithTimeout(
            url,
            {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload),
            }
        );

        if (!response.ok) {
            const txt = await response.text();
            log(`[ERROR] ${response.status}`, txt);
            throw new Error(`${response.status}: ${txt}`);
        }

        const data = await response.json();
        log(`[RESPONSE] ${response.status}`, data);
        // Conversion tracking log (BR11)
        log(`[CONVERSION] Added product ${productId} (${productName}) to cart. Quantity: ${quantity}`);
        return data;
    } catch (error) {
        log(`[EXCEPTION] Add to cart failed:`, error);
        throw error;
    }
};

export const removeFromCart = async (productId: string): Promise<any> => {
    const url = `${API_HOST}/api/v1/cart/items/${productId}`;
    log(`[REQUEST] DELETE ${url}`);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Removed from cart:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to remove from cart:`, error);
        throw error;
    }
};

export const updateCartQuantity = async (productId: string, quantity: number): Promise<any> => {
    const url = `${API_HOST}/api/v1/cart/items/${productId}`;
    const payload = { product_id: productId, quantity: quantity };
    log(`[REQUEST] PATCH ${url}`, payload);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'PATCH',
            headers: HEADERS,
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Updated cart quantity:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to update cart quantity:`, error);
        throw error;
    }
};

export const clearCart = async (): Promise<any> => {
    const url = `${API_HOST}/api/v1/cart`;
    log(`[REQUEST] DELETE ${url}`);
    try {
        const response = await fetchWithTimeout(url, {
            method: 'DELETE',
            headers: HEADERS
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        log(`[RESPONSE] Cart cleared:`, data);
        return data;
    } catch (error) {
        log(`[ERROR] Failed to clear cart:`, error);
        throw error;
    }
};

export const login = async (username: string, password: string): Promise<boolean> => {
    const payload = {
        username: username,
        password: password,
        store: "carrefour_park_lake" // Default store for now
    };

    const url = `${API_HOST}/api/v1/auth/login`;

    log(`[REQUEST] POST ${url}`, { headers: HEADERS, body: { ...payload, password: "***" } });

    try {
        const response = await fetchWithTimeout(
            url,
            {
                method: 'POST',
                headers: HEADERS,
                body: JSON.stringify(payload),
            }
        );

        if (!response.ok) {
            const txt = await response.text();
            log(`[ERROR] ${response.status}`, txt);
            throw new Error(`${response.status}: ${txt}`);
        }

        const data = await response.json();
        log(`[RESPONSE] ${response.status}`, { ...data, cookies: "***" });
        return true;

    } catch (error) {
        log(`[EXCEPTION] Login failed:`, error);
        return false;
    }
};

// =============================================================================
// Weather
// =============================================================================

export const getCalendarContext = async (days: number = 7): Promise<any> => {
    const url = `${API_HOST}/api/v1/calendar/holidays?days=${days}`;
    log(`[REQUEST] GET ${url}`);
    const response = await fetch(url, { headers: { "x-api-key": API_KEY, "Accept": "application/json" } });
    if (!response.ok) throw new Error(`Calendar API ${response.status}`);
    return response.json();
};

export const getWeatherContext = async (lat: number, lon: number): Promise<any> => {
    const url = `${API_HOST}/api/v1/weather/current?lat=${lat}&lon=${lon}&hours=3`;
    log(`[REQUEST] GET ${url}`);
    const response = await fetch(url, { headers: { "x-api-key": API_KEY, "Accept": "application/json" } });
    if (!response.ok) {
        const txt = await response.text();
        throw new Error(`Weather API ${response.status}: ${txt}`);
    }
    return response.json();
};

// =============================================================================
// Fallback
// =============================================================================

const fallbackSearch = async (query: string): Promise<Product[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    const normalizedQuery = query.toLowerCase();
    const queryParts = normalizedQuery.split(' ').filter(p => p.length > 2);

    const matches = DEMO_DB.filter(p => {
        const text = `${p.product_name} ${p.category} ${p.producer}`.toLowerCase();
        return queryParts.some(part => text.includes(part));
    });

    return matches.length > 0 ? matches : [...DEMO_DB].sort(() => 0.5 - Math.random()).slice(0, 4);
};