"""Compatibility DocumentProcessor wrapper for resume parsing pipeline.

This module provides a DocumentProcessor that uses the DocumentLoaderFactory
to load documents and expose a simple interface used by higher-level code.
"""
from typing import List
from ..loaders.document_loader import DocumentLoaderFactory, DocumentLoaderConfig, DocumentPage

class DocumentProcessor:
    def __init__(self, ocr_enabled: bool = True):
        self.config = DocumentLoaderConfig(ocr_enabled=ocr_enabled)
        self.loader = DocumentLoaderFactory.create_loader("", self.config)

    def load(self, path: str) -> List[DocumentPage]:
        return self.loader.load(path)

__all__ = ["DocumentProcessor"]
