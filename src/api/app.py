from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from src.api.routes import router
from src.config.settings import settings
from src.utils.auth import get_current_active_user, User
from src.utils.rate_limiting import rate_limit_exceeded_handler
from src.utils.monitoring import MetricsMiddleware, get_metrics, health_check, detailed_health_check
from loguru import logger
import uvicorn
import os
import sys

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Code Review Assistant API",
    description="AI-powered code review assistant with RAG",
    version="1.0.0",
    docs_url="/api/docs" if settings.enable_authentication else None,
    redoc_url="/api/redoc" if settings.enable_authentication else None,
)

# Add security middleware
if settings.enable_rate_limiting:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.api_host == "0.0.0.0" else [settings.api_host]
)

# Monitoring middleware
if settings.enable_monitoring:
    app.add_middleware(MetricsMiddleware)

# Validate and mount static files
try:
    static_dir = "src/api/static"
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    else:
        logger.warning(f"Static directory not found: {static_dir}")
except Exception as e:
    logger.error(f"Failed to mount static files: {e}")

# Validate and setup templates
try:
    templates_dir = "src/api/templates"
    if os.path.exists(templates_dir):
        templates = Jinja2Templates(directory=templates_dir)
    else:
        logger.error(f"Templates directory not found: {templates_dir}")
        templates = None
except Exception as e:
    logger.error(f"Failed to setup templates: {e}")
    templates = None

# Include API routes
app.include_router(router, prefix="/api/v1")

# Authentication routes
@app.post("/api/v1/auth/login", response_model=dict)
async def login(login_data: "LoginRequest"):
    """Authenticate user and return access token"""
    from src.models.schemas import LoginRequest
    from src.utils.auth import authenticate_user, create_access_token

    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/auth/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """Logout user (client should discard token)"""
    return {"message": "Successfully logged out"}

@app.get("/api/v1/auth/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

# Dashboard routes (no prefix for web interface)
@app.get("/")
async def dashboard(request: Request, current_user: User = Depends(get_current_active_user)):
    """Main dashboard page"""
    try:
        from src.rag.pipeline import RAGPipeline
        rag_pipeline = RAGPipeline()
        stats = rag_pipeline.get_stats()
        # Mock additional stats for display
        display_stats = {
            "total_reviews": stats.get("total_vectors", 0),
            "avg_processing_time": 3.5,  # Mock value
            "active_models": 1,
            "vector_count": stats.get("total_vectors", 0)
        }
        return templates.TemplateResponse("dashboard.html", {"request": request, "stats": display_stats})
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {"request": request, "stats": {}})

@app.get("/stats")
async def get_stats():
    """Get system statistics (alias for /api/v1/stats)"""
    try:
        from src.rag.pipeline import RAGPipeline
        rag_pipeline = RAGPipeline()
        stats = rag_pipeline.get_stats()
        # Enhanced stats for dashboard
        enhanced_stats = {
            "total_reviews": stats.get("total_reviews", 0),
            "avg_processing_time": 2.3,  # Mock data - would need to track actual times
            "active_models": 1,  # Number of active LLM models
            "vector_count": stats.get("total_reviews", 0),
            "review_trends": [12, 19, 15, 25, 22, 30, 28],  # Last 7 days mock data
            "issue_distribution": [25, 20, 30, 15, 10]  # Security, Performance, Code Quality, Best Practices, Documentation
        }
        return enhanced_stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/review")
async def manual_review_page(request: Request):
    """Manual review page"""
    return templates.TemplateResponse("review.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse("src/api/static/favicon.ico")

# Configure logging
logger.add("logs/app.log", rotation="10 MB", retention="1 week")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        logger.info("Starting Code Review Assistant API")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"LLM Provider: {settings.llm_provider}")
        logger.info(f"Vector DB path: {settings.chroma_persist_directory}")
        logger.info(f"Collection name: {settings.chroma_collection_name}")
        
        # Validate critical directories
        os.makedirs(settings.chroma_persist_directory, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        # Validate API keys
        if settings.llm_provider == "openai" and not settings.openai_api_key:
            logger.error("OPENAI_API_KEY not configured")
        elif settings.llm_provider == "gemini" and not settings.gemini_api_key:
            logger.error("GEMINI_API_KEY not configured")
        
        if not settings.github_token:
            logger.warning("GITHUB_TOKEN not configured - GitHub features will be limited")
        
        logger.info("Startup validation complete")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        logger.info("Shutting down Code Review Assistant API")
        # Add cleanup tasks here if needed
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )