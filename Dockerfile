# Production Dockerfile for WMS API
# Base image
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# App (src-layout) + deps
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md
COPY uv.lock ./uv.lock
COPY src ./src
RUN pip install --no-cache-dir . && \
    find /usr/local -depth \
    \( \
        -name __pycache__ \
        -o -name '*.pyc' \
        -o -name '*.pyo' \
    \) -exec rm -rf '{}' +

EXPOSE 8000

CMD ["gunicorn", "app.api:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
