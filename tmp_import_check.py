"""Temporary import check: map legacy top-level names to backend.* then test imports.
"""
import importlib, sys, os, traceback, types

ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Legacy roots to alias to backend.<root>
_LEGACY = [
    'utils', 'services', 'models', 'loaders', 'scripts', 'storage', 'database'
]

for r in _LEGACY:
    backend_name = f'backend.{r}'
    try:
        pkg = importlib.import_module(backend_name)
        alias = types.ModuleType(r)
        if hasattr(pkg, '__path__'):
            alias.__path__ = list(pkg.__path__)
        if hasattr(pkg, '__file__'):
            alias.__file__ = getattr(pkg, '__file__')
        alias.__package__ = r
        alias.__name__ = r
        sys.modules[r] = alias

        # import backend submodules and register under legacy dotted names
        pkg_path = os.path.join(ROOT, 'backend', r)
        if os.path.isdir(pkg_path):
            for fname in os.listdir(pkg_path):
                if not fname.endswith('.py') or fname.startswith('__'):
                    continue
                mod_name = fname[:-3]
                full_backend_mod = f"backend.{r}.{mod_name}"
                try:
                    submod = importlib.import_module(full_backend_mod)
                    alias_name = f"{r}.{mod_name}"
                    sys.modules[alias_name] = submod
                except Exception:
                    pass
    except Exception:
        pass

try:
    from services.matching_integrator import MatchingIntegrator
    from services.matching_enhancer import MatchingEnhancer
    from services.rag_service import RAGService
    from database.db_connection import get_db_session
    from models.models import Job
    print('IMPORTS OK')
except Exception:
    traceback.print_exc()

print('\n--- Attempt to import test module directly ---')
try:
    import importlib
    importlib.import_module('backend.tests.test_improved_matching')
    print('Test module imported OK')
except Exception:
    traceback.print_exc()
