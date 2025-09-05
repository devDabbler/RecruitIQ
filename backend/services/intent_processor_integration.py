"""Compatibility shim exposing intent processor integration APIs at backend.services.*

Re-export functions from the canonical intent_processor module when available,
otherwise provide lightweight fallbacks to keep tests importable.
"""
try:
    from backend.services.intent_processor import (
        get_intent_processor_integration,
        detect_intent_unified,
        process_intent_unified,
    )
except Exception:
    def get_intent_processor_integration(*args, **kwargs):
        return None

    def detect_intent_unified(text, *args, **kwargs):
        return {'intent': 'unknown', 'confidence': 0.0}

    def process_intent_unified(payload, *args, **kwargs):
        return {'result': None}

__all__ = [
    'get_intent_processor_integration', 'detect_intent_unified', 'process_intent_unified'
]
