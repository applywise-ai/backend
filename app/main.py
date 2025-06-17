from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import applications, websocket
from .core.config import settings
import logging

# Logging is now configured in app/__init__.py
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application")

app = FastAPI(
    title="ApplyWise API",
    description="Backend API for ApplyWise job application automation",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ApplyWise API",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }

# Include routers
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 