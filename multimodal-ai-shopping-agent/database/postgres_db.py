"""
PostgreSQL Database for Multi-Tenant Authentication
Replaces SQLite with Cloud SQL PostgreSQL for shared access between worker pool and API
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

logger = logging.getLogger("postgres_db")

# Database connection configuration
# For Cloud SQL, use Unix socket or IP with Cloud SQL Proxy
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "/cloudsql/formare-ai:europe-west1:bringo-db"),  # Unix socket for Cloud Run
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "bringo_auth"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# Connection pool (shared across requests)
_connection_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """Get or create the connection pool (Thread-safe)"""
    global _connection_pool

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                try:
                    logger.info("Creating Threaded PostgreSQL connection pool...")
                    _connection_pool = pool.ThreadedConnectionPool(
                        minconn=1,
                        maxconn=20,  # Increased for higher concurrency
                        **DB_CONFIG
                    )
                    logger.info("✅ Threaded PostgreSQL connection pool created")
                except Exception as e:
                    logger.error(f"❌ Failed to create connection pool: {e}")
                    raise

    return _connection_pool


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            pool = get_connection_pool()
            pool.putconn(conn)


def init_database():
    """
    Initialize the database schema with multi-tenant support.
    Tables use email as the tenant identifier.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Create credentials table (multi-tenant by email)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    session_cookie TEXT,
                    cookie_expires TIMESTAMP WITH TIME ZONE,
                    last_login TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """)

            # Create index on email for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_credentials_email
                ON credentials(email)
            """)

            # Create stores table (shared across all tenants)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    store_id VARCHAR(255) PRIMARY KEY,
                    store_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    url TEXT,
                    status TEXT,
                    schedule JSONB,
                    address TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """)

            # Create index on category for filtering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stores_category
                ON stores(category)
            """)

            # Create session history table (for auditing)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_history (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    session_cookie TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    FOREIGN KEY (email) REFERENCES credentials(email) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_history_email
                ON session_history(email, created_at DESC)
            """)

            conn.commit()
            logger.info("✅ PostgreSQL database schema initialized")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


def save_credentials(email: str, password: str, session_cookie: Optional[str] = None) -> bool:
    """
    Save or update credentials for a user (tenant).

    Args:
        email: User's email (tenant identifier)
        password: User's password
        session_cookie: Optional session cookie (PHPSESSID)

    Returns:
        True if saved successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Upsert (INSERT or UPDATE)
            cursor.execute("""
                INSERT INTO credentials (email, password, session_cookie, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (email)
                DO UPDATE SET
                    password = EXCLUDED.password,
                    session_cookie = EXCLUDED.session_cookie,
                    updated_at = NOW()
            """, (email, password, session_cookie))

            logger.info(f"✅ Saved credentials for: {email}")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to save credentials: {e}")
        return False


def get_credentials(email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get credentials from database.

    Args:
        email: Optional email to get specific credentials.
               If None, returns the most recently updated credentials.

    Returns:
        Dict with credentials or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            if email:
                cursor.execute("""
                    SELECT email, password, session_cookie, cookie_expires, last_login
                    FROM credentials
                    WHERE email = %s
                """, (email,))
            else:
                # Get most recently updated credentials
                cursor.execute("""
                    SELECT email, password, session_cookie, cookie_expires, last_login
                    FROM credentials
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)

            row = cursor.fetchone()

            if row:
                return {
                    "username": row["email"],  # Alias for compatibility
                    "email": row["email"],
                    "password": row["password"],
                    "session_cookie": row["session_cookie"],
                    "cookie_expires": row["cookie_expires"].isoformat() if row["cookie_expires"] else None,
                    "last_login": row["last_login"].isoformat() if row["last_login"] else None
                }

            return None

    except Exception as e:
        logger.error(f"❌ Failed to get credentials: {e}")
        return None


def update_session(email: str, session_cookie: str, expires: str) -> bool:
    """
    Update session cookie for user.

    Args:
        email: User's email
        session_cookie: Session cookie value (PHPSESSID)
        expires: Expiration timestamp (ISO format string)

    Returns:
        True if updated successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Convert ISO string to timestamp
            expires_dt = datetime.fromisoformat(expires)

            cursor.execute("""
                UPDATE credentials
                SET session_cookie = %s,
                    cookie_expires = %s,
                    last_login = NOW(),
                    updated_at = NOW()
                WHERE email = %s
            """, (session_cookie, expires_dt, email))

            # Log to session history
            cursor.execute("""
                INSERT INTO session_history (email, action, session_cookie, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (email, "refresh", session_cookie, expires_dt))

            logger.info(f"✅ Updated session for: {email}")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to update session: {e}")
        return False


def verify_credentials(email: str, password: str) -> bool:
    """
    Verify credentials against the database.
    
    Args:
        email: User email
        password: User password to check

    Returns:
        True if credentials match
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password FROM credentials WHERE email = %s", (email,))
            row = cursor.fetchone()
            if row and row[0] == password:
                return True
            return False
    except Exception as e:
        logger.error(f"❌ Failed to verify credentials: {e}")
        return False


def log_session_action(email: str, action: str, session_cookie: Optional[str] = None, expires_at: Optional[datetime] = None) -> bool:
    """
    Log a session-related action to history.

    Args:
        email: User's email
        action: Action name (e.g., "check_ok", "refresh_trigger", "error")
        session_cookie: Optional session cookie
        expires_at: Optional expiration datetime

    Returns:
        True if logged successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO session_history (email, action, session_cookie, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (email, action, session_cookie, expires_at))
            return True
    except Exception as e:
        logger.error(f"❌ Failed to log session action: {e}")
        return False


def delete_credentials(email: str) -> bool:
    """
    Delete credentials from database.

    Args:
        email: Email to delete

    Returns:
        True if deleted successfully
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM credentials WHERE email = %s", (email,))

            logger.info(f"✅ Deleted credentials for: {email}")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to delete credentials: {e}")
        return False


def get_all_users() -> List[Dict[str, Any]]:
    """
    Get all users (tenants) in the system.
    Useful for multi-tenant worker pool that manages multiple accounts.

    Returns:
        List of user dictionaries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT email, session_cookie, cookie_expires, last_login, created_at
                FROM credentials
                ORDER BY email
            """)

            rows = cursor.fetchall()

            return [
                {
                    "email": row["email"],
                    "username": row["email"],  # Alias
                    "session_cookie": row["session_cookie"],
                    "cookie_expires": row["cookie_expires"].isoformat() if row["cookie_expires"] else None,
                    "last_login": row["last_login"].isoformat() if row["last_login"] else None,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None
                }
                for row in rows
            ]

    except Exception as e:
        logger.error(f"❌ Failed to get all users: {e}")
        return []


def save_store(store_id: str, store_name: str, category: str, url: str,
               status: str, schedule: dict, address: str) -> bool:
    """Save store to database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            import json
            schedule_json = json.dumps(schedule, ensure_ascii=False)

            cursor.execute("""
                INSERT INTO stores (store_id, store_name, category, url, status, schedule, address, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, NOW())
                ON CONFLICT (store_id)
                DO UPDATE SET
                    store_name = EXCLUDED.store_name,
                    category = EXCLUDED.category,
                    url = EXCLUDED.url,
                    status = EXCLUDED.status,
                    schedule = EXCLUDED.schedule,
                    address = EXCLUDED.address,
                    updated_at = NOW()
            """, (store_id, store_name, category, url, status, schedule_json, address))

            return True

    except Exception as e:
        logger.error(f"❌ Failed to save store: {e}")
        return False


def get_stores_by_category(categories: List[str], status: Optional[str] = "Open") -> List[Dict[str, Any]]:
    """Get stores matching categories"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = "SELECT * FROM stores WHERE category = ANY(%s)"
            params = [categories]

            if status:
                query += " AND status = %s"
                params.append(status)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"❌ Failed to get stores: {e}")
        return []


def get_all_stores() -> List[Dict[str, Any]]:
    """Get all stores"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("SELECT * FROM stores")
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"❌ Failed to get all stores: {e}")
        return []


def get_store_by_id(store_id: str) -> Optional[Dict[str, Any]]:
    """Get specific store by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("SELECT * FROM stores WHERE store_id = %s", (store_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    except Exception as e:
        logger.error(f"❌ Failed to get store: {e}")
        return None


# Initialize database on module import (will create tables if they don't exist)
try:
    init_database()
except Exception as e:
    logger.warning(f"Could not initialize database on import: {e}")
    logger.warning("Database will be initialized on first connection")
