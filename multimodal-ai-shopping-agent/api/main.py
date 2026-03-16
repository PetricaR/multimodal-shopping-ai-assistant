"""
FastAPI Application Entry Point
===============================
Production-ready configuration for the Bringo Product Similarity API.
"""
import sys
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- 1. Environment Setup (Critical for Docker/Imports) ---
def _setup_python_path():
    """Ensures project root is in sys.path for module resolution."""
    try:
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    except Exception:
        pass

_setup_python_path()

# --- 2. Configuration & Imports ---
from config.settings import settings
from api.routes import similarity, auth, store, cart, recipes, live_search, user_profile, chef, config, debug, weather, calendar

# --- 3. App Factory ---
def create_app() -> FastAPI:
    """Initializes the FastAPI application with middleware and routes."""
    
    # Initialize App
    application = FastAPI(
        title="Bringo Product Similarity API",
        description="Multimodal product similarity search using Vertex AI (512D, TreeAH, Ranking API)",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Configure Middleware (CORS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routes
    application.include_router(similarity.router)
    application.include_router(auth.router)
    application.include_router(store.router)
    application.include_router(cart.router)
    application.include_router(recipes.router)
    application.include_router(live_search.router)
    application.include_router(user_profile.router)
    application.include_router(chef.router)
    application.include_router(config.router)
    application.include_router(debug.router)
    application.include_router(weather.router)
    application.include_router(calendar.router)

    @application.api_route("/health", methods=["GET", "HEAD"])
    async def health():
        return {"status": "ok"}

    return application

# --- 4. Application Instance ---
# Global instance required for uvicorn/gunicorn
app = create_app()

# --- 5. Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api.main")

# --- 6. Entry Point ---
if __name__ == "__main__":
    import os

    # Cloud Run compatible configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", settings.API_PORT))

    logger.info("🚀 Starting Bringo Product Similarity API...")
    logger.info(f"🔧 Configuration:")
    logger.info(f"   • Env: Production Mode")
    logger.info(f"   • Host: {host}:{port}")
    logger.info(f"   • Model: {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DIMENSION}D)")
    logger.info(f"   • Ranking: {settings.RANKING_MODEL}")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False  # Production mode
    )
