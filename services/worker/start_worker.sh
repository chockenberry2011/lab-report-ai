#!/bin/bash

# Lab AI Worker startup script

set -e

echo "Starting Lab AI Worker..."

# Environment variables
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export DATA_DIR="${DATA_DIR:-/data}"
export WORKER_CONCURRENCY="${WORKER_CONCURRENCY:-1}"

# Create data directories
mkdir -p "${DATA_DIR}/inbox"
mkdir -p "${DATA_DIR}/outbox" 
mkdir -p "${DATA_DIR}/temp"

echo "Data directories created:"
echo "  Inbox: ${DATA_DIR}/inbox"
echo "  Outbox: ${DATA_DIR}/outbox"
echo "  Temp: ${DATA_DIR}/temp"

# Test Redis connection
echo "Testing Redis connection..."
python3 connect_redis.py

# Ensure concurrency is 1
export WORKER_CONCURRENCY=1

# Start Celery worker
echo "🚀 Starting Celery worker with concurrency=${WORKER_CONCURRENCY}..."
echo "📋 Worker configuration:"
echo "   - Concurrency: ${WORKER_CONCURRENCY}"
echo "   - Queue: lab_processing"
echo "   - Time limit: 1800s (30min)"
echo "   - Soft time limit: 1500s (25min)"
echo "   - Redis URL: ${REDIS_URL}"

exec celery -A tasks worker \
  --loglevel=info \
  --concurrency=${WORKER_CONCURRENCY} \
  --queues=lab_processing \
  --hostname=worker@%h \
  --time-limit=1800 \
  --soft-time-limit=1500 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=50