FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY services/trainer/requirements.txt /app/requirements.txt

# Install PyTorch CPU build first for better compatibility on Apple Silicon
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio && \
    pip install --no-cache-dir -r /app/requirements.txt

# Make sure sitecustomize is on sys.path
ENV PYTHONPATH=/app

# Copy service code + root shims
COPY services/trainer /app/services/trainer
# COPY sitecustomize.py sitecustomize_test.py /app/

# Toolbox mode: keep container up for exec
CMD ["sh", "-lc", "sleep infinity"]