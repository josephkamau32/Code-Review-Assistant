"""
Rate limiting utilities using Redis
"""
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from src.config.settings import settings
import redis

# Initialize Redis connection
redis_client = redis.from_url(settings.redis_url)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    strategy="fixed-window"
)


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key based on IP and endpoint"""
    client_ip = get_remote_address(request)
    endpoint = request.url.path
    return f"rate_limit:{client_ip}:{endpoint}"


def check_rate_limit(request: Request) -> None:
    """Check if request exceeds rate limit"""
    if not settings.enable_rate_limiting:
        return

    key = get_rate_limit_key(request)

    # Get current count
    current_count = redis_client.get(key)
    if current_count is None:
        current_count = 0
    else:
        current_count = int(current_count)

    # Check if limit exceeded
    if current_count >= settings.rate_limit_requests:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

    # Increment counter
    redis_client.incr(key)
    redis_client.expire(key, settings.rate_limit_window_seconds)


# Rate limit decorators for specific endpoints
def limit_requests():
    """Decorator for rate limiting"""
    return limiter.limit(f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds}s")


# Custom rate limit exceeded handler
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors"""
    return {
        "error": "Rate limit exceeded",
        "detail": f"Too many requests. Limit: {settings.rate_limit_requests} per {settings.rate_limit_window_seconds} seconds",
        "retry_after": settings.rate_limit_window_seconds
    }