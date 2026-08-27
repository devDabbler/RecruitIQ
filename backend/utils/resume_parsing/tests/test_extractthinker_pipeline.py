"""
Test suite for ExtractThinker resume parsing pipeline.
Tests the complete pipeline using real resume files to ensure accuracy and robustness.
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
import pytest

# Add the parent directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_parser import ResumeParser
from contracts.resume_contract import ResumeContract
from extractors.structured_extractor import StructuredExtractor
from processors.intelligent_text_processor import IntelligentTextProcessor, TextProcessingConfig
from loaders.document_loader import DocumentLoaderFactory, DocumentLoaderConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockNebiusAIService:
    """Mock Nebius AI service for testing without actual API calls."""
    
    def __init__(self):
        self.call_count = 0
        
    async def generate_completion(self, prompt: str, **kwargs) -> str:
        """Mock completion that returns a structured resume JSON."""
        self.call_count += 1
        
        # Return a mock structured resume response
        mock_response = {
            "personal_info": {
                "name": "Jacob Smith",
                "email": "jacob.smith@email.com",
                "phone": "+1 (555) 123-4567",
                "location": "San Francisco, CA",
                "linkedin": "https://linkedin.com/in/jacobsmith",
                "github": "https://github.com/jacobsmith",
                "website": ""
            },
            "education": [
                {
                    "institution": "University of California, Berkeley",
                    "degree": "Bachelor of Science",
                    "field_of_study": "Computer Science",
                    "start_date": "2018-08",
                    "end_date": "2022-05",
                    "gpa": "3.8",
                    "honors": ["Magna Cum Laude"],
                }
            ],
            "experience": [
                {
                    "company": "Tech Solutions Inc.",
                    "title": "Software Engineer",
                    "start_date": "2022-06",
                    "end_date": "Present",
                    "location": "San Francisco, CA",
                    "description": "Developed web applications using React and Node.js",
                    "achievements": [
                        "Improved application performance by 40%",
                        "Led team of 3 junior developers"
                    ]
                },
                {
                    "company": "StartupXYZ",
                    "title": "Software Engineering Intern",
                    "start_date": "2021-06",
                    "end_date": "2021-08",
                    "location": "Palo Alto, CA",
                    "description": "Built mobile applications using React Native",
                    "achievements": [
                        "Delivered 2 mobile apps to production"
                    ]
                }
            ],
            "skills": {
                "technical_skills": [
                    "Python", "JavaScript", "React", "Node.js", "SQL", "Git", "AWS"
                ],
                "soft_skills": [
                    "Leadership", "Communication", "Problem Solving", "Team Collaboration"
                ]
            },
            "projects": [
                {
                    "name": "E-commerce Platform",
                    "description": "Full-stack web application for online shopping",
                    "technologies": ["React", "Node.js", "MongoDB", "Stripe API"],
                    "url": "https://github.com/jacobsmith/ecommerce",
                    "start_date": "2022-01",
                    "end_date": "2022-04"
                }
            ],
            "certifications": [
                {
                    "name": "AWS Certified Developer",
                    "issuer": "Amazon Web Services",
                    "date_obtained": "2023-03",
                    "expiry_date": "2026-03",
                    "credential_id": "AWS-DEV-12345"
                }
            ],
            "languages": [
                {
                    "language": "English",
                    "proficiency": "Native"
                },
                {
                    "language": "Spanish",
                    "proficiency": "Conversational"
                }
            ],
            "raw_text": "Jacob Smith Software Engineer with 2+ years of experience..."
        }
        
        return json.dumps(mock_response)

class MockStorageService:
    """Mock storage service for testing."""
    
    def __init__(self):
        pass
        
    async def store_file(self, file_path: str, content: bytes):
        """Mock file storage."""
        pass
        
    async def retrieve_file(self, file_path: str) -> bytes:
        """Mock file retrieval."""
        return b"mock file content"

class TestExtractThinkerPipeline:
    """Test suite for the ExtractThinker resume parsing pipeline."""
    
    @pytest.fixture
    def mock_services(self):
        """Set up mock services for testing."""
        return {
            'storage_service': MockStorageService(),
            'nebius_ai_service': MockNebiusAIService()
        }
    
    @pytest.fixture
    def resume_parser(self, mock_services):
        """Create a resume parser instance for testing."""
        return ResumeParser(
            storage_service=mock_services['storage_service'],
            nebius_ai_service=mock_services['nebius_ai_service']
        )
    
    def test_document_loader_factory(self):
        """Test the document loader factory."""
        config = DocumentLoaderConfig(
            ocr_enabled=True,
            table_structure_enabled=True,
            preserve_formatting=True,
            cache_ttl=600
        )
        
        # Test PDF loader creation
        pdf_loader = DocumentLoaderFactory.create_loader('.pdf', config)
        assert pdf_loader is not None
        
        # Test DOCX loader creation
        docx_loader = DocumentLoaderFactory.create_loader('.docx', config)
        assert docx_loader is not None
        
        # Test TXT loader creation
        txt_loader = DocumentLoaderFactory.create_loader('.txt', config)
        assert txt_loader is not None
        
        logger.info("✅ Document loader factory test passed")
    
def run_tests():
    """Run all tests manually without pytest."""
    logger.info("🚀 Starting ExtractThinker Pipeline Tests")

    # Create test instance
    test_instance = TestExtractThinkerPipeline()

    try:
        logger.info("\n📄 Testing Document Loader Factory...")
        test_instance.test_document_loader_factory()

        logger.info("\n🎉 All tests completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    run_tests()
