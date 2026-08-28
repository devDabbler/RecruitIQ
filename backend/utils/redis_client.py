"""
Async Redis client singleton for backend services.
"""
import logging
from typing import Optional, Any
import redis.asyncio as redis_asyncio
from backend.utils.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

_redis_client: Optional[redis_asyncio.Redis] = None

async def get_redis_client() -> redis_asyncio.Redis:
    """
    Returns a Redis client instance.
    
    Returns:
        redis.asyncio.Redis: Configured Redis client instance
        
    Raises:
        ImportError: If redis package is not installed
        redis.RedisError: If connection to Redis fails
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
        
    settings = get_settings()
    
    # No password: the servers this runs against don't have auth configured.
    # The db index is load-bearing in production, where db 0 belongs to a
    # different system on the same Redis server.
    redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
    
    try:
        _redis_client = redis_asyncio.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            max_connections=10,
            health_check_interval=30
        )
        
        # Test the connection
        await _redis_client.ping()
        logger.info("Successfully connected to Redis at %s", redis_url)
        
        return _redis_client
        
    except Exception as e:
        logger.error("Failed to connect to Redis at %s: %s", redis_url, str(e))
        _redis_client = None
        raise
    
    return _redis_client
