# Custom Airflow image with Lab AI dependencies
FROM apache/airflow:2.8.1

# Switch to root to install system dependencies
USER root

# Install system dependencies for ARM64 compatibility
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        vim \
        wget \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to airflow user
USER airflow

# Copy requirements file
COPY requirements.txt /requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /requirements.txt

# Copy custom configuration
COPY config/airflow.cfg /opt/airflow/airflow.cfg

# Set environment variables
ENV PYTHONPATH="/opt/airflow:/scripts:/services:${PYTHONPATH}"
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags
ENV AIRFLOW__CORE__BASE_LOG_FOLDER=/opt/airflow/logs
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command (overridden by docker-compose)
CMD ["airflow", "webserver"]