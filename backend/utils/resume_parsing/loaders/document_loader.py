"""
Document loader factory and config for resume parsing pipeline.
"""

from typing import Any, Optional, List
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DocumentLoaderConfig:
    def __init__(self, file_path: str = '', file_type: str = 'pdf', window: int = 1, ocr_enabled: bool = False, **kwargs):
        self.file_path = file_path
        self.file_type = file_type
        self.window = window
        self.ocr_enabled = ocr_enabled
        for k, v in kwargs.items():
            setattr(self, k, v)

class DocumentPage:
    """Represents a single page of a document"""
    def __init__(self, content: str, page_number: int = 1):
        self.content = content
        self.page_number = page_number

class DocumentLoader:
    """Base document loader"""
    def __init__(self, config: DocumentLoaderConfig):
        self.config = config
    
    def load(self, file_path: str) -> List[DocumentPage]:
        """Load document and return pages"""
        raise NotImplementedError

class PDFDocumentLoader(DocumentLoader):
    """PDF document loader using existing PDF extraction utilities"""
    def load(self, file_path: str) -> List[DocumentPage]:
        """Load PDF file and extract text using existing utilities"""
        try:
            # Use the existing PDF extraction method from parse_service
            text = self._extract_from_pdf(file_path)
            return [DocumentPage(text, 1)]
        except Exception as e:
            logger.error(f"Error loading PDF {file_path}: {str(e)}")
            return [DocumentPage("PDF content could not be loaded", 1)]
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file using pypdf, with pdfplumber fallback."""
        text = ""
        # Try pypdf first
        try:
            import pypdf
            with open(file_path, "rb") as f:
                pdf = pypdf.PdfReader(f)
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {str(e)}")
        
        # Fallback to pdfplumber if text is empty
        if not text.strip():
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                logger.error(f"pdfplumber extraction failed: {str(e)}")
        
        logger.info(f"Extracted PDF text length: {len(text)}")
        return text

class DocumentLoaderFactory:
    @staticmethod
    def create_loader(file_path: str, config: DocumentLoaderConfig) -> DocumentLoader:
        """Create appropriate document loader based on file type"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return PDFDocumentLoader(config)
        else:
            # Default to PDF loader for unknown types
            return PDFDocumentLoader(config)
