"""Pytest collection shim to map legacy top-level imports to backend.* modules.

This is a temporary compatibility shim added to speed up test collection without
refactoring the whole codebase. It registers backend packages under the legacy
top-level names so imports like `import services.foo` resolve to
`backend.services.foo` during tests.

Keep this file small and safe: it only runs during pytest collection.
"""
import importlib
import sys
import os
import types
import inspect
import pytest
import os
import random

_ROOT = os.path.dirname(__file__)

# Safe list of legacy top-level roots that show up across tests and modules
_LEGACY_ROOTS = [
    "utils", "services", "models", "loaders", "scripts",
    "storage", "core", "crud", "routers", "schemas"
]

for root in _LEGACY_ROOTS:
    backend_name = f"backend.{root}"
    try:
        pkg = importlib.import_module(backend_name)
        # Create a lightweight alias package module so imports like `import
        # database` don't execute package code twice but still provide a
        # proper __path__ for submodule resolution.
        alias = types.ModuleType(root)
        # copy key attributes from real package
        if hasattr(pkg, '__path__'):
            alias.__path__ = list(pkg.__path__)
        if hasattr(pkg, '__file__'):
            alias.__file__ = getattr(pkg, '__file__')
        alias.__package__ = root
        alias.__name__ = root
        # Register alias before importing submodules
        sys.modules[root] = alias

        # Import and register backend submodules under legacy names mapping to
        # the same module objects so relative imports inside those modules
        # continue to use the backend package context.
        try:
            pkg_path = os.path.join(_ROOT, 'backend', root)
            if os.path.isdir(pkg_path):
                for fname in os.listdir(pkg_path):
                    if not fname.endswith('.py') or fname.startswith('__'):
                        continue
                    mod_name = fname[:-3]
                    full_backend_mod = f"backend.{root}.{mod_name}"
                    try:
                        submod = importlib.import_module(full_backend_mod)
                        alias_name = f"{root}.{mod_name}"
                        # Register the already-imported backend submodule under
                        # the legacy dotted name so import machinery finds it.
                        sys.modules[alias_name] = submod
                    except Exception:
                        # ignore import errors for optional submodules
                        pass
        except Exception:
            pass
    except Exception:
        # If the backend package isn't present, keep going — tests referencing it
        # will fail later with a clear error; we don't want to crash collection.
        pass

# Ensure repo root is on sys.path for tests that rely on it (pytest usually does this)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# Monkeypatch pytest.skip at collection time so tests that call pytest.skip
# at module import time (without allow_module_level=True) continue to behave
# as intended. This is a test-runner-only shim; it does not change application
# code or runtime behavior outside pytest.
def _wrap_pytest_skip():
    original_skip = pytest.skip

    def _skip_wrapper(*args, **kwargs):
        # If caller didn't pass allow_module_level, detect if we're being
        # called from module import time (i.e., during collection) by
        # inspecting the call stack for a module-level frame.
        if 'allow_module_level' not in kwargs:
            # Walk stack to see if any frame is executing at module level
            for frame_info in inspect.stack():
                # If function name is '<module>' it's module-level execution
                if frame_info.function == '<module>':
                    kwargs['allow_module_level'] = True
                    break
        return original_skip(*args, **kwargs)

    pytest.skip = _skip_wrapper


# Install the wrapper immediately during pytest collection import
try:
    _wrap_pytest_skip()
except Exception:
    # Don't let failures here break test collection; it's a best-effort shim.
    pass


def pytest_configure(config):
    """Register custom pytest markers for opt-in live API tests."""
    try:
        config.addinivalue_line(
            "markers",
            "live_api: mark test to run against live external APIs (requires OPENROUTER_API_KEY and openrouter_enabled=True)."
        )
    except Exception:
        # best-effort; don't interrupt collection
        pass


def pytest_collection_modifyitems(config, items):
    """Skip tests marked with @pytest.mark.live_api unless live API is explicitly enabled.

    This avoids accidental runs of integration tests that call external services.
    """
    try:
        # Lazy import settings to avoid side-effects during collection when not needed
        from backend.utils.config import get_settings

        settings = get_settings()
        openrouter_key = getattr(settings, 'openrouter_api_key', '') or os.environ.get('OPENROUTER_API_KEY', '')
        openrouter_enabled = getattr(settings, 'openrouter_enabled', False)
        live_enabled = bool(openrouter_key) and bool(openrouter_enabled)

        if not live_enabled:
            skip_marker = pytest.mark.skip(reason=(
                "Live API tests skipped - set OPENROUTER_API_KEY and OPENROUTER_ENABLED=true to enable"
            ))
            for item in items:
                if 'live_api' in item.keywords:
                    item.add_marker(skip_marker)
    except Exception:
        # Don't fail collection if anything goes wrong here
        pass


# Fixture available for opt-in tests that need a live LLM service instance.
@pytest.fixture
def live_llm():
    """Provide a real LLMService instance for tests marked live_api.

    Tests should request this fixture explicitly. The fixture will skip if live
    API is not enabled or no API key is present.
    """
    from backend.utils.config import get_settings
    from backend.services.llm_service import get_llm_service

    settings = get_settings()
    openrouter_key = getattr(settings, 'openrouter_api_key', '') or os.environ.get('OPENROUTER_API_KEY', '')
    openrouter_enabled = getattr(settings, 'openrouter_enabled', False)
    if not (openrouter_key and openrouter_enabled):
        pytest.skip("Live LLM fixture skipped - set OPENROUTER_API_KEY and OPENROUTER_ENABLED=true to enable", allow_module_level=True)

    # Return a real, initialized service. Tests are responsible for rate-limiting.
    service = get_llm_service(settings)
    return service
