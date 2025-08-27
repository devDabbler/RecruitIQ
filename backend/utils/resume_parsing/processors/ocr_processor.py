"""
OCR Processor
Extracts text from images and scanned documents
"""
import os
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class OCRProcessor(BaseProcessor):
    """
    OCR processor for text extraction from images and scanned documents
    Supports multiple OCR engines with fallback mechanisms
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize OCR processor with configuration
        
        Args:
            config: Configuration dictionary with OCR settings
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        
        # Configure OCR engines
        self.ocr_engines = self._initialize_ocr_engines()
        
    def _initialize_ocr_engines(self) -> Dict[str, Any]:
        """Initialize available OCR engines based on configuration"""
        engines = {}
        
        # Try to load pytesseract
        try:
            import pytesseract
            engines['pytesseract'] = pytesseract
            self.logger.info("Initialized pytesseract OCR engine")
        except ImportError:
            self.logger.warning("pytesseract not available")
        
        # Try to load EasyOCR
        try:
            import easyocr
            import torch
            import platform
            
            # Configure EasyOCR to use appropriate device
            if platform.system() == 'Darwin' and torch.backends.mps.is_available():
                # Use MPS (Metal Performance Shaders) for Apple Silicon
                gpu = True
                self.logger.info("Using MPS for GPU acceleration")
            elif platform.system() == 'Windows':
                try:
                    import torch_directml
                    # Use DirectML for AMD/NVIDIA GPUs on Windows
                    torch_directml.device()  # Initialize DirectML
                    gpu = True
                    self.logger.info("Using DirectML for GPU acceleration")
                except ImportError:
                    # Fallback to CPU if DirectML is not available
                    gpu = False
                    self.logger.info("DirectML not available, falling back to CPU")
            elif platform.system() == 'Linux' and hasattr(torch.backends, 'rocm') and torch.backends.rocm.is_available():
                # Use ROCm for AMD GPUs (Linux only)
                gpu = True
                self.logger.info("Using ROCm for GPU acceleration")
            elif torch.cuda.is_available():
                # Use CUDA for NVIDIA GPUs
                gpu = True
                self.logger.info("Using CUDA for GPU acceleration")
            else:
                # Fallback to CPU
                gpu = False
                self.logger.info("Using CPU for OCR processing")
                
            engines['easyocr'] = easyocr.Reader(['en'], gpu=gpu)
            self.logger.info(f"Initialized EasyOCR engine with GPU: {gpu}")
        except ImportError:
            self.logger.warning("easyocr not available")
            
        return engines
    
    async def process(self, file_path: str) -> str:
        """
        Extract text from a document with OCR fallback if needed
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text content
        """
        # Check file type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # For standard document types, try standard extraction first
        if file_ext in ['.pdf', '.docx', '.doc', '.txt']:
            try:
                text = await self._extract_text_from_document(file_path, file_ext)
                if text and len(text.strip()) > 100:  # Basic validation
                    return text
            except Exception as e:
                self.logger.warning(f"Standard extraction failed: {str(e)}")
        
        # Try OCR for images or as fallback
        if file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp'] or not text:
            try:
                return await self._extract_text_with_ocr(file_path)
            except Exception as e:
                self.logger.error(f"OCR extraction failed: {str(e)}")
                raise
    
    async def _extract_text_from_document(self, file_path: str, file_ext: str) -> str:
        """Extract text from standard document formats"""
        if file_ext == '.pdf':
            return await self._extract_text_from_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            return await self._extract_text_from_docx(file_path)
        elif file_ext == '.txt':
            return await self._extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported document type: {file_ext}")
    
    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF using multiple libraries with fallback"""
        text = ""
        
        # Try pdfplumber first
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or '' for page in pdf.pages)
            if text and len(text.strip()) > 100:
                return text
        except Exception as e:
            self.logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = "\n".join(page.extract_text() or '' for page in reader.pages)
            return text
        except Exception as e:
            self.logger.warning(f"PyPDF2 extraction failed: {str(e)}")
            raise
    
    async def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX/DOC"""
        import docx2txt
        return docx2txt.process(file_path)
    
    async def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    async def _extract_text_with_ocr(self, file_path: str) -> str:
        """Extract text using OCR engines"""
        if not self.ocr_engines:
            raise ValueError("No OCR engines available")
        
        # Try pytesseract first if available
        if 'pytesseract' in self.ocr_engines:
            try:
                from PIL import Image
                pytesseract = self.ocr_engines['pytesseract']
                img = Image.open(file_path)
                text = pytesseract.image_to_string(img)
                if text and len(text.strip()) > 50:
                    return text
            except Exception as e:
                self.logger.warning(f"pytesseract OCR failed: {str(e)}")
        
        # Try EasyOCR if available
        if 'easyocr' in self.ocr_engines:
            try:
                reader = self.ocr_engines['easyocr']
                result = reader.readtext(file_path, detail=0)
                text = "\n".join(result)
                return text
            except Exception as e:
                self.logger.warning(f"EasyOCR failed: {str(e)}")
        
        raise ValueError("All OCR engines failed")