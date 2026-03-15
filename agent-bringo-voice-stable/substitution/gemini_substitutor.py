from google import genai
from typing import List, Dict
import json
import logging

logger = logging.getLogger(__name__)

class GeminiSubstitutor:
    """
    Context-aware product substitution using Gemini 3.0 Flash
    
    Considers:
    - Missing product
    - Current basket composition
    - User purchase history
    - Dietary restrictions
    - Price constraints
    - Brand preferences
    """
    
    def __init__(self):
        # Initializing the client with Vertex AI enabled
        self.client = genai.Client(vertexai=True)
        self.model = "gemini-3-flash-preview"  # Latest, fast and capable
    
    def select_best(
        self,
        missing_product: Dict,
        candidates: List[Dict],  # From Ranking API
        current_basket: List[Dict],
        user_history: List[Dict],
        top_n: int = 3
    ) -> List[Dict]:
        """
        Select best substitutions considering full context
        """
        
        # Build context-rich prompt
        prompt = self._build_substitution_prompt(
            missing_product,
            candidates,
            current_basket,
            user_history,
            top_n
        )
        
        try:
            # Get Gemini's reasoning
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.2,  # Consistent, logical choices
                    max_output_tokens=4500,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "substitutions": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "product_id": {"type": "STRING"},
                                        "confidence": {"type": "NUMBER"},
                                        "reasoning": {"type": "STRING"},
                                        "price_difference": {"type": "NUMBER"}
                                    }
                                }
                            }
                        }
                    },
                    thinking_config=genai.types.ThinkingConfig(
                        include_thoughts=True  # Deep reasoning enabled
                    ) if "thinking" in self.model else None
                )
            )
            
            # Parse results
            gemini_choices = json.loads(response.text)
            
            # Merge with full product data
            final_suggestions = []
            for choice in gemini_choices.get('substitutions', [])[:top_n]:
                product = self._find_product(choice['product_id'], candidates)
                if product:
                    # Enforce consistency with expected output keys
                    product['gemini_confidence'] = choice.get('confidence')
                    product['substitution_reason'] = choice.get('reasoning')
                    product['price_difference'] = choice.get('price_difference')
                    final_suggestions.append(product)
            
            return final_suggestions
            
        except Exception as e:
            logger.error(f"Gemini substitution error: {e}")
            # Fallback: return top_n from candidates
            return candidates[:top_n]
    
    def _build_substitution_prompt(
        self,
        missing_product: Dict,
        candidates: List[Dict],
        current_basket: List[Dict],
        user_history: List[Dict],
        top_n: int
    ) -> str:
        """
        Build comprehensive context for Gemini
        """
        
        # Analyze user preferences from history
        user_prefs = self._analyze_user_preferences(user_history)
        
        # Analyze basket context
        basket_context = self._analyze_basket(current_basket)
        
        prompt = f"""
You are a smart shopping assistant at Carrefour (Bringo) helping a customer find a substitute for an unavailable product.

MISSING PRODUCT:
- Name: {missing_product.get('product_name', 'Unknown')}
- Category: {missing_product.get('category', 'Unknown')}
- Producer: {missing_product.get('producer', 'Unknown')}
- Price: {missing_product.get('price', 0)} RON
- Description: {missing_product.get('description', '')}

CURRENT BASKET CONTEXT:
{basket_context}

USER PREFERENCES (from past orders):
{user_prefs}

AVAILABLE SUBSTITUTES (ranked by similarity):
{self._format_candidates(candidates[:30])}

TASK:
Select the TOP {top_n} best substitutes. 

CRITICAL RULE:
If the AVAILABLE SUBSTITUTES are fundamentally different from the MISSING PRODUCT (e.g., trying to substitute 'Gelatina' with 'Paste' or 'Fasole'), you MUST assign a VERY LOW confidence score (below 0.2) or omit them. 
Your goal is to be HONEST. If no good match exists, explain why in the 'reasoning'.

Selection Criteria:
1. SIMILARITY: Must be in the same functional category (e.g., baking ingredients for baking ingredients).
2. BASKET FIT: Complements other items ({basket_context}) only if the product itself is a reasonable match.
3. PREFERENCES: Matches user style.
4. PRICE: Within ±30% range.

IMPORTANT:
- Never say a product is a "good match" just because it matches the basket if it's the wrong category.
- If missing product is BIO, prioritize BIO.

OUTPUT:
Return top {top_n} as a JSON object with 'substitutions' array:
- product_id
- confidence (Scale 0-1. Use < 0.3 for questionable matches)
- reasoning (In Romanian. Be specific. If it's a bad match but the only one available, SAY SO.)
- price_difference
"""
        
        return prompt
    
    def _analyze_user_preferences(self, user_history: List[Dict]) -> str:
        """Extract user preferences from purchase history"""
        
        if not user_history:
            return "No purchase history available."
        
        # Count preferences
        total_items = 0
        bio_count = 0
        premium_count = 0
        total_price = 0
        
        premium_brands = ['Carrefour Selection', 'Gusturi Românești', 'Bio Village', 'Filiera Calității']
        
        for order in user_history:
            items = order.get('items', [])
            for item in items:
                total_items += 1
                name = item.get('product_name', '').lower()
                producer = item.get('producer', '').lower()
                price = item.get('price', 0)
                
                if 'bio' in name:
                    bio_count += 1
                
                if any(brand.lower() in producer or brand.lower() in name for brand in premium_brands):
                    premium_count += 1
                
                total_price += price
        
        avg_item_price = total_price / max(total_items, 1)
        
        prefs = f"""
- Total past orders: {len(user_history)}
- BIO preference: {bio_count}/{total_items} items ({bio_count/max(total_items,1)*100:.1f}%)
- Premium brands: {premium_count}/{total_items} items ({premium_count/max(total_items,1)*100:.1f}%)
- Average item price: {avg_item_price:.2f} RON
- Price sensitivity: {'HIGH' if avg_item_price < 15 else 'MEDIUM' if avg_item_price < 30 else 'LOW'}
"""
        
        return prefs
    
    def _analyze_basket(self, current_basket: List[Dict]) -> str:
        """Understand what else user is buying"""
        
        if not current_basket:
            return "Empty basket (first item)."
        
        categories = [item.get('category', 'Unknown') for item in current_basket]
        total_value = sum(item.get('price', 0) * item.get('quantity', 1) 
                         for item in current_basket)
        
        context = f"""
- Items in basket: {len(current_basket)}
- Categories: {', '.join(set(categories))}
- Total basket value: {total_value:.2f} RON
- Top Basket items: {', '.join([item.get('product_name', '')[:50] for item in current_basket[:5]])}
"""
        
        return context
    
    def _format_candidates(self, candidates: List[Dict]) -> str:
        """Format candidates for prompt"""
        
        formatted = []
        for i, candidate in enumerate(candidates, 1):
            formatted.append(f"""
{i}. {candidate.get('product_name', 'Unknown')}
   - ID: {candidate.get('product_id', candidate.get('id', 'Unknown'))}
   - Category: {candidate.get('category', 'Unknown')}
   - Producer: {candidate.get('producer', 'Unknown')}
   - Price: {candidate.get('price', 0)} RON
   - Similarity: {candidate.get('ranking_score', candidate.get('similarity_score', 0)):.2f}
   - In stock: {candidate.get('in_stock', True)}
""")
        
        return '\n'.join(formatted)
    
    def _find_product(self, product_id: str, candidates: List[Dict]) -> Dict:
        """Find full product data in candidates"""
        for c in candidates:
            if c.get('product_id') == product_id or c.get('id') == product_id:
                return c
        return None
