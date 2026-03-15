"""
Pydantic models for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class SearchRequest(BaseModel):
    """Request model for product similarity search"""
    
    product_name: Optional[str] = Field(
        None,
        description="Product name to find similar products for"
    )
    
    query_text: Optional[str] = Field(
        None,
        description="Text query for product search (Romanian)"
    )
    
    top_k: int = Field(
        20,
        ge=1,
        le=100,
        description="Number of similar products to return"
    )
    
    use_ranking: bool = Field(
        True,
        description="Enable Ranking API for precision (+15-25% accuracy)"
    )
    
    in_stock_only: bool = Field(
        False,
        description="Only return products in stock"
    )

    # Multi-store and multi-query support
    multi_store: bool = Field(
        False,
        description="Enable multi-store parallel search"
    )
    
    queries: Optional[List[str]] = Field(
        None,
        description="List of search queries for sequential or multi-store execution"
    )

    # Query enrichment & price filtering
    use_query_enrichment: bool = Field(
        False,
        description="Use Gemini to parse price constraints from natural-language queries"
    )
    price_min: Optional[float] = Field(None, description="Minimum price filter (RON)")
    price_max: Optional[float] = Field(None, description="Maximum price filter (RON)")

    class Config:
        json_schema_extra = {
            "example": {
                "product_name": "Lapte Zuzu 3.5% 1L",
                "top_k": 20,
                "use_ranking": True,
                "in_stock_only": False
            }
        }

class ProductInfo(BaseModel):
    """Product information model"""
    
    product_id: str
    variant_id: Optional[str] = None
    product_name: str
    category: Optional[str] = None
    producer: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    in_stock: bool = False
    
    # Store information
    store_id: Optional[str] = None
    store_name: Optional[str] = None
    delivery_fee: Optional[float] = None
    url: Optional[str] = None
    
    similarity_score: Optional[float] = Field(
        None,
        description="Cosine similarity score (0-1, higher = more similar)"
    )
    
    ranking_score: Optional[float] = Field(
        None,
        description="Ranking API relevance score (0-1, higher = more relevant)"
    )
    
    distance: Optional[float] = Field(
        None,
        description="Vector distance (lower = more similar)"
    )

    # Substitution specific fields
    gemini_confidence: Optional[float] = Field(
        None,
        description="Gemini's confidence in this substitution (0-1)"
    )
    
    substitution_reason: Optional[str] = Field(
        None,
        description="Romanian reasoning for this substitution"
    )
    
    price_difference: Optional[float] = Field(
        None,
        description="Price difference from missing product (RON)"
    )

    # Search & Optimization scores (Reference alignment)
    price_score: Optional[float] = Field(None, description="Score based on price competitive (0-1)")
    quality_score: Optional[float] = Field(None, description="Score based on brand/category quality (0-1)")
    budget_fit: Optional[float] = Field(None, description="How well this fits the user's budget (0-1)")
    match_reason: Optional[str] = Field(None, description="Detailed reason why this product matched")

class SearchResponse(BaseModel):
    """Response model for product similarity search"""
    
    query_product: Optional[ProductInfo] = Field(
        None,
        description="The query product (if searched by product_id)"
    )
    
    similar_products: List[ProductInfo] = Field(
        [],
        description="List of similar products ranked by relevance"
    )
    
    search_method: str = Field(
        ...,
        description="Search method used: 'multimodal_with_ranking', 'multimodal_only', or 'text_search'"
    )
    
    candidates_retrieved: int = Field(
        ...,
        description="Number of candidates retrieved from Vector Search"
    )
    
    candidates_ranked: Optional[int] = Field(
        None,
        description="Number of candidates reranked (if Ranking API used)"
    )
    
    query_time_ms: float = Field(
        ...,
        description="Total query time in milliseconds"
    )

    # Metadata for end-to-end flow
    cache_key: Optional[str] = Field(None, description="Key to retrieve these results from persistent cache")
    optimization_summary: Optional[str] = Field(None, description="Summary of best store/price options")
    searched_stores: List[str] = Field(default=[], description="List of stores searched")
    enriched_query: Optional[str] = Field(None, description="Cleaned query after Gemini enrichment")
    applied_filters: Optional[Dict] = Field(None, description="Filters applied to the search results")

class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str
    version: str
    components: dict

# --- Substitution Models ---

class SubstitutionRequest(BaseModel):
    """Request model for product substitution suggestions"""
    missing_product_name: str
    current_basket: List[Dict] = Field(default=[], description="Items currently in the basket")
    user_history: List[Dict] = Field(default=[], description="Past purchase history of the user")
    top_k: int = Field(default=5, description="Number of suggestions to return")

    class Config:
        json_schema_extra = {
            "example": {
                "missing_product_name": "Lapte Zuzu 3.5% 1L",
                "top_k": 5,
                "current_basket": [{"product_id": "54321", "product_name": "Paste Băneasa", "category": "Paste", "price": 5.5, "quantity": 1}],
                "user_history": []
            }
        }

class SubstitutionResponse(BaseModel):
    """Response model for product substitution suggestions"""
    missing_product: ProductInfo
    suggestions: List[ProductInfo]
    query_time_ms: float
    method: str
    metadata: Optional[Dict] = None

# --- Shopping Agent Models ---

class AuthCredentials(BaseModel):
    """Credentials for Bringo authentication"""
    username: str
    password: str
    store: Optional[str] = "carrefour_park_lake"

class AuthResponse(BaseModel):
    """Authentication result"""
    status: str
    message: Optional[str] = None
    username: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    phpsessid: Optional[str] = None
    expires_at: Optional[str] = None

class StoreSearchRequest(BaseModel):
    """Request to find stores at an address"""
    address: str

class StoreInfo(BaseModel):
    """Store information"""
    store_id: str
    name: str
    category: str
    url: str
    status: str
    schedule: Optional[Dict[str, str]] = None

class StoreListResponse(BaseModel):
    """List of stores"""
    status: str
    stores: List[StoreInfo]
    count: int

class CartItemRequest(BaseModel):
    """Item to add to cart"""
    product_id: str
    variant_id: Optional[str] = None  # Ideally provided, fallback to scraping
    product_url: Optional[str] = None  # Required if variant_id is missing
    quantity: int = 1
    product_name: Optional[str] = None
    store_id: Optional[str] = None

class CartBatchRequest(BaseModel):
    """Batch add to cart"""
    items: List[CartItemRequest]
    store_id: Optional[str] = None

class CartOperationResponse(BaseModel):
    """Cart operation result"""
    status: str
    message: str
    cart_count: Optional[int] = None
    items_added: Optional[List[Dict]] = None
    failed_items: Optional[List[Dict]] = None
    timing_ms: Optional[Dict] = None
    quantity: Optional[int] = None

class RecipeSearchRequest(BaseModel):
    """Recipe search request"""
    food_name: str

class RecipeInfo(BaseModel):
    """Recipe details"""
    recipe_name: str
    url: str
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    servings: Optional[str] = None
    ingredients: List[str]
    formatted_summary: Optional[str] = None
    shopping_list: Optional[str] = None

class RecipeResponse(BaseModel):
    """Recipe search response"""
    status: str
    found: bool
    recipe: Optional[RecipeInfo] = None
    suggestions: Optional[List[str]] = None
    error: Optional[str] = None

class RecipeIngredientsResponse(BaseModel):
    """Response model for getting ingredients from a recipe"""
    status: str
    message: Optional[str] = None
    recipe_name: Optional[str] = None
    servings: Optional[str] = None
    ingredients: List[str] = Field(default_factory=list)
    ingredient_groups: Dict[str, List[str]] = Field(default_factory=dict)
    shopping_list: Optional[str] = None
    url: Optional[str] = None

class OptimizationRequest(BaseModel):
    """Request to optimize a shopping list for a specific budget"""
    cache_key: str
    budget_ron: float

class OptimizationResult(BaseModel):
    """Result of budget optimization"""
    status: str
    budget: float
    final_total: float
    items: List[ProductInfo]
    under_budget: bool
    savings: float
    message: Optional[str] = None

class LiveSearchRequest(BaseModel):
    """Request for real-time multi-store search"""
    queries: List[str]
    stores: Optional[List[Dict[str, str]]] = None
    address: Optional[str] = None

# --- Chef AI Personalization Models ---

class PhysicalStats(BaseModel):
    age: int
    gender: str
    weight_kg: float

class DietaryProfile(BaseModel):
    calorie_target: int
    primary_diets: List[str]
    allergies: List[str]
    exclusions: List[str]
    nutrition_targets: List[str]

class MealPreferences(BaseModel):
    meal_types: List[str]
    complexity: str
    adults: int
    children: int
    frequency_cooking: str
    variety: str
    cooking_methods: List[str]

class FinancialProfile(BaseModel):
    budget_ron_month: float

class UserProfile(BaseModel):
    """Full user profile for Chef AI (BR01, BR02, BR03)"""
    user_id: str = "default_user"
    physical: PhysicalStats
    dietary: DietaryProfile
    preferences: MealPreferences
    finance: FinancialProfile

class UserProfileUpdate(BaseModel):
    """Request model for updating specific profile sections"""
    physical: Optional[PhysicalStats] = None
    dietary: Optional[DietaryProfile] = None
    preferences: Optional[MealPreferences] = None
    finance: Optional[FinancialProfile] = None


class MealItem(BaseModel):
    name: str
    description: Optional[str] = None
    recipe_url: Optional[str] = None
    image_url: Optional[str] = None
    prep_time: Optional[str] = None

class DayPlan(BaseModel):
    day_name: str
    breakfast: MealItem
    lunch: MealItem
    dinner: MealItem
    snack: MealItem

class WeeklyPlan(BaseModel):
    title: str
    days: Dict[str, DayPlan]

class DishDetails(BaseModel):
    name: str
    ingredients: List[str]
    instructions: List[str]
    cooking_time_minutes: int
    servings: int

class SpecialEventPlan(BaseModel):
    event_type: str
    guest_count: int
    dishes: List[DishDetails]
    extras: List[str]
