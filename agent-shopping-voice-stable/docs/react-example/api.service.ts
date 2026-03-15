/**
 * Bringo API Service
 * 
 * Production-ready implementation for React/React Native apps.
 * 
 * API Endpoints:
 * - Health: GET http://34.78.177.35/health
 * - Search: POST http://34.78.177.35/api/v1/search
 */

import { Product } from '../types';

// =============================================================================
// Configuration
// =============================================================================

export const API_BASE_URL = "http://34.78.177.35";
export const API_KEY = "bringo_secure_shield_2026";

const HEADERS: HeadersInit = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
};

const TIMEOUT_MS = 15000;

// =============================================================================
// Logging
// =============================================================================

let apiLogger: ((msg: string) => void) | null = null;

export const setApiLogger = (logger: (msg: string) => void) => {
    apiLogger = logger;
};

const log = (prefix: string, msg: string, data?: any) => {
    let logMsg = `[API Service] [${prefix}] ${msg}`;

    if (data !== undefined) {
        if (data instanceof Error) {
            logMsg += `\n${data.message}`;
        } else if (typeof data === 'object') {
            logMsg += `\n${JSON.stringify(data, null, 2)}`;
        } else {
            logMsg += `\n${String(data)}`;
        }
    }

    console.log(logMsg);
    if (apiLogger) apiLogger(logMsg);
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
        ranking_score: p.ranking_score ?? 0,
        similarity_score: p.similarity_score ?? 0,
    };
};

// =============================================================================
// Fallback Demo Data
// =============================================================================

const DEMO_DB: Product[] = [
    { product_id: "coff1", product_name: "Cafea Macinata Jacobs Kronung 500g", category: "coffee", producer: "Jacobs", price: 24.50, images: ["https://placehold.co/400?text=Jacobs+Kronung"], ranking_score: 0.99, similarity_score: 0.99, in_stock: true },
    { product_id: "coff2", product_name: "Capsule Cafea Nespresso Original 10buc", category: "coffee", producer: "Nespresso", price: 21.00, images: ["https://placehold.co/400?text=Nespresso"], ranking_score: 0.98, similarity_score: 0.98, in_stock: true },
    { product_id: "d1", product_name: "Lapte Zuzu 3.5% 1L", category: "dairy", producer: "Albalact", price: 8.50, images: ["https://placehold.co/400?text=Lapte+Zuzu"], ranking_score: 0.98, similarity_score: 0.98, in_stock: true },
    { product_id: "b1", product_name: "Paine Toast HapiHap", category: "bakery", producer: "Boromir", price: 6.20, images: ["https://placehold.co/400?text=Paine+Toast"], ranking_score: 0.91, similarity_score: 0.91, in_stock: true },
    { product_id: "c1", product_name: "Paste Barilla Spaghetti 500g", category: "cooking", producer: "Barilla", price: 6.50, images: ["https://placehold.co/400?text=Barilla"], ranking_score: 0.95, similarity_score: 0.95, in_stock: true },
];

// =============================================================================
// HTTP Client with Timeout
// =============================================================================

const fetchWithTimeout = async (
    url: string,
    options: RequestInit,
    timeoutMs: number = TIMEOUT_MS
): Promise<Response> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);

        // Re-throw with better error message
        if (error instanceof Error) {
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeoutMs}ms`);
            }
            throw error;
        }
        throw new Error('Network request failed');
    }
};

// =============================================================================
// API Functions
// =============================================================================

/**
 * Health Check
 * GET /health
 * 
 * @returns true if API is healthy, false otherwise
 */
export const checkHealth = async (): Promise<boolean> => {
    const url = `${API_BASE_URL}/health`;
    log('REQUEST', `GET ${url}`);

    try {
        const response = await fetchWithTimeout(url, { method: 'GET' }, 5000);

        if (!response.ok) {
            log('ERROR', `Health check failed with status ${response.status}`);
            return false;
        }

        const data = await response.json();
        log('RESPONSE', 'Health check successful', data);
        return data.status === 'healthy';

    } catch (error) {
        log('ERROR', 'Health check failed', error);
        return false;
    }
};

/**
 * Search Products by Text Query (Semantic Search)
 * POST /api/v1/search with query_text
 * 
 * @param query - Search query text (e.g., "lapte bio", "cafea")
 * @param topK - Number of results to return (default: 20)
 * @returns Array of matching products
 */
export const searchProducts = async (query: string, topK: number = 20): Promise<Product[]> => {
    const url = `${API_BASE_URL}/api/v1/search`;
    const payload = {
        query_text: query,
        top_k: topK,
        use_ranking: true,
        in_stock_only: false,
    };

    log('REQUEST', `POST ${url}`, payload);

    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            log('ERROR', `API returned ${response.status}: ${errorText}`);
            throw new Error(`API Error: ${response.status}`);
        }

        const data = await response.json();
        const products = data.similar_products || [];

        log('RESPONSE', `Found ${products.length} products in ${data.query_time_ms?.toFixed(0) || '?'}ms`);

        return products.map(mapApiProduct);

    } catch (error) {
        log('ERROR', 'Search failed, using fallback', error);
        return fallbackSearch(query);
    }
};

/**
 * Search Products by Product Name (Similarity Search)
 * POST /api/v1/search with product_name
 * 
 * @param productName - Exact product name to find similar products for
 * @param topK - Number of results to return (default: 20)
 * @returns Array of similar products
 */
export const searchByProductName = async (productName: string, topK: number = 20): Promise<Product[]> => {
    const url = `${API_BASE_URL}/api/v1/search`;
    const payload = {
        product_name: productName,
        top_k: topK,
        use_ranking: true,
        in_stock_only: false,
    };

    log('REQUEST', `POST ${url}`, payload);

    try {
        const response = await fetchWithTimeout(url, {
            method: 'POST',
            headers: HEADERS,
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            log('ERROR', `API returned ${response.status}: ${errorText}`);
            throw new Error(`API Error: ${response.status}`);
        }

        const data = await response.json();
        const products = data.similar_products || [];

        log('RESPONSE', `Found ${products.length} products | Method: ${data.search_method || 'unknown'}`);

        return products.map(mapApiProduct);

    } catch (error) {
        log('ERROR', 'Product search failed, using fallback', error);
        return fallbackSearch(productName);
    }
};

// =============================================================================
// Fallback Search (Offline Mode)
// =============================================================================

const fallbackSearch = (query: string): Product[] => {
    const normalizedQuery = query.toLowerCase();
    const queryParts = normalizedQuery.split(' ').filter(p => p.length > 2);

    const matches = DEMO_DB.filter(p => {
        const text = `${p.product_name} ${p.category} ${p.producer}`.toLowerCase();
        return queryParts.some(part => text.includes(part));
    });

    if (matches.length === 0) {
        return [...DEMO_DB].sort(() => 0.5 - Math.random()).slice(0, 4);
    }

    return matches;
};

// =============================================================================
// Types (include in types.ts)
// =============================================================================

/*
export interface Product {
    product_id: string;
    product_name: string;
    category: string;
    producer: string;
    price: number;
    images: string[];
    in_stock: boolean;
    ranking_score: number;
    similarity_score: number;
}
*/
