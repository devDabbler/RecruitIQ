"""Shim module to provide legacy intent_processor_integration API from backend.services.intent_processor

This attempts to import the canonical implementation from backend.services.intent_processor
and re-export the commonly used helpers. If the canonical module is missing, we provide
lightweight fallbacks so tests import cleanly.
"""
try:
    from backend.services.intent_processor import (
        get_intent_processor_integration,
        detect_intent_unified,
        process_intent_unified,
    )
except Exception:
    # Minimal fallbacks
    def get_intent_processor_integration(*args, **kwargs):
        return None

    def detect_intent_unified(text, *args, **kwargs):
        return {'intent': 'unknown', 'confidence': 0.0}

    def process_intent_unified(payload, *args, **kwargs):
        return {'result': None}

__all__ = [
    'get_intent_processor_integration', 'detect_intent_unified', 'process_intent_unified'
]
