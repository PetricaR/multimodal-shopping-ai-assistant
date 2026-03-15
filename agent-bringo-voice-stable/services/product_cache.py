"""
Database cache for product_details (product_id + variant_id)
Speeds up add_to_cart operations by avoiding repeated URL scraping

This cache stores:
- product_url → (product_id, variant_id, product_name)

Benefits:
- 🚀 Instant add_to_cart (no scraping needed)
- 💾 Persistent across sessions
- ⏱️ TTL-based expiration (24h default)
- 🔄 Auto-refresh on cache miss
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "product_details_cache.db")

def init_product_cache_db():
    """Initialize the product details cache database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_details_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_url TEXT UNIQUE NOT NULL,
                product_url_hash TEXT NOT NULL,
                product_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                product_name TEXT,
                store_id TEXT,
                price REAL,
                image_url TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        
        # Create index on product_url_hash for fast lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_hash 
            ON product_details_cache(product_url_hash)
        """)
        
        # Create index on expires_at for cleanup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at 
            ON product_details_cache(expires_at)
        """)
        
        # Create index on store_id for store-specific queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_store_id 
            ON product_details_cache(store_id)
        """)
        
        # 🚀 NEW: Index on product_id for ultra-fast variant_id lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_id 
            ON product_details_cache(product_id)
        """)
        
        # 🚀 NEW: Composite index for product_id + store_id (fastest lookup)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_store 
            ON product_details_cache(product_id, store_id)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Product details cache database initialized: {DB_PATH}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize product cache database: {e}")
        return False


def _get_url_hash(url: str) -> str:
    """Generate consistent hash for URL"""
    return hashlib.md5(url.encode()).hexdigest()


def save_product_details(
    product_url: str,
    product_id: str,
    variant_id: str,
    product_name: Optional[str] = None,
    store_id: Optional[str] = None,
    price: Optional[float] = None,
    image_url: Optional[str] = None,
    ttl_hours: int = 24
) -> bool:
    """
    Save product details to cache
    
    Args:
        product_url: Full product URL
        product_id: Extracted product ID
        variant_id: Extracted variant ID (vsp-X-XXX-XXXXX)
        product_name: Product name (optional)
        store_id: Store ID (optional)
        ttl_hours: Time to live in hours (default 24h)
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Ensure database exists
        if not os.path.exists(DB_PATH):
            init_product_cache_db()
        
        # Calculate timestamps
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=ttl_hours)
        url_hash = _get_url_hash(product_url)
        
        # Save to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Use INSERT OR REPLACE to update if exists
        cursor.execute("""
            INSERT OR REPLACE INTO product_details_cache 
            (product_url, product_url_hash, product_id, variant_id, product_name, store_id, price, image_url,
             created_at, expires_at, last_accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT access_count FROM product_details_cache WHERE product_url = ?), 0) + 1)
        """, (
            product_url,
            url_hash,
            product_id,
            variant_id,
            product_name,
            store_id,
            price,
            image_url,
            created_at.isoformat(),
            expires_at.isoformat(),
            created_at.isoformat(),
            product_url  # For COALESCE subquery
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Cached product details: {product_id} → {variant_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save product details to cache: {e}")
        return False


def load_product_details(product_url: str) -> Optional[Dict[str, Any]]:
    """
    Load product details from cache
    
    Args:
        product_url: Full product URL
        
    Returns:
        Dict with product_id, variant_id, product_name, etc. if found and not expired
        None if not found or expired
    """
    try:
        # Ensure database exists
        if not os.path.exists(DB_PATH):
            logger.info("Cache database doesn't exist yet")
            return None
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        url_hash = _get_url_hash(product_url)
        now = datetime.now().isoformat()
        
        # Query cache
        cursor.execute("""
            SELECT product_id, variant_id, product_name, store_id, price, image_url, created_at, expires_at, access_count
            FROM product_details_cache
            WHERE product_url_hash = ? AND expires_at > ?
        """, (url_hash, now))
        
        row = cursor.fetchone()
        
        if row:
            # Update access count and last_accessed_at
            cursor.execute("""
                UPDATE product_details_cache
                SET last_accessed_at = ?, access_count = access_count + 1
                WHERE product_url_hash = ?
            """, (now, url_hash))
            conn.commit()
            
            result = {
                'status': 'success',
                'source': 'cache',
                'product_id': row[0],
                'variant_id': row[1],
                'product_name': row[2],
                'store_id': row[3],
                'price': row[4],
                'image_url': row[5],
                'cached_at': row[6],
                'expires_at': row[7],
                'access_count': row[8],
                'product_url': product_url
            }
            
            logger.info(f"✅ Cache HIT: {row[0]} → {row[1]} (accessed {result['access_count']} times)")
            conn.close()
            return result
        
        conn.close()
        logger.info(f"Cache MISS: {product_url[:80]}...")
        return None
        
    except Exception as e:
        logger.error(f"❌ Failed to load product details from cache: {e}")
        return None


def cleanup_expired_cache(max_age_hours: int = 48) -> int:
    """
    Remove expired entries from cache
    
    Args:
        max_age_hours: Remove entries older than this (default 48h)
        
    Returns:
        Number of entries deleted
    """
    try:
        if not os.path.exists(DB_PATH):
            return 0
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        
        cursor.execute("""
            DELETE FROM product_details_cache
            WHERE expires_at < ?
        """, (cutoff_time,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"🗑️ Cleaned up {deleted_count} expired product cache entries")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Failed to cleanup expired cache: {e}")
        return 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics
    
    Returns:
        Dict with cache stats (total entries, expired, most accessed products, etc.)
    """
    try:
        if not os.path.exists(DB_PATH):
            return {
                'status': 'empty',
                'message': 'Cache database does not exist yet'
            }
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM product_details_cache")
        total = cursor.fetchone()[0]
        
        # Active (not expired)
        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM product_details_cache
            WHERE expires_at > ?
        """, (now,))
        active = cursor.fetchone()[0]
        
        # Expired
        expired = total - active
        
        # Most accessed products
        cursor.execute("""
            SELECT product_name, product_id, variant_id, access_count, store_id
            FROM product_details_cache
            WHERE expires_at > ?
            ORDER BY access_count DESC
            LIMIT 10
        """, (now,))
        
        top_products = [
            {
                'product_name': row[0],
                'product_id': row[1],
                'variant_id': row[2],
                'access_count': row[3],
                'store_id': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        # Cache size (MB)
        try:
            cursor.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
            size_bytes = cursor.fetchone()[0]
            size_mb = size_bytes / (1024 * 1024)
        except:
            size_mb = 0.0
        
        conn.close()
        
        return {
            'status': 'active',
            'total_entries': total,
            'active_entries': active,
            'expired_entries': expired,
            'cache_size_mb': round(size_mb, 2),
            'top_products': top_products,
            'database_path': DB_PATH
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get cache stats: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


def invalidate_product_cache(product_url: str) -> bool:
    """
    Manually invalidate (delete) a specific product from cache
    Useful when product details change
    
    Args:
        product_url: Product URL to invalidate
        
    Returns:
        True if deleted, False otherwise
    """
    try:
        if not os.path.exists(DB_PATH):
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        url_hash = _get_url_hash(product_url)
        cursor.execute("""
            DELETE FROM product_details_cache
            WHERE product_url_hash = ?
        """, (url_hash,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"🗑️ Invalidated cache for: {product_url[:80]}...")
        
        return deleted
        
    except Exception as e:
        logger.error(f"❌ Failed to invalidate cache: {e}")
        return False


def load_variant_by_product_id(product_id: str, store_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    🚀 ULTRA-FAST LOOKUP: Get variant_id directly by product_id
    
    This is MUCH faster than URL-based lookup when you already have product_id
    from search results. Avoids scraping entirely!
    
    Args:
        product_id: Product ID (e.g., "857828")
        store_id: Optional store filter (e.g., "auchan_colosseum")
        
    Returns:
        Dict with variant_id and other details if found and not expired
        None if not found or expired
    """
    try:
        if not os.path.exists(DB_PATH):
            logger.info("Cache database doesn't exist yet")
            return None
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Query cache by product_id
        if store_id:
            # Prefer same store (more likely to be correct variant)
            cursor.execute("""
                SELECT product_id, variant_id, product_name, store_id, product_url, 
                       price, image_url, created_at, expires_at, access_count
                FROM product_details_cache
                WHERE product_id = ? AND store_id = ? AND expires_at > ?
                ORDER BY last_accessed_at DESC
                LIMIT 1
            """, (product_id, store_id, now))
        else:
            # Any store (fallback)
            cursor.execute("""
                SELECT product_id, variant_id, product_name, store_id, product_url,
                       price, image_url, created_at, expires_at, access_count
                FROM product_details_cache
                WHERE product_id = ? AND expires_at > ?
                ORDER BY last_accessed_at DESC
                LIMIT 1
            """, (product_id, now))
        
        row = cursor.fetchone()
        
        if row:
            # Update access stats
            cursor.execute("""
                UPDATE product_details_cache
                SET last_accessed_at = ?, access_count = access_count + 1
                WHERE product_id = ? AND variant_id = ?
            """, (now, row[0], row[1]))
            conn.commit()
            
            result = {
                'status': 'success',
                'source': 'cache_by_product_id',
                'product_id': row[0],
                'variant_id': row[1],
                'product_name': row[2],
                'store_id': row[3],
                'product_url': row[4],
                'price': row[5],
                'image_url': row[6],
                'cached_at': row[7],
                'expires_at': row[8],
                'access_count': row[9]
            }
            
            logger.info(f"⚡ ULTRA-FAST HIT: product_id {product_id} → {row[1]} (no scraping needed!)")
            conn.close()
            return result
        
        conn.close()
        logger.info(f"Cache MISS for product_id: {product_id}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Failed to load variant by product_id: {e}")
        return None


# Auto-initialize on import
if not os.path.exists(DB_PATH):
    init_product_cache_db()
