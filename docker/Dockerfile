# =============================================================================
# RegulaForge - Production Dockerfile
# Multi-stage build: builder -> runner
# =============================================================================

# Stage 1: Build dependencies
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copy dependency files
COPY backend/pyproject.toml backend/poetry.lock* ./

# Install dependencies (without dev)
RUN poetry install --no-root --only main && \
    rm -rf $POETRY_CACHE_DIR


# Stage 2: Runtime image
FROM python:3.11-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    REGULAFORGE_ENVIRONMENT=production

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r regulaforge && \
    useradd -r -g regulaforge -d /app -s /sbin/nologin regulaforge

# Copy virtual environment from builder
COPY --from=builder /app/.venv ./.venv

# Copy application code
COPY backend/src/regulaforge ./regulaforge
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Create data directories
RUN mkdir -p /data/regulaforge/uploads /data/regulaforge/models /tmp/regulaforge && \
    chown -R regulaforge:regulaforge /app /data /tmp/regulaforge

USER regulaforge

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "regulaforge.interfaces.api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info"]
