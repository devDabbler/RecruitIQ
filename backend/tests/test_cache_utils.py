import pytest
from unittest.mock import patch, AsyncMock
from backend.utils.cache.cache_utils import cache_result

@pytest.mark.asyncio
async def test_cache_result_decorator():
    # Mock the cache
    with patch('backend.utils.cache.cache_utils.cache') as mock_cache:
        # The real cache exposes async get/set, so the mocks must be awaitable
        mock_cache.get = AsyncMock(return_value=None)  # No cached value initially
        mock_cache.set = AsyncMock()
        
        # Create a test function with the decorator
        @cache_result(expiry=3600)
        async def sample_function(test_param: str):
            return {"result": f"processed_{test_param}"}
        
        # Call the function
        result = await sample_function("test_value")
        
        # Assertions
        assert result == {"result": "processed_test_value"}
        
        # Verify cache operations
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()

@pytest.mark.asyncio
async def test_cache_result_decorator_with_cached_value():
    # Mock the cache to return a cached value
    with patch('backend.utils.cache.cache_utils.cache') as mock_cache:
        # The real cache exposes async get/set, so the mocks must be awaitable
        mock_cache.get = AsyncMock(return_value='{"result": "cached_result"}')
        mock_cache.set = AsyncMock()
        
        # Create a test function with the decorator
        @cache_result(expiry=3600)
        async def sample_function(test_param: str):
            return {"result": f"processed_{test_param}"}
        
        # Call the function
        result = await sample_function("test_value")
        
        # Assertions
        assert result == {"result": "cached_result"}
        
        # Verify cache get was called but set was not
        mock_cache.get.assert_called_once()
        # set should not be called since we got a cached value
        mock_cache.set.assert_not_called()
