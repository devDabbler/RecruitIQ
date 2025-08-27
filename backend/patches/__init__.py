"""
Initialize patches for cross-platform compatibility and application enhancements.
This module provides fixes for platform-specific issues and applies code patches.
"""
import platform
import sys
import os
import importlib.util
import logging
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Only apply Windows-specific patches when running on Windows
if platform.system() == "Windows":
    # Path to our mock pwd module
    pwd_module_path = Path(__file__).parent / "pwd.py"
    
    # Create a new module spec and add it to sys.modules
    spec = importlib.util.spec_from_file_location("pwd", pwd_module_path)
    pwd_module = importlib.util.module_from_spec(spec)
    sys.modules["pwd"] = pwd_module
    spec.loader.exec_module(pwd_module)
    
    logger.info("Windows compatibility patch applied: Mock 'pwd' module loaded")

# Apply all functional patches
try:
    from backend.patches.apply_patches import apply_all_patches
    apply_all_patches()
except Exception as e:
    logger.error(f"Failed to apply patches: {str(e)}")