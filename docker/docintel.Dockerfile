FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system deps: Tesseract for OCR, fonts for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies via Poetry
COPY pyproject.toml poetry.lock* README.md ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --only main --no-interaction --no-ansi && \
    rm -rf ~/.cache/pip

# Download spaCy model for NER
RUN python -m spacy download en_core_web_trf 2>/dev/null || true

COPY src/ ./src/

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8100/api/v1/documents/health || exit 1

CMD ["uvicorn", "regulaforge.document_intelligence.interfaces.standalone:app", \
     "--host", "0.0.0.0", "--port", "8100", "--workers", "2"]
