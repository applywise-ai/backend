from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import applications, websocket, jobs
from .core.config import settings
import logging
import asyncio
import atexit
from contextlib import asynccontextmanager
from .services.browser import browser_pool
from .db.postgres import postgres_manager
from .db.firestore import firestore_manager

# Logging is now configured in app/__init__.py
logger = logging.getLogger(__name__)


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
        postgres_manager.cleanup()
        
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
    """Cleanup function for atexit handler"""
    logger.info("🧹 atexit cleanup initiated...")
    try:
        browser_pool.close_all()
        postgres_manager.cleanup()
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

# Include routers
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 