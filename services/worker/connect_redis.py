#!/usr/bin/env python3
"""
Redis connection script for worker startup.
Tests Redis connection with exponential backoff retry logic.
"""

import os
import sys
import time
import redis


def connect_with_retry(redis_url: str, max_duration: int = 120) -> bool:
    """
    Test Redis connection with exponential backoff retry logic.
    
    Args:
        redis_url: Redis connection URL
        max_duration: Maximum time to retry in seconds (default: 2 minutes)
    
    Returns:
        True if connection successful, False otherwise
    """
    start_time = time.time()
    retry_delay = 0.5  # Start with 0.5 seconds
    max_delay = 30.0   # Cap at 30 seconds
    
    print(f"🔗 Connecting to Redis at {redis_url}")
    
    while time.time() - start_time < max_duration:
        try:
            client = redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=5)
            # Test the connection
            client.ping()
            print("✅ Redis connection test successful")
            return True
            
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            elapsed = time.time() - start_time
            remaining = max_duration - elapsed
            
            if remaining <= 0:
                print(f"❌ Failed to connect to Redis after {max_duration}s: {str(e)}")
                return False
            
            print(f"⚠️  Redis connection failed (after {elapsed:.1f}s): {str(e)}")
            print(f"🔄 Retrying in {retry_delay:.1f}s (remaining: {remaining:.1f}s)")
            
            time.sleep(retry_delay)
            
            # Exponential backoff: double the delay, but cap at max_delay
            retry_delay = min(retry_delay * 2, max_delay)
    
    print(f"❌ Redis connection timeout after {max_duration} seconds")
    return False


if __name__ == "__main__":
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    if connect_with_retry(redis_url):
        print("🟢 Redis connection ready - proceeding with worker startup")
        sys.exit(0)
    else:
        print("🔴 Redis connection failed - worker startup aborted")
        sys.exit(1)