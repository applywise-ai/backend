from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import applications, websocket, jobs
from .core.config import settings
import logging
import asyncio
import atexit
import signal
import sys
import os
from contextlib import asynccontextmanager
from .services.browser import browser_pool
from .db.supabase import supabase_manager
from .db.firestore import firestore_manager

# Logging is now configured in app/__init__.py
logger = logging.getLogger(__name__)

# Global flag to track shutdown state
_shutdown_initiated = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_initiated
    if not _shutdown_initiated:
        _shutdown_initiated = True
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        try:
            cleanup_resources()
            logger.info("✅ Graceful shutdown completed")
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
        finally:
            # Force exit to prevent restart
            os._exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    logger.info("🚀 Application startup initiated")
    
    # Initialize resources if needed
    logger.info("✅ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔄 Application shutdown initiated - cleaning up resources...")
    
    try:
        # Close all browser drivers
        logger.info("🌐 Closing browser pool...")
        browser_pool.close_all()
        
        # Close database connections
        logger.info("🐘 Closing database connections...")
        supabase_manager.cleanup()
        
        # Close Firestore connections
        logger.info("🔥 Closing Firestore connections...")
        firestore_manager.cleanup()
        
        # Small delay to allow cleanup to complete
        await asyncio.sleep(0.1)
        
        logger.info("✅ Resource cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error during shutdown cleanup: {e}")

logger.info("Starting FastAPI application")

app = FastAPI(
    title="ApplyWise API",
    description="Backend API for ApplyWise job application automation",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup_resources():
    """Cleanup function for atexit handler and signal handlers"""
    global _shutdown_initiated
    if _shutdown_initiated:
        return  # Already cleaning up
    
    _shutdown_initiated = True
    
    try:
        # Close all browser drivers
        logger.info("🌐 Closing browser pool...")
        browser_pool.close_all()
        
        # Close database connections
        logger.info("🐘 Closing database connections...")
        supabase_manager.cleanup()
        
        # Close Firestore connections
        logger.info("🔥 Closing Firestore connections...")
        firestore_manager.cleanup()
        
        logger.info("✅ atexit cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error during atexit cleanup: {e}")

# Register cleanup function for process termination
atexit.register(cleanup_resources)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "ApplyWise API is running", "version": "1.0.0"}

@app.post("/shutdown")
async def shutdown_endpoint():
    """Manual shutdown endpoint for testing"""
    logger.info("🛑 Manual shutdown requested via API endpoint")
    cleanup_resources()
    return {"message": "Shutdown initiated"}

# Include routers
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

# Import and include Stripe router
from .api.routes import stripe
app.include_router(stripe.router, prefix="/stripe", tags=["stripe"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 