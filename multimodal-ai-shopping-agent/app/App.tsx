// =====================================================================
// BRINGO CHEF AI - Updated for Gemini 2.5 Flash Native Audio (Dec 2025)
// =====================================================================
//
// KEY UPDATES FROM LATEST DOCUMENTATION:
//
// 1. MODEL: gemini-live-2.5-flash-native-audio (Stable GA - March 2026)
//    - Stable GA model replacing the December 2025 preview
//    - Improved Romanian language support
//    - Better function calling with native audio
//
// 2. AUDIO CONFIG:
//    - Input: 16kHz PCM audio (required for native audio)
//    - Output: 24kHz PCM audio (model default)
//    - Speech Config: languageCode: 'ro-RO' for Romanian
//    - Optional voice selection (Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr)
//
// 3. NEW FEATURES:
//    - Affective Dialog: Enable emotion-aware responses
//    - Thinking Mode: Configure thinking budget for complex reasoning
//    - Enhanced transcription: Both input and output audio transcription
//
// 4. IMPROVED ERROR HANDLING:
//    - Better WebSocket error reporting
//    - Enhanced tool call error messages
//    - Session reconnection logic
//
// 5. OPTIMIZATIONS:
//    - Batched UI updates for better performance
//    - Improved audio streaming with proper chunking
//    - Better microphone handling with echo cancellation
//
// =====================================================================

import React, { useState, useEffect, useRef } from 'react';
import { FunctionDeclaration, GoogleGenAI, LiveServerMessage, Modality, Type } from '@google/genai';
import { Product, AgentState, LogMessage } from './types';
import {
  searchProducts, searchByProductName, checkHealth, setApiLogger,
  addToCart, removeFromCart, updateCartQuantity, clearCart, login, getRecipeIngredients, optimizeBudget, optimizeCart,
  getUserProfile, updateUserProfile, proposeMealPlan, getMealPlanDetails,
  getSystemConfig, getWeatherContext, getCalendarContext
} from './services/api';
import { AudioUtils, PCMStreamPlayer } from './services/audio';
import { Visualizer } from './components/Visualizer';
import { ChatMessage } from './components/ChatMessage';
import { ProfileSettings } from './components/ProfileSettings';
import { ProductResultsBlock } from './components/ProductResultsBlock';

// =====================================================================
// HELPERS
// =====================================================================

/** Strip model thinking blocks (<thinking>...</thinking>) before displaying */
const stripThinking = (text: string): string =>
  text.replace(/<thinking>[\s\S]*?<\/thinking>/gi, '').trim();

/** Remove agent-internal logic patterns from chat display text */
const filterAgentDisplay = (text: string): string => {
  let out = text;

  // 1. Strip fenced code blocks (JSON tool args, etc.)
  out = out.replace(/```[\s\S]*?```/g, '');

  // 2. Strip markdown headings entirely (agent should never use them)
  out = out.replace(/^#{1,6}\s+.+$/gm, '');

  // 3. Strip "bold heading" lines that are internal reasoning titles
  //    e.g. "**Analyzing the Request**", "**Formulating Search Queries**"
  out = out.replace(/^\*\*[^*\n]{3,60}\*\*\s*$/gm, '');

  // 4. Strip whole paragraphs that are clearly internal planning/reasoning
  //    Matches: "I've determined...", "I'm focusing on...", "I've confirmed...", "I've formulated..."
  const planningParagraph = /^[^\n]*\b(I(?:'ve|'m| have| am| will|'ll))\s+(?:determined|confirmed|identified|formulated|constructed|focused|decided|concluded|noted|realized|going to|now going|about to|planning)[^\n]*/gim;
  out = out.replace(planningParagraph, '');

  // 5. Strip sentences/lines describing tool employment
  out = out.replace(/[^.!?\n]*\b(employ|use|call|invoke|execute|trigger|utilize)\s+the\s+\w[\w_]*\s+tool[^.!?\n]*/gi, '');
  out = out.replace(/[^.!?\n]*\b(I(?:'ve| have| will|'ll| am|'m))\s+(?:decided to |going to |now |about to )?(?:employ|use|call|invoke|execute|run|trigger)\s+\w[\w_]*[^.!?\n]*/gi, '');

  // 6. Strip lines describing parameter configuration
  out = out.replace(/^[^.!?\n]*\b(configured?|set|specified|passed|included)\s+the\s+`?\w+`?\s*(parameter|param|argument|arg|query|value)[^.!?\n]*$/gim, '');

  // 7. Strip lines about search strategy/limits
  out = out.replace(/^[^.!?\n]*\b(search strategy|opted to search|set a limit|keep results concise|search across)[^.!?\n]*$/gim, '');

  // 8. Strip inline backtick code (tool names, params — always technical)
  out = out.replace(/`[^`]+`/g, '');

  // 9. Strip bare JSON objects/arrays
  out = out.replace(/^\s*[\[\{][\s\S]*?[\]\}]\s*$/gm, '');

  // 10. Ensure space after punctuation concatenated by streaming (e.g. "Got it!For" → "Got it! For")
  out = out.replace(/([.!?])([A-Z])/g, '$1 $2');

  // 11. Collapse multiple blank lines
  out = out.replace(/\n{3,}/g, '\n\n');

  return out.trim();
};

// =====================================================================
// TOOL DEFINITIONS - Following Function Calling Best Practices
// =====================================================================

const findShoppingItemsTool: FunctionDeclaration = {
  name: "find_shopping_items",
  description: "Search for products in the shopping catalog. Can handle multiple queries for multi-store or list search.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      queries: {
        type: Type.ARRAY,
        items: { type: Type.STRING },
        description: "List of items to search (e.g. ['coffee', 'milk', 'bread']). Use multi_store=true for cross-store price comparison."
      },
      multi_store: {
        type: Type.BOOLEAN,
        description: "Set to true to search across ALL available stores for best price/quality."
      },
      limit: {
        type: Type.NUMBER,
        description: "Max products to display per query."
      }
    },
    required: ["queries"]
  }
};

const suggestSubstitutionTool: FunctionDeclaration = {
  name: "suggest_substitution",
  description: "Find intelligent substitutions for a specific product when an item is missing or out of stock.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      product_name: { type: Type.STRING, description: "The name of the product that is unavailable." }
    },
    required: ["product_name"]
  }
};

const addToCartTool: FunctionDeclaration = {
  name: "add_to_cart",
  description: "Add a product to the shopping cart. ALWAYS confirm with user before adding.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      product_id: { type: Type.STRING, description: "The ID of the product to add." },
      quantity: { type: Type.NUMBER, description: "Quantity to add. Default is 1." },
      product_url: { type: Type.STRING, description: "URL of the product (optional)." },
      product_name: { type: Type.STRING, description: "Name of the product (for logging/confirmation)." },
      price: { type: Type.NUMBER, description: "Price of the product in RON (IMPORTANT: include this from search results)." }
    },
    required: ["product_id"]
  }
};

const removeFromCartTool: FunctionDeclaration = {
  name: "remove_from_cart",
  description: "Remove a product completely from the shopping cart.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      product_id: { type: Type.STRING, description: "The ID of the product to remove." },
      product_name: { type: Type.STRING, description: "Name of the product (optional)." }
    },
    required: ["product_id"]
  }
};

const updateCartQuantityTool: FunctionDeclaration = {
  name: "update_cart_quantity",
  description: "Update the quantity of a product already in the cart.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      product_id: { type: Type.STRING, description: "The ID of the product to update." },
      quantity: { type: Type.NUMBER, description: "New quantity for the product." },
      product_name: { type: Type.STRING, description: "Name of the product (optional)." }
    },
    required: ["product_id", "quantity"]
  }
};

const getRecipeIngredientsTool: FunctionDeclaration = {
  name: "get_recipe_ingredients",
  description: "Search for a recipe and extract a structured shopping list of ingredients.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      food_name: { type: Type.STRING, description: "Name of the dish or recipe." }
    },
    required: ["food_name"]
  }
};

const optimizeBudgetTool: FunctionDeclaration = {
  name: "optimize_budget",
  description: "Automatically adjust the shopping list to fit a specific budget while maximizing quality.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      cache_key: { type: Type.STRING, description: "Key from previous find_shopping_items result." },
      budget: { type: Type.NUMBER, description: "Maximum budget in RON." }
    },
    required: ["cache_key", "budget"]
  }
};

const optimizeShoppingStrategyTool: FunctionDeclaration = {
  name: "optimize_shopping_strategy",
  description: "Compare shopping strategies: Cheapest Mixed vs Best Single Store.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      cache_key: { type: Type.STRING, description: "Key from previous find_shopping_items result." }
    },
    required: ["cache_key"]
  }
};

const proposeMealPlanTool: FunctionDeclaration = {
  name: 'propose_meal_plan',
  description: 'Generate a personalized daily meal plan proposal based on user profile, weather, and season.',
};

const getMealPlanDetailsTool: FunctionDeclaration = {
  name: 'get_meal_plan_details',
  description: 'Generate full recipe details (ingredients, instructions, nutrition) for a chosen meal plan.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      meal_plan: {
        type: Type.OBJECT,
        description: 'Map of meal types to recipe names',
        properties: {
          breakfast: { type: Type.STRING },
          lunch: { type: Type.STRING },
          dinner: { type: Type.STRING },
          snack: { type: Type.STRING }
        }
      }
    },
    required: ['meal_plan']
  }
};

const manageUserProfileTool: FunctionDeclaration = {
  name: 'manage_user_profile',
  description: 'View or update user physical stats, dietary constraints, and budget.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      action: { type: Type.STRING, description: 'Either "view" or "update"' },
      profile_update: {
        type: Type.OBJECT,
        description: 'Partial user profile data if updating',
        properties: {
          physical: { type: Type.OBJECT },
          dietary: { type: Type.OBJECT },
          preferences: { type: Type.OBJECT },
          finance: { type: Type.OBJECT }
        }
      }
    },
    required: ['action']
  }
};

const getCalendarContextTool: FunctionDeclaration = {
  name: 'get_calendar_context',
  description: 'Get upcoming Romanian public holidays for the next 7 days. Call this when planning meals, recipes, or shopping for a holiday (e.g. Easter, Christmas, 1 Decembrie). Use it to suggest festive recipes and traditional ingredients.',
};

const getWeatherContextTool: FunctionDeclaration = {
  name: 'get_weather_context',
  description: 'Get current weather conditions at the user\'s location. Call this to tailor product, recipe, or meal suggestions to the weather (e.g. hot soup on a cold rainy day, cold drinks on a hot sunny day, umbrella reminder, etc.).',
};

// =====================================================================
// SYSTEM INSTRUCTION - Optimized for Romanian Voice Interaction
// =====================================================================

const SYSTEM_INSTRUCTION = `You are a next-generation AI shopping companion built on Google Gemini. You are warm, fast, proactive, and smart. You speak naturally like a knowledgeable friend who loves food and smart shopping.

# PERSONA & VOICE
- Name: Shopping AI Assistant
- Personality: Enthusiastic, helpful, concise. Never robotic.
- Opening (first turn only): "Hi! I'm your AI shopping assistant. I can hear you, see images, search products, and build your cart in real time. What can I help you with?"
- Language: English (switch to Romanian if user speaks Romanian)
- Brevity: 1–2 sentences for simple actions, max 3 for complex ones
- Never read out long lists — summarize: "Found 8 products — best match is X at Y RON"

# MULTIMODAL SUPERPOWERS
Vision: When user shares an image → immediately identify ALL food/products visible → suggest a dish or shopping need → call find_shopping_items for missing items
Voice: You are listening in real time. Respond immediately. Handle interruptions gracefully.
Context: Remember what was found this session. "The first one" = most recent search result #1.

# TOOLS & WHEN TO USE THEM
1. find_shopping_items(queries[], multi_store, limit)
   → Any product search request. Always search, never guess products.
   → Multi-product: queries=["milk","eggs","bread"] in ONE call

2. add_to_cart(product_id, quantity, product_name, price)
   → User says yes/add/ok/sure/that one/the first → CALL THIS IMMEDIATELY
   → ALWAYS pass price. NEVER say "added" without calling the tool.

3. get_recipe_ingredients(food_name)
   → Recipe or "how to make" requests → get ingredients → offer to search them all

4. propose_meal_plan()
   → Weekly or daily meal planning requests

5. optimize_budget(cache_key, budget)
   → User mentions a budget ("under 100 RON") → call after search

6. manage_user_profile(action)
   → Dietary preferences, allergies, budget setup

7. get_calendar_context()
   → Call when user asks about upcoming holidays, weekend plans, or festive cooking
   → Also call at the start of meal planning to check for nearby holidays
   → Returns: list of Romanian public holidays in the next 7 days (date + name)
   → Use to suggest traditional festive recipes (e.g. cozonac for Easter/Christmas, sarmale for holidays)

8. get_weather_context()
   → Call at the start of ANY meal plan, recipe, or product recommendation session
   → Also call when user mentions the weather or asks "what should I cook/eat today"
   → Returns: temperature (°C), condition (Sunny/Rainy/Cloudy/etc.), humidity, wind, precipitation probability
   → Use this to tailor suggestions: hot soup when cold/rainy, salads/cold drinks when hot/sunny, comfort food when stormy

# LIVE INTERACTION PATTERNS

Search flow:
  User: "find eggs" → call find_shopping_items(["eggs"]) → "Got it! Best match: Ouă Ferma Noastră 10-pack at 8.50 RON. Add it?"
  User: "yes" → call add_to_cart(...) → "✓ Eggs added!"

Image flow:
  User: [photo of fridge] → "I see milk, cheese and leftover chicken. You could make a creamy chicken pasta! Want me to find the missing ingredients?"
  → call find_shopping_items(["pasta","heavy cream","garlic"])

Recipe flow:
  User: "how do I make tiramisu?" → call get_recipe_ingredients("tiramisu") → "Tiramisu needs mascarpone, eggs, ladyfingers, espresso, and cocoa. Want me to add them to your cart?"

Multi-item flow:
  User: "I need ingredients for a salad" → call find_shopping_items(["lettuce","tomatoes","cucumber","olive oil","feta"])

Weather-aware flow:
  User: "what should I cook today?" → call get_weather_context() → if cold/rainy: "It's 8°C and rainy — perfect for a warm soup! Want me to find ingredients for a creamy tomato soup?" → call find_shopping_items(["tomatoes","cream","onion","garlic"])
  User: "suggest something for tonight" → call get_weather_context() first, then propose_meal_plan() with weather context in mind

# GROUNDING & ACCURACY
- Product info comes from live catalog search — always call find_shopping_items, never invent products or prices
- Recipe ingredients come from get_recipe_ingredients — powered by Gemini AI with real recipes
- For nutrition questions, seasonal tips, or cooking advice you can answer directly from your knowledge

# CRITICAL RULES
1. ALWAYS call tools — never fake product names, prices, or cart actions
2. ALWAYS pass price to add_to_cart (get it from search results)
3. After adding to cart → confirm briefly → ask "Anything else?"
4. On image → analyze first, then immediately search
5. Be proactive: after a recipe, offer to search all ingredients at once
6. Handle "the first/second/cheapest/that one" by referencing the last search result

# CONVERSATION STYLE — MANDATORY
- NEVER narrate or describe your tool calls. Do NOT say "I'll use find_shopping_items", "I'm calling the X tool", "I've configured the queries parameter", "I've set a limit of N products", or any variation of this.
- NEVER use markdown headings (##, ###) or bold headings (**Analyzing the Request**, **Formulating Queries**, etc.) in your responses.
- NEVER use backtick code formatting for tool names, parameters, or values.
- NEVER write internal reasoning like "I've determined...", "I've confirmed...", "I'm focusing on...", "I've formulated...".
- Call tools SILENTLY. Only speak the result after the tool returns.
- Your entire visible response must be pure natural conversation — no technical details, no internal reasoning, no JSON.
- Bad: "**Analyzing the Request** — I've determined the user wants eggs. I've formulated a search strategy focusing on 'oua bio'."
- Bad: "I've decided to employ the \`find_shopping_items\` tool with \`queries\`=[\"eggs\",\"milk\"]"
- Good: (call tool silently, then) "Found eggs and milk! Best egg option is Toneli 10-pack at 22.19 RON. Want to add them?"
`;

const SUGGESTIONS = [
  "Find eggs and milk",
  "What can I cook with chicken and rice?",
  "I have a budget of 150 RON",
  "Give me a weekly meal plan",
  "How do I make tiramisu?",
  "Show me vegetarian products"
];

// Discriminated union chat entry types (mirrors text-prod)
interface TextChatEntry {
  id: string;
  type: 'text';
  role: 'user' | 'agent';
  text: string;
  timestamp: string;
}

interface ProductChatEntry {
  id: string;
  type: 'product_results';
  queryGroups: { query: string; products: Product[] }[];
  isSubstitution: boolean;
  timestamp: string;
}

type ChatEntry = TextChatEntry | ProductChatEntry;

interface CartItem {
  product_id: string;
  product_name: string;
  price: number;
  quantity: number;
  image_url?: string;
}

// =====================================================================
// TOOLS CONFIG
// =====================================================================

const toolsConfig = {
  tools: [
    {
      functionDeclarations: [
        findShoppingItemsTool, suggestSubstitutionTool, addToCartTool, removeFromCartTool,
        updateCartQuantityTool, getRecipeIngredientsTool, optimizeBudgetTool,
        optimizeShoppingStrategyTool, proposeMealPlanTool, getMealPlanDetailsTool,
        manageUserProfileTool, getWeatherContextTool, getCalendarContextTool
      ]
    },
    // Google Search grounding — enables real-time nutrition info, seasonal tips, cooking advice
    { googleSearch: {} }
  ],
};

// =====================================================================
// MAIN COMPONENT
// =====================================================================

function App() {
  // State management
  const [currentPage, setCurrentPage] = useState<'login' | 'chat'>('login');
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [apiKey, setApiKey] = useState<string>('');
  const [products, setProducts] = useState<Product[]>([]);
  const [isSubstitutionMode, setIsSubstitutionMode] = useState<boolean>(false);
  const [chatHistory, setChatHistory] = useState<ChatEntry[]>([]);
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [agentState, setAgentState] = useState<AgentState>(AgentState.DISCONNECTED);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [textInput, setTextInput] = useState('');
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [isSoundEnabled, setIsSoundEnabled] = useState(false);
  const [uploadedImagePreview, setUploadedImagePreview] = useState<string | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Cart state
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [cartOpen, setCartOpen] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Auth state
  const [bringoUsername, setBringoUsername] = useState('');
  const [bringoPassword, setBringoPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [bringoAuthStatus, setBringoAuthStatus] = useState<'none' | 'loading' | 'authenticated' | 'error'>('none');
  const [bringoAuthMsg, setBringoAuthMsg] = useState('');
  const [selectedStore, setSelectedStore] = useState('carrefour_park_lake');

  // Audio state
  const [isMicEnabled, setIsMicEnabled] = useState(true);
  const inputAudioContextRef = useRef<AudioContext | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  const inputSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const audioPlayerRef = useRef<PCMStreamPlayer | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const liveSessionRef = useRef<any>(null);
  const isMicEnabledRef = useRef(false);
  const isSoundEnabledRef = useRef(false);

  // Streaming buffers
  const userStreamingTextRef = useRef<string>('');
  const agentStreamingTextRef = useRef<string>('');
  const lastUIUpdateRef = useRef<number>(0);
  const currentStreamingRole = useRef<'user' | 'agent' | null>(null);
  const UI_UPDATE_THROTTLE_MS = 100; // Update UI every 100ms for smoother streaming

  // Scroll refs
  const chatEndRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // =====================================================================
  // INITIALIZATION
  // =====================================================================

  useEffect(() => {
    const loadConfig = async () => {
      // Always fetch from backend at runtime — key must NOT be baked into the JS bundle
      // (baked keys get auto-revoked by Google's scanners within minutes)
      const cfg = await getSystemConfig();
      if (cfg?.google_api_key) {
        setApiKey(cfg.google_api_key);
      }
    };
    loadConfig();
  }, []);

  useEffect(() => {
    const checkSavedSession = async () => {
      const savedSession = localStorage.getItem('bringo_session');

      if (savedSession) {
        try {
          const session = JSON.parse(savedSession);
          const hoursSinceLogin = (Date.now() - session.timestamp) / (1000 * 60 * 60);

          if (hoursSinceLogin < 12) {
            setBringoUsername(session.username);
            setBringoPassword(session.password);
            addLog('system', `Auto-login: ${session.username}`);

            const success = await login(session.username, session.password);
            if (success) {
              setBringoAuthStatus('authenticated');
              setBringoAuthMsg(`Logged in as ${session.username}`);
              setCurrentPage('chat');
              addLog('system', 'AUTO-LOGIN: SUCCESS');
            } else {
              localStorage.removeItem('bringo_session');
              addLog('system', 'AUTO-LOGIN: FAILED');
            }
          } else {
            localStorage.removeItem('bringo_session');
            addLog('system', 'AUTO-LOGIN: Session expired');
          }
        } catch (e) {
          localStorage.removeItem('bringo_session');
          addLog('system', 'AUTO-LOGIN: Error');
        }
      }

      setIsCheckingAuth(false);
    };

    checkSavedSession();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    checkHealth().then(isHealthy => {
      const status = isHealthy ? "ONLINE" : "OFFLINE";
      addLog('system', `API HEALTH: ${status}`);
      if (!isHealthy) {
        setErrorMsg("Shopping AI API is not accessible!");
      }
    });

    setApiLogger((msg) => addLog('system', msg));

    return () => { disconnect(); };
  }, []);

  useEffect(() => {
    isMicEnabledRef.current = isMicEnabled;
  }, [isMicEnabled]);

  useEffect(() => {
    isSoundEnabledRef.current = isSoundEnabled;
  }, [isSoundEnabled]);

  // =====================================================================
  // HELPER FUNCTIONS
  // =====================================================================

  const addLog = (sender: 'user' | 'agent' | 'system', text: string) => {
    setLogs(prev => [...prev.slice(-50), { timestamp: new Date().toLocaleTimeString(), sender, text }]);
  };

  const addChatMessage = (role: 'user' | 'agent', text: string) => {
    const entry: TextChatEntry = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      type: 'text',
      role,
      text,
      timestamp: new Date().toLocaleTimeString(),
    };
    setChatHistory(prev => [...prev, entry]);
  };

  const addProductResults = (queryGroups: { query: string; products: Product[] }[], isSubstitution: boolean) => {
    const entry: ProductChatEntry = {
      id: `products-${Date.now()}`,
      type: 'product_results',
      queryGroups,
      isSubstitution,
      timestamp: new Date().toLocaleTimeString(),
    };
    setChatHistory(prev => [...prev, entry]);
  };

  const updateLastChatMessage = (role: 'user' | 'agent', text: string) => {
    setChatHistory(prev => {
      for (let i = prev.length - 1; i >= 0; i--) {
        const entry = prev[i];
        if (entry.type === 'text' && entry.role === role) {
          const updated = [...prev];
          updated[i] = { ...entry, text };
          return updated;
        }
      }
      return prev;
    });
  };

  const formatPrice = (price: number): string => {
    return price.toFixed(2).replace('.', ',');
  };

  // Cart helpers
  const addItemToLocalCart = (product: { product_id: string; product_name: string; price: number; image_url?: string }, qty: number = 1) => {
    setCartItems(prev => {
      const existing = prev.find(c => c.product_id === product.product_id);
      if (existing) {
        return prev.map(c => c.product_id === product.product_id ? { ...c, quantity: c.quantity + qty } : c);
      }
      return [...prev, { ...product, quantity: qty }];
    });
    setCartOpen(true);
  };

  const removeFromLocalCart = (product_id: string) => {
    setCartItems(prev => prev.filter(c => c.product_id !== product_id));
  };

  const updateLocalCartQuantity = (product_id: string, qty: number) => {
    setCartItems(prev => {
      if (qty <= 0) return prev.filter(c => c.product_id !== product_id);
      return prev.map(c => c.product_id === product_id ? { ...c, quantity: qty } : c);
    });
  };

  const cartTotal = cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);

  // =====================================================================
  // CONNECTION MANAGEMENT - Updated for Gemini 2.5 Flash
  // =====================================================================

  const disconnect = () => {
    audioPlayerRef.current?.stop();
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (inputSourceRef.current) { inputSourceRef.current.disconnect(); inputSourceRef.current = null; }
    if (inputAudioContextRef.current?.state !== 'closed') inputAudioContextRef.current?.close();
    if (outputAudioContextRef.current?.state !== 'closed') outputAudioContextRef.current?.close();
    inputAudioContextRef.current = null;
    outputAudioContextRef.current = null;
    liveSessionRef.current = null;
    setAgentState(AgentState.DISCONNECTED);
    setIsMicEnabled(false);
    addLog('system', 'SESSION ENDED');
  };

  const logout = () => {
    disconnect();
    localStorage.removeItem('bringo_session');
    setBringoAuthStatus('none');
    setBringoAuthMsg('');
    setBringoUsername('');
    setBringoPassword('');
    setCurrentPage('login');
    addLog('system', 'LOGOUT: Session cleared');
  };

  const connect = async () => {
    let keyToUse = apiKey;
    if (!keyToUse) {
      addLog('system', 'Loading API key from Secret Manager...');
      const cfg = await getSystemConfig();
      if (cfg?.google_api_key) {
        keyToUse = cfg.google_api_key;
        setApiKey(keyToUse);
        addLog('system', '✅ API key loaded');
      } else {
        setErrorMsg("Gemini API key is missing!");
        return;
      }
    }

    try {
      setAgentState(AgentState.CONNECTING);
      setErrorMsg(null);
      addLog('system', 'CONNECTING...');

      // Initialize audio contexts
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      inputAudioContextRef.current = new AudioContextClass({ sampleRate: 16000 });
      outputAudioContextRef.current = new AudioContextClass({ sampleRate: 24000 });
      audioPlayerRef.current = new PCMStreamPlayer(outputAudioContextRef.current);

      // Request microphone
      addLog('system', 'Requesting microphone...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1
        }
      });
      addLog('system', '✅ Microphone granted');

      // Initialize Gemini AI
      addLog('system', 'Initializing Gemini AI...');
      const ai = new GoogleGenAI({ apiKey: keyToUse });

      // =====================================================================
      // GEMINI 2.5 FLASH NATIVE AUDIO LATEST - supports bidiGenerateContent
      // =====================================================================
      const sessionPromise = ai.live.connect({
        model: 'gemini-2.5-flash-native-audio-latest',
        config: {
          // Native audio model ALWAYS requires AUDIO modality
          responseModalities: [Modality.AUDIO],
          systemInstruction: SYSTEM_INSTRUCTION,
          tools: toolsConfig.tools,
          inputAudioTranscription: {},
          outputAudioTranscription: {},
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: { voiceName: 'Kore' }
            }
          },
        },
        callbacks: {
          onopen: () => {
            setAgentState(AgentState.LISTENING);
            addLog('system', 'CONNECTION ESTABLISHED');

            sessionPromise.then(session => {
              liveSessionRef.current = session;
              addLog('system', '✅ Session initialized');
            }).catch(err => {
              console.error('Session error:', err);
              addLog('system', `❌ Session failed: ${err?.message}`);
              setAgentState(AgentState.DISCONNECTED);
            });

            // Setup audio processing
            if (!inputAudioContextRef.current) return;
            const ctx = inputAudioContextRef.current;
            const source = ctx.createMediaStreamSource(stream);
            inputSourceRef.current = source;
            const processor = ctx.createScriptProcessor(4096, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
              if (!isMicEnabledRef.current) return;

              const inputData = e.inputBuffer.getChannelData(0);
              const resampledData = AudioUtils.resample(inputData, ctx.sampleRate, 16000);
              const pcmBuffer = AudioUtils.floatTo16BitPCM(resampledData);
              const base64Data = AudioUtils.base64Encode(new Uint8Array(pcmBuffer));

              if (liveSessionRef.current) {
                liveSessionRef.current.sendRealtimeInput({
                  media: { mimeType: 'audio/pcm;rate=16000', data: base64Data }
                });
              }
            };

            source.connect(processor);
            processor.connect(ctx.destination);

            if (ctx.state === 'suspended') ctx.resume();
            if (outputAudioContextRef.current?.state === 'suspended') outputAudioContextRef.current.resume();
          },

          onmessage: async (msg: LiveServerMessage) => {
            let hasUpdates = false;

            // User speech transcript
            if (msg.serverContent?.inputTranscription?.text) {
              const newText = msg.serverContent.inputTranscription.text;
              userStreamingTextRef.current += newText;

              // Start new user message if not already streaming
              if (currentStreamingRole.current !== 'user') {
                currentStreamingRole.current = 'user';
                addChatMessage('user', userStreamingTextRef.current);
              }
              hasUpdates = true;
            }

            // Agent speech transcript (AUDIO modality)
            if (msg.serverContent?.outputTranscription?.text) {
              const newText = stripThinking(msg.serverContent.outputTranscription.text);
              agentStreamingTextRef.current += newText;

              if (currentStreamingRole.current !== 'agent') {
                currentStreamingRole.current = 'agent';
                addChatMessage('agent', agentStreamingTextRef.current);
              }
              hasUpdates = true;
            }

            // Agent text response (TEXT modality)
            if (msg.serverContent?.modelTurn?.parts) {
              for (const part of msg.serverContent.modelTurn.parts) {
                if (part.text) {
                  agentStreamingTextRef.current += stripThinking(part.text);
                  if (currentStreamingRole.current !== 'agent') {
                    currentStreamingRole.current = 'agent';
                    addChatMessage('agent', agentStreamingTextRef.current);
                  }
                  hasUpdates = true;
                }
              }
            }

            // Audio playback (AUDIO modality only)
            const audioData = msg.serverContent?.modelTurn?.parts?.[0]?.inlineData?.data;
            if (audioData && isSoundEnabledRef.current) {
              setAgentState(AgentState.SPEAKING);
              audioPlayerRef.current?.playChunk(audioData);
            }

            // Update UI (throttled for smooth streaming)
            if (hasUpdates) {
              const now = Date.now();
              const timeSinceLastUpdate = now - lastUIUpdateRef.current;

              if (timeSinceLastUpdate >= UI_UPDATE_THROTTLE_MS) {
                if (currentStreamingRole.current === 'user' && userStreamingTextRef.current.trim()) {
                  updateLastChatMessage('user', userStreamingTextRef.current.trim());
                }
                if (currentStreamingRole.current === 'agent' && agentStreamingTextRef.current.trim()) {
                  updateLastChatMessage('agent', filterAgentDisplay(stripThinking(agentStreamingTextRef.current)).trim());
                }
                lastUIUpdateRef.current = now;
              }
            }

            // Interruption
            if (msg.serverContent?.interrupted) {
              audioPlayerRef.current?.stop();

              // Finalize any streaming message
              if (currentStreamingRole.current === 'agent' && agentStreamingTextRef.current.trim()) {
                const interruptedText = filterAgentDisplay(stripThinking(agentStreamingTextRef.current)).trim();
                updateLastChatMessage('agent', interruptedText);
                addLog('agent', interruptedText);
              }

              agentStreamingTextRef.current = '';
              currentStreamingRole.current = null;
              addLog('system', 'INTERRUPTED');
              setAgentState(AgentState.LISTENING);
            }

            // Turn complete
            if (msg.serverContent?.turnComplete) {
              // Finalize user message if exists
              if (userStreamingTextRef.current.trim()) {
                updateLastChatMessage('user', userStreamingTextRef.current.trim());
                addLog('user', userStreamingTextRef.current.trim());
                userStreamingTextRef.current = '';
              }

              // Finalize agent message — strip thinking blocks and internal logic
              if (agentStreamingTextRef.current.trim()) {
                const finalText = filterAgentDisplay(stripThinking(agentStreamingTextRef.current)).trim();
                updateLastChatMessage('agent', finalText);
                addLog('agent', finalText);
                agentStreamingTextRef.current = '';
              }

              currentStreamingRole.current = null;
              lastUIUpdateRef.current = 0;

              if (!audioPlayerRef.current?.isPlaying) {
                setAgentState(AgentState.LISTENING);
              }
            }

            // Tool calls
            if (msg.toolCall) {
              setAgentState(AgentState.THINKING);
              const toolNames = msg.toolCall.functionCalls?.map(c => c.name).join(', ');
              addLog('system', `🔧 TOOL CALL: ${toolNames}`);
              console.log('Tool calls received:', msg.toolCall.functionCalls);

              for (const call of msg.toolCall.functionCalls) {
                addLog('agent', `▶️ EXEC: ${call.name}`);
                console.log(`Executing ${call.name} with args:`, call.args);
                let result: any = {};

                try {
                  // Execute tool calls
                  if (call.name === 'find_shopping_items') {
                    const args = call.args as any;
                    const queries: string[] = Array.isArray(args.queries) ? args.queries : [args.queries || args.query_text || ''];
                    const limit = args.limit || 8;
                    const multiStore = args.multi_store || false;
                    // Search per-query to preserve grouping for display
                    const queryGroups: { query: string; products: Product[] }[] = [];
                    for (const q of queries) {
                      const qProducts = await searchProducts([q], multiStore, limit);
                      queryGroups.push({ query: q, products: qProducts });
                    }
                    const allProducts = queryGroups.flatMap(g => g.products);
                    setProducts(allProducts);
                    setIsSubstitutionMode(false);
                    addProductResults(queryGroups, false);
                    addLog('system', `FOUND ${allProducts.length} products across ${queries.length} queries`);
                    result = { products: allProducts.map(p => ({ id: p.product_id, name: p.product_name, price: p.price, store: p.producer })) };
                  }
                  else if (call.name === 'suggest_substitution') {
                    const args = call.args as any;
                    const data = await searchByProductName(args.product_name, 10);
                    setProducts(data);
                    setIsSubstitutionMode(true);
                    addProductResults([{ query: args.product_name, products: data }], true);
                    result = { substitutions: data.map(p => ({ id: p.product_id, name: p.product_name, price: p.price })) };
                  }
                  else if (call.name === 'add_to_cart') {
                    const args = call.args as any;
                    const qty = args.quantity || 1;
                    const productName = args.product_name || args.product_id;
                    const providedPrice = args.price; // Price from AI's search results

                    addLog('system', `🛒 ADD TO CART: ${productName} (qty: ${qty}, price: ${providedPrice || '?'})`);
                    console.log('Adding to cart:', { product_id: args.product_id, quantity: qty, name: productName, price: providedPrice });

                    const data = await addToCart(args.product_id, qty, args.product_url, args.product_name);

                    const addedProduct = data.items_added?.[0] || {};
                    const foundProduct = products.find(p => p.product_id === args.product_id);

                    // Priority: AI-provided price > API response > found product > 0
                    const finalPrice = providedPrice || addedProduct.price || foundProduct?.price || 0;

                    const cartItem = {
                      product_id: args.product_id,
                      product_name: addedProduct.product_name || args.product_name || foundProduct?.product_name || args.product_id,
                      price: finalPrice,
                      image_url: addedProduct.image_url || foundProduct?.images?.[0] || foundProduct?.image_url || undefined
                    };

                    addItemToLocalCart(cartItem, qty);
                    addLog('system', `✅ Added ${cartItem.product_name} to cart (${finalPrice} RON)`);
                    console.log('Cart updated:', cartItem);

                    result = {
                      success: true,
                      message: `Product "${cartItem.product_name}" has been added to cart! (Quantity: ${qty}, Price: ${finalPrice} RON)`
                    };
                  }
                  else if (call.name === 'remove_from_cart') {
                    const args = call.args as any;
                    await removeFromCart(args.product_id);
                    removeFromLocalCart(args.product_id);
                    result = { success: true, message: "Product removed from cart." };
                  }
                  else if (call.name === 'update_cart_quantity') {
                    const args = call.args as any;
                    await updateCartQuantity(args.product_id, args.quantity);
                    updateLocalCartQuantity(args.product_id, args.quantity);
                    result = { success: true, message: `Quantity updated to ${args.quantity}.` };
                  }
                  else if (call.name === 'get_recipe_ingredients') {
                    const args = call.args as any;
                    result = await getRecipeIngredients(args.food_name, apiKey);
                  }
                  else if (call.name === 'optimize_budget') {
                    const args = call.args as any;
                    result = await optimizeBudget(args.cache_key, args.budget);
                  }
                  else if (call.name === 'optimize_shopping_strategy') {
                    const args = call.args as any;
                    result = await optimizeCart(args.cache_key);
                  }
                  else if (call.name === 'propose_meal_plan') {
                    result = await proposeMealPlan();
                  }
                  else if (call.name === 'get_meal_plan_details') {
                    const args = call.args as any;
                    result = await getMealPlanDetails(args.meal_plan);
                  }
                  else if (call.name === 'manage_user_profile') {
                    const args = call.args as any;
                    result = args.action === 'view' ? await getUserProfile() : await updateUserProfile(args.profile_update);
                  }
                  else if (call.name === 'get_calendar_context') {
                    result = await getCalendarContext(7);
                    const count = result.holidays?.length ?? 0;
                    addLog('system', `📅 Calendar: ${count} holiday(s) in next 7 days`);
                  }
                  else if (call.name === 'get_weather_context') {
                    // Get browser geolocation, fallback to Bucharest
                    const coords = await new Promise<{ lat: number; lon: number }>((resolve) => {
                      if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                          (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
                          () => resolve({ lat: 44.4268, lon: 26.1025 }), // Bucharest fallback
                          { timeout: 4000 }
                        );
                      } else {
                        resolve({ lat: 44.4268, lon: 26.1025 });
                      }
                    });
                    result = await getWeatherContext(coords.lat, coords.lon);
                    addLog('system', `🌤 Weather: ${result.temperature}°C, ${result.condition}`);
                  }
                } catch (err) {
                  const errorMsg = err instanceof Error ? err.message : String(err);
                  addLog('system', `❌ ERROR (${call.name}): ${errorMsg}`);
                  console.error(`Tool error (${call.name}):`, err);
                  result = { error: `Failed: ${errorMsg}` };
                }

                // Send result back to AI
                if (liveSessionRef.current) {
                  console.log(`Sending tool response for ${call.name}:`, result);
                  addLog('system', `📤 Sending result for ${call.name}`);
                  liveSessionRef.current.sendToolResponse({
                    functionResponses: [{ name: call.name, id: call.id, response: result }]
                  });
                }
              }
            }
          },

          onclose: (event: any) => {
            setAgentState(AgentState.DISCONNECTED);
            addLog('system', `CONNECTION CLOSED - ${event?.code}: ${event?.reason || 'Unknown'}`);
          },

          onerror: (err) => {
            console.error("Live session error:", err);
            setAgentState(AgentState.DISCONNECTED);
            setErrorMsg("Gemini Live connection error");
            addLog('system', `CONNECTION ERROR: ${err?.message || 'Unknown'}`);
          }
        }
      });

    } catch (err) {
      console.error(err);
      setErrorMsg("Could not connect to Gemini Live");
      setAgentState(AgentState.DISCONNECTED);
      addLog('system', `FATAL ERROR: ${err}`);
    }
  };

  // =====================================================================
  // TEXT INPUT
  // =====================================================================

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || agentState === AgentState.DISCONNECTED) return;
    
    const query = textInput.trim();
    setTextInput('');
    addChatMessage('user', query);
    addLog('user', query);
    
    if (liveSessionRef.current) {
      liveSessionRef.current.sendClientContent({ turns: [{ parts: [{ text: query }] }] });
    }
  };

  const sendSuggestion = (text: string) => {
    if (agentState === AgentState.DISCONNECTED) return;
    addChatMessage('user', text);
    addLog('user', text);
    if (liveSessionRef.current) {
      liveSessionRef.current.sendClientContent({ turns: [{ parts: [{ text }] }] });
    }
  };

  // =====================================================================
  // IMAGE UPLOAD
  // =====================================================================

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || agentState === AgentState.DISCONNECTED) return;

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const base64Data = dataUrl.split(',')[1];
      const mimeType = file.type || 'image/jpeg';

      setUploadedImagePreview(dataUrl);
      addChatMessage('user', `[Image: ${file.name}]`);
      addLog('user', `IMAGE UPLOAD: ${file.name} (${mimeType})`);

      if (liveSessionRef.current) {
        liveSessionRef.current.sendClientContent({
          turns: [{
            parts: [
              { inlineData: { mimeType, data: base64Data } },
              { text: 'Analyze this image. What products, ingredients, or food items do you see? Based on what you identify, what do you recommend I buy or cook? Search for the relevant products in the catalog.' }
            ]
          }]
        });
      }
    };
    reader.readAsDataURL(file);
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  // =====================================================================
  // BRINGO LOGIN
  // =====================================================================

  const handleBringoLogin = async () => {
    if (!bringoUsername || !bringoPassword) {
      setBringoAuthMsg('Please enter your email and password.');
      setBringoAuthStatus('error');
      return;
    }
    
    setBringoAuthStatus('loading');
    setBringoAuthMsg('');
    addLog('system', `BRINGO LOGIN: ${bringoUsername}`);
    
    try {
      const success = await login(bringoUsername, bringoPassword);
      if (success) {
        localStorage.setItem('bringo_session', JSON.stringify({
          username: bringoUsername,
          password: bringoPassword,
          timestamp: Date.now()
        }));

        setBringoAuthStatus('authenticated');
        setBringoAuthMsg(`Logged in as ${bringoUsername}`);
        addLog('system', 'BRINGO AUTH: SUCCESS');
        setTimeout(() => setCurrentPage('chat'), 1500);
      } else {
        setBringoAuthStatus('error');
        setBringoAuthMsg('Authentication failed.');
        addLog('system', 'BRINGO AUTH: FAILED');
      }
    } catch (err) {
      setBringoAuthStatus('error');
      setBringoAuthMsg('Authentication error.');
      addLog('system', `BRINGO AUTH ERROR: ${err}`);
    }
  };

  // =====================================================================
  // CART ACTIONS
  // =====================================================================

  const handleAddToCart = async (product: Product) => {
    try {
      await addToCart(product.product_id, 1, undefined, product.product_name);
      const img = product.image_url || product.images?.[0];
      addItemToLocalCart({
        product_id: product.product_id,
        product_name: product.product_name,
        price: product.price || 0,
        image_url: img
      });
      addLog('system', `ADDED: ${product.product_name}`);
    } catch (err) {
      setErrorMsg(`Could not add ${product.product_name}`);
    }
  };

  const handleRemoveFromCart = async (product_id: string, product_name: string) => {
    try {
      await removeFromCart(product_id);
      removeFromLocalCart(product_id);
      addLog('system', `REMOVED: ${product_name}`);
    } catch (err) {
      setErrorMsg(`Could not remove ${product_name}`);
    }
  };

  const handleUpdateQuantity = async (product_id: string, product_name: string, newQty: number) => {
    if (newQty <= 0) {
      handleRemoveFromCart(product_id, product_name);
      return;
    }
    try {
      await updateCartQuantity(product_id, newQty);
      updateLocalCartQuantity(product_id, newQty);
    } catch (err) {
      setErrorMsg(`Could not update ${product_name}`);
    }
  };

  const handleClearCart = async () => {
    if (cartItems.length === 0 || !window.confirm("Are you sure you want to clear the cart?")) return;
    
    try {
      await clearCart();
      setCartItems([]);
      addLog('system', 'CART CLEARED');
    } catch (err) {
      setErrorMsg("Could not clear the cart");
    }
  };

  // =====================================================================
  // RENDER
  // =====================================================================

  if (isCheckingAuth) {
    return (
      <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-500 to-blue-700 rounded-2xl flex items-center justify-center shadow-2xl animate-pulse">
            <span className="text-3xl">🛒</span>
          </div>
          <p className="text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // =====================================================================
  // LOGIN PAGE
  // =====================================================================
  if (currentPage === 'login') {
    return (
      <div className="min-h-screen flex font-sans overflow-hidden">

        {/* ── LEFT HERO PANEL ─────────────────────────────────────────── */}
        <div className="hidden lg:flex flex-col w-[58%] bg-[#050A15] relative overflow-hidden p-14 xl:p-20">
          {/* Background mesh */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_80%_60%_at_20%_-10%,rgba(59,130,246,0.18),transparent)]"></div>
            <div className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-[radial-gradient(circle,rgba(139,92,246,0.12),transparent_70%)]"></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[500px] bg-blue-950/30 rounded-full blur-[80px]"></div>
            <div className="absolute inset-0 opacity-[0.03]"
              style={{backgroundImage:'linear-gradient(rgba(255,255,255,0.5) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.5) 1px,transparent 1px)',backgroundSize:'60px 60px'}}>
            </div>
          </div>

          {/* Logo */}
          <div className="relative flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30 text-xl">
              🛒
            </div>
            <span className="text-white font-semibold text-[15px] tracking-tight">Shopping AI Assistant</span>
          </div>

          {/* Main headline */}
          <div className="relative mt-16 mb-12">
            <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-1.5 mb-6">
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></div>
              <span className="text-blue-300 text-[11px] font-medium tracking-wide uppercase">Powered by Gemini 2.5 Flash</span>
            </div>
            <h1 className="text-5xl xl:text-6xl font-bold text-white leading-[1.1] tracking-tight mb-5">
              The future of<br />
              <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-blue-300 bg-clip-text text-transparent">
                smart shopping
              </span>
            </h1>
            <p className="text-gray-400 text-lg leading-relaxed max-w-md">
              Voice-powered AI that identifies ingredients from photos, plans meals, and optimizes your cart — all in real time.
            </p>
          </div>

          {/* Feature cards */}
          <div className="relative grid grid-cols-2 gap-3 mb-12">
            {[
              { icon: '🎙️', title: 'Voice & Text', desc: 'Talk or type naturally' },
              { icon: '📸', title: 'Image Recognition', desc: 'Scan ingredients instantly' },
              { icon: '🥗', title: 'Meal Planning', desc: 'Personalized recipes' },
              { icon: '💰', title: 'Budget Optimizer', desc: 'Smart price tracking' },
            ].map(f => (
              <div key={f.title} className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-4 backdrop-blur-sm hover:bg-white/[0.06] transition-colors">
                <div className="text-2xl mb-2">{f.icon}</div>
                <div className="text-white text-[13px] font-semibold">{f.title}</div>
                <div className="text-gray-500 text-[11px] mt-0.5">{f.desc}</div>
              </div>
            ))}
          </div>

          {/* Bottom trust bar */}
          <div className="relative mt-auto flex items-center gap-6 pt-6 border-t border-white/[0.06]">
            {['Google Cloud', 'Vertex AI', 'Vector Search'].map(label => (
              <div key={label} className="flex items-center gap-2">
                <div className="w-5 h-5 bg-white/10 rounded-md"></div>
                <span className="text-gray-600 text-[11px]">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── RIGHT FORM PANEL ────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center bg-white px-8 py-12">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-violet-600 rounded-xl flex items-center justify-center shadow-md text-lg">🛒</div>
            <span className="text-gray-900 font-bold text-[16px]">Shopping AI</span>
          </div>

          <div className="w-full max-w-[360px]">
            {/* Heading */}
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Welcome back</h2>
              <p className="text-gray-500 text-sm mt-1">Sign in to access your personalized assistant</p>
            </div>

            {/* Form */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">Email</label>
                <input
                  type="email"
                  value={bringoUsername}
                  onChange={(e) => setBringoUsername(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full bg-gray-50 border border-gray-200 text-sm px-4 py-3 rounded-xl text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 outline-none transition-all placeholder-gray-400"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={bringoPassword}
                    onChange={(e) => setBringoPassword(e.target.value)}
                    placeholder="••••••••"
                    onKeyDown={(e) => e.key === 'Enter' && handleBringoLogin()}
                    className="w-full bg-gray-50 border border-gray-200 text-sm px-4 py-3 pr-11 rounded-xl text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 outline-none transition-all placeholder-gray-400"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors p-1"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    )}
                  </button>
                </div>
              </div>

              {bringoAuthMsg && (
                <div className={`px-4 py-2.5 rounded-xl text-xs flex items-center gap-2 ${
                  bringoAuthStatus === 'authenticated' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                  bringoAuthStatus === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                  'bg-blue-50 text-blue-700 border border-blue-200'
                }`}>
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    bringoAuthStatus === 'authenticated' ? 'bg-emerald-500' :
                    bringoAuthStatus === 'error' ? 'bg-red-500' : 'bg-blue-500 animate-pulse'
                  }`}></div>
                  {bringoAuthMsg}
                </div>
              )}

              <button
                onClick={handleBringoLogin}
                disabled={bringoAuthStatus === 'loading'}
                className="w-full bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-violet-600 text-white font-semibold text-sm py-3 rounded-xl transition-all shadow-md shadow-blue-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {bringoAuthStatus === 'loading' ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign In
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                  </>
                )}
              </button>

              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200"></div></div>
                <div className="relative flex justify-center"><span className="px-3 bg-white text-[10px] text-gray-400 uppercase tracking-widest">or</span></div>
              </div>

              <button
                onClick={() => setCurrentPage('chat')}
                className="w-full bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 text-gray-600 hover:text-gray-900 text-sm font-medium py-3 rounded-xl transition-all"
              >
                Continue as guest
              </button>
            </div>

            <div className="mt-8 pt-6 border-t border-gray-100 flex items-center justify-center gap-1.5 text-[11px] text-gray-400">
              <svg className="w-3 h-3 text-emerald-500" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
              <span>Gemini AI {apiKey ? 'ready' : 'connecting...'} &middot; Secured by Google Cloud</span>
            </div>
          </div>
        </div>

      </div>
    );
  }

  // =====================================================================
  // CHAT PAGE - Google-style 3-column layout
  // =====================================================================
  return (
    <div className="flex h-screen bg-[#f8f9fa] text-gray-900 overflow-hidden font-sans">

      {/* LEFT PANEL - Chat */}
      <aside className="w-[420px] flex-shrink-0 flex flex-col bg-white border-r border-gray-200 shadow-sm">

        {/* Header Bar */}
        <div className="h-14 flex items-center px-4 border-b border-gray-100 bg-white gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-violet-600 rounded-xl flex items-center justify-center shadow-sm flex-shrink-0">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.937A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-semibold text-gray-900 tracking-tight truncate">Shopping <span className="text-blue-600">AI</span></h1>
            {/* Store Selector */}
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              className="mt-0.5 text-[11px] text-gray-500 bg-gray-50 border border-gray-200 rounded px-1 py-0.5 outline-none cursor-pointer hover:border-blue-300 hover:text-blue-600 transition-colors max-w-full"
            >
              <option value="carrefour_park_lake">Carrefour Park Lake</option>
              <option value="carrefour_mega_mall">Carrefour Mega Mall</option>
              <option value="carrefour_plaza_romania">Carrefour Plaza Romania</option>
              <option value="carrefour_baneasa">Carrefour Baneasa</option>
              <option value="auchan_titan">Auchan Titan</option>
              <option value="auchan_militari">Auchan Militari</option>
              <option value="mega_image">Mega Image</option>
            </select>
          </div>
          <div className="flex-shrink-0">
            <Visualizer state={agentState} />
          </div>
          {bringoAuthStatus === 'authenticated' ? (
            <div className="flex items-center gap-1.5 flex-shrink-0 pl-2 border-l border-gray-100">
              <button
                onClick={() => setIsProfileOpen(true)}
                className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-50 border border-gray-200 hover:bg-blue-50 hover:border-blue-200 transition-colors"
                title="My Profile"
              >
                <span className="text-xs">👤</span>
                <span className="text-[10px] text-gray-600 font-medium">Profile</span>
              </button>
              <button
                onClick={logout}
                className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-50 border border-gray-200 hover:bg-red-50 hover:border-red-200 transition-colors group"
                title="Sign out"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 group-hover:bg-red-500 transition-colors"></div>
                <span className="text-[10px] text-gray-600 font-medium group-hover:text-red-600">Out</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCurrentPage('login')}
              className="flex-shrink-0 text-xs text-white font-medium bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded-full transition-colors"
            >
              Sign in
            </button>
          )}
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-[#f8f9fa]">
          {/* Microphone disabled warning */}
          {!isMicEnabled && agentState !== AgentState.DISCONNECTED && (
            <div className="mx-auto max-w-md mt-4">
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                <svg className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-amber-900">Microphone is off</p>
                  <p className="text-xs text-amber-700 mt-1">Press the microphone button to enable voice chat</p>
                </div>
              </div>
            </div>
          )}

          {/* Image preview */}
          {uploadedImagePreview && (
            <div className="mx-auto max-w-xs mt-2 relative group">
              <img src={uploadedImagePreview} alt="Uploaded" className="w-full rounded-xl border border-purple-200 shadow-sm" />
              <button
                onClick={() => setUploadedImagePreview(null)}
                className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/50 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          )}

          {chatHistory.length === 0 && agentState !== AgentState.DISCONNECTED && (
            <div className="text-center text-gray-400 flex flex-col items-center justify-center h-full min-h-[180px]">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-blue-50 flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </div>
              <p className="text-sm font-medium text-gray-500">Speak or type a message</p>
              {isMicEnabled && (
                <p className="text-xs text-green-600 mt-2 flex items-center justify-center gap-1">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                  Microphone active - speak freely!
                </p>
              )}
            </div>
          )}
          {chatHistory.map((entry) => {
            if (entry.type === 'text') {
              return <ChatMessage key={entry.id} role={entry.role} text={entry.text} timestamp={entry.timestamp} />;
            }
            if (entry.type === 'product_results') {
              return (
                <ProductResultsBlock
                  key={entry.id}
                  queryGroups={entry.queryGroups}
                  isSubstitution={entry.isSubstitution}
                  cartItems={cartItems}
                  onAddToCart={handleAddToCart}
                  onIncrementQuantity={(productId, productName) => {
                    const item = cartItems.find(i => i.product_id === productId);
                    handleUpdateQuantity(productId, productName, (item?.quantity || 0) + 1);
                  }}
                  onDecrementQuantity={(productId, productName) => {
                    const item = cartItems.find(i => i.product_id === productId);
                    handleUpdateQuantity(productId, productName, (item?.quantity || 1) - 1);
                  }}
                />
              );
            }
            return null;
          })}
          <div ref={chatEndRef} />
        </div>

        {/* Suggestions (when no chat history and connected) */}
        {chatHistory.length === 0 && agentState !== AgentState.DISCONNECTED && (
          <div className="px-4 pb-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => sendSuggestion(s)}
                className="px-3 py-1.5 rounded-full bg-white border border-gray-200 text-xs text-gray-600 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all shadow-sm"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="p-3 bg-white border-t border-gray-100">
          <div className="flex items-center gap-2">
            {agentState === AgentState.DISCONNECTED ? (
              <button
                onClick={connect}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2.5 rounded-xl transition-all shadow-sm flex items-center justify-center gap-2"
              >
                <div className="w-2 h-2 rounded-full bg-white animate-pulse"></div>
                Connect
              </button>
            ) : (
              <div className="flex-1 space-y-2">
                <form onSubmit={handleTextSubmit} className="relative flex items-center gap-2">
                  {/* Image Upload Button */}
                  <input
                    ref={imageInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleImageUpload}
                  />
                  <button
                    type="button"
                    onClick={() => imageInputRef.current?.click()}
                    className="w-9 h-9 rounded-full flex items-center justify-center bg-gray-100 border border-gray-200 hover:bg-purple-50 hover:border-purple-300 text-gray-500 hover:text-purple-600 transition-all flex-shrink-0"
                    title="Send an image"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </button>

                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={textInput}
                      onChange={(e) => setTextInput(e.target.value)}
                      placeholder="Type a message or send an image..."
                      className="w-full bg-[#f1f3f4] text-sm p-3 pr-28 rounded-full text-gray-800 focus:bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-300 border border-transparent outline-none placeholder-gray-400 transition-all"
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {/* Sound Toggle */}
                      <button
                        type="button"
                        onClick={() => setIsSoundEnabled(!isSoundEnabled)}
                        className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${isSoundEnabled ? 'bg-blue-500 text-white shadow-sm' : 'bg-gray-200 text-gray-400 hover:bg-gray-300'}`}
                        title={isSoundEnabled ? "Sound on (click to mute)" : "Sound off (click to enable)"}
                      >
                        {isSoundEnabled ? (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
                        ) : (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>
                        )}
                      </button>
                      {/* Integrated Microphone Toggle */}
                      <button
                        type="button"
                        onClick={() => setIsMicEnabled(!isMicEnabled)}
                        className={`w-8 h-8 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${isMicEnabled
                          ? 'bg-red-500 text-white shadow-md'
                          : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                          }`}
                        title={isMicEnabled ? "Microphone On" : "Microphone Off"}
                      >
                        {isMicEnabled ? (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z" />
                          </svg>
                        )}
                      </button>

                      {/* Send Button */}
                      <button type="submit" className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-700 flex items-center justify-center transition-colors">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" /></svg>
                      </button>
                    </div>
                  </div>
                </form>

                {/* Status indicator / Disconnect */}
                <div className="flex items-center justify-between px-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {/* Microphone status */}
                    <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isMicEnabled ? 'bg-red-500 animate-pulse' : 'bg-gray-300'}`}></div>
                    <span className="text-[11px] text-gray-500 font-medium">
                      {isMicEnabled ? 'Live Audio' : 'Text Only'}
                    </span>

                    {/* Agent state indicator */}
                    {agentState === AgentState.SPEAKING && (
                      <div className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-100 rounded-full">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse flex-shrink-0"></div>
                        <span className="text-[10px] text-blue-600 font-semibold">Speaking</span>
                      </div>
                    )}
                    {agentState === AgentState.THINKING && (
                      <div className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-100 rounded-full">
                        <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse flex-shrink-0"></div>
                        <span className="text-[10px] text-amber-600 font-semibold">Thinking</span>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={disconnect}
                    className="text-[11px] text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors flex-shrink-0"
                  >
                    <span>End</span>
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              </div>
            )}

            {/* Unified Microfon for Activation (when disconnected) */}
            {agentState === AgentState.DISCONNECTED && (
              <button
                onClick={() => { connect(); setIsMicEnabled(true); }}
                className="p-2.5 rounded-xl bg-gray-100 border border-gray-300 text-gray-500 hover:bg-blue-50 hover:text-blue-600 transition-all group"
                title="Connect with Voice"
              >
                <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* CENTER - Products Canvas */}
      <main className="flex-1 relative flex flex-col min-h-screen overflow-hidden">

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-8">

          {/* ZERO STATE: Hero */}
          {products.length === 0 && !errorMsg && (
            <div className="h-full flex flex-col items-center justify-center text-center pb-20">
              <div className="w-16 h-16 mb-6 rounded-full bg-blue-100 flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-gray-900 mb-3">
                How can I help you<br />
                <span className="text-blue-600">today?</span>
              </h2>
              <p className="text-gray-500 text-base mb-8 max-w-md">
                Recipe recommendations, product search, image analysis with ingredients.
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendSuggestion(s)}
                    className="px-4 py-2 rounded-full bg-white border border-gray-200 text-sm text-gray-600 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all shadow-sm hover:shadow"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* RESULTS — horizontal scrollable gallery */}
          {products.length > 0 && (
            <div className="animate-fade-in pb-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700">
                  {isSubstitutionMode ? "Smart Substitutions" : "Search Results"}
                  <span className="ml-2 text-gray-400 font-normal">{products.length} products</span>
                </h3>
                <button onClick={() => setProducts([])} className="text-xs text-gray-400 hover:text-gray-600 underline transition-colors">
                  Clear
                </button>
              </div>
              <ProductResultsBlock
                queryGroups={[{ query: 'products', products }]}
                isSubstitution={isSubstitutionMode}
                cartItems={cartItems}
                onAddToCart={handleAddToCart}
                onIncrementQuantity={(productId, productName) => {
                  const item = cartItems.find(i => i.product_id === productId);
                  handleUpdateQuantity(productId, productName, (item?.quantity || 0) + 1);
                }}
                onDecrementQuantity={(productId, productName) => {
                  const item = cartItems.find(i => i.product_id === productId);
                  handleUpdateQuantity(productId, productName, (item?.quantity || 1) - 1);
                }}
              />
            </div>
          )}

          {/* ERROR */}
          {errorMsg && products.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center bg-red-50 border border-red-200 text-red-700 p-6 rounded-2xl max-w-md">
                <p className="text-lg font-semibold mb-2">Error</p>
                <p className="text-sm">{errorMsg}</p>
                <button onClick={() => setErrorMsg(null)} className="mt-4 text-sm text-red-500 hover:text-red-700 underline">Close</button>
              </div>
            </div>
          )}
        </div>

        {/* COLLAPSIBLE LOGS */}
        <div className={`${logsExpanded ? 'h-36' : 'h-7'} bg-gray-900 flex flex-col shrink-0 relative z-30 transition-all duration-200`}>
          <div
            className="h-7 bg-gray-800 flex items-center px-3 gap-2 cursor-pointer hover:bg-gray-700 transition-colors"
            onClick={() => setLogsExpanded(!logsExpanded)}
          >
            <span className="text-[10px] text-gray-400 font-mono uppercase tracking-widest">Logs</span>
            <span className="text-[10px] text-gray-500">{logs.length}</span>
            <span className="ml-auto text-[10px] text-gray-500">{logsExpanded ? '▼' : '▶'}</span>
          </div>
          {logsExpanded && (
            <div className="flex-1 overflow-y-auto p-2 font-mono text-[10px] space-y-0.5">
              {logs.slice(-20).map((log, idx) => (
                <div key={idx} className="break-words flex gap-2">
                  <span className="text-gray-600 w-14 shrink-0 text-right">{log.timestamp}</span>
                  <span className={`w-10 shrink-0 font-bold ${log.sender === 'user' ? 'text-green-400' : log.sender === 'agent' ? 'text-blue-400' : 'text-purple-400'}`}>
                    {log.sender.toUpperCase()}
                  </span>
                  <span className="text-gray-400 truncate">{log.text}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* RIGHT PANEL - Cart */}
      {cartOpen && (
        <aside className="w-80 flex-shrink-0 flex flex-col bg-white border-l border-gray-200 shadow-sm">

          {/* Cart Header */}
          <div className="h-14 flex items-center px-4 border-b border-gray-100 bg-white">
            <svg className="w-5 h-5 text-gray-600 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" /></svg>
            <h2 className="text-sm font-semibold text-gray-900 flex-1">My Cart</h2>
            <span className="text-xs text-gray-400">{cartItems.length} {cartItems.length === 1 ? 'item' : 'items'}</span>
            <button onClick={() => setCartOpen(false)} className="ml-2 w-6 h-6 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>

          {/* Cart Items */}
          <div className="flex-1 overflow-y-auto">
            {cartItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 px-6">
                <svg className="w-12 h-12 text-gray-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" /></svg>
                <p className="text-sm font-medium text-gray-400">Cart is empty</p>
                <p className="text-xs text-gray-300 mt-1 text-center">Add products from the search results</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {cartItems.map((item) => (
                  <div key={item.product_id} className="px-4 py-3 flex gap-3 hover:bg-gray-50 transition-colors">
                    <div className="w-12 h-12 rounded-lg bg-white border border-gray-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                      {item.image_url ? (
                        <img
                          src={item.image_url}
                          alt={item.product_name}
                          className="w-full h-full object-contain p-0.5"
                          onError={(e) => {
                            const target = e.currentTarget;
                            target.style.display = 'none';
                            const parent = target.parentElement;
                            if (parent) {
                              parent.innerHTML = `<svg class="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>`;
                            }
                          }}
                        />
                      ) : (
                        <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-800 line-clamp-2 leading-tight mb-1">{item.product_name}</p>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 bg-gray-100/50 rounded-lg p-0.5 border border-gray-200">
                          <button
                            onClick={() => handleUpdateQuantity(item.product_id, item.product_name, item.quantity - 1)}
                            className="w-5 h-5 flex items-center justify-center rounded-md hover:bg-white hover:shadow-sm text-gray-600 transition-all"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" /></svg>
                          </button>
                          <span className="text-[11px] font-bold text-gray-800 w-4 text-center">{item.quantity}</span>
                          <button
                            onClick={() => handleUpdateQuantity(item.product_id, item.product_name, item.quantity + 1)}
                            className="w-5 h-5 flex items-center justify-center rounded-md hover:bg-white hover:shadow-sm text-gray-600 transition-all"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" /></svg>
                          </button>
                        </div>
                        {item.price > 0 && (
                          <span className="text-xs font-semibold text-gray-700">{formatPrice(item.price * item.quantity)} RON</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleRemoveFromCart(item.product_id, item.product_name)}
                      className="w-8 h-8 rounded-lg hover:bg-red-50 flex items-center justify-center text-gray-300 hover:text-red-500 transition-all flex-shrink-0 self-center border border-transparent hover:border-red-100"
                      title="Remove"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Cart Footer / Total */}
          {cartItems.length > 0 && (
            <div className="border-t border-gray-200 p-4 bg-gray-50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-600">Estimated total</span>
                <span className="text-lg font-bold text-gray-900">{formatPrice(cartTotal)} <span className="text-xs font-normal text-gray-500">RON</span></span>
              </div>
              <button
                onClick={handleClearCart}
                className="w-full text-xs text-gray-400 hover:text-red-500 py-1.5 transition-colors"
              >
                Clear cart
              </button>
            </div>
          )}
        </aside>
      )}

      {/* Cart Toggle (when cart panel is closed) */}
      {!cartOpen && (
        <button
          onClick={() => setCartOpen(true)}
          className="fixed right-4 top-4 z-50 w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-all"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" /></svg>
          {cartItems.length > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">{cartItems.length}</span>
          )}
        </button>
      )}

      {/* Profile Settings Modal */}
      <ProfileSettings isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />

      {/* Error Toast */}
      {errorMsg && products.length > 0 && (
        <div className="fixed bottom-6 right-6 p-4 bg-white border border-red-200 text-red-700 rounded-xl shadow-lg flex items-center gap-3 z-[1000] max-w-sm">
          <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
          <div className="flex-grow min-w-0">
            <p className="text-sm">{errorMsg}</p>
          </div>
          <button onClick={() => setErrorMsg(null)} className="w-6 h-6 rounded-full hover:bg-red-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
