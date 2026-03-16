"""
Database for caching recipe search results to avoid redundant scraping
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Database path
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "recipe_cache.db"

def init_recipe_cache_db():
    """Initialize the recipe cache database"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_key TEXT UNIQUE NOT NULL,
                recipe_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                recipe_name TEXT
            )
        """)
        
        # Create index on query_key for fast lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_key 
            ON recipe_cache(query_key)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Recipe cache database initialized: {DB_PATH}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize recipe cache database: {e}")
        return False

def save_recipe_to_cache(query: str, recipe_data: Dict[str, Any], ttl_days: int = 7) -> bool:
    """Save recipe result to database"""
    try:
        if not DB_PATH.exists():
            init_recipe_cache_db()
            
        # Normalize query key
        query_key = query.strip().lower()
        
        # Calculate expiry
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=ttl_days)
        
        # Convert to JSON string
        recipe_json = json.dumps(recipe_data, ensure_ascii=False)
        recipe_name = recipe_data.get("recipe_name", "Unknown")
        
        # Save to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO recipe_cache 
            (query_key, recipe_json, created_at, expires_at, recipe_name)
            VALUES (?, ?, ?, ?, ?)
        """, (
            query_key,
            recipe_json,
            created_at.isoformat(),
            expires_at.isoformat(),
            recipe_name
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Cached recipe for '{query}': {recipe_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save recipe to cache: {e}")
        return False

def load_recipe_from_cache(query: str) -> Optional[Dict[str, Any]]:
    """Load recipe from database by query"""
    try:
        if not DB_PATH.exists():
            return None
            
        query_key = query.strip().lower()
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Load from database
        cursor.execute("""
            SELECT recipe_json, expires_at 
            FROM recipe_cache 
            WHERE query_key = ?
        """, (query_key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        recipe_json, expires_at_str = row
        
        # Check expiry
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now() > expires_at:
            logger.warning(f"⚠️ Recipe cache expired for: {query}")
            return None
        
        # Parse JSON
        recipe_data = json.loads(recipe_json)
        recipe_data["from_cache"] = True
        
        logger.info(f"✅ Loaded recipe from cache for: '{query}'")
        return recipe_data
        
    except Exception as e:
        logger.error(f"❌ Failed to load recipe from cache: {e}")
        return None

# Initialize database on module import
if not DB_PATH.exists():
    init_recipe_cache_db()
