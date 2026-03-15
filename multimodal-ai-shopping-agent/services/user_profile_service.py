import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class UserProfileService:
    """
    Manages user profiles for personalized meal planning (BR01, BR02, BR03)
    Simulates a database using a local JSON file.
    """
    
    PROFILE_FILE = Path(__file__).parent.parent / "data" / "user_profiles.json"
    
    @staticmethod
    def _ensure_data_dir():
        UserProfileService.PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not UserProfileService.PROFILE_FILE.exists():
            with open(UserProfileService.PROFILE_FILE, "w") as f:
                json.dump({}, f)

    @staticmethod
    def get_profile(user_id: str = "default_user") -> Dict[str, Any]:
        """Retrieve user profile by ID"""
        UserProfileService._ensure_data_dir()
        try:
            with open(UserProfileService.PROFILE_FILE, "r") as f:
                profiles = json.load(f)
            return profiles.get(user_id, UserProfileService.get_default_profile())
        except Exception as e:
            logger.error(f"Error reading profile: {e}")
            return UserProfileService.get_default_profile()

    @staticmethod
    def save_profile(profile_data: Dict[str, Any], user_id: str = "default_user") -> bool:
        """Save/Update user profile"""
        UserProfileService._ensure_data_dir()
        try:
            with open(UserProfileService.PROFILE_FILE, "r") as f:
                profiles = json.load(f)
            
            # Merge with existing if needed, or overwrite
            current = profiles.get(user_id, UserProfileService.get_default_profile())
            current.update(profile_data)
            profiles[user_id] = current
            
            with open(UserProfileService.PROFILE_FILE, "w") as f:
                json.dump(profiles, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return False

    @staticmethod
    def get_default_profile() -> Dict[str, Any]:
        """Reference values from BR01, BR02, BR03"""
        return {
            "physical": {
                "age": 48,
                "gender": "Female",
                "weight_kg": 58
            },
            "dietary": {
                "calorie_target": 1800,
                "primary_diets": ["Mediterranean"],
                "allergies": [],
                "exclusions": [],
                "nutrition_targets": ["Eat healthy", "Budget-friendly"]
            },
            "preferences": {
                "meal_types": ["breakfast", "lunch", "dinner"],
                "complexity": "basic",
                "adults": 1,
                "children": 0,
                "frequency_cooking": "daily",
                "variety": "medium",
                "cooking_methods": ["Stovetop cooking", "Oven baking"]
            },
            "finance": {
                "budget_ron_month": 400
            }
        }
