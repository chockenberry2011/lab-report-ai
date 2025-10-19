FROM --platform=linux/arm64 python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better layer caching
COPY services/worker/requirements.txt /app/requirements.txt

# Install dependencies (including dependencies from other services needed by worker)
COPY services/extractor/requirements.txt /tmp/requirements-extractor.txt
COPY services/trainer/requirements.txt /tmp/requirements-trainer.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements-extractor.txt && \
    pip install --no-cache-dir -r /tmp/requirements-trainer.txt

# Copy service code + root shims
COPY services /app/services
# COPY sitecustomize.py sitecustomize_test.py /app/

# Set PYTHONPATH so services resolves as a top-level package
ENV PYTHONPATH=/app

# Ensure Python packages have __init__.py files (backup safety)
RUN touch /app/services/__init__.py \
    && touch /app/services/worker/__init__.py \
    && touch /app/services/extractor/__init__.py \
    && touch /app/services/trainer/__init__.py

# Make scripts executable
RUN chmod +x /app/services/worker/start_worker.sh /app/services/worker/connect_redis.py /app/services/worker/test_connection.py

# Set working directory to worker service
WORKDIR /app/services/worker

CMD ["./start_worker.sh"]