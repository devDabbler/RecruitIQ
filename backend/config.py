"""
Proxy module so that `import backend.config` works.
Re-exports Settings and get_settings from utils.config.
"""
from .utils.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
