"""
Cache Management Page
Provides comprehensive cache management for both Streamlit and Redis caches
"""

import streamlit as st
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from frontend.utils.cache_manager import cache_manager, clear_streamlit_cache, clear_redis_cache, get_cache_stats

logger = logging.getLogger(__name__)

def page():
    """Main cache management page"""
    st.title("Cache Management")
    st.markdown("Manage application caches for optimal performance")
    
    # Initialize session state
    if "cache_management_initialized" not in st.session_state:
        st.session_state.cache_management_initialized = True
    
    # Sidebar for cache management options
    with st.sidebar:
        st.header("Cache Management Options")
        
        # Auto-clear settings
        st.subheader("Auto-Clear Settings")
        auto_clear_enabled = st.checkbox("Enable Auto-Clear", value=False, help="Automatically clear old cache entries")
        
        if auto_clear_enabled:
            max_age_hours = st.slider("Max Cache Age (hours)", min_value=1, max_value=168, value=24, help="Clear cache older than this")
            
            if st.button("Check Cache Age"):
                should_clear = cache_manager.should_clear_cache(max_age_hours)
                if should_clear:
                    st.warning(f"Cache is older than {max_age_hours} hours. Consider clearing.")
                else:
                    st.success(f"Cache is within {max_age_hours} hours old.")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Cache Statistics")
        
        if st.button("Refresh Cache Stats", help="Get latest cache statistics"):
            with st.spinner("Fetching cache statistics..."):
                stats = get_cache_stats()
                
                if 'error' not in stats:
                    display_cache_statistics(stats)
                else:
                    st.error(f"Failed to get cache statistics: {stats['error']}")
        
        # Show last known stats if available
        if "last_cache_stats" in st.session_state:
            st.info("Last known cache statistics:")
            display_cache_statistics(st.session_state.last_cache_stats)
    
    with col2:
        st.subheader("Quick Actions")
        
        # Streamlit cache management
        st.write("**Streamlit Cache:**")
        if st.button("Clear Streamlit Cache", help="Clear all Streamlit cached data"):
            with st.spinner("Clearing Streamlit cache..."):
                result = clear_streamlit_cache()
                st.success("Streamlit cache cleared successfully")
                # st.json(result)  # Commented out for production
        
        # Redis cache management
        st.write("**Redis Cache:**")
        if st.button("Clear Redis Cache", help="Clear all Redis cached data"):
            with st.spinner("Clearing Redis cache..."):
                result = clear_redis_cache()
                if 'error' not in result:
                    st.success("Redis cache cleared successfully")
                else:
                    st.error(f"Failed to clear Redis cache: {result['error']}")
                # st.json(result)  # Commented out for production
        
        # Clear all caches
        st.write("**All Caches:**")
        if st.button("Clear All Caches", help="Clear both Streamlit and Redis caches"):
            with st.spinner("Clearing all caches..."):
                streamlit_result = clear_streamlit_cache()
                redis_result = clear_redis_cache()
                
                st.success("All caches cleared")
                # st.json({
                #     'streamlit': streamlit_result,
                #     'redis': redis_result
                # })  # Commented out for production
    
    # Detailed cache management
    st.subheader("Detailed Cache Management")
    
    # Cache type selection
    cache_types = ['resume_parse', 'embedding', 'duplicate_check', 'user_session', 'api_response']
    selected_cache_type = st.selectbox(
        "Select Cache Type to Manage:",
        cache_types,
        help="Choose which type of cache to manage"
    )
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button(f"Clear {selected_cache_type} Cache"):
            with st.spinner(f"Clearing {selected_cache_type} cache..."):
                result = clear_redis_cache(selected_cache_type)
                if 'error' not in result:
                    st.success(f"{selected_cache_type} cache cleared successfully")
                else:
                    st.error(f"Failed to clear {selected_cache_type} cache: {result['error']}")
                # st.json(result)  # Commented out for production
    
    with col4:
        if st.button("Clear Expired Cache"):
            with st.spinner("Clearing expired cache entries..."):
                # This would need a new endpoint for clearing expired cache
                st.info("Expired cache clearing feature coming soon")
    
    # Cache health monitoring
    st.subheader("Cache Health Monitoring")
    
    if st.button("Check Cache Health"):
        with st.spinner("Checking cache health..."):
            try:
                from frontend.utils.http_client import get_sync_client
                client = get_sync_client()
                url = "http://localhost:8000/api/cache/health"
                if client is None:
                    import requests as _requests
                    resp = _requests.get(url, timeout=10)
                else:
                    resp = client.get(url, timeout=10.0)
                resp.raise_for_status()
                health_result = resp.json()
                
                if health_result.get('status') == 'healthy':
                    st.success("✅ Cache system is healthy")
                    # st.json(health_result)  # Commented out for production
                else:
                    st.error("❌ Cache system is unhealthy")
                    # st.json(health_result)  # Commented out for production
                    
            except Exception as e:
                st.error(f"Failed to check cache health: {e}")
    
    # Cache performance recommendations
    st.subheader("Performance Recommendations")
    
    # Get cache stats for recommendations
    try:
        stats = get_cache_stats()
        if 'error' not in stats:
            provide_cache_recommendations(stats)
        else:
            st.info("Unable to provide recommendations - cache statistics unavailable")
    except Exception as e:
        st.info("Unable to provide recommendations - cache system unavailable")
    
    # Cache management history
    st.subheader("Cache Management History")
    
    last_cleared = cache_manager.get_cache_clear_time()
    if last_cleared:
        st.info(f"Last cache clear: {last_cleared.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show time since last clear
        time_since = datetime.now() - last_cleared
        st.metric("Time Since Last Clear", f"{time_since.days} days, {time_since.seconds // 3600} hours")
    else:
        st.info("No cache clear history available")

def display_cache_statistics(stats: Dict[str, Any]):
    """Display cache statistics in a user-friendly format"""
    
    # Redis memory info
    if 'redis_memory' in stats:
        st.write("**Redis Memory Usage:**")
        memory = stats['redis_memory']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Used Memory", memory.get('used_memory_human', 'Unknown'))
        with col2:
            st.metric("Peak Memory", memory.get('used_memory_peak_human', 'Unknown'))
        with col3:
            st.metric("Max Memory", memory.get('maxmemory_human', 'Unknown'))
    
    # Cache type statistics
    st.write("**Cache Entries by Type:**")
    
    cache_data = []
    for cache_type, info in stats.items():
        if cache_type != 'redis_memory' and isinstance(info, dict):
            cache_data.append({
                'Type': info.get('description', cache_type),
                'Count': info.get('count', 0),
                'TTL (hours)': round(info.get('ttl', 0) / 3600, 1)
            })
    
    if cache_data:
        st.dataframe(cache_data, use_container_width=True)
    else:
        st.info("No cache entries found")
    
    # Store stats in session state for later use
    st.session_state.last_cache_stats = stats

def provide_cache_recommendations(stats: Dict[str, Any]):
    """Provide cache performance recommendations based on statistics"""
    
    recommendations = []
    
    # Check Redis memory usage
    if 'redis_memory' in stats:
        memory = stats['redis_memory']
        used_memory = memory.get('used_memory_human', '0B')
        
        # Simple memory usage check (this is a basic implementation)
        if 'MB' in used_memory or 'GB' in used_memory:
            recommendations.append("💡 Consider clearing old cache entries to free up memory")
    
    # Check cache entry counts
    total_entries = 0
    for cache_type, info in stats.items():
        if cache_type != 'redis_memory' and isinstance(info, dict):
            count = info.get('count', 0)
            total_entries += count
            
            # Check for specific cache types with high counts
            if cache_type == 'resume_parse' and count > 100:
                recommendations.append("📄 High number of cached resume parsing results - consider clearing old entries")
            elif cache_type == 'embedding' and count > 500:
                recommendations.append("🧠 High number of cached embeddings - consider clearing old entries")
    
    if total_entries > 1000:
        recommendations.append("⚠️ Large number of cache entries - consider clearing to improve performance")
    
    # Check cache age
    last_cleared = cache_manager.get_cache_clear_time()
    if last_cleared:
        age_hours = (datetime.now() - last_cleared).total_seconds() / 3600
        if age_hours > 48:
            recommendations.append("⏰ Cache is older than 48 hours - consider clearing for optimal performance")
    
    # Display recommendations
    if recommendations:
        st.write("**Recommendations:**")
        for rec in recommendations:
            st.write(rec)
    else:
        st.success("✅ Cache performance looks good!")

if __name__ == "__main__":
    page() 