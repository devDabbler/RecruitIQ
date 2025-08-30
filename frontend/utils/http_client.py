import streamlit as st


def _httpx_available():
    try:
        import httpx  # type: ignore
        return True
    except Exception:
        return False


@st.cache_resource
def get_sync_client(timeout: float = 20.0):
    """Return a cached httpx.Client or None if httpx isn't available."""
    if not _httpx_available():
        return None
    import httpx
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=50)
    return httpx.Client(timeout=timeout, limits=limits)


@st.cache_resource
def get_async_client(timeout: float = 30.0):
    """Return a cached httpx.AsyncClient or None if httpx isn't available."""
    if not _httpx_available():
        return None
    import httpx
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=50)
    return httpx.AsyncClient(timeout=timeout, limits=limits)
"""Reusable HTTP client helpers for the Streamlit frontend.

Provides cached sync and async httpx clients to avoid recreating connection
pools on every rerun. Keep functions small and parameterized so the app
remains dynamic.
"""
from typing import Optional
import streamlit as st

try:
    import httpx
except Exception:
    httpx = None


@st.cache_resource
def get_sync_client(timeout: float = 30.0, max_connections: int = 50, max_keepalive: int = 10) -> Optional[object]:
    """Return a cached httpx.Client instance for synchronous requests.

    Returns None if httpx isn't available. Callers should raise a useful
    error if the client is None.
    """
    if httpx is None:
        return None
    limits = httpx.Limits(max_keepalive_connections=max_keepalive, max_connections=max_connections)
    return httpx.Client(timeout=timeout, limits=limits)


@st.cache_resource
def get_async_client(timeout: float = 30.0, max_connections: int = 50, max_keepalive: int = 10) -> Optional[object]:
    """Return a cached httpx.AsyncClient instance for async requests.

    Use this when you have async code paths. Streamlit apps are primarily
    synchronous, so prefer `get_sync_client` for most frontend calls.
    """
    if httpx is None:
        return None
    limits = httpx.Limits(max_keepalive_connections=max_keepalive, max_connections=max_connections)
    return httpx.AsyncClient(timeout=timeout, limits=limits)
