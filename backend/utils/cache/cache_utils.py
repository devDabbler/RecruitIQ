from functools import wraps
from typing import Callable, Any
import hashlib
import json

# Mock cache implementation since we don't have the actual cache imported
# In a real implementation, this would be replaced with the actual cache service
class MockCache:
    def __init__(self):
        self.storage = {}
    
    async def get(self, key):
        return self.storage.get(key)
    
    async def set(self, key, value, ex=None):
        self.storage[key] = value

cache = MockCache()

def cache_result(expiry: int = 3600):  # 1 hour cache by default
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments (include positional args excluding 'self')
            instance_id = str(id(args[0])) if args else "static"
            key_payload = {
                "instance_id": instance_id,
                "args": [str(a) for a in args[1:]],  # skip 'self'
                "kwargs": kwargs,
            }
            cache_key = f"{func.__name__}:{hashlib.md5(json.dumps(key_payload, default=str).encode()).hexdigest()}"
            
            # Try to get cached result
            cached = await cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
            
            # Call the function and cache the result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, json.dumps(result), ex=expiry)
            return result
        return wrapper
    return decorator
