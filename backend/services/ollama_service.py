"""Compatibility shim for Ollama service imports.

This module provides `get_ollama_service` used by legacy code/tests. If a
local model service exists, return an instance; otherwise return None.
"""
def get_ollama_service():
    try:
        from .local_model_service import LocalModelService
        return LocalModelService()
    except Exception:
        return None

try:
    from .local_model_service import LocalModelService as OllamaService
except Exception:
    class OllamaService:
        def __init__(self, *args, **kwargs):
            pass

__all__ = ["get_ollama_service", "OllamaService"]
