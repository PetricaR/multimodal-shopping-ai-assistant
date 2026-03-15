"""
Recipe Search Tools for Shopping Agent

Integrates Jamila Cuisine recipe scraper to help users find recipes
and suggest shopping lists based on recipe ingredients.
"""

import json
from typing import Dict, List, Optional, Any
from services.jamila_scraper import JamilaRecipeScraper, Recipe

# Initialize global scraper instance
_scraper = None

def get_scraper() -> JamilaRecipeScraper:
    """Get or create scraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = JamilaRecipeScraper(delay=1.0)
    return _scraper


def search_recipe(food_name: str) -> Dict[str, Any]:
    """
    Search for a recipe by food name and return detailed recipe information.
    """
    try:
        scraper = get_scraper()
        recipe = scraper.get_recipe(food_name)
        
        if recipe and recipe.name != "Error":
            # Generate formatted summary
            summary = _format_recipe_summary(recipe)
            
            return {
                'success': True,
                'recipe_name': recipe.name,
                'url': recipe.url,
                'description': recipe.description,
                'prep_time': recipe.prep_time,
                'cook_time': recipe.cook_time,
                'total_time': recipe.total_time,
                'servings': recipe.servings,
                'ingredients': recipe.ingredients,
                'instructions': recipe.instructions,
                'nutrition_info': recipe.nutrition_info,
                'tags': recipe.tags,
                'image_url': recipe.image_url,
                'video_url': recipe.video_url,
                'formatted_summary': summary,
                'scraped_at': recipe.scraped_at
            }
        else:
            return {
                'success': False,
                'error': f'Nu am găsit rețetă pentru "{food_name}"',
                'suggestion': 'Încearcă să reformulezi căutarea sau caută un alt fel de mâncare.'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Eroare la căutarea rețetei: {str(e)}',
            'suggestion': 'Te rog încearcă din nou mai târziu.'
        }


def get_recipe_ingredients_for_shopping(food_name: str) -> Dict[str, Any]:
    """
    Get recipe ingredients formatted as a shopping list.
    """
    try:
        scraper = get_scraper()
        recipe = scraper.get_recipe(food_name)
        
        if recipe and recipe.name != "Error":
            # Group ingredients by category (if groups exist)
            ingredient_groups = {}
            current_group = "Ingrediente"
            ingredient_groups[current_group] = []
            
            for ingredient in recipe.ingredients:
                if ingredient.startswith('#'):
                    # New group header
                    current_group = ingredient[1:].strip()
                    ingredient_groups[current_group] = []
                else:
                    ingredient_groups[current_group].append(ingredient)
            
            # Format shopping list
            shopping_list = _format_shopping_list(recipe.name, recipe.servings, ingredient_groups)
            
            return {
                'success': True,
                'recipe_name': recipe.name,
                'servings': recipe.servings,
                'ingredients': recipe.ingredients,
                'ingredient_groups': ingredient_groups,
                'shopping_list': shopping_list,
                'url': recipe.url,
                'prep_time': recipe.prep_time,
                'cook_time': recipe.cook_time
            }
        else:
            return {
                'success': False,
                'error': f'Nu am găsit rețetă pentru "{food_name}"'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Eroare: {str(e)}'
        }


from google import genai
import os

def suggest_recipe_by_ingredients(available_ingredients: List[str]) -> Dict[str, Any]:
    """
    Suggest recipes based on ingredients using Gemini AI.
    Falls back to basic mapping if AI fails.
    """
    # 1. Try Gemini AI first
    try:
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if api_key:
            client = genai.Client(api_key=api_key)
            
            ingredients_str = ", ".join(available_ingredients)
            prompt = f"""
            I have these ingredients: {ingredients_str}.
            Suggest 5 specific Romanian recipes I can cook with some or all of these.
            Return ONLY a valid JSON array of strings, e.g., ["Sarmale", "Pilaf"].
            Do not include markdown formatting or explanations.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean up potential markdown code blocks
            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "")
            
            suggestions = json.loads(text)
            
            if isinstance(suggestions, list) and len(suggestions) > 0:
                return {
                    'success': True,
                    'suggestions': suggestions[:5],
                    'message': f'Am găsit {len(suggestions)} idei de rețete bazate pe ingredientele tale (AI):',
                    'source': 'ai'
                }
    except Exception as e:
        # Log error but continue to fallback
        print(f"AI Suggestion failed: {e}")

    # 2. Fallback to hardcoded mappings
    recipe_suggestions = {
        'pui': ['pilaf de pui', 'pui la cuptor', 'salata de pui', 'supa de pui'],
        'carne': ['sarmale', 'chiftele', 'tocanita', 'musaca'],
        'peste': ['peste la gratar', 'peste la cuptor', 'file de peste pane'],
        'orez': ['pilaf', 'orez cu legume', 'sushi', 'budinca de orez'],
        'paste': ['paste carbonara', 'paste bolognese', 'lasagna', 'paste cu branza'],
        'cartofi': ['cartofi la cuptor', 'piure de cartofi', 'cartofi prajiti'],
        'branza': ['placinta cu branza', 'papanasi', 'paste cu branza'],
        'oua': ['omleta', 'clatite', 'prajitura'],
        'lapte': ['budinca', 'iaurt', 'orez cu lapte'],
        'faina': ['paine', 'pizza', 'placinta', 'clatite']
    }
    
    suggestions = []
    for ingredient in available_ingredients:
        ingredient_lower = ingredient.lower()
        for key, recipes in recipe_suggestions.items():
            if key in ingredient_lower or ingredient_lower in key:
                suggestions.extend(recipes)
    
    # Deduplicate
    unique_suggestions = list(dict.fromkeys(suggestions))
    
    if unique_suggestions:
        return {
            'success': True,
            'suggestions': unique_suggestions[:5],
            'message': f'Am găsit {len(unique_suggestions)} rețete potrivite (Fallback):',
            'source': 'fallback'
        }
    else:
        return {
            'success': True,
            'suggestions': ['pizza', 'paste carbonara', 'supa de legume', 'salata'],
            'message': 'Nu am găsit rețete specifice, dar iată câteva sugestii populare:',
            'source': 'default'
        }


def _format_recipe_summary(recipe: Recipe) -> str:
    """Format recipe as human-readable summary"""
    lines = []
    
    lines.append(f"🍽️  **{recipe.name}**")
    lines.append(f"🔗 {recipe.url}")
    lines.append("")
    
    if recipe.description:
        lines.append(f"📝 {recipe.description[:200]}{'...' if len(recipe.description) > 200 else ''}")
        lines.append("")
    
    # Timing info
    timing = []
    if recipe.prep_time:
        timing.append(f"⏱️  Prep: {recipe.prep_time}")
    if recipe.cook_time:
        timing.append(f"🔥 Cook: {recipe.cook_time}")
    if recipe.total_time:
        timing.append(f"⏰ Total: {recipe.total_time}")
    if recipe.servings:
        timing.append(f"👥 Porții: {recipe.servings}")
    
    if timing:
        lines.append(" | ".join(timing))
        lines.append("")
    
    # Ingredients
    if recipe.ingredients:
        lines.append(f"🥘 **INGREDIENTE** ({len(recipe.ingredients)} items):")
        for ingredient in recipe.ingredients[:15]:  # First 15
            if ingredient.startswith('#'):
                lines.append(f"   **{ingredient[1:].strip()}:**")
            else:
                lines.append(f"   • {ingredient}")
        
        if len(recipe.ingredients) > 15:
            lines.append(f"   ... și încă {len(recipe.ingredients) - 15} ingrediente")
        lines.append("")
    
    # Instructions
    if recipe.instructions:
        lines.append(f"📋 **MOD DE PREPARARE** ({len(recipe.instructions)} pași):")
        for i, instruction in enumerate(recipe.instructions[:3], 1):
            lines.append(f"   {i}. {instruction[:150]}{'...' if len(instruction) > 150 else ''}")
        
        if len(recipe.instructions) > 3:
            lines.append(f"   ... și încă {len(recipe.instructions) - 3} pași")
        lines.append("")
    
    # Nutrition
    if recipe.nutrition_info:
        lines.append("📊 **VALORI NUTRITIONALE:**")
        for key, value in list(recipe.nutrition_info.items())[:6]:
            lines.append(f"   • {key}: {value}")
        lines.append("")
    
    # Media
    media = []
    if recipe.image_url:
        media.append("📸 Imagine")
    if recipe.video_url:
        media.append("🎥 Video")
    
    if media:
        lines.append(f"🎬 **Media:** {' | '.join(media)}")
    
    if recipe.tags:
        lines.append(f"🏷️  **Categorii:** {', '.join(recipe.tags[:5])}")
    
    return "\n".join(lines)


def _format_shopping_list(recipe_name: str, servings: Optional[str], ingredient_groups: Dict[str, List[str]]) -> str:
    """Format ingredients as shopping list"""
    lines = []
    
    lines.append(f"🛒 **LISTA DE CUMPĂRĂTURI**")
    lines.append(f"📝 Pentru: {recipe_name}")
    if servings:
        lines.append(f"👥 Porții: {servings}")
    lines.append("")
    lines.append("=" * 50)
    lines.append("")
    
    for group_name, ingredients in ingredient_groups.items():
        if ingredients:  # Only show groups with ingredients
            lines.append(f"**{group_name}:**")
            for ingredient in ingredients:
                lines.append(f"  ☐ {ingredient}")
            lines.append("")
    
    lines.append("=" * 50)
    lines.append("💡 **Tip:** Poți căuta aceste produse cu comanda:")
    lines.append(f'    "Caută [nume ingredient] în [magazin]"')
    
    return "\n".join(lines)
