# Substitution Logic: Generative Reasoning Deep-Dive

This document explores the "Intelligent Substitution" engine's design, focusing on the prompt engineering and context injection used with Gemini 1.5 Flash.

## 🧠 The Substitution Problem

Substitution in groceries isn't just about finding a "similar" product. It's about finding a "suitable" product based on:

1. **Dietary Constraints**: If the user buys organic, don't substitute with non-organic.
2. **Size/Quantity Logic**: If 500g is out, 250g x 2 is a valid substitute, but 2kg might not be.
3. **Historical Preference**: If the user always buys the budget brand, don't substitute with the premium brand.

## 🛠️ The Prompting Strategy: "Few-Shot Chain of Thought"

We use Gemini 1.5 Flash not as a simple classifier, but as a **reasoning agent**.

### 1. Context Injection (The prompt payload)

We provide Gemini with a structured JSON payload containing:

- **Target Product**: The metadata of the item out-of-stock.
- **Candidate List**: 5-10 similar products retrieved by our Vector Search.
- **User Persona**: Extracted from their `basket_items` and `user_history`.

### 2. Constraint Progamming (Instruction)

The system instructions for Gemini include strict formatting rules:

- **No Hallucinations**: You must ONLY pick from the provided Candidate List.
- **Reasoning Required**: Every choice must be backed by a `reason` (e.g., "Matched low-fat preference").
- **Confidence Scoring**: Gemini assigns a 0-1 confidence score based on how well the price and attributes align.

## 🔬 Learning Note: Why Gemini 1.5 Flash?

We chose **Flash** over **Pro** for substitution for several reasons:

- **Token Throughput**: Flash is significantly faster at generating JSON responses, which is critical for real-time checkout flows.
- **Cost Performance**: Substitution logic requires processing a lot of "context" (product ingredients, user logs). Flash's lower price-per-token makes this viable at a scale of millions of substitutions per month.
- **Instruction Following**: In our tests, Flash 1.5 achieved 99% accuracy in following the required JSON schema, which is higher than many larger models that tend to be "chatty."

## 🛣️ The Future: Reinforcement Learning from Feedback (RLHF)

A technical improvement for this module would be:

1. User clicks "Accept" or "Reject" on a substitute.
2. Store this feedback in BigQuery.
3. Use this data to fine-tune the substitution prompt or a smaller downstream model.
