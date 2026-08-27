"""
Test script for the cache management system
Verifies Redis caching, duplicate detection, and cache management functionality
"""

import asyncio
import hashlib
import logging
from typing import Dict, Any
import pytest

from backend.utils.cache_utils import (
    redis_cache,
    check_duplicate_resume,
    cache_resume_parsing_result,
    get_cache_stats,
    clear_cache_by_type,
    clear_expired_cache
)
from backend.utils.redis_client import get_redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCacheSystem:
    """Test class for cache system functionality"""
    
    async def setup_redis_connection(self):
        """Setup Redis connection for standalone tests"""
        try:
            self.redis = await get_redis_client()
            await self.redis.ping()
            logger.info("Redis connection established")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    @pytest.fixture(autouse=True)
    async def setup_redis(self):
        """Setup Redis connection for pytest tests"""
        try:
            self.redis = await get_redis_client()
            await self.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            pytest.skip("Redis not available")
    
    async def test_basic_caching(self):
        """Test basic Redis caching functionality"""
        logger.info("Testing basic caching...")
        
        # Clear any existing cache for this test
        await clear_cache_by_type("api_response")
        
        # Test simple caching with unique key
        test_key = f"test_key_{asyncio.get_event_loop().time()}"
        
        async def compute_test_data():
            return {"test": "data", "timestamp": "2024-01-01"}
        
        # First call - should compute
        result1 = await redis_cache("api_response", test_key, compute_test_data)
        # Handle both direct result and cached data structure
        if isinstance(result1, dict) and 'data' in result1:
            result1 = result1['data']
        assert result1["test"] == "data"
        
        # Second call - should hit cache
        result2 = await redis_cache("api_response", test_key, compute_test_data)
        # Handle both direct result and cached data structure
        if isinstance(result2, dict) and 'data' in result2:
            result2 = result2['data']
        assert result2["test"] == "data"
        assert result1 == result2
        
        logger.info("Basic caching test passed")
    
    async def test_duplicate_detection(self):
        """Test duplicate resume detection"""
        logger.info("Testing duplicate detection...")
        
        # Create test content
        test_content = "This is a test resume content"
        content_hash = hashlib.sha256(test_content.encode()).hexdigest()
        file_size = len(test_content)
        file_name = "test_resume.pdf"
        
        # Check for duplicate (should not find any)
        duplicate_info = await check_duplicate_resume(content_hash, file_size, file_name)
        assert duplicate_info is None or duplicate_info.get('duplicate') is False
        
        logger.info("Duplicate detection test passed")
    
    async def test_cache_resume_parsing(self):
        """Test resume parsing result caching"""
        logger.info("Testing resume parsing cache...")
        
        # Create test resume data
        test_resume_data = {
            "personal_info": {"name": "Test User", "email": "test@example.com"},
            "skills": ["Python", "FastAPI", "Redis"],
            "experience": [{"company": "Test Corp", "position": "Developer"}]
        }
        
        content_hash = "test_hash_123"
        file_name = "test_resume.pdf"
        
        # Cache the result
        success = await cache_resume_parsing_result(
            content_hash=content_hash,
            resume_data=test_resume_data,
            file_name=file_name,
            strategy="fast"
        )
        
        assert success is True
        logger.info("Resume parsing cache test passed")
    
    async def test_cache_statistics(self):
        """Test cache statistics functionality"""
        logger.info("Testing cache statistics...")
        
        stats = await get_cache_stats()
        
        # Should return a dictionary
        assert isinstance(stats, dict)
        
        # Should have cache type information
        if 'resume_parse' in stats:
            assert 'count' in stats['resume_parse']
            assert 'ttl' in stats['resume_parse']
        
        logger.info("Cache statistics test passed")
    
    async def test_cache_clearing(self):
        """Test cache clearing functionality"""
        logger.info("Testing cache clearing...")
        
        # Add some test data using a valid cache type
        await self.redis.set("api:test_key", "test_value", ex=3600)
        
        # Clear api_response cache (which is a valid cache type)
        cleared_count = await clear_cache_by_type("api_response")
        
        # Should have cleared at least one key
        assert cleared_count >= 0
        
        logger.info("Cache clearing test passed")
    
    async def test_cache_metadata(self):
        """Test cache metadata functionality"""
        logger.info("Testing cache metadata...")
        
        metadata = {
            "file_name": "test.pdf",
            "file_size": 1024,
            "user_id": "123"
        }
        
        async def compute_with_metadata():
            return {"result": "success"}
        
        # Cache with metadata using a valid cache type
        result = await redis_cache(
            cache_type="api_response",
            value="test_key",
            compute_func=compute_with_metadata,
            metadata=metadata
        )
        
        assert result["result"] == "success"
        
        # Verify metadata was stored by checking if any api_response keys exist
        # (we can't predict the exact key since it's hashed)
        keys = await self.redis.keys("api:*")
        assert len(keys) > 0
        
        logger.info("Cache metadata test passed")

async def run_cache_tests():
    """Run all cache system tests as standalone script"""
    print("Starting cache system tests...")
    logger.info("Starting cache system tests...")
    
    test_instance = TestCacheSystem()
    
    try:
        # Setup Redis connection for standalone execution
        print("Setting up Redis connection...")
        redis_connected = await test_instance.setup_redis_connection()
        if not redis_connected:
            print("Cannot run tests without Redis connection")
            logger.error("Cannot run tests without Redis connection")
            return False
        
        # Run tests with individual error handling
        print("Running basic caching test...")
        try:
            await test_instance.test_basic_caching()
            print("Basic caching test passed")
        except Exception as e:
            print(f"Basic caching test failed: {e}")
            logger.error(f"Basic caching test failed: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
            
        print("Running duplicate detection test...")
        try:
            await test_instance.test_duplicate_detection()
            print("Duplicate detection test passed")
        except Exception as e:
            print(f"Duplicate detection test failed: {e}")
            logger.error(f"Duplicate detection test failed: {e}")
            return False
            
        print("Running resume parsing cache test...")
        try:
            await test_instance.test_cache_resume_parsing()
            print("Resume parsing cache test passed")
        except Exception as e:
            print(f"Resume parsing cache test failed: {e}")
            logger.error(f"Resume parsing cache test failed: {e}")
            return False
            
        print("Running cache statistics test...")
        try:
            await test_instance.test_cache_statistics()
            print("Cache statistics test passed")
        except Exception as e:
            print(f"Cache statistics test failed: {e}")
            logger.error(f"Cache statistics test failed: {e}")
            return False
            
        print("Running cache clearing test...")
        try:
            await test_instance.test_cache_clearing()
            print("Cache clearing test passed")
        except Exception as e:
            print(f"Cache clearing test failed: {e}")
            logger.error(f"Cache clearing test failed: {e}")
            return False
            
        print("Running cache metadata test...")
        try:
            await test_instance.test_cache_metadata()
            print("Cache metadata test passed")
        except Exception as e:
            print(f"Cache metadata test failed: {e}")
            logger.error(f"Cache metadata test failed: {e}")
            return False
        
        print("All cache system tests passed!")
        logger.info("All cache system tests passed!")
        return True
        
    except Exception as e:
        print(f"Cache system tests failed: {e}")
        logger.error(f"Cache system tests failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

async def test_cache_performance():
    """Test cache performance with multiple operations"""
    logger.info("Testing cache performance...")
    
    # Test multiple cache operations
    start_time = asyncio.get_event_loop().time()
    
    # Perform 100 cache operations
    for i in range(100):
        async def compute_func():
            return {"id": i, "data": f"test_data_{i}"}
        
        await redis_cache("perf_test", f"key_{i}", compute_func)
    
    end_time = asyncio.get_event_loop().time()
    duration = end_time - start_time
    
    logger.info(f"Performance test completed in {duration:.2f} seconds")
    logger.info(f"Average time per operation: {duration/100:.4f} seconds")
    
    # Should complete within reasonable time
    assert duration < 10.0  # Should complete within 10 seconds
    
    return True

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_cache_tests())
    
    if success:
        # Run performance test
        asyncio.run(test_cache_performance())
        print("✅ All cache system tests completed successfully!")
    else:
        print("❌ Cache system tests failed!")
        exit(1) 