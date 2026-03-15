"""
Wrapper for Session Keep-Alive Worker with FastAPI endpoint for Cloud Run
Runs FastAPI in a background thread while the worker runs in the main thread
"""

import logging
import threading
import os
import signal
import sys
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from session_keepalive_worker import SessionKeepAliveWorker
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker_with_http")

# Global worker instance
worker_instance = None
worker_start_time = datetime.now()

# Create FastAPI app
app = FastAPI(
    title="Bringo Session Keep-Alive Worker",
    description="Background worker that keeps Bringo sessions alive",
    version="1.0.0"
)

@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run"""
    uptime = (datetime.now() - worker_start_time).total_seconds()

    return JSONResponse({
        "status": "healthy",
        "service": "bringo-session-keepalive",
        "uptime_seconds": uptime,
        "worker_running": worker_instance is not None and worker_instance.running
    }, status_code=200)

@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse({
        "service": "Bringo Session Keep-Alive Worker",
        "status": "running",
        "endpoints": {
            "health": "/health"
        }
    }, status_code=200)

def run_fastapi():
    """Run FastAPI server in background thread"""
    # Get port from environment (Cloud Run provides PORT env var)
    port = int(os.environ.get('PORT', 8080))

    logger.info(f"🌐 Starting FastAPI server on port {port}...")

    # Run uvicorn server
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=port,
        log_level='info',
        access_log=False  # Reduce noise
    )

def main():
    """Main entry point - runs worker in main thread"""
    global worker_instance

    logger.info("=" * 60)
    logger.info("🔧 Bringo Session Keep-Alive Worker with FastAPI")
    logger.info("=" * 60)

    # Start FastAPI in background thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info("✅ FastAPI server thread started")

    # Small delay to ensure FastAPI starts
    import time
    time.sleep(2)

    logger.info("🚀 Starting worker in main thread...")

    # Configuration from environment
    refresh_buffer = int(settings.SESSION_REFRESH_BUFFER_MINUTES or 30)
    poll_interval = int(settings.SESSION_POLL_INTERVAL_SECONDS or 60)
    validate_interval = int(settings.SESSION_VALIDATE_INTERVAL_MINUTES or 15)

    # Create and run worker in main thread (this allows signal handlers to work)
    worker_instance = SessionKeepAliveWorker(
        refresh_buffer_minutes=refresh_buffer,
        poll_interval_seconds=poll_interval,
        validate_interval_minutes=validate_interval
    )

    # Run worker (this blocks in main thread)
    worker_instance.run()

if __name__ == "__main__":
    main()
