"""
Authentication Routes
Endpoints for Bringo login and session management
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from services.auth_service import AuthService
from api import models

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    store: Optional[str] = "carrefour_park_lake"

@router.post("/api/v1/auth/login", response_model=models.AuthResponse)
async def login(request: LoginRequest, background_tasks: BackgroundTasks):
    """
    Authenticate with Bringo.
    If username/password not provided, tries to use configured defaults.
    """
    try:
        # 1. Determine credentials
        username = request.username
        password = request.password
        
        if not username or not password:
            # Try to get from config/db
            creds = AuthService.get_credentials_from_config()
            if creds.get("status") == "success":
                username = creds.get("username")
                password = creds.get("password")
            else:
                raise HTTPException(status_code=400, detail="Credentials not provided and not found in configuration")
        
        # 2a. Check for existing valid session to avoid duplicate logins
        try:
            # Check DB state first
            existing_auth = AuthService.get_authentication_from_state()
            if existing_auth.get("status") == "authenticated":
                # Validate it's actually still alive
                validation = AuthService.validate_session(existing_auth.get("session_cookie"))
                if validation.get("status") == "valid":
                    logger.info(f"✅ Reusing existing valid session for {existing_auth.get('username')}")
                    return models.AuthResponse(
                        status="success",
                        message="Session reused",
                        username=existing_auth.get("username"),
                        phpsessid=existing_auth.get("session_cookie"),
                        expires_at=existing_auth.get("expires_at")
                    )
                else:
                    logger.info("⚠️ Existing session invalid/expired. Creating new one.")
        except Exception as e:
            logger.warning(f"Session reuse check failed: {e}")

        # 2b. Authenticate (Selenium)
        # Note: This is a blocking operation involving Selenium. 
        # For production, this should ideally be offloaded to a worker task, but for now we run it synchronously
        # or we could make it async if AuthService was async (it uses blocking selenium).
        # We can run it in a threadpool to avoid blocking the event loop.
        
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            AuthService.authenticate_with_credentials, 
            username, 
            password, 
            request.store
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=401, detail=result.get("message"))
            
        return models.AuthResponse(
            status="success",
            message="Authentication successful",
            username=username,
            cookies=result.get("cookies"),
            phpsessid=result.get("phpsessid"),
            expires_at=result.get("expires_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/auth/status", response_model=models.AuthResponse)
async def check_status():
    """
    Check current authentication status from database persistence
    """
    try:
        result = AuthService.get_authentication_from_state()
        
        status = result.get("status")
        
        if status == "authenticated":
            # Optional: Validate validity with a quick request?
            # For now, just return what DB says to be fast
            return models.AuthResponse(
                status="authenticated",
                username=result.get("username"),
                phpsessid=result.get("session_cookie"),
                expires_at=result.get("expires_at")
            )
        else:
            return models.AuthResponse(
                status=status,
                message=result.get("message")
            )
            
    except Exception as e:
        logger.error(f"Status check error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/auth/verify", response_model=models.AuthResponse)
async def verify_credentials(request: LoginRequest):
    """
    Verify user credentials directly against the PostgreSQL database.
    Does not attempt Bringo authentication, just checks if we have the right password locally.
    """
    try:
        if not request.username or not request.password:
            raise HTTPException(status_code=400, detail="Username and password are required")
            
        from database import db_adapter as db
        
        is_valid = db.verify_credentials(request.username, request.password)
        
        if is_valid:
            # Check if we also have an active session
            auth_info = db.get_credentials(request.username)
            return models.AuthResponse(
                status="success",
                message="Credentials verified",
                username=request.username,
                phpsessid=auth_info.get("session_cookie") if auth_info else None,
                expires_at=auth_info.get("cookie_expires") if auth_info else None
            )
        else:
            return models.AuthResponse(
                status="failed",
                message="Invalid username or password"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
