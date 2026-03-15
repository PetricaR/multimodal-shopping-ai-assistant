# ⚖️ Ranking & Substitution: Intelligence Layers

These components transform a "Similar" search into a "Relevant" recommendation. They use cross-encoders and generative AI to add a layer of human-like reasoning to the system.

---

## 📄 `ranking/reranker.py`: The Precision Filter

While Vector Search finds candidate items in a 512D space, the **Vertex AI Ranking API** acts as a "Judge."

### 1. The Cross-Encoder Architecture

Unlike vector cosine distance (which is a fast approximation), the Ranking API uses a **Cross-Encoder**.

* It looks at the **Actual Text** of the search query and the **Actual Text** of the product metadata at the same time.
* This allows it to detect subtle nuances like negative words (e.g., "Non-Bio") or specific flavor variations that might be lost in a compressed 512D vector.

### 2. Implementation Workflow (`rerank`)

1. **Format Records**: Converts product dictionaries into `RankingRecord` objects (lines 67-74).
2. **Request Construction**: Sends the query string and the top 150 candidate records to `semantic-ranker-004`.
3. **Score Normalization**: The API returns a **Raw Relevance Score**. We sort high-to-low and return the top `N` requested results.
4. **Fallback Mechanism**: If the Ranking API times out or fails (lines 106-111), the script automatically returns the original Vector Search candidates. This "Fail-Safe" design ensures that an API glitch doesn't crash the Retailer's entire search page.

---

## 📄 `substitution/gemini_substitutor.py`: The Substitution Brain

When a product is unavailable, the `GeminiSubstitutor` performs complex reasoning to select the best replacement.

### 1. The Context-Rich Prompt (`_build_substitution_prompt`)

The soul of this component is a highly detailed prompt that gives Gemini 4 specific context blocks:

* **The Missing Item**: Full category, brand, and price.
* **The User Persona**: Analyzes purchase history to determine if the user is a "Bio Fan", a "Premium Buyer", or "Price Sensitive" (lines 111, 163-203).
* **The Current Basket**: Determines the "Meal Context" (e.g., if the user has wine and flour, they are likely baking/dining) (lines 113, 205-222).
* **Candidate Pool**: The top 30 reranked items from Phase 2.

### 2. High-Fidelity Reasoning

* **Chain-of-Thought**: We use `ThinkingConfig(include_thoughts=True)` to allow Gemini to "think out loud" before arriving at the final choice.
* **Strict Output Schema**: We use a **Response Schema** (lines 55-71) to ensure the output is always a valid JSON. This prevents "parsing errors" that plague standard LLM implementations.
* **Reasoning in Romanian**: The prompt specifically asks for the explanation in Romanian (line 155), ensuring the final UI message is ready for the local customer base: *"Am ales acest produs deoarece este tot BIO și are un preț similar cu cel lipsă."*

---

## 🔍 Model Selection Trade-offs

* **Ranking API (`semantic-ranker-004`)**: Selected for its extreme speed and low cost ($0.002 per 1k records). It handles the "Big Batch" of candidates.
* **Gemini Flash/Pro**: Selected for the "Final Mile." It handles the deep reasoning for the final 3 recommendations, providing the "Why" behind every substitute.
