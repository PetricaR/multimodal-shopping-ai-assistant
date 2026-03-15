
import os
import sys
import logging

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_auth")

# Load environment
load_dotenv()

from services.auth_service import AuthService

def test_auth():
    username = os.getenv("BRINGO_USERNAME")
    password = os.getenv("BRINGO_PASSWORD")

    if not username or not password:
        logger.error("BRINGO_USERNAME or BRINGO_PASSWORD not found in environment")
        return

    logger.info(f"Testing auth for user: {username}")

    try:
        result = AuthService.authenticate_with_credentials(username, password)

        if result.get("status") == "success":
            logger.info("✅ Authentication SUCCESS!")
            logger.info(f"PHPSESSID: {result.get('phpsessid')}")
            logger.info(f"Cookies: {list(result.get('cookies', {}).keys())}")
        else:
            logger.error(f"❌ Authentication FAILED: {result.get('message')}")

    except Exception as e:
        logger.error(f"❌ Script Error: {e}")

if __name__ == "__main__":
    test_auth()
