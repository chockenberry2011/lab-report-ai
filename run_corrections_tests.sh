#!/bin/bash

# Test runner for corrections API tests
# This script runs the tests in the Docker environment where dependencies are available

echo "🧪 Running corrections API tests..."

# Check if we're in Docker or have the dependencies locally
if command -v docker-compose &> /dev/null; then
    echo "📦 Running tests in Docker environment..."
    docker-compose exec api python -m pytest tests/api/test_corrections_api.py -v
else
    echo "🐍 Running tests locally (requires FastAPI dependencies)..."
    python -m pytest tests/api/test_corrections_api.py -v
fi

echo "✅ Test run complete!"