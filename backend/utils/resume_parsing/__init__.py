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
# Unified public import – always use Nebius-backed parser
from .parser import ResumeParser
from .parser_factory import create_resume_parser

# Nebius AI-based parser
from .nebius_ai_parser import NebiusAIParser

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
    'NebiusAIParser',
    
    # Data models
    'ResumeData', 'PersonalInfo', 'Education', 'Experience',
    'Skill', 'Project', 'Certification', 'Language',
    
    # Processors
    'BaseProcessor', 'OCRProcessor',
    'MarkdownProcessor', 'SectionProcessor',
    
    # Extractors
    'BaseExtractor'
]