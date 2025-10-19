"""
Celery configuration for Lab AI Worker
"""

import os

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Broker and result backend
broker_url = REDIS_URL
result_backend = REDIS_URL

# Task configuration
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True

# Worker configuration
worker_concurrency = int(os.getenv("WORKER_CONCURRENCY", "1"))
worker_prefetch_multiplier = 1
task_acks_late = True
task_reject_on_worker_lost = True

# Queue configuration
task_routes = {
    'worker.process_lab_report': {'queue': 'lab_processing'},
    'worker.test_task': {'queue': 'lab_processing'},
    'worker.health_check': {'queue': 'lab_processing'},
}

# Task time limits
task_time_limit = 30 * 60  # 30 minutes
task_soft_time_limit = 25 * 60  # 25 minutes

# Result expiry
result_expires = 24 * 60 * 60  # 24 hours

# Beat schedule (if needed for periodic tasks)
beat_schedule = {
    'cleanup-old-jobs': {
        'task': 'worker.cleanup_old_jobs',
        'schedule': 3600.0,  # Run every hour
    },
}

# Redis connection pool settings
broker_connection_retry_on_startup = True
broker_connection_retry = True
broker_connection_max_retries = 10