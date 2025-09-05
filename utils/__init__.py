"""Compatibility shim: expose backend.utils as top-level `utils` package for tests and legacy imports.

This module re-exports the backend.utils package so code that imports `utils.xxx` continues to work
without changing a large number of import statements across the codebase and tests.
"""

from importlib import import_module
import sys

# Import the backend.utils package and re-export at the top-level `utils` package
_backend_utils = import_module('backend.utils')

# Expose backend.utils attributes at utils package level
for attr in dir(_backend_utils):
    if not attr.startswith('_'):
        try:
            globals()[attr] = getattr(_backend_utils, attr)
        except Exception:
            pass

# Ensure commonly used subpackages (resume_parsing, database, etc.) are importable as
# `utils.resume_parsing` by mapping them to the backend equivalents in sys.modules.
_subpackages = [
    'resume_parsing',
    'database',
    'enhanced_resume_parser',
    'resume_parser',
]
for sub in _subpackages:
    backend_name = f'backend.utils.{sub}'
    utils_name = f'utils.{sub}'
    try:
        module = import_module(backend_name)
        sys.modules[utils_name] = module
        globals()[sub] = module
    except Exception:
        # If a submodule doesn't exist, ignore — tests that need it will fail separately
        pass

__all__ = [name for name in globals().keys() if not name.startswith('_')]
