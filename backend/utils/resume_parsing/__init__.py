"""
Resume Parsing Package
Provides a modular, robust resume parsing implementation with:
- NLP-based extraction using spaCy
- Local model integration
- OCR processing for images and scanned documents
- Markdown formatting for better structure
- Section detection and extraction
- Standardized data models
"""

# Main parser and factory functions
from .resume_parser_main import ResumeParser
from .parser_factory import create_resume_parser

# Data models
from .models.resume_schema import (
    ResumeData, PersonalInfo, Education, Experience,
    Skill, Project, Certification, Language
)

# Make processors available
from .processors import (
    BaseProcessor, OCRProcessor, 
    MarkdownProcessor, SectionProcessor
)

# Make extractors available
from .extractors import (
    BaseExtractor
)

__all__ = [
    # Main parser
    'ResumeParser', 'create_resume_parser',

    # Data models
    'ResumeData', 'PersonalInfo', 'Education', 'Experience',
    'Skill', 'Project', 'Certification', 'Language',
    
    # Processors
    'BaseProcessor', 'OCRProcessor',
    'MarkdownProcessor', 'SectionProcessor',
    
    # Extractors
    'BaseExtractor'
]