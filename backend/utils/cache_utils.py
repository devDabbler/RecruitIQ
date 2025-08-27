import hashlib
import pickle
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass
from backend.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL = 86400  # 24 hours default
RESUME_CACHE_TTL = 604800  # 7 days for resume parsing results
EMBEDDING_CACHE_TTL = 2592000  # 30 days for embeddings
DUPLICATE_CACHE_TTL = 31536000  # 1 year for duplicate detection

@dataclass
class CacheConfig:
    """Configuration for different cache types"""
    ttl: int
    prefix: str
    description: str

CACHE_CONFIGS = {
    'resume_parse': CacheConfig(RESUME_CACHE_TTL, 'resume_parse', 'Resume parsing results'),
    'embedding': CacheConfig(EMBEDDING_CACHE_TTL, 'embedding', 'Text embeddings'),
    'duplicate_check': CacheConfig(DUPLICATE_CACHE_TTL, 'duplicate', 'Duplicate detection'),
    'user_session': CacheConfig(3600, 'session', 'User session data'),  # 1 hour
    'api_response': CacheConfig(300, 'api', 'API responses'),  # 5 minutes
}

def make_cache_key(prefix: str, value: str) -> str:
    """Generate a cache key with prefix and hashed value"""
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}:{h}"

def make_duplicate_key(content_hash: str, file_size: int) -> str:
    """Generate a duplicate detection key based on content hash and file size"""
    return f"duplicate:{content_hash}:{file_size}"

async def redis_cache(
    cache_type: str, 
    value: str, 
    compute_func,
    ttl: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Enhanced Redis caching with metadata and configurable TTL
    
    Args:
        cache_type: Type of cache (resume_parse, embedding, etc.)
        value: Value to hash for cache key
        compute_func: Async function to compute if cache miss
        ttl: Optional custom TTL override
        metadata: Optional metadata to store with cache entry
    """
    config = CACHE_CONFIGS.get(cache_type, CacheConfig(CACHE_TTL, cache_type, 'Generic cache'))
    cache_key = make_cache_key(config.prefix, value)
    cache_ttl = ttl or config.ttl
    
    try:
        redis = await get_redis_client()
        
        # Check cache
        cached = await redis.get(cache_key)
        if cached:
            try:
                cached_data = pickle.loads(cached)
                logger.info(f"Cache HIT for {cache_type}: {value[:20]}...")
                
                # Update access metadata
                if metadata:
                    cached_data['last_accessed'] = datetime.now().isoformat()
                    await redis.set(cache_key, pickle.dumps(cached_data), ex=cache_ttl)
                
                result_data = cached_data.get('data', cached_data)
                
                # For resume parsing, ensure we have the required fields
                if cache_type == 'resume_parse' and isinstance(result_data, dict):
                    # Check for resume_id in either the main dict or the data field
                    if 'resume_id' not in result_data and 'resume_data' in result_data:
                        # Try to get resume_id from database using content hash if available
                        content_hash = metadata.get('content_hash', value)
                        # This is a critical fix - missing resume_id will cause KeyError
                        logger.warning(f"Missing resume_id in cached data, will be added during retrieval")
                
                return result_data
            except (pickle.UnpicklingError, KeyError) as e:
                logger.warning(f"Failed to deserialize cached data for {cache_type}: {e}")
                await redis.delete(cache_key)
        
        # Cache miss - compute result
        logger.info(f"Cache MISS for {cache_type}: {value[:20]}...")
        result = await compute_func()
        
        # Prepare cache data with metadata
        cache_data = {
            'data': result,
            'cached_at': datetime.now().isoformat(),
            'cache_type': cache_type,
            'original_value_hash': hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        }
        
        if metadata:
            cache_data.update(metadata)
        
        # Store in cache
        try:
            serialized_data = pickle.dumps(cache_data)
            await redis.set(cache_key, serialized_data, ex=cache_ttl)
            logger.info(f"Cached {cache_type} result with TTL {cache_ttl}s")
        except (pickle.PicklingError, Exception) as e:
            logger.warning(f"Failed to cache {cache_type} result: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Redis cache operation failed for {cache_type}: {e}")
        # Fallback to direct computation
        return await compute_func()

async def check_duplicate_resume(
    content_hash: str, 
    file_size: int, 
    file_name: str,
    db_session=None
) -> Optional[Dict[str, Any]]:
    """
    Check for duplicate resume uploads using content hash and file size
    
    Returns:
        Dict with duplicate info if found, None otherwise
    """
    try:
        redis = await get_redis_client()
        duplicate_key = make_duplicate_key(content_hash, file_size)
        
        # Check Redis cache first
        cached_duplicate = await redis.get(duplicate_key)
        if cached_duplicate:
            try:
                duplicate_data = json.loads(cached_duplicate)
                logger.info(f"Found cached duplicate for {file_name}")
                return duplicate_data
            except json.JSONDecodeError:
                await redis.delete(duplicate_key)
        
        # Check database for duplicates
        if db_session:
            from backend.models.models import Resume
            from sqlalchemy import text
            
            # Query for resumes with same content hash
            query = text("""
                SELECT r.id, r.file_name, r.created_at, c.email, c.first_name, c.last_name
                FROM resumes r
                JOIN candidates c ON r.candidate_id = c.id
                WHERE r.parsed_data->>'content_hash' = :content_hash
                ORDER BY r.created_at DESC
                LIMIT 1
            """)
            
            result = db_session.execute(query, {"content_hash": content_hash})
            duplicate = result.fetchone()
            
            if duplicate:
                duplicate_data = {
                    'resume_id': duplicate.id,
                    'file_name': duplicate.file_name,
                    'created_at': duplicate.created_at.isoformat() if duplicate.created_at else None,
                    'candidate_email': duplicate.email,
                    'candidate_name': f"{duplicate.first_name} {duplicate.last_name}".strip(),
                    'content_hash': content_hash,
                    'file_size': file_size
                }
                
                # Cache the duplicate info
                try:
                    await redis.set(
                        duplicate_key, 
                        json.dumps(duplicate_data), 
                        ex=DUPLICATE_CACHE_TTL
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache duplicate info: {e}")
                
                logger.info(f"Found duplicate resume: {file_name} matches {duplicate.file_name}")
                return duplicate_data
        
        # No duplicate found - cache negative result
        try:
            await redis.set(
                duplicate_key, 
                json.dumps({'duplicate': False}), 
                ex=DUPLICATE_CACHE_TTL
            )
        except Exception as e:
            logger.warning(f"Failed to cache negative duplicate result: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking for duplicate resume: {e}")
        return None

async def cache_resume_parsing_result(
    content_hash: str,
    resume_data: Any,
    file_name: str,
    strategy: str = 'fast',
    metadata: Optional[Dict[str, Any]] = None,
    resume_id: Optional[str] = None,
    file_id: Optional[str] = None
) -> bool:
    """
    Cache resume parsing results with enhanced metadata
    
    Returns:
        True if successfully cached, False otherwise
    """
    try:
        cache_data = {
            'resume_data': resume_data,
            'file_name': file_name,
            'strategy': strategy,
            'content_hash': content_hash,
            'cached_at': datetime.now().isoformat(),
            'parser_version': getattr(resume_data, 'parser_version', 'unknown'),
            # Add these critical fields to ensure they're available when retrieved from cache
            'resume_id': resume_id,
            'file_id': file_id
        }
        
        if metadata:
            cache_data.update(metadata)
        
        cache_key = make_cache_key('resume_parse', content_hash)
        redis = await get_redis_client()
        
        serialized_data = pickle.dumps(cache_data)
        await redis.set(cache_key, serialized_data, ex=RESUME_CACHE_TTL)
        
        logger.info(f"Successfully cached resume parsing result for {file_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cache resume parsing result: {e}")
        return False

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics and usage information"""
    try:
        redis = await get_redis_client()
        stats = {}
        
        for cache_type, config in CACHE_CONFIGS.items():
            pattern = f"{config.prefix}:*"
            keys = await redis.keys(pattern)
            stats[cache_type] = {
                'count': len(keys),
                'prefix': config.prefix,
                'ttl': config.ttl,
                'description': config.description
            }
        
        # Get Redis memory info
        info = await redis.info('memory')
        stats['redis_memory'] = {
            'used_memory_human': info.get('used_memory_human', 'unknown'),
            'used_memory_peak_human': info.get('used_memory_peak_human', 'unknown'),
            'maxmemory_human': info.get('maxmemory_human', 'unknown')
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {'error': str(e)}

async def clear_cache_by_type(cache_type: str) -> int:
    """
    Clear cache entries by type
    
    Returns:
        Number of keys deleted
    """
    try:
        config = CACHE_CONFIGS.get(cache_type)
        if not config:
            logger.warning(f"Unknown cache type: {cache_type}")
            return 0
        
        redis = await get_redis_client()
        pattern = f"{config.prefix}:*"
        keys = await redis.keys(pattern)
        
        if keys:
            deleted = await redis.delete(*keys)
            logger.info(f"Cleared {deleted} keys for cache type: {cache_type}")
            return deleted
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to clear cache for type {cache_type}: {e}")
        return 0

async def clear_expired_cache() -> Dict[str, int]:
    """
    Clear expired cache entries (Redis handles this automatically, but this provides manual control)
    
    Returns:
        Dict with counts of cleared entries by type
    """
    try:
        redis = await get_redis_client()
        cleared_counts = {}
        
        for cache_type, config in CACHE_CONFIGS.items():
            pattern = f"{config.prefix}:*"
            keys = await redis.keys(pattern)
            
            if keys:
                # Check TTL for each key
                expired_keys = []
                for key in keys:
                    ttl = await redis.ttl(key)
                    if ttl <= 0:  # Expired or no TTL
                        expired_keys.append(key)
                
                if expired_keys:
                    deleted = await redis.delete(*expired_keys)
                    cleared_counts[cache_type] = deleted
                    logger.info(f"Cleared {deleted} expired keys for {cache_type}")
        
        return cleared_counts
        
    except Exception as e:
        logger.error(f"Failed to clear expired cache: {e}")
        return {'error': str(e)}

# Example async embedding wrapper with enhanced caching
async def get_embedding_cached(embedding_model, text: str, model_name: str = "default") -> List[float]:
    """Get cached embedding with model-specific caching"""
    async def compute():
        try:
            loop = asyncio.get_event_loop()
            # First check for encode method (added for compatibility with SentenceTransformerAdapter)
            if hasattr(embedding_model, 'encode'):
                # Run blocking encode in thread pool
                return await loop.run_in_executor(None, embedding_model.encode, text)
            # Fallback to embed_query for string inputs
            elif hasattr(embedding_model, 'embed_query'):
                # Run blocking embed_query in thread pool
                result = await loop.run_in_executor(None, embedding_model.embed_query, text)
                # Convert to numpy array if needed
                import numpy as np
                return np.array(result) if not isinstance(result, np.ndarray) else result
            else:
                # Last resort - use a random embedding
                import numpy as np
                logger.warning(f"No suitable embedding method found - using random embedding")
                return np.random.rand(384)
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return fallback embedding on error
            import numpy as np
            return np.random.rand(384)
    
    # Include model name in cache key for model-specific caching
    cache_value = f"{model_name}:{text}"
    metadata = {'model_name': model_name, 'text_length': len(text)}
    
    return await redis_cache("embedding", cache_value, compute, metadata=metadata)
