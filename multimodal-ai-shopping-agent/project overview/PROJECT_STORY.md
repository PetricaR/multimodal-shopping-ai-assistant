# Project Story: Shopping AI Assistant

## Inspiration

Grocery shopping is a universal chore that often feels disconnected from the way we actually cook and eat. We plan meals based on what's in our fridge, the weather outside, our budget, and our dietary goals—yet the tools we use to buy groceries are static grids of products.

I was inspired to build **Shopping AI Assistant** to bridge that gap. I wanted an agent that doesn't just search for "milk," but understands that I'm trying to bake a cake for my daughter's birthday, checks my fridge to see if I already have eggs, and proposes a recipe that fits my $20 budget. With the release of **Gemini 2.5 Flash Native Audio**, I realized we finally had the multimodal, low-latency foundation necessary to make this feel like a natural conversation with a knowledgeable friend.

## How it was built

The Shopping AI Assistant is a full-stack application built using:

### 1. The Brain (Gemini 2.5 Flash Native Audio)

The core intelligence is powered by Gemini's new Realtime API via WebSockets. By using the `gemini-2.5-flash-native-audio-latest` model with the `AUDIO` modality, the agent can hear the user and respond with human-like voice streaming in milliseconds.

### 2. The Senses (Multimodal Input & Context)

The agent doesn't just listen; it sees and contextualizes:

- **Vision:** Users can upload photos of their fridge or pantry, and Gemini analyzes the image to identify ingredients and suggest recipes.
- **Context Engines:** The backend provides real-time APIs for weather (to suggest hot soup on a rainy day) and Romanian public holidays (to suggest traditional festive foods like *cozonac*).

### 3. The Hands (Function Calling & Database)

We implemented 13 distinct tools (Functions) that the agent can call autonomously to interact with the real world:

- **`find_shopping_items`**: Queries a live, real-world catalog of over 25,000 Romanian supermarket products using **Vertex AI Vector Search**.
- **`add_to_cart` / `remove_from_cart`**: Real-time cart management synced with the UI.
- **`optimize_budget`**: Uses a knapsack-style optimization algorithm to fit meals into a user's target budget.

$$ \max \sum_{i=1}^{n} v_i x_i \quad \text{subject to} \quad \sum_{i=1}^{n} p_i x_i \leq B $$
*(Where $v_i$ is the nutritional value/relevance of item $i$, $p_i$ is the price, and $B$ is the total budget).*

### 4. The Interface (React + Cloud Run)

The frontend is a modern React/Vite application that handles audio context capture via WebAudio API, streaming PCM data directly to Gemini while rendering a synced, visual shopping cart and product gallery. Both front and backend are containerized and deployed on **Google Cloud Run** for dynamic auto-scaling.

## Challenges we faced

1. **Audio Streaming Complexity:** Handling real-time raw PCM streaming (`16kHz` mono input, `24kHz` output) between the browser's WebAudio API and Gemini's WebSocket required precise buffer management to prevent audio stuttering and memory leaks.
2. **Hallucination Prevention:** Early versions of the agent would "invent" products and prices when asked for recipes. We strictly constrained the agent via the `SYSTEM_INSTRUCTION` to *never* speak a price or product name without first calling the `find_shopping_items` tool.
3. **Synchronizing State:** Keeping the React UI (visual cart) perfectly synced with the agent's internal tool calls (e.g., when the agent says "I've added milk") required careful interception and mapping of `FunctionCall` events in the frontend payload.

## What we learned

- **Native Audio is a Paradigm Shift:** The difference between traditional STT/TTS pipelines and native audio models is night and day. Emotion, hesitation, and interruption handling finally feel natural.
- **Tool Calling defines the Agent:** An LLM is only as good as the tools you give it. Designing granular, predictable APIs (like `suggest_substitution` and `optimize_budget`) proved much more effective than giving the model massive, generic endpoints.
- **Multimodal Context is King:** We found that combining image input (a photo of a fridge) with weather data (it's raining) creates a surprisingly empathetic and useful AI response that pure text cannot achieve.
