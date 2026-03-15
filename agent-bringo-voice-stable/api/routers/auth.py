"""
Authentication Routes
Endpoints for user login and session management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging
import json

from api.models import AuthCredentials, AuthResponse
from api.tools import authentication

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger("auth_router")

@router.post("/login", response_model=AuthResponse)
async def login(creds: AuthCredentials):
    """
    Authenticate with Bringo using credentials.
    Returns session cookies and status.
    """
    try:
        # Use authentication tool
        result_json = authentication.authenticate_with_credentials(
            username=creds.username,
            password=creds.password,
            store=creds.store
        )
        
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            return AuthResponse(
                status="success",
                username=creds.username,
                cookies=result.get("cookies"),
                phpsessid=result.get("phpsessid"),
                expires_at=result.get("expires_at")
            )
        else:
            raise HTTPException(status_code=401, detail=result.get("message", "Authentication failed"))
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=AuthResponse)
async def auth_status():
    """
    Check current authentication status from database persistence.
    """
    try:
        result_json = authentication.get_authentication_from_state()
        result = json.loads(result_json)
        
        return AuthResponse(
            status=result.get("status", "unknown"),
            username=result.get("username"),
            phpsessid=result.get("session_cookie"),
            expires_at=result.get("expires_at")
        )
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout():
    """
    Clear credentials (placeholder)
    """
    return {"status": "success", "message": "Logged out (local session cleared)"}
