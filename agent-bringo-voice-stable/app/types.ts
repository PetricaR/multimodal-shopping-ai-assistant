export interface Product {
  product_id: string;
  product_name: string;
  category?: string;
  producer?: string;
  price: number;
  in_stock?: boolean;
  image_url?: string;
  images?: string[];
  ranking_score?: number;
  similarity_score?: number;
  distance?: number;
  gemini_confidence?: number;
  substitution_reason?: string;
  price_difference?: number;
}

export interface BasketItem {
  product_id: string;
  quantity: number;
}

export interface UserProfile {
  id: string;
  history: string[]; // List of product IDs or names
}

export enum AgentState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  LISTENING = 'LISTENING',
  THINKING = 'THINKING',
  SPEAKING = 'SPEAKING',
}

export interface LogMessage {
  timestamp: string;
  sender: 'user' | 'agent' | 'system';
  text: string;
}