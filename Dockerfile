FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first to leverage Docker layer caching for dependency installation
COPY pyproject.toml README.md /app/

# Upgrade pip and install the runtime dependencies listed in pyproject.toml
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir \
    "fastapi>=0.120.1" \
    "google>=3.0.0" \
    "google-genai>=1.46.0" \
    "httpx>=0.28.1" \
    "langchain>=1.0.2" \
    "numpy>=2.3.4" \
    "openai>=2.6.1" \
    "pydantic>=2.12.3" \
    "python-dotenv>=1.2.1" \
    "supabase>=2.22.2" \
    "tiktoken>=0.12.0" \
    "uvicorn>=0.38.0"

# Copy application code
COPY . /app

# Create a non-root user and make them owner of the app directory
RUN useradd -m appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Simple HTTP healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ || exit 1

# Default command — runs the app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
