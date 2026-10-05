# Stage 1: Build stage for compiling dependencies and installing wheels
FROM python:3.11.9-slim AS builder

WORKDIR /build

# Install build dependencies required for compiling native C/C++ packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into /install prefix so build tools don't carry over
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Minimal runtime image without compilers
FROM python:3.11.9-slim AS runner

WORKDIR /app

# Install only curl for health checks (no compilers or build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p data/vector_db logs && \
    chown -R appuser:appuser data logs /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Add security labels
LABEL maintainer="Code Review Assistant"
LABEL security.scan="enabled"
LABEL version="1.0.0"

# Healthcheck
# Note on startup behavior:
# Settings validation (src/config/settings.py) executes at module import time when uvicorn starts.
# If required keys (e.g. GEMINI_API_KEY or OPENAI_API_KEY) are missing or invalid, the process
# exits immediately with status code 1 before the server binds to port 8000. In container
# environments (Docker/K8s), this results in an immediate container exit / CrashLoopBackOff
# prior to HEALTHCHECK's 40-second start-period elapsing.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]