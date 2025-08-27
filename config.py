"""
Top-level proxy module for application settings.
Allows `import config` to resolve to backend.utils.config.Settings.
"""
from backend.utils.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
