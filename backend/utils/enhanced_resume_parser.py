"""Compatibility wrapper for legacy tests that expect EnhancedResumeParser.

This thin wrapper delegates to the new NebiusAIParser implementation so that
older documentation scripts and tests continue to import and use
`utils.enhanced_resume_parser.EnhancedResumeParser` without modification.
The goal is to avoid hard-coding behaviour while preserving backwards
compatibility for test suites that have not yet been migrated.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser


class EnhancedResumeParser:
    """Legacy-compatible parser that proxies to `NebiusAIParser`."""

    def __init__(self, **kwargs: Any) -> None:
        # Accept arbitrary kwargs for forward compatibility but ignore them for now
        self._parser = NebiusAIParser(**kwargs)

    async def parse_resume(self, file_path: str | Path, **kwargs: Any) -> Dict[str, Any]:
        """Asynchronously parse a resume file and return structured data.

        This mirrors the coroutine signature used in enhanced parser tests.
        """
        return await self._parser.parse_file(str(file_path))

    # Synchronous helper for scripts that call parse directly
    def parse(self, file_path: str | Path, **kwargs: Any) -> Dict[str, Any]:
        """Synchronously parse a resume file (blocking helper)."""
        return self._parser.parse(file_path, **kwargs)
