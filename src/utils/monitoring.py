"""
Monitoring and observability utilities
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import psutil
import os
from loguru import logger
from src.config.settings import settings

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes'
)

CPU_USAGE = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage'
)

REVIEW_COUNT = Counter(
    'code_reviews_total',
    'Total code reviews performed',
    ['language', 'status']
)

VECTOR_DB_SIZE = Gauge(
    'vector_db_size',
    'Size of vector database',
    ['collection']
)

LLM_TOKENS_USED = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model']
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Increment active connections
        ACTIVE_CONNECTIONS.inc()

        try:
            response = await call_next(request)

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(time.time() - start_time)

            return response

        finally:
            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()


def update_system_metrics():
    """Update system-level metrics"""
    try:
        # Memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        MEMORY_USAGE.set(memory_info.rss)

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        CPU_USAGE.set(cpu_percent)

    except Exception as e:
        logger.warning(f"Failed to update system metrics: {e}")


def get_metrics():
    """Get Prometheus metrics"""
    update_system_metrics()
    return generate_latest()


def record_review_metrics(language: str, status: str = "success"):
    """Record code review metrics"""
    REVIEW_COUNT.labels(language=language, status=status).inc()


def record_llm_usage(provider: str, model: str, tokens: int = 0):
    """Record LLM usage metrics"""
    LLM_TOKENS_USED.labels(provider=provider, model=model).inc(tokens)


def update_vector_db_metrics(collection: str, size: int):
    """Update vector database metrics"""
    VECTOR_DB_SIZE.labels(collection=collection).set(size)


# Health check functions
def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "code-review-assistant",
        "version": "1.0.0"
    }


def detailed_health_check():
    """Detailed health check with component status"""
    health_status = {
        "status": "healthy",
        "service": "code-review-assistant",
        "version": "1.0.0",
        "components": {}
    }

    # Check vector database
    try:
        from src.rag.vector_store import VectorStoreManager
        vector_store = VectorStoreManager()
        stats = vector_store.get_collection_stats()
        health_status["components"]["vector_db"] = {
            "status": "healthy",
            "collection": stats.get("collection_name"),
            "documents": stats.get("total_reviews", 0)
        }
    except Exception as e:
        health_status["components"]["vector_db"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # Check LLM service
    try:
        from src.rag.llm_service import LLMService
        llm_service = LLMService()
        health_status["components"]["llm_service"] = {
            "status": "healthy",
            "provider": llm_service.provider,
            "model": llm_service.model
        }
    except Exception as e:
        health_status["components"]["llm_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # Check embedding service
    try:
        from src.rag.embeddings import EmbeddingService
        embedding_service = EmbeddingService()
        health_status["components"]["embedding_service"] = {
            "status": "healthy",
            "provider": embedding_service.provider
        }
    except Exception as e:
        health_status["components"]["embedding_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # Check GitHub client
    try:
        from src.utils.github_client import GitHubClient
        github_client = GitHubClient()
        health_status["components"]["github_client"] = {
            "status": "healthy" if github_client.client else "degraded",
            "configured": bool(github_client.client)
        }
    except Exception as e:
        health_status["components"]["github_client"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # System resources
    try:
        import psutil
        health_status["system"] = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
    except Exception as e:
        health_status["system"] = {"error": str(e)}

    return health_status