# ==============================================================================
# STAGE 1: Builder
# ==============================================================================
FROM python:3.12-slim as builder

# Avoid writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install requirements
COPY backend/requirements.txt .
# We use the pip extra index for CPU-only PyTorch as defined in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ==============================================================================
# STAGE 2: Production Runtime
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    HF_HOME="/app/.cache/huggingface" \
    TRANSFORMERS_CACHE="/app/.cache/huggingface" \
    HF_HUB_CACHE="/app/.cache/huggingface"

WORKDIR /app

# Install runtime dependencies (e.g., libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with a home directory
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY backend/app /app/app
# Create directories for logs/store to ensure they exist
RUN mkdir -p /app/app/etl/logs /app/app/etl/reports /app/app/document_generation/store && \
    chown -R appuser:appuser /app/app

# Explicitly create and configure Hugging Face cache directory
RUN mkdir -p /app/.cache/huggingface && \
    chown -R appuser:appuser /app/.cache

# Switch to non-root user
USER appuser

# Verify the user has write permissions to the cache directory
RUN touch /app/.cache/huggingface/test_write.txt && rm /app/.cache/huggingface/test_write.txt

EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
