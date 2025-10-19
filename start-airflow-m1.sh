#!/bin/bash
# Quick start script for Airflow on ARM64/M1 Macs

set -e

echo "🚀 Starting Lab AI Airflow on ARM64/M1..."
echo "This script will start Airflow services with proper ARM64 support."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check Docker architecture
ARCH=$(docker version --format '{{.Server.Arch}}')
if [ "$ARCH" != "arm64" ]; then
    echo "⚠️  Warning: Docker architecture is $ARCH, not arm64"
    echo "This may cause compatibility issues on M1 Macs."
fi

# Create necessary directories
echo "📁 Creating data directories..."
mkdir -p data/{inbox,outbox,archive,training,labelstudio}
mkdir -p models

# Set up environment
echo "🔧 Setting up environment..."
export DOCKER_DEFAULT_PLATFORM=linux/arm64

# Step 1: Start PostgreSQL first
echo "1️⃣  Starting PostgreSQL database..."
docker-compose up -d airflow-postgres

# Wait for PostgreSQL to be healthy
echo "⏳ Waiting for PostgreSQL to be ready..."
timeout=60
counter=0
while [ $counter -lt $timeout ]; do
    if docker-compose exec airflow-postgres pg_isready -U airflow >/dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    echo "   Waiting... (${counter}s)"
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -ge $timeout ]; then
    echo "❌ PostgreSQL failed to start within ${timeout}s"
    docker-compose logs airflow-postgres
    exit 1
fi

# Step 2: Initialize Airflow database
echo "2️⃣  Initializing Airflow database..."
docker-compose up airflow-init

# Check if initialization was successful
if [ $? -ne 0 ]; then
    echo "❌ Airflow initialization failed"
    docker-compose logs airflow-init
    exit 1
fi

# Step 3: Start core Airflow services
echo "3️⃣  Starting Airflow webserver and scheduler..."
docker-compose up -d airflow-webserver airflow-scheduler

# Wait for services to be ready
echo "⏳ Waiting for Airflow services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service status..."
docker-compose ps airflow-postgres airflow-webserver airflow-scheduler

# Test webserver connectivity
timeout=60
counter=0
while [ $counter -lt $timeout ]; do
    if curl -f http://localhost:8081/health >/dev/null 2>&1; then
        echo "✅ Airflow webserver is ready!"
        break
    fi
    echo "   Waiting for webserver... (${counter}s)"
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -ge $timeout ]; then
    echo "⚠️  Airflow webserver may not be fully ready yet"
    echo "Check logs: docker-compose logs airflow-webserver"
else
    echo ""
    echo "🎉 Airflow is ready!"
    echo ""
    echo "📊 Access Airflow UI:"
    echo "   URL: http://localhost:8081"
    echo "   Username: admin"
    echo "   Password: admin"
    echo ""
    echo "🔧 Useful commands:"
    echo "   Stop:     docker-compose down"
    echo "   Logs:     docker-compose logs -f airflow-scheduler"
    echo "   Status:   docker-compose ps"
    echo ""
    echo "📋 Available DAGs:"
    echo "   - lab_pipeline: Hourly batch processing"
    echo "   - lab_pipeline_weekly_training: Weekly model training"
    echo ""
fi

# Show final status
echo "📈 Final service status:"
docker-compose ps

echo ""
echo "💡 Next steps:"
echo "1. Upload PDF files to data/inbox/"
echo "2. Enable DAGs in Airflow UI"
echo "3. Monitor pipeline execution"
echo ""
echo "📖 For more info, see orchestrator/README.md"