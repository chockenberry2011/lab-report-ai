#!/bin/bash
# Custom entrypoint for Lab AI Airflow containers

set -e

# Wait for database to be ready
if [ "$1" = "webserver" ] || [ "$1" = "scheduler" ]; then
    echo "Waiting for PostgreSQL to be ready..."
    while ! pg_isready -h airflow-postgres -p 5432; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 1
    done
    echo "PostgreSQL is ready!"
fi

# Create necessary directories
echo "Creating Lab AI directories..."
mkdir -p /data/{inbox,outbox,archive,training,labelstudio}
mkdir -p /models
mkdir -p /opt/airflow/logs

# Set permissions
chmod -R 755 /data /models /opt/airflow/logs 2>/dev/null || true

# Install additional Python packages if requirements file exists
if [ -f "/requirements.txt" ]; then
    echo "Installing additional Python packages..."
    pip install --no-cache-dir -r /requirements.txt
fi

# Set Python path
export PYTHONPATH="/opt/airflow:/scripts:/services:${PYTHONPATH}"

echo "Starting Airflow service: $1"

# Execute the original command
exec airflow "$@"