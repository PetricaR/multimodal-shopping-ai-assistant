
import logging
from typing import Optional
from fastapi import Header, HTTPException

from vector_search import SearchEngine
from vector_search.name_search_engine import NameSearchEngine
from ranking import Reranker
from data import BigQueryClient
from substitution.gemini_substitutor import GeminiSubstitutor
from features.realtime_server import RealTimeFeatureServer
from services.auth_service import AuthService
from config.settings import settings

logger = logging.getLogger(__name__)

# Initialize components (lazy loading)
_search_engine: Optional[SearchEngine] = None
_session_refresh_lock = False  # Prevent concurrent session refreshes
_name_search_engine: Optional[NameSearchEngine] = None
_reranker: Optional[Reranker] = None
_bq_client: Optional[BigQueryClient] = None
_gemini_substitutor: Optional[GeminiSubstitutor] = None
_feature_server: Optional[RealTimeFeatureServer] = None

async def verify_api_key(x_api_key: str = Header(None)):
    """Simple API Key verification"""
    if settings.API_AUTH_KEY != "no-key-set":
        if x_api_key != settings.API_AUTH_KEY:
            logger.warning(f"Invalid API Key attempt: {x_api_key}")
            raise HTTPException(status_code=403, detail="Forbidden: Invalid API Key")
    return x_api_key

def get_search_engine() -> SearchEngine:
    """Get or initialize search engine"""
    global _search_engine
    if _search_engine is None:
        logger.info("Initializing Search Engine...")
        _search_engine = SearchEngine()
    return _search_engine

def get_name_search_engine() -> NameSearchEngine:
    """Get or initialize name search engine"""
    global _name_search_engine
    if _name_search_engine is None:
        logger.info("Initializing Name Search Engine...")
        _name_search_engine = NameSearchEngine()
        if not _name_search_engine.is_available():
            logger.warning("Name Search Engine not available - will fallback to BigQuery")
    return _name_search_engine

def get_reranker() -> Reranker:
    """Get or initialize reranker"""
    global _reranker
    if _reranker is None:
        logger.info("Initializing Ranking API...")
        _reranker = Reranker()
    return _reranker

def get_bq_client() -> BigQueryClient:
    """Get or initialize BigQuery client"""
    global _bq_client
    if _bq_client is None:
        logger.info("Initializing BigQuery client...")
        _bq_client = BigQueryClient()
    return _bq_client

def get_gemini_substitutor() -> GeminiSubstitutor:
    """Get or initialize Gemini substitutor"""
    global _gemini_substitutor
    if _gemini_substitutor is None:
        logger.info("Initializing Gemini Substitutor...")
        _gemini_substitutor = GeminiSubstitutor()
    return _gemini_substitutor

def get_feature_server() -> RealTimeFeatureServer:
    """Get or initialize Feature Store server"""
    global _feature_server
    if _feature_server is None:
        logger.info("Initializing Feature Store Server...")
        _feature_server = RealTimeFeatureServer()
    return _feature_server

def get_authenticated_user():
    """
    Dependency to verify user is authenticated and session is valid.

    Behavior depends on ENABLE_SESSION_VALIDATION_ON_REQUEST setting:
    - If True (default for now): Validates session on every request (adds latency)
    - If False (recommended with worker pool): Only checks database, worker handles refresh

    When using the session keep-alive worker pool, set ENABLE_SESSION_VALIDATION_ON_REQUEST=False
    to avoid validation overhead on every request.
    """
    auth_status = AuthService.get_authentication_from_state()

    if auth_status.get("status") != "authenticated":
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please login first.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Optionally validate session with Bringo server
    # When using worker pool, disable this to avoid latency
    if settings.ENABLE_SESSION_VALIDATION_ON_REQUEST:
        phpsessid = auth_status.get("session_cookie")
        if phpsessid:
            logger.info("Validating session with Bringo server...")
            validation = AuthService.validate_session(phpsessid)

            if validation.get("status") == "expired":
                # Session expired on server, try to auto-refresh
                logger.warning("⚠️ Session expired, attempting auto-refresh...")

                # Prevent concurrent session refreshes
                global _session_refresh_lock
                if _session_refresh_lock:
                    logger.info("⏳ Session refresh already in progress, waiting...")
                    import time
                    max_wait = 30  # seconds
                    wait_time = 0
                    while _session_refresh_lock and wait_time < max_wait:
                        time.sleep(0.5)
                        wait_time += 0.5

                    # Refresh completed by another request, get updated auth
                    if not _session_refresh_lock:
                        logger.info("✅ Session refreshed by concurrent request")
                        return AuthService.get_authentication_from_state()

                try:
                    _session_refresh_lock = True

                    # Get credentials from database
                    creds_result = AuthService.get_credentials_from_config()
                    if creds_result.get("status") == "success":
                        username = creds_result.get("username")
                        password = creds_result.get("password")
                        store = creds_result.get("store", "carrefour_park_lake")

                        # Re-authenticate
                        logger.info(f"🔄 Re-authenticating {username}...")
                        auth_result = AuthService.authenticate_with_credentials(username, password, store)

                        if auth_result.get("status") == "success":
                            logger.info("✅ Session refreshed successfully")
                            # Return new auth status
                            return AuthService.get_authentication_from_state()
                        else:
                            raise HTTPException(
                                status_code=401,
                                detail="Session expired and auto-refresh failed. Please login manually.",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
                    else:
                        raise HTTPException(
                            status_code=401,
                            detail="Session expired and credentials not available for refresh. Please login.",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                finally:
                    _session_refresh_lock = False
    else:
        logger.debug("Session validation on request is disabled (using worker pool for keep-alive)")

    return auth_status
