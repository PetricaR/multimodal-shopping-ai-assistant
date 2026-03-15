"""
Database for caching search results to avoid large JSON string parameters
This solves the malformed function call issue with very large search results
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
DB_PATH = DATA_DIR / "search_cache.db"

def init_cache_db():
    """Initialize the search results cache database"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_results_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                search_results_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL,
                products_count INTEGER DEFAULT 0,
                stores_count INTEGER DEFAULT 0
            )
        """)
        
        # Create index on cache_key for fast lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_key 
            ON search_results_cache(cache_key)
        """)
        
        # Create index on expires_at for cleanup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at 
            ON search_results_cache(expires_at)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Search cache database initialized: {DB_PATH}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize cache database: {e}")
        return False

def save_search_results(search_results: Dict[str, Any], ttl_hours: int = 24) -> Optional[str]:
    """Save search results to database and return cache_key"""
    try:
        if not DB_PATH.exists():
            init_cache_db()
            
        # Generate cache key (timestamp + hash)
        import hashlib
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(json.dumps(search_results, sort_keys=True).encode()).hexdigest()[:8]
        cache_key = f"search_{content_hash}_{int(datetime.now().timestamp())}"
        
        # Calculate expiry
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=ttl_hours)
        
        # Extract metadata
        status = search_results.get("status", "unknown")
        products_count = 0
        stores_count = search_results.get("stores_count", 0)
        
        # Count total products
        results = search_results.get("results", {})
        if isinstance(results, dict):
            for product_data in results.values():
                if isinstance(product_data, dict):
                    products = product_data.get("products", [])
                    if isinstance(products, list):
                        products_count += len(products)
        
        # Convert to JSON string
        results_json = json.dumps(search_results, ensure_ascii=False)
        
        # Save to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO search_results_cache 
            (cache_key, search_results_json, created_at, expires_at, status, products_count, stores_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            cache_key,
            results_json,
            created_at.isoformat(),
            expires_at.isoformat(),
            status,
            products_count,
            stores_count
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Cached search results: {cache_key} ({products_count} products, {stores_count} stores)")
        return cache_key
        
    except Exception as e:
        logger.error(f"❌ Failed to save search results to cache: {e}")
        return None

def load_search_results(cache_key: str) -> Optional[Dict[str, Any]]:
    """Load search results from database by cache_key"""
    try:
        if not DB_PATH.exists():
            return None
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Load from database
        cursor.execute("""
            SELECT search_results_json, expires_at 
            FROM search_results_cache 
            WHERE cache_key = ?
        """, (cache_key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.warning(f"⚠️ Cache key not found: {cache_key}")
            return None
        
        results_json, expires_at_str = row
        
        # Check expiry
        expires_at = datetime.fromisoformat(expires_at_str)
        now = datetime.now(expires_at.tzinfo)
        if now > expires_at:
            logger.warning(f"⚠️ Cache expired: {cache_key}")
            # Delete expired entry
            delete_cache_entry(cache_key)
            return None
        
        # Parse JSON
        search_results = json.loads(results_json)
        
        logger.info(f"✅ Loaded search results from cache: {cache_key}")
        return search_results
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse cached JSON for {cache_key}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to load search results from cache: {e}")
        return None

def delete_cache_entry(cache_key: str) -> bool:
    """Delete a specific cache entry"""
    try:
        if not DB_PATH.exists():
            return False
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM search_results_cache WHERE cache_key = ?", (cache_key,))
        
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        
        if deleted:
            logger.info(f"✅ Deleted cache entry: {cache_key}")
        
        return deleted
        
    except Exception as e:
        logger.error(f"❌ Failed to delete cache entry: {e}")
        return False

def cleanup_expired_cache(max_age_hours: int = 48) -> int:
    """Clean up expired cache entries"""
    try:
        if not DB_PATH.exists():
            return 0
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM search_results_cache 
            WHERE expires_at < ?
        """, (cutoff.isoformat(),))
        
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            logger.info(f"✅ Cleaned up {deleted} expired cache entries")
        
        return deleted
        
    except Exception as e:
        logger.error(f"❌ Failed to cleanup cache: {e}")
        return 0

def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the cache"""
    try:
        if not DB_PATH.exists():
            return {'status': 'empty', 'message': 'Cache database does not exist yet'}
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM search_results_cache")
        total = cursor.fetchone()[0]
        
        # Active entries (not expired)
        cursor.execute("""
            SELECT COUNT(*) FROM search_results_cache 
            WHERE expires_at > ?
        """, (datetime.now().isoformat(),))
        active = cursor.fetchone()[0]
        
        # Total products cached
        cursor.execute("SELECT SUM(products_count) FROM search_results_cache")
        total_products = cursor.fetchone()[0] or 0
        
        # Total stores cached
        cursor.execute("SELECT SUM(stores_count) FROM search_results_cache")
        total_stores = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "total_products": total_products,
            "total_stores": total_stores
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get cache stats: {e}")
        return {}

# Initialize database on module import
if not DB_PATH.exists():
    init_cache_db()
