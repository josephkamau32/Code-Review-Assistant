from fastapi import FastAPI
from src.api.routes import router
from src.config.settings import settings
from loguru import logger
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Code Review Assistant API",
    description="AI-powered code review assistant with RAG",
    version="1.0.0"
)

# Include routes
app.include_router(router, prefix="/api/v1")

# Configure logging
logger.add("logs/app.log", rotation="10 MB", retention="1 week")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Code Review Assistant API")
    logger.info(f"Vector DB path: {settings.chroma_persist_directory}")
    logger.info(f"Collection name: {settings.chroma_collection_name}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Code Review Assistant API")

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )