"""
Cache Management API Endpoints
Provides endpoints for managing Redis cache and getting cache statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging

from backend.utils.cache_utils import (
    clear_cache_by_type, 
    clear_expired_cache, 
    get_cache_stats
)
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])

@router.get("/stats")
async def get_cache_statistics():
    """
    Get cache statistics including Redis memory usage and cache entry counts
    """
    try:
        stats = await get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache statistics: {str(e)}")

@router.post("/clear")
async def clear_all_cache():
    """
    Clear all cache entries
    """
    try:
        results = {}
        cleared_counts = {}
        
        # Clear each cache type
        for cache_type in ['resume_parse', 'embedding', 'duplicate_check', 'user_session', 'api_response']:
            count = await clear_cache_by_type(cache_type)
            cleared_counts[cache_type] = count
        
        # Clear expired entries
        expired_counts = await clear_expired_cache()
        
        results = {
            'cleared_by_type': cleared_counts,
            'expired_cleared': expired_counts,
            'total_cleared': sum(cleared_counts.values())
        }
        
        logger.info(f"Cleared all cache: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.post("/clear/{cache_type}")
async def clear_cache_by_type_endpoint(cache_type: str):
    """
    Clear cache entries by specific type
    
    Args:
        cache_type: Type of cache to clear (resume_parse, embedding, duplicate_check, etc.)
    """
    try:
        count = await clear_cache_by_type(cache_type)
        
        result = {
            'cache_type': cache_type,
            'cleared_count': count,
            'status': 'success'
        }
        
        logger.info(f"Cleared {count} entries for cache type: {cache_type}")
        return result
        
    except Exception as e:
        logger.error(f"Error clearing cache type {cache_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache type {cache_type}: {str(e)}")

@router.post("/clear/expired")
async def clear_expired_cache_endpoint():
    """
    Clear only expired cache entries
    """
    try:
        expired_counts = await clear_expired_cache()
        
        result = {
            'expired_cleared': expired_counts,
            'total_expired_cleared': sum(expired_counts.values()) if isinstance(expired_counts, dict) else 0
        }
        
        logger.info(f"Cleared expired cache entries: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error clearing expired cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear expired cache: {str(e)}")

@router.get("/health")
async def cache_health_check():
    """
    Health check for cache system
    """
    try:
        stats = await get_cache_stats()
        
        # Check if Redis is accessible
        if 'error' in stats:
            return {
                'status': 'unhealthy',
                'error': stats['error'],
                'message': 'Cache system is not accessible'
            }
        
        return {
            'status': 'healthy',
            'cache_stats': stats,
            'message': 'Cache system is operational'
        }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'Cache system health check failed'
        } 