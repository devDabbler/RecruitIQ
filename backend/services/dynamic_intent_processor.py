"""Shim for dynamic intent processor imports used by older tests.

Delegate to backend.services.intent_processor where possible.
"""
try:
    from .intent_processor import get_dynamic_intent_processor, Intent  # type: ignore
except Exception:
    # Fallback minimal implementations
    class Intent:
        def __init__(self, name: str):
            self.name = name

    def get_dynamic_intent_processor():
        def _processor(text: str):
            return Intent("unknown")
        return _processor

__all__ = ["get_dynamic_intent_processor", "Intent"]
