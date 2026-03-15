"""
Unified SQLite Database for Bringo API Tools
Combines authentication credentials and store selection persistence.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("bringo_db")

# Database location
DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "bringo.db"


def init_database():
    """Initialize the unified database with required tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # --- Authentication Table ---
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
        
        # --- Stores Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT UNIQUE NOT NULL,
                store_name TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                schedule TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON credentials(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_store_id ON stores(store_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON stores(category)")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Unified database initialized at {DB_PATH}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


# --- Authentication Methods ---

def save_credentials(username: str, password: str, session_cookie: str = None) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT id FROM credentials WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE credentials 
                SET password = ?, session_cookie = ?, updated_at = ?
                WHERE username = ?
            """, (password, session_cookie, now, username))
        else:
            cursor.execute("""
                INSERT INTO credentials (username, password, session_cookie, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password, session_cookie, now, now))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save credentials: {e}")
        return False

def get_credentials(username: str = None) -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if username:
            cursor.execute("SELECT * FROM credentials WHERE username = ?", (username,))
        else:
            cursor.execute("SELECT * FROM credentials ORDER BY updated_at DESC LIMIT 1")
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get credentials: {e}")
        return None

def update_session(username: str, session_cookie: str, expires: str = None) -> bool:
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
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update session: {e}")
        return False


# --- Store Persistence Methods ---

def save_store(store_id: str, store_name: str, category: str, url: str, 
               status: str = "Open", schedule: Optional[Dict] = None, 
               address: Optional[str] = None) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        schedule_json = json.dumps(schedule) if schedule else None
        
        cursor.execute("""
            INSERT INTO stores (store_id, store_name, category, url, status, schedule, address, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(store_id) 
            DO UPDATE SET 
                store_name = excluded.store_name,
                category = excluded.category,
                url = excluded.url,
                status = excluded.status,
                schedule = excluded.schedule,
                address = excluded.address,
                updated_at = CURRENT_TIMESTAMP
        """, (store_id, store_name, category, url, status, schedule_json, address))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save store {store_id}: {e}")
        return False

def get_store_by_id(store_id: str) -> Optional[Dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            store = dict(row)
            if store['schedule']:
                store['schedule'] = json.loads(store['schedule'])
            return store
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get store {store_id}: {e}")
        return None

def get_stores_by_category(categories: List[str], status: str = "Open") -> List[Dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(categories))
        query = f"SELECT * FROM stores WHERE category IN ({placeholders}) AND status = ?"
        cursor.execute(query, categories + [status])
        rows = cursor.fetchall()
        conn.close()
        
        stores = []
        for row in rows:
            store = dict(row)
            if store['schedule']:
                store['schedule'] = json.loads(store['schedule'])
            stores.append(store)
        return stores
    except Exception as e:
        logger.error(f"❌ Failed to get stores by category: {e}")
        return []

def get_all_stores() -> List[Dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stores ORDER BY store_name")
        rows = cursor.fetchall()
        conn.close()
        
        stores = []
        for row in rows:
            store = dict(row)
            if store['schedule']:
                store['schedule'] = json.loads(store['schedule'])
            stores.append(store)
        return stores
    except Exception as e:
        logger.error(f"❌ Failed to get all stores: {e}")
        return []

# Initialize on import
init_database()
