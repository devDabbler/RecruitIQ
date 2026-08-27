"""
Cache Management Utility for Streamlit Frontend
Handles both Streamlit cache clearing and Redis cache management
"""

import streamlit as st
import asyncio
import requests
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages both Streamlit and Redis caches"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.session_state_key = "cache_last_cleared"
    
    def clear_streamlit_cache(self, cache_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Clear Streamlit caches
        
        Args:
            cache_types: List of cache types to clear. If None, clears all.
                        Options: ['data', 'resource', 'experimental_memo', 'experimental_singleton']
        
        Returns:
            Dict with clearing results
        """
        results = {}
        
        if cache_types is None:
            cache_types = ['data', 'resource', 'experimental_memo', 'experimental_singleton']
        
        try:
            for cache_type in cache_types:
                if cache_type == 'data':
                    st.cache_data.clear()
                    results['data'] = "Cleared all cached data"
                elif cache_type == 'resource':
                    st.cache_resource.clear()
                    results['resource'] = "Cleared all cached resources"
                elif cache_type == 'experimental_memo':
                    st.experimental_memo.clear()
                    results['experimental_memo'] = "Cleared all experimental memo cache"
                elif cache_type == 'experimental_singleton':
                    st.experimental_singleton.clear()
                    results['experimental_singleton'] = "Cleared all experimental singleton cache"
                else:
                    results[cache_type] = f"Unknown cache type: {cache_type}"
            
            # Update session state
            st.session_state[self.session_state_key] = datetime.now().isoformat()
            
            logger.info(f"Cleared Streamlit caches: {list(results.keys())}")
            return results
            
        except Exception as e:
            logger.error(f"Error clearing Streamlit cache: {e}")
            return {'error': str(e)}
    
    async def clear_redis_cache(self, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear Redis cache through API call
        
        Args:
            cache_type: Specific cache type to clear. If None, clears all.
        
        Returns:
            Dict with clearing results
        """
        try:
            async with httpx.AsyncClient() as client:
                if cache_type:
                    url = f"{self.api_base_url}/api/cache/clear/{cache_type}"
                else:
                    url = f"{self.api_base_url}/api/cache/clear"
                
                response = await client.post(url, timeout=30.0)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Cleared Redis cache: {result}")
                return result
                
        except Exception as e:
            logger.error(f"Error clearing Redis cache: {e}")
            return {'error': str(e)}
    
    def clear_streamlit_cache_sync(self, cache_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Synchronous wrapper for clear_streamlit_cache"""
        return self.clear_streamlit_cache(cache_types)
    
    def clear_redis_cache_sync(self, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for clear_redis_cache"""
        try:
            # Prefer cached sync httpx client
            try:
                from frontend.utils.http_client import get_sync_client
                client = get_sync_client()
            except Exception:
                client = None

            if cache_type:
                url = f"{self.api_base_url.rstrip('/')}/api/cache/clear/{cache_type}"
            else:
                url = f"{self.api_base_url.rstrip('/')}/api/cache/clear"

            if client is None:
                resp = requests.post(url, timeout=30)
                resp.raise_for_status()
                return resp.json()
            else:
                resp = client.post(url, timeout=30.0)
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            logger.error(f"Error clearing Redis cache (sync): {e}")
            return {'error': str(e)}
    
    def get_cache_clear_time(self) -> Optional[datetime]:
        """Get the last time cache was cleared"""
        if self.session_state_key in st.session_state:
            try:
                return datetime.fromisoformat(st.session_state[self.session_state_key])
            except ValueError:
                return None
        return None
    
    def should_clear_cache(self, max_age_hours: int = 24) -> bool:
        """
        Check if cache should be cleared based on age
        
        Args:
            max_age_hours: Maximum age in hours before cache should be cleared
        
        Returns:
            True if cache should be cleared
        """
        last_cleared = self.get_cache_clear_time()
        if last_cleared is None:
            return True
        
        age = datetime.now() - last_cleared
        return age.total_seconds() > (max_age_hours * 3600)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics from Redis"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.api_base_url}/api/cache/stats"
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    def get_cache_stats_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_cache_stats"""
        try:
            try:
                from frontend.utils.http_client import get_sync_client
                client = get_sync_client()
            except Exception:
                client = None

            url = f"{self.api_base_url.rstrip('/')}/api/cache/stats"
            if client is None:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                return resp.json()
            else:
                resp = client.get(url, timeout=30.0)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Error getting cache stats (sync): {e}")
            return {'error': str(e)}
    

# Global cache manager instance
cache_manager = CacheManager()

# Convenience functions for easy access
def clear_streamlit_cache(cache_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Clear Streamlit cache"""
    return cache_manager.clear_streamlit_cache(cache_types)

def clear_redis_cache(cache_type: Optional[str] = None) -> Dict[str, Any]:
    """Clear Redis cache"""
    return cache_manager.clear_redis_cache_sync(cache_type)

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return cache_manager.get_cache_stats_sync()

def should_clear_cache(max_age_hours: int = 24) -> bool:
    """Check if cache should be cleared"""
    return cache_manager.should_clear_cache(max_age_hours) 