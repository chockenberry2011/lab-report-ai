#!/usr/bin/env python3
"""
Test script to verify worker Redis connection and JobRegistry integration.
"""

import os
import sys
import time
from pathlib import Path

# Add parent directories to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent.parent))

from tasks import connect_to_redis_with_retry, update_job_status, logger


def test_redis_connection():
    """Test Redis connection with retry logic"""
    print("🧪 Testing Redis connection...")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    try:
        redis_client = connect_to_redis_with_retry(redis_url, max_duration=30)
        print("✅ Redis connection test successful!")
        return redis_client
    except Exception as e:
        print(f"❌ Redis connection test failed: {str(e)}")
        return None


def test_job_registry_update():
    """Test JobRegistry status updates"""
    print("🧪 Testing JobRegistry updates...")
    
    test_job_id = f"test_job_{int(time.time())}"
    
    try:
        # Test status transitions
        print(f"📝 Testing status updates for job: {test_job_id}")
        
        # Test processing status
        update_job_status(test_job_id, "processing")
        print("✅ Processing status update successful")
        
        # Test success status
        update_job_status(test_job_id, "completed", output_file=f"/data/outbox/{test_job_id}.json")
        print("✅ Completed status update successful")
        
        # Test failure status
        test_job_id_fail = f"test_job_fail_{int(time.time())}"
        update_job_status(test_job_id_fail, "failed", error="Test error message")
        print("✅ Failed status update successful")
        
        return True
        
    except Exception as e:
        print(f"❌ JobRegistry test failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("🚀 Starting worker connection and JobRegistry tests...")
    print("=" * 60)
    
    # Test 1: Redis connection
    redis_client = test_redis_connection()
    if not redis_client:
        print("❌ Redis connection failed - aborting tests")
        sys.exit(1)
    
    print()
    
    # Test 2: JobRegistry updates
    if test_job_registry_update():
        print("✅ JobRegistry integration test successful")
    else:
        print("❌ JobRegistry integration test failed")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("🎉 All tests passed! Worker is ready for job processing.")


if __name__ == "__main__":
    main()