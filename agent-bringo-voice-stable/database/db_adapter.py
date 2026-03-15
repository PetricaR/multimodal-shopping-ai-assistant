"""
Database Adapter - Automatically switches between SQLite and PostgreSQL
Based on USE_POSTGRES environment variable
"""

import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("db_adapter")

# Determine which database to use
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

if USE_POSTGRES:
    logger.info("🐘 Using PostgreSQL database (multi-tenant, shared)")
    from database import postgres_db as db_impl
else:
    logger.info("📦 Using SQLite database (single-tenant, local)")
    from services import db as db_impl


# Expose all database functions
def init_database():
    """Initialize the database schema"""
    return db_impl.init_database()


def save_credentials(username: str, password: str, session_cookie: Optional[str] = None) -> bool:
    """
    Save or update credentials for a user.

    Args:
        username: User's email/username
        password: User's password
        session_cookie: Optional session cookie (PHPSESSID)

    Returns:
        True if saved successfully
    """
    # For PostgreSQL, username is email
    return db_impl.save_credentials(username, password, session_cookie)


def get_credentials(username: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get credentials from database.

    Args:
        username: Optional username to get specific credentials.
                 If None, returns the most recently used credentials.

    Returns:
        Dict with credentials or None if not found
    """
    return db_impl.get_credentials(username)


def update_session(username: str, session_cookie: str, expires: str) -> bool:
    """
    Update session cookie for user.

    Args:
        username: User's username/email
        session_cookie: Session cookie value (PHPSESSID)
        expires: Expiration timestamp (ISO format string)

    Returns:
        True if updated successfully
    """
    return db_impl.update_session(username, session_cookie, expires)


def delete_credentials(username: str) -> bool:
    """
    Delete credentials from database.

    Args:
        username: Username to delete

    Returns:
        True if deleted successfully
    """
    return db_impl.delete_credentials(username)


def log_session_action(username: str, action: str, session_cookie: Optional[str] = None, expires_at: Optional[Any] = None) -> bool:
    """
    Log a session-related action to history.

    Args:
        username: User's username/email
        action: Action name
        session_cookie: Optional session cookie
        expires_at: Optional expiration datetime

    Returns:
        True if logged successfully
    """
    if hasattr(db_impl, 'log_session_action'):
        return db_impl.log_session_action(username, action, session_cookie, expires_at)
    return False


def verify_credentials(username: str, password: str) -> bool:
    """
    Verify credentials against the database.

    Args:
        username: User's email
        password: User's password

    Returns:
        True if credentials match
    """
    if hasattr(db_impl, 'verify_credentials'):
        return db_impl.verify_credentials(username, password)
    return False


def save_store(store_id: str, store_name: str, category: str, url: str,
               status: str, schedule: dict, address: str) -> bool:
    """Save store to database"""
    return db_impl.save_store(store_id, store_name, category, url, status, schedule, address)


def get_stores_by_category(categories: list, status: str = "Open") -> list:
    """Get stores matching categories"""
    return db_impl.get_stores_by_category(categories, status)


def get_all_stores() -> list:
    """Get all stores"""
    return db_impl.get_all_stores()


def get_store_by_id(store_id: str) -> dict:
    """Get specific store by ID"""
    return db_impl.get_store_by_id(store_id)


# Multi-tenant specific functions (only for PostgreSQL)
def get_all_users() -> List[Dict[str, Any]]:
    """
    Get all users (tenants) in the system.
    Only works with PostgreSQL. Returns empty list for SQLite.

    Returns:
        List of user dictionaries
    """
    if USE_POSTGRES and hasattr(db_impl, 'get_all_users'):
        return db_impl.get_all_users()
    else:
        # For SQLite, return single user if exists
        creds = get_credentials()
        return [creds] if creds else []


# Export database type for conditional logic
DATABASE_TYPE = "postgresql" if USE_POSTGRES else "sqlite"


def get_database_info() -> Dict[str, Any]:
    """
    Get information about the current database configuration.

    Returns:
        Dict with database type and connection details
    """
    info = {
        "type": DATABASE_TYPE,
        "multi_tenant": USE_POSTGRES,
        "shared": USE_POSTGRES,
    }

    if USE_POSTGRES:
        info.update({
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "bringo_auth"),
        })
    else:
        info.update({
            "path": db_impl.DB_PATH if hasattr(db_impl, 'DB_PATH') else "data/credentials.db"
        })

    return info


# Log database configuration on import
_db_info = get_database_info()
logger.info(f"Database configured: {_db_info}")
