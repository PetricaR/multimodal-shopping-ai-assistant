import asyncio
import logging
import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from google import genai
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_gemini_3():
    logger.info(f"🚀 Verifying Gemini 3 integration...")
    logger.info(f"Model ID from settings: {settings.GENERATION_MODEL}")
    
    if settings.GENERATION_MODEL != "gemini-3-flash-preview":
        logger.error("❌ Model version mismatch in settings!")
        return

    try:
        # Use Vertex AI as per standard config or API key fallback
        # Given settings.py structure, it might rely on credentials or key
        api_key = settings.GOOGLE_API_KEY
        client = None
        
        if api_key and "no-key-set" not in api_key:
            logger.info("Using API Key authentication")
            client = genai.Client(api_key=api_key)
        else:
            logger.info("Using Vertex AI default credentials")
            client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location=settings.LOCATION)
            
        response = client.models.generate_content(
            model=settings.GENERATION_MODEL,
            contents="Hello, explain in one sentence why you are fast.",
        )
        
        logger.info(f"✅ Response received: {response.text}")
        logger.info("Gemini 3 Flash Preview is ACTIVE and working.")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)

if __name__ == "__main__":
    verify_gemini_3()
