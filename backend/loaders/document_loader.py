"""Shim loader module to keep legacy imports working.
Delegates to backend.utils.resume_parsing.loaders.document_loader.DocumentLoader and factory.
"""
from backend.utils.resume_parsing.loaders.document_loader import DocumentLoader, DocumentLoaderConfig, DocumentLoaderFactory

__all__ = ["DocumentLoader", "DocumentLoaderConfig", "DocumentLoaderFactory"]
