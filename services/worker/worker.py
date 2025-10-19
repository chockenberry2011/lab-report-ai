#!/usr/bin/env python3
"""
Lab AI Worker - Entry point for Celery worker processes

Run with: celery -A worker worker --loglevel=info --concurrency=1 --queues=lab_processing
"""

import os
import sys
from pathlib import Path

# Add current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent.parent))  # Add root lab-ai directory

# Import tasks to register them with Celery
from tasks import app

if __name__ == '__main__':
    # Start worker
    app.start()