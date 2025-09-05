"""Compatibility utils package for resume_parsing (contains text utilities).
This package provides minimal, well-tested helpers used by legacy tests and code.
"""
from .text_utils import *

__all__ = [name for name in globals().keys() if not name.startswith("_")]
