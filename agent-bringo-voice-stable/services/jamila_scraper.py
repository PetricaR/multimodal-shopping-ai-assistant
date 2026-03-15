"""
Jamila Cuisine Recipe Scraper
A web scraper specifically designed to extract detailed recipe information 
from jamilacuisine.ro and save it as structured JSON data.
"""

import json
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from google import genai
import os
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class Recipe:
    """Structured recipe data model"""
    name: str
    url: str
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    total_time: Optional[str] = None
    servings: Optional[str] = None
    difficulty: Optional[str] = None
    ingredients: List[str] = None
    instructions: List[str] = None
    nutrition_info: Dict[str, str] = None
    tags: List[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    scraped_at: Optional[str] = None

    def __post_init__(self):
        if self.ingredients is None:
            self.ingredients = []
        if self.instructions is None:
            self.instructions = []
        if self.nutrition_info is None:
            self.nutrition_info = {}
        if self.tags is None:
            self.tags = []


class JamilaRecipeScraper:
    """Web scraper for jamilacuisine.ro recipes"""
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize scraper with rate limiting
        """
        self.base_url = "https://jamilacuisine.ro"
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.EXCLUDED_PATHS = [
            '/retete-video/ciorbe-si-supe/',
            '/retete-video/aperitive/',
            '/retete-video/dulciuri/',
            '/retete-video/mancaruri/',
            '/retete-video/paine/',
            '/retete-video/salate/',
            '/retete-video/torturi/',
            '/retete-video/diverse/'
        ]
    
    def search_recipe(self, food_name: str) -> List[Dict[str, str]]:
        """
        Search for recipes by food name using site search
        """
        search_url = f"{self.base_url}/?s={quote(food_name)}"
        
        try:
            # Respect rate limiting
            time.sleep(self.delay)
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Use a unified set of selectors to find recipe links
            selectors = [
                'h3.pcsl-title a',      # Small list titles
                'h2.penci-entry-title a', # Grid titles
                'h1.post-title a',      # Post titles
                'a[href*="reteta"]',    # Links containing "reteta"
                'a[href*="video"]'      # Links containing "video"
            ]
            
            # Set of seen URLs to avoid duplicates
            seen_urls = set()
            
            for selector in selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    if not href or not title:
                        continue
                        
                    # Skip if not internal link
                    if 'jamilacuisine.ro' not in href:
                        continue
                        
                    # Skip if already seen
                    if href in seen_urls:
                        continue
                        
                    # Skip excluded paths (categories)
                    if any(exclude in href for exclude in self.EXCLUDED_PATHS):
                        continue
                        
                    # Match query keywords (case insensitive)
                    query_keywords = food_name.lower().split()
                    if not any(keyword in title.lower() for keyword in query_keywords):
                        continue
                        
                    # Add to results
                    seen_urls.add(href)
                    results.append({
                        'title': title,
                        'url': href
                    })
            
            # If no results found with strict matching, try looser logic
            if not results:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    if not href or not title:
                        continue
                        
                    if href in seen_urls:
                        continue
                        
                    if 'jamilacuisine.ro' not in href:
                        continue
                        
                    if not ('reteta' in href.lower() or 'video' in href.lower()):
                        continue
                        
                    if any(exclude in href for exclude in self.EXCLUDED_PATHS):
                        continue
                        
                    seen_urls.add(href)
                    results.append({
                        'title': title,
                        'url': href
                    })

            return results[:5]  # Return top 5 results
            
        except requests.RequestException as e:
            logger.error(f"Error searching for recipe: {e}")
            return []
    
    def _select_best_recipe_with_ai(self, user_query: str, search_results: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """
        Use Gemini AI to intelligently select the best recipe match
        """
        try:
            # Configure Gemini
            api_key = settings.GOOGLE_API_KEY
            if not api_key:
                logger.warning("⚠️ No Gemini API key found, falling back to manual selection")
                return None
            
            # Handle potential SecretStr or plain string
            if hasattr(api_key, 'get_secret_value'):
                api_key_str = api_key.get_secret_value()
            else:
                api_key_str = str(api_key)
                
            client = genai.Client(api_key=api_key_str)
            
            # Prepare recipe options for AI
            recipes_text = ""
            for i, result in enumerate(search_results, 1):
                recipes_text += f"{i}. {result['title']}\n"
            
            # AI prompt for semantic matching
            prompt = f"""You are a recipe matching expert. The user wants to cook: "{user_query}"

Here are the available recipes from Jamila Cuisine:

{recipes_text}

YOUR TASK:
Analyze which recipe BEST matches what the user wants to cook.

UNDERSTANDING RULES:
1. Synonyms: "paste" includes spaghete, penne, tagliatelle, macaroane, fettuccine
2. Synonyms: "pui" includes chicken, pasare
3. Synonyms: "carne" includes vita, porc, beef, veal
4. Synonyms: "peste" includes salmon, somon, ton, fish, pește
5. Context matters: "carbonara" is a specific Italian pasta dish
6. Avoid category pages (they don't have actual recipes)
7. Prefer exact matches over similar dishes

EXAMPLES:
- User: "paste carbonara" → Select "Spaghete carbonara" (spaghete is pasta type)
- User: "pizza" → Select "Pizza turnata" (exact match)
- User: "pui la cuptor" → Select recipe with "pui" AND "cuptor"
- User: "sarmale" → Select "Sarmale" (exact Romanian dish)

RESPOND WITH ONLY THE NUMBER (1, 2, 3, etc.) OF THE BEST MATCH.
If uncertain or no good match, respond with "0".

Best match number:"""

            # Get AI response
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            ai_choice = response.text.strip()
            
            logger.info(f"🤖 AI selected: {ai_choice}")
            
            # Parse AI response
            try:
                choice_num = int(ai_choice)
                if 1 <= choice_num <= len(search_results):
                    selected = search_results[choice_num - 1]
                    logger.info(f"✅ AI match: {selected['title']}")
                    return selected
                else:
                    logger.warning(f"⚠️ AI returned invalid choice: {choice_num}")
                    return None
            except ValueError:
                logger.warning(f"⚠️ AI returned non-numeric response: {ai_choice}")
                return None
        
        except Exception as e:
            logger.error(f"❌ AI selection error: {e}")
            return None
    
    def extract_recipe_details(self, recipe_url: str) -> Recipe:
        """
        Extract detailed recipe information from a JamilaCuisine recipe page
        """
        try:
            time.sleep(self.delay)  # Rate limiting
            response = self.session.get(recipe_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Initialize recipe object
            recipe = Recipe(
                name=self._extract_title(soup),
                url=recipe_url,
                scraped_at=time.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # Extract recipe details using JSON-LD and HTML
            recipe.description = self._extract_description(soup)
            recipe.prep_time = self._extract_time_info(soup, 'prep')
            recipe.cook_time = self._extract_time_info(soup, 'cook')
            recipe.total_time = self._extract_time_info(soup, 'total')
            recipe.servings = self._extract_servings(soup)
            recipe.ingredients = self._extract_ingredients(soup)
            recipe.instructions = self._extract_instructions(soup)
            recipe.nutrition_info = self._extract_nutrition(soup)
            recipe.tags = self._extract_tags(soup)
            recipe.image_url = self._extract_image_url(soup, recipe_url)
            recipe.video_url = self._extract_video_url(soup)
            
            return recipe
            
        except requests.RequestException as e:
            logger.error(f"Error extracting recipe details: {e}")
            return Recipe(name="Error", url=recipe_url)
    
    def _extract_json_ld_data(self, soup: BeautifulSoup) -> Dict:
        """Extract JSON-LD structured data"""
        json_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                
                # Handle single recipe object
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    return data
                
                # Handle @graph structure (common in WordPress)
                elif isinstance(data, dict) and '@graph' in data:
                    for item in data['@graph']:
                        if item.get('@type') == 'Recipe':
                            return item
                            
            except json.JSONDecodeError:
                continue
        
        return {}
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract recipe title"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('name'):
            return json_data['name']
        
        # HTML selectors
        selectors = [
            'h1.post-title',
            'h1.entry-title',
            'h1.recipe-title',
            '.wprm-recipe-name',
            'h1'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        return "Unknown Recipe"
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract recipe description"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('description'):
            return json_data['description']
        
        # Look for recipe summary/description
        selectors = [
            '.wprm-recipe-summary',
            '.recipe-description',
            '.entry-content p:first-of-type'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        return None
    
    def _extract_time_info(self, soup: BeautifulSoup, time_type: str) -> Optional[str]:
        """Extract time information (prep, cook, total)"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        
        time_key_map = {
            'prep': 'prepTime',
            'cook': 'cookTime', 
            'total': 'totalTime'
        }
        
        json_key = time_key_map.get(time_type)
        if json_key and json_data.get(json_key):
            time_str = json_data[json_key]
            # Convert ISO 8601 duration (PT20M) to readable format
            if time_str.startswith('PT'):
                return self._parse_iso_duration(time_str)
            return time_str
        
        # HTML selectors
        css_class_map = {
            'prep': ['.wprm-recipe-prep-time', '.prep-time'],
            'cook': ['.wprm-recipe-cook-time', '.cook-time'],
            'total': ['.wprm-recipe-total-time', '.total-time']
        }
        
        selectors = css_class_map.get(time_type, [])
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if any(word in text.lower() for word in ['min', 'ore', 'hour', 'minute']):
                    return text
        
        return None
    
    def _parse_iso_duration(self, duration: str) -> str:
        """Convert ISO 8601 duration to readable format"""
        # Simple parser for PT20M, PT1H30M etc.
        duration = duration.replace('PT', '')
        
        hours = 0
        minutes = 0
        
        if 'H' in duration:
            hours_str = duration.split('H')[0]
            hours = int(hours_str) if hours_str.isdigit() else 0
            duration = duration.split('H')[1] if 'H' in duration else duration
        
        if 'M' in duration:
            minutes_str = duration.replace('M', '')
            minutes = int(minutes_str) if minutes_str.isdigit() else 0
        
        if hours > 0 and minutes > 0:
            return f"{hours} ora {minutes} minute"
        elif hours > 0:
            return f"{hours} ora"
        elif minutes > 0:
            return f"{minutes} minute"
        
        return duration
    
    def _extract_servings(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract number of servings"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('recipeYield'):
            yield_data = json_data['recipeYield']
            if isinstance(yield_data, list):
                return yield_data[0] if yield_data else None
            return str(yield_data)
        
        # HTML selectors
        selectors = [
            '.wprm-recipe-servings',
            '.servings',
            '.recipe-servings'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if re.search(r'\d+', text):
                    return text
        
        return None
    
    def _extract_ingredients(self, soup: BeautifulSoup) -> List[str]:
        """Extract ingredients list with improved parsing for JamilaCuisine structure"""
        ingredients = []
        
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('recipeIngredient'):
            return [ing.strip() for ing in json_data['recipeIngredient'] if ing.strip()]
        
        # Look for ingredient groups (Pentru aluat, Pentru topping, etc.)
        ingredient_groups = soup.select('.wprm-recipe-ingredient-group')
        
        if ingredient_groups:
            for group in ingredient_groups:
                # Get group name if available
                group_name = group.select_one('.wprm-recipe-group-name')
                if group_name:
                    group_title = group_name.get_text(strip=True)
                    # Add group header as a comment in ingredients
                    ingredients.append(f"# {group_title}")
                
                # Get ingredients in this group
                group_ingredients = group.select('.wprm-recipe-ingredient')
                for ingredient in group_ingredients:
                    ingredient_text = self._parse_single_ingredient(ingredient)
                    if ingredient_text:
                        ingredients.append(ingredient_text)
        else:
            # Fallback to all ingredients without groups
            all_ingredients = soup.select('.wprm-recipe-ingredient')
            for ingredient in all_ingredients:
                ingredient_text = self._parse_single_ingredient(ingredient)
                if ingredient_text:
                    ingredients.append(ingredient_text)
        
        # If still no ingredients, try basic selectors
        if not ingredients:
            selectors = [
                '.recipe-ingredients li',
                '.ingredients li',
                '.wprm-recipe-ingredients li'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        if text and len(text) > 3:
                            # Clean up checkbox symbols and extra spaces
                            text = re.sub(r'^[▢\s]+', '', text)
                            ingredients.append(text)
                    if ingredients:
                        break
        
        return ingredients
    
    def _parse_single_ingredient(self, ingredient_element) -> Optional[str]:
        """Parse a single ingredient element with amount, unit, and name"""
        try:
            # Try structured parsing first
            amount = ingredient_element.select_one('.wprm-recipe-ingredient-amount')
            unit = ingredient_element.select_one('.wprm-recipe-ingredient-unit') 
            name = ingredient_element.select_one('.wprm-recipe-ingredient-name')
            
            if amount and name:
                # Build ingredient string
                ingredient_parts = []
                
                amount_text = amount.get_text(strip=True)
                if amount_text:
                    ingredient_parts.append(amount_text)
                
                unit_text = unit.get_text(strip=True) if unit else ""
                if unit_text:
                    ingredient_parts.append(unit_text)
                
                name_text = name.get_text(strip=True)
                if name_text:
                    # Clean up HTML tags from name (like <strong>oregano</strong>)
                    name_text = re.sub(r'<[^>]+>', '', name_text)
                    ingredient_parts.append(name_text)
                
                if ingredient_parts:
                    result = ' '.join(ingredient_parts)
                    # Clean up extra spaces
                    result = re.sub(r'\s+', ' ', result)
                    return result
            else:
                # Fallback to full element text
                text = ingredient_element.get_text(strip=True)
                if text and len(text) > 3:
                    # Remove checkbox symbols and clean up
                    text = re.sub(r'^[▢\s]+', '', text)
                    text = re.sub(r'\s+', ' ', text)
                    return text
        
        except Exception:
            # Last resort - just get text content
            text = ingredient_element.get_text(strip=True)
            if text and len(text) > 3:
                text = re.sub(r'^[▢\s]+', '', text)
                text = re.sub(r'\s+', ' ', text)
                return text
        
        return None
    
    def _extract_instructions(self, soup: BeautifulSoup) -> List[str]:
        """Extract cooking instructions with better parsing"""
        instructions = []
        
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('recipeInstructions'):
            for instruction in json_data['recipeInstructions']:
                if isinstance(instruction, dict):
                    text = instruction.get('text', '')
                    if text:
                        instructions.append(text.strip())
                elif isinstance(instruction, str):
                    instructions.append(instruction.strip())
            
            if instructions:
                return instructions
        
        # Look for instruction groups
        instruction_groups = soup.select('.wprm-recipe-instruction-group')
        
        if instruction_groups:
            for group in instruction_groups:
                # Get group instructions
                group_instructions = group.select('.wprm-recipe-instruction-text')
                for instruction in group_instructions:
                    text = instruction.get_text(strip=True)
                    if text and len(text) > 10:
                        instructions.append(text)
        else:
            # Fallback selectors
            selectors = [
                '.wprm-recipe-instructions .wprm-recipe-instruction-text',
                '.wprm-recipe-instruction .wprm-recipe-instruction-text',
                '.recipe-instructions li',
                '.instructions li'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(strip=True)
                        if text and len(text) > 10:
                            instructions.append(text)
                    if instructions:
                        break
        
        # Also look for text content that mentions video instructions
        if not instructions:
            # Look for paragraph content that might contain instructions
            content_paragraphs = soup.select('.post-entry p, .entry-content p')
            for para in content_paragraphs:
                text = para.get_text(strip=True)
                if any(keyword in text.lower() for keyword in ['instructiuni', 'preparare', 'mod de', 'reteta', 'urmareste']):
                    if len(text) > 50:  # Substantial instruction text
                        instructions.append(text)
                        break
        
        return instructions
    
    def _extract_nutrition(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract nutrition information with enhanced parsing"""
        nutrition = {}
        
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('nutrition'):
            nutrition_data = json_data['nutrition']
            if isinstance(nutrition_data, dict):
                for key, value in nutrition_data.items():
                    if key != '@type' and value:
                        # Clean up key names
                        clean_key = key.replace('Content', '').replace('content', '')
                        nutrition[clean_key] = str(value)
        
        # Look for nutrition labels in HTML - JamilaCuisine specific format
        nutrition_container = soup.select_one('.wprm-nutrition-label-container')
        if nutrition_container:
            # Parse the nutrition text line (like "Calorii: 437kcal | Glucide: 31g | ...")
            nutrition_text = nutrition_container.get_text()
            
            # Split by | to get individual nutrition facts
            nutrition_parts = nutrition_text.split('|')
            for part in nutrition_parts:
                part = part.strip()
                if ':' in part:
                    try:
                        key, value = part.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        if key and value:
                            nutrition[key] = value
                    except ValueError:
                        continue
        
        # Also look for individual nutrition elements
        nutrition_elements = soup.select('.wprm-nutrition-label-text-nutrition-container')
        for element in nutrition_elements:
            label_elem = element.select_one('.wprm-nutrition-label-text-nutrition-label')
            value_elem = element.select_one('.wprm-nutrition-label-text-nutrition-value')
            unit_elem = element.select_one('.wprm-nutrition-label-text-nutrition-unit')
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True).replace(':', '').strip()
                value = value_elem.get_text(strip=True)
                unit = unit_elem.get_text(strip=True) if unit_elem else ''
                
                if label and value:
                    nutrition[label] = f"{value} {unit}".strip()
        
        return nutrition
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract recipe tags"""
        tags = []
        
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        
        # Extract recipe category and cuisine
        for key in ['recipeCategory', 'recipeCuisine']:
            value = json_data.get(key)
            if value:
                if isinstance(value, list):
                    tags.extend(value)
                else:
                    tags.append(value)
        
        # HTML selectors for tags
        tag_selectors = [
            '.pctmp-term-item',
            '.recipe-tags a',
            '.tags a',
            '.post-tags a'
        ]
        
        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                tag_text = element.get_text(strip=True)
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
        
        return tags
    
    def _extract_image_url(self, soup: BeautifulSoup, recipe_url: str) -> Optional[str]:
        """Extract recipe image URL"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('image'):
            image_data = json_data['image']
            if isinstance(image_data, list) and image_data:
                return image_data[0]
            elif isinstance(image_data, str):
                return image_data
        
        # HTML selectors
        selectors = [
            '.wprm-recipe-image img',
            '.recipe-image img',
            '.post-image img',
            'meta[property="og:image"]'
        ]
        
        for selector in selectors:
            if 'meta' in selector:
                element = soup.select_one(selector)
                if element:
                    return element.get('content')
            else:
                element = soup.select_one(selector)
                if element:
                    src = element.get('src') or element.get('data-src')
                    if src:
                        return urljoin(recipe_url, src)
        
        return None
    
    def _extract_video_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract recipe video URL"""
        # Try JSON-LD first
        json_data = self._extract_json_ld_data(soup)
        if json_data.get('video'):
            video_data = json_data['video']
            if isinstance(video_data, dict):
                return video_data.get('contentUrl') or video_data.get('embedUrl')
            elif isinstance(video_data, str):
                return video_data
        
        # Look for YouTube embeds
        iframe = soup.select_one('iframe[src*="youtube.com"]')
        if iframe:
            return iframe.get('src')
        
        return None
    
    def get_recipe(self, food_name: str) -> Optional[Recipe]:
        """
        Main method to get recipe by food name
        """
        logger.info(f"Searching for: {food_name}")
        
        # Search for recipes
        search_results = self.search_recipe(food_name)
        
        if not search_results:
            logger.info("No search results found")
            return None
        
        logger.info(f"Found {len(search_results)} results")
        
        # AI-POWERED SEMANTIC MATCHING: Let Gemini decide the best match
        best_match = self._select_best_recipe_with_ai(food_name, search_results)
        
        if not best_match:
            logger.info("\n⚠️ AI couldn't select best match, using fallback")
            # Fallback: use first non-category result
            for result in search_results:
                if not any(exclude in result['url'] for exclude in self.EXCLUDED_PATHS):
                    best_match = result
                    break
        
        if not best_match:
            best_match = search_results[0]  # Final fallback
        
        recipe_url = best_match['url']
        logger.info(f"\n✅ BEST MATCH: {best_match['title']}")
        logger.info(f"🔗 URL: {recipe_url}")
        
        # Extract detailed recipe information
        recipe = self.extract_recipe_details(recipe_url)
        
        return recipe

