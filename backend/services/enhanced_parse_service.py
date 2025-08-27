"""Compatibility wrapper service used by legacy tests expecting `EnhancedParseService`.

The service provides a minimal API that delegates to `ResumeService`, which
is already used in production for Nebius AI powered parsing. Only a subset of
methods required by the legacy documentation/test scripts are implemented.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from backend.services.resume_service import ResumeService


class EnhancedParseService:
    """Thin wrapper around the existing `ResumeService`."""

    def __init__(self, **kwargs: Any) -> None:
        self._service = ResumeService(**kwargs)

    async def parse_file(self, file_path: str | Path, **kwargs: Any) -> Dict[str, Any]:
        """Asynchronously parse a file and return structured resume data."""
        return await self._service.parse_file(file_path, **kwargs)

    # Synchronous shortcut sometimes used in older scripts
    def parse(self, file_path: str | Path, **kwargs: Any) -> Dict[str, Any]:
        """Synchronously parse a resume file."""
        return self._service.parse(file_path, **kwargs)
