"""
SQLite Database for Authentication Credentials Persistence
"""

import sqlite3
import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("authentication_db")

# Database location - store in ai_agents/bringo-multimodal-live/data if possible, otherwise local to module
# Using a data directory is cleaner for persistence
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "credentials.db"

def init_database():
    """Initialize the credentials database with schema"""
    try:
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create credentials table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                session_cookie TEXT,
                cookie_expires TEXT,
                last_login TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_username ON credentials(username)
        """)

        # Create stores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                store_id TEXT PRIMARY KEY,
                store_name TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT,
                status TEXT,
                schedule TEXT,
                address TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create index for stores
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category ON stores(category)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Credentials database initialized at {DB_PATH}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize credentials database: {e}")
        raise

def save_credentials(username: str, password: str, session_cookie: str = None) -> bool:
    """
    Save or update credentials in database
    
    Args:
        username: User's email/username
        password: User's password
        session_cookie: Optional session cookie (PHPSESSID)
    
    Returns:
        True if saved successfully
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Check if credentials exist
        cursor.execute("SELECT id FROM credentials WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing credentials
            # Only update password if provided and not empty (logic check might be needed if we want to update ONLY cookie)
            # For now, following original logic: if calling save, we expect valid data
            cursor.execute("""
                UPDATE credentials 
                SET password = ?, session_cookie = ?, updated_at = ?
                WHERE username = ?
            """, (password, session_cookie, now, username))
            logger.info(f"✅ Updated credentials for: {username}")
        else:
            # Insert new credentials
            cursor.execute("""
                INSERT INTO credentials (username, password, session_cookie, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password, session_cookie, now, now))
            logger.info(f"✅ Saved new credentials for: {username}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save credentials: {e}")
        return False


def get_credentials(username: str = None) -> dict:
    """
    Get credentials from database
    
    Args:
        username: Optional username to get specific credentials
                 If None, returns the most recently used credentials
    
    Returns:
        Dict with credentials or None if not found
    """
    try:
        if not DB_PATH.exists():
            return None
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if username:
            cursor.execute("""
                SELECT * FROM credentials WHERE username = ?
            """, (username,))
        else:
            # Get most recently updated credentials
            cursor.execute("""
                SELECT * FROM credentials ORDER BY updated_at DESC LIMIT 1
            """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "username": row["username"],
                "password": row["password"],
                "session_cookie": row["session_cookie"],
                "cookie_expires": row["cookie_expires"],
                "last_login": row["last_login"]
            }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Failed to get credentials: {e}")
        return None


def update_session(username: str, session_cookie: str, expires: str = None) -> bool:
    """
    Update session cookie for user
    
    Args:
        username: User's username
        session_cookie: Session cookie value (PHPSESSID)
        expires: Optional expiration timestamp
    
    Returns:
        True if updated successfully
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE credentials 
            SET session_cookie = ?, cookie_expires = ?, last_login = ?, updated_at = ?
            WHERE username = ?
        """, (session_cookie, expires, now, now, username))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Updated session for: {username}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update session: {e}")
        return False


def delete_credentials(username: str) -> bool:
    """
    Delete credentials from database
    
    Args:
        username: Username to delete
    
    Returns:
        True if deleted successfully
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM credentials WHERE username = ?", (username,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Deleted credentials for: {username}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to delete credentials: {e}")
        return False

        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to delete credentials: {e}")
        return False


def save_store(store_id: str, store_name: str, category: str, url: str, status: str, schedule: dict, address: str) -> bool:
    """Save store to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        schedule_json = json.dumps(schedule, ensure_ascii=False)
        
        cursor.execute("""
            INSERT OR REPLACE INTO stores 
            (store_id, store_name, category, url, status, schedule, address, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (store_id, store_name, category, url, status, schedule_json, address, now, now))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save store: {e}")
        return False

def get_stores_by_category(categories: list, status: str = "Open") -> list:
    """Get stores matching categories"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(categories))
        query = f"SELECT * FROM stores WHERE category IN ({placeholders})"
        params = list(categories)
        
        if status:
            query += " AND status = ?"
            params.append(status)
            
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"❌ Failed to get stores: {e}")
        return []

def get_all_stores() -> list:
    """Get all stores"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM stores")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"❌ Failed to get all stores: {e}")
        return []

def get_store_by_id(store_id: str) -> dict:
    """Get specific store by ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get store: {e}")
        return None

# Initialize database on module import
init_database()
