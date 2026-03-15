"""
Debug routes for database inspection
"""
from fastapi import APIRouter, HTTPException
from database import db_adapter as db
import logging

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])
logger = logging.getLogger(__name__)

@router.get("/database/info")
async def get_database_info():
    """Get database configuration information"""
    try:
        info = db.get_database_info()
        return {
            "status": "success",
            "database": info
        }
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/users")
async def get_all_users():
    """Get all users from database"""
    try:
        users = db.get_all_users()
        return {
            "status": "success",
            "count": len(users),
            "users": users
        }
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/credentials/{username}")
async def get_user_credentials(username: str):
    """Get credentials for specific user"""
    try:
        creds = db.get_credentials(username)
        if not creds:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        return {
            "status": "success",
            "credentials": creds
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))
