FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install uv && uv sync --no-dev --frozen

COPY src/ ./src/

ENTRYPOINT ["python", "-m", "regulaforge.ingestion.interfaces.commands"]
CMD ["--help"]
