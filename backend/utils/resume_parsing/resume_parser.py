"""Compatibility shim module providing `resume_parser` module expected by tests.
Re-exports `ResumeParser` from the canonical `parser.py` implementation.
"""
from .parser import ResumeParser

# Also provide a factory for legacy callers
from .parser_factory import create_resume_parser

__all__ = ["ResumeParser", "create_resume_parser"]
