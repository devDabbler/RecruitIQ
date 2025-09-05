"""Minimal AIExtractor stub for compatibility with tests.

This provides a simple `AIExtractor` class with an `extract` method that
returns an empty structure when the full implementation isn't available.
"""
from typing import Dict, Any


class AIExtractor:
    def __init__(self, *args, **kwargs):
        pass

    async def extract(self, text: str) -> Dict[str, Any]:
        # Conservative fallback: return minimal structure expected by callers
        return {
            'experience': [],
            'education': [],
            'skills': []
        }

    def extract_sync(self, text: str) -> Dict[str, Any]:
        return {
            'experience': [],
            'education': [],
            'skills': []
        }

__all__ = ['AIExtractor']
