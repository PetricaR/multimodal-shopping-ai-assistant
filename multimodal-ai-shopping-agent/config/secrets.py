"""
Secret Manager integration for secure API key storage.

Best practices (2026):
- Never expose API keys in environment variables (risk of leakage)
- Use Secret Manager API directly (not file system)
- Pin secret versions in production
- Apply least-privilege IAM

References:
- https://cloud.google.com/secret-manager/docs/best-practices
- https://cloud.google.com/run/docs/configuring/services/secrets
"""

import logging
import os
from typing import Optional
from google.cloud import secretmanager
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretManagerClient:
    """Client for accessing Google Cloud Secret Manager"""

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Secret Manager client.

        Args:
            project_id: GCP project ID (defaults to GOOGLE_CLOUD_PROJECT env var)
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "formare-ai")
        self.client = None

    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        """Lazy load Secret Manager client"""
        if self.client is None:
            try:
                self.client = secretmanager.SecretManagerServiceClient()
                logger.info("✅ Secret Manager client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Secret Manager client: {e}")
                raise
        return self.client

    @lru_cache(maxsize=10)
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Retrieve a secret from Secret Manager.

        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")

        Returns:
            Secret value as string, or None if not found

        Best practice: In production, pin to specific version instead of "latest"
        """
        try:
            client = self._get_client()

            # Build the resource name
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"

            logger.info(f"🔐 Fetching secret: {secret_name} (version: {version})")

            # Access the secret
            response = client.access_secret_version(request={"name": name})

            # Decode the secret payload
            secret_value = response.payload.data.decode("UTF-8")

            logger.info(f"✅ Successfully retrieved secret: {secret_name}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ Failed to retrieve secret '{secret_name}': {e}")
            return None

    def get_gemini_api_key(self) -> Optional[str]:
        """
        Get Gemini API key from Secret Manager.

        Fallback order (for development):
        1. Secret Manager (production)
        2. Environment variable (local development only)

        Returns:
            Gemini API key or None
        """
        # Try Secret Manager first (production best practice)
        api_key = self.get_secret("gemini-api-key")

        if api_key:
            logger.info("✅ Using Gemini API key from Secret Manager")
            return api_key

        # Fallback to environment variable (local development only)
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            logger.warning("⚠️  Using Gemini API key from environment variable (not recommended for production)")
            return api_key

        logger.error("❌ No Gemini API key found in Secret Manager or environment")
        return None


# Global instance
_secret_manager = SecretManagerClient()


def get_gemini_api_key() -> Optional[str]:
    """
    Convenience function to get Gemini API key.

    This is the recommended way to access the API key in your application.
    """
    return _secret_manager.get_gemini_api_key()
