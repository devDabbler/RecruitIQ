"""Top-level shim package for `services` -> forwards to `backend.services`.

This file dynamically maps imports of `services` to the existing
`backend.services` package so legacy top-level imports continue to work
without changing the rest of the codebase.

Keep this shim minimal and dynamic to avoid hardcoding behavior.
"""
import importlib
import sys
import types

_backend_name = "backend.services"
try:
    _backend_mod = importlib.import_module(_backend_name)
    # Register the backend module under the top-level name so imports like
    # `import services.enhanced_parse_service` resolve correctly.
    sys.modules[__name__] = _backend_mod
except Exception:
    # Provide a harmless empty module so tests that import services don't crash
    # at import-time; real attribute access will surface errors normally.
    sys.modules.setdefault(__name__, types.ModuleType(__name__))
