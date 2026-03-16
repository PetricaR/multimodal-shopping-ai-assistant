export interface Product {
  product_id: string;
  product_name: string;
  category?: string;
  producer?: string;
  price: number;
  in_stock?: boolean;
  image_url?: string;
  images?: string[];
  url?: string;
  variant_id?: string;
  store_id?: string;
  store_name?: string;
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
  physical?: {
    age?: number;
    gender?: 'male' | 'female' | 'other';
    weight?: number;
    height?: number;
  };
  dietary?: {
    primary_diet?: string[];
    allergies?: string[];
    exclusions?: string[];
    calorie_target?: number;
    nutritional_goals?: string[];
  };
  preferences?: {
    meal_types?: string[];
    cooking_methods?: string[];
    complexity?: 'novice' | 'basic' | 'intermediate' | 'advanced';
    family_members?: { adults: number; children: number };
    leftovers?: boolean;
    cooking_frequency?: string;
    shopping_frequency?: string;
    variety_per_week?: 'low' | 'medium' | 'high';
    favorite_foods?: { breakfast?: string[]; lunch?: string[]; dinner?: string[] };
  };
  finance?: {
    monthly_budget?: { min: number; max: number; currency: string };
  };
  history: string[];
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