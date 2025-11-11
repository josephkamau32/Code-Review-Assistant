"""
Expose Prometheus metrics
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import APIRouter
from fastapi.responses import Response

metrics_router = APIRouter()

# Define metrics
review_requests_total = Counter(
    'code_review_requests_total',
    'Total number of code review requests'
)

review_duration_seconds = Histogram(
    'code_review_duration_seconds',
    'Time spent processing code reviews',
    buckets=[1, 5, 10, 30, 60, 120]
)

suggestions_generated = Counter(
    'code_review_suggestions_generated_total',
    'Total number of suggestions generated',
    ['severity', 'category']
)

vector_db_size = Gauge(
    'vector_db_reviews_total',
    'Total number of reviews in vector database'
)

llm_tokens_used = Counter(
    'llm_tokens_used_total',
    'Total number of LLM tokens consumed',
    ['model']
)


@metrics_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )