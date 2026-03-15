from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from api import models, dependencies
from services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/user", tags=["user-profile"])

@router.get("/profile", response_model=models.UserProfile)
async def get_user_profile(user_id: str = "default_user"):
    """Retrieve personal configuration (BR01, BR02, BR03)"""
    try:
        profile = UserProfileService.get_profile(user_id)
        return profile
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")

@router.post("/profile", response_model=models.UserProfile)
async def update_user_profile(request: models.UserProfileUpdate, user_id: str = "default_user"):
    """Update personal configuration (BR01, BR02, BR03)"""
    try:
        # Convert Pydantic to dict, excluding None
        update_data = request.dict(exclude_none=True)
        success = UserProfileService.save_profile(update_data, user_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save profile")
            
        return UserProfileService.get_profile(user_id)
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))
