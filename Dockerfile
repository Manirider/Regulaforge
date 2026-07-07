# =============================================================================
# RegulaForge - Production Dockerfile
# Multi-stage build: builder -> runner
# =============================================================================

FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY backend/pyproject.toml backend/poetry.lock* ./

RUN poetry install --no-dev --no-interaction --no-ansi && \
    rm -rf $POETRY_CACHE_DIR


FROM python:3.10-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv ./.venv

COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

USER nobody

EXPOSE 8000

CMD ["uvicorn", "regulaforge.interfaces.api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
