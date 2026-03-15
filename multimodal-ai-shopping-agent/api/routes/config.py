from fastapi import APIRouter, HTTPException, Depends
from config.settings import settings
from config.secrets import get_gemini_api_key
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(tags=["Config"])
logger = logging.getLogger("api.routes.config")

class SystemConfig(BaseModel):
    google_api_key: Optional[str] = None
    status: str
    version: str = "1.0.0"

@router.api_route("/api/v1/config", methods=["GET", "HEAD"], response_model=SystemConfig)
async def get_config():
    """
    Returns essential system configuration for the frontend.

    Security best practice (2026):
    - Retrieves Gemini API key from Secret Manager (not environment variables)
    - Prevents key leakage through environment dumps or logs
    - Follows Google Cloud best practices for secret management

    References:
    - https://cloud.google.com/secret-manager/docs/best-practices
    - https://cloud.google.com/run/docs/configuring/services/secrets
    """
    # Try Secret Manager first (production best practice)
    api_key = get_gemini_api_key()

    if not api_key:
        logger.warning("❌ Gemini API key not found in Secret Manager or environment")
        logger.info("ℹ️  Run './setup-gemini-secret.sh YOUR_API_KEY' to configure Secret Manager")
        return SystemConfig(status="warning", google_api_key=None)

    logger.info("✅ Gemini API key retrieved successfully from Secret Manager")
    return SystemConfig(
        status="ok",
        google_api_key=api_key
    )
