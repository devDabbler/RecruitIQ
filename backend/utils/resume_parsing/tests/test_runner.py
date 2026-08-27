"""
Simple test runner for the ExtractThinker resume parsing pipeline.

Run a single PDF/DOCX resume through the end-to-end parser using the live
Nebius AI backend.

Usage:
    python test_runner.py <path/to/resume.pdf>

Alternatively, export RESUME_FILE env var before running. One of these two
inputs is required; there is no hard-coded default.
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv, find_dotenv

# Important: Load environment variables FIRST before any other imports
project_root = Path(__file__).resolve().parents[3]  # Go up 3 levels to project root
dotenv_path = project_root / '.env'
if dotenv_path.exists():
    print(f"Loading environment variables from {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    # Try alternative location
    dotenv_path = Path(__file__).resolve().parents[2] / '.env'  # backend folder
    if dotenv_path.exists():
        print(f"Loading environment variables from {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Use find_dotenv as last resort
        found_dotenv = find_dotenv()
        if found_dotenv:
            print(f"Loading environment variables from found .env: {found_dotenv}")
            load_dotenv(dotenv_path=found_dotenv)
        else:
            print("WARNING: No .env file found. Environment variables may not be loaded correctly.")
            
# Verify NEBIUS_API_KEY is loaded
nebius_api_key = os.environ.get('NEBIUS_API_KEY') or os.environ.get('NEBIUS_API_TOKEN')
if nebius_api_key:
    print("✅ NEBIUS_API_KEY found in environment variables")
else:
    print("⚠️ NEBIUS_API_KEY not found in environment - resume parsing will fail!")
    # Helpful hint
    print("HINT: Create a .env file in project root with NEBIUS_API_KEY=your_key_here")

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock class removed - We now use the real Nebius AI service for all testing

class MockStorageService:
    """Mock storage service for testing."""
    
    async def store_file(self, file_path: str, content: bytes):
        pass
        
    async def retrieve_file(self, file_path: str) -> bytes:
        return b"mock file content"

async def test_resume_parsing():
    """Test the complete resume parsing pipeline."""
    logger.info("🚀 Starting ExtractThinker Resume Parsing Test")
    logger.info("=" * 60)
    
    try:
        # Import our modules
        from backend.utils.resume_parsing.resume_parser_main import ResumeParser
        from backend.utils.resume_parsing.contracts.resume_contract import ResumeContract
        from backend.utils.resume_parsing.processors.intelligent_text_processor import (
            IntelligentTextProcessor, 
            TextProcessingConfig,
            TextProcessingResult
        )
        
        # Create real services - use Nebius AI only
        from backend.services.nebius_ai_service import get_nebius_ai_service
        
        storage_service = None  # Replace with real storage if needed, or leave as None if not required
        
        # Get Nebius AI service using the configuration system
        nebius_ai_service = get_nebius_ai_service()
        
        # Check if the service was created successfully
        if not nebius_ai_service or not nebius_ai_service.api_key:
            raise RuntimeError('NEBIUS_API_KEY environment variable not set or Nebius AI service not configured')
        
        # Create resume parser with Nebius AI service
        logger.info("📝 Initializing ExtractThinker Resume Parser...")
        resume_parser = ResumeParser(
            storage_service=storage_service,
            llm_service=nebius_ai_service,
            ollama_service=nebius_ai_service  # Use Nebius AI service for ollama_service parameter
        )
        
        # Determine resume file to test
        # Parse command line arguments properly
        import argparse
        parser = argparse.ArgumentParser(description="Test the resume parsing pipeline")
        parser.add_argument("--resume-file", type=str, help="Path to resume file to test")
        
        # Handle both direct arg (test_runner.py resume.pdf) and named arg (test_runner.py --resume-file resume.pdf)
        args, unknown = parser.parse_known_args()
        
        cli_resume_path = None
        if args.resume_file:
            # Handle named argument --resume-file
            cli_resume_path = args.resume_file
            logger.info(f"📄 CLI resume file provided with --resume-file: {cli_resume_path}")
        elif len(unknown) > 0:
            # Handle positional argument
            cli_resume_path = unknown[0]
            logger.info(f"📄 CLI resume file provided as positional argument: {cli_resume_path}")
        else:
            # Try environment variable
            resume_file_path = os.getenv("RESUME_FILE")
            if resume_file_path:
                logger.info(f"📄 RESUME_FILE env var provided: {resume_file_path}")
            else:
                logger.error("❌ No resume file provided. Please provide a file via CLI arg or RESUME_FILE env var.")
                raise FileNotFoundError("No resume file provided")
        
        # Proceed with testing
        resume_file_path = Path(cli_resume_path or resume_file_path)
        
        if not resume_file_path.exists():
            logger.error(f"❌ Resume file not found: {resume_file_path}")
            raise FileNotFoundError(f"Resume file not found: {resume_file_path}")
        else:
            logger.info(f"📄 Testing with actual resume file: {resume_file_path}")
            
            # Parse the actual resume
            result = await resume_parser.parse_resume(str(resume_file_path))
            
            logger.info("✅ Resume parsing completed!")
            
            # Display results
            if result.personal_info:
                logger.info("👤 Personal Info:")
                logger.info(f"   Name: {result.personal_info.name}")
                logger.info(f"   Email: {result.personal_info.email}")
                logger.info(f"   Phone: {result.personal_info.phone}")
                logger.info(f"   Location: {result.personal_info.location}")
            
            if result.experience:
                logger.info(f"💼 Experience ({len(result.experience)} entries):")
                for i, exp in enumerate(result.experience, 1):
                    logger.info(f"    {i}. {exp.title} at {exp.company}")
                    logger.info(f"       Duration: {exp.start_date} - {exp.end_date}")
                    logger.info(f"       Experience object attributes: {dir(exp)}")
                    logger.info(f"       Highlights attribute exists: {type(exp.highlights)} = {exp.highlights}")
                    if not exp.highlights:
                        logger.info("       ⚠️  Highlights list is empty")
                    else:
                        for j, highlight in enumerate(exp.highlights, 1):
                            logger.info(f"           {j}. {highlight}")

                    # --- NEW BULLET POINT DEBUGGING ---
                    if hasattr(exp, 'get_bullet_points'):
                        try:
                            bullet_points = exp.get_bullet_points()
                        except Exception as e:
                            bullet_points = []
                            logger.error(f"       ❌ Error calling get_bullet_points(): {e}")
                        logger.info(f"       Bullet Points via get_bullet_points ({len(bullet_points)}):")
                        if bullet_points:
                            for k, bp in enumerate(bullet_points, 1):
                                logger.info(f"           {k}. {bp}")
                        else:
                            logger.warning("       ⚠️  No bullet points returned by get_bullet_points()")

                        # Compare highlights vs bullet_points for quick discrepancy insight
                        if exp.highlights and bullet_points and exp.highlights != bullet_points:
                            logger.warning("       ⚠️  Mismatch detected between 'highlights' and 'get_bullet_points' output")
                    
                    # Show the raw description for debugging
                    if hasattr(exp, 'description') and exp.description:
                        desc_preview = (exp.description[:200] + '...') if len(exp.description) > 200 else exp.description
                        logger.info(f"       Raw description: {desc_preview}")
                else:
                    logger.warning("       ⚠️  Description is empty for this job!")

                # --- RAW TEXT CONTEXT DEBUGGING ---
                # Try to print a slice of raw_text around this job title/company for debugging
                if hasattr(result, 'raw_text') and result.raw_text:
                    job_identifiers = []
                    if exp.title:
                        job_identifiers.append(exp.title)
                    if exp.company:
                        job_identifiers.append(exp.company)
                    job_context_found = False
                    for ident in job_identifiers:
                        idx = result.raw_text.find(ident)
                        if idx != -1:
                            start = max(0, idx - 300)
                            end = min(len(result.raw_text), idx + 300)
                            context_snippet = result.raw_text[start:end].replace('\n', ' ')
                            logger.info(f"       [RAW TEXT CONTEXT for '{ident}']: ...{context_snippet}...")
                            job_context_found = True
                            break
                    if not job_context_found:
                        logger.warning(f"       ⚠️  Could not find job context in raw_text for title/company: {job_identifiers}")
                else:
                    logger.warning("       ⚠️  No raw_text available for job context debugging!")
            
            if result.education:
                logger.info(f"🎓 Education ({len(result.education)} entries):")
                for i, edu in enumerate(result.education[:2], 1):  # Show first 2
                    logger.info(f"   {i}. {edu.degree} in {edu.field_of_study}")
                    logger.info(f"      Institution: {edu.institution}")
            
            if result.skills:
                logger.info(f"🛠️  Skills ({len(result.skills)} total):")
                skill_names = [skill.name for skill in result.skills[:8] if skill.name]
                logger.info(f"   {', '.join(skill_names)}...")  # Show first 8
            
            # Show metadata
            if hasattr(result, 'metadata') and result.metadata:
                logger.info(f"📊 Metadata:")
                logger.info(f"   Parser Version: {result.metadata.get('parser_version')}")
                logger.info(f"   Extraction Method: {result.metadata.get('extraction_method')}")
                logger.info(f"   AI Used: {result.metadata.get('ai_extractor_used')}")
                logger.info(f"   Document Intelligence: {result.metadata.get('document_intelligence')}")
        
        logger.info("=" * 60)
        logger.info("🎉 ExtractThinker Pipeline Test Completed Successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}")
        logger.error("Stack trace:", exc_info=True)
        raise

async def test_individual_components():
    """Test individual components of the pipeline."""
    logger.info("\n🧪 Testing Individual Components")
    logger.info("-" * 40)
    
    try:
        # Test 1: Intelligent Text Processor
        logger.info("1️⃣ Testing Intelligent Text Processor...")
        from backend.utils.resume_parsing.processors.intelligent_text_processor import (
            IntelligentTextProcessor, 
            TextProcessingConfig,
            TextProcessingResult
        )
        
        config = TextProcessingConfig(
            deep_clean=True,
            fix_merged_words=True,
            normalize_dates=True
        )
        processor = IntelligentTextProcessor(config)
        
        # Test with sample text
        sample_text = "JacobSmith\nSoftwareEngineer\njacob.smith@email.com|(555)123-4567"
        
        # Use the async process method
        result_dict = await processor.process(sample_text)
        
        # Log the results
        logger.info(f"   ✅ Original: {sample_text[:30]}...")
        logger.info(f"   ✅ Processed: {result_dict['processed_text'][:50]}...")
        logger.info(f"   ✅ Stats: {result_dict['stats']}")
        
        # Test 2: Document Loader Factory
        logger.info("2️⃣ Testing Document Loader Factory...")
        from backend.utils.resume_parsing.loaders.document_loader import (
            DocumentLoaderFactory, 
            DocumentLoaderConfig
        )
        
        # Create a test PDF file
        import tempfile
        from fpdf import FPDF
        
        # Create a temporary directory and test PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            # Create a simple PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Test Resume", ln=True, align='C')
            pdf.cell(200, 10, txt="Name: Test User", ln=True, align='L')
            pdf.output(temp_pdf.name)
            
            # Now test loading it
            loader_config = DocumentLoaderConfig(ocr_enabled=True)
            try:
                pdf_loader = DocumentLoaderFactory.create_loader(temp_pdf.name, loader_config)
                logger.info("   ✅ PDF Loader created successfully")
                
                # Test loading the document
                pages = pdf_loader.load(temp_pdf.name)
                logger.info(f"   ✅ Successfully loaded {len(pages)} pages")
                for i, page in enumerate(pages, 1):
                    logger.info(f"   ✅ Page {i} has {len(page.content)} characters")
                    logger.info(f"   ✅ Page {i} preview: {page.content[:100]}...")
                    
            except Exception as e:
                logger.error(f"   ❌ Error creating or using PDF loader: {str(e)}", exc_info=True)
            
            # Clean up
            try:
                os.unlink(temp_pdf.name)
            except:
                pass
        
        # Test 3: Resume Contract Validation
        logger.info("3️⃣ Testing Resume Contract Validation...")
        from backend.utils.resume_parsing.contracts.resume_contract import (
            ResumeContract, 
            PersonalInfoContract
        )
        
        sample_data = {
            "personal_info": {
                "name": "Jacob Smith",
                "email": "jacob.smith@example.com",
                "phone": "(555) 123-4567",
                "location": "San Francisco, CA"
            },
            "experience": [
                {
                    "title": "Senior Software Engineer",
                    "company": "Tech Corp Inc.",
                    "start_date": "2020-01",
                    "end_date": "2023-12",
                    "description": "Developed and maintained web applications"
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "B.S. Computer Science",
                    "field_of_study": "Computer Science",
                    "start_date": "2015-09",
                    "end_date": "2019-05"
                }
            ],
            "skills": [
                {"name": "Python", "category": "Programming"},
                {"name": "Django", "category": "Framework"},
                {"name": "React", "category": "Frontend"},
                {"name": "Communication", "category": "Soft Skills"},
                {"name": "Teamwork", "category": "Soft Skills"}
            ],
            "projects": [],
            "certifications": [],
            "languages": [{"name": "English", "proficiency": "Native"}],
            "raw_text": "Sample resume text for testing"
        }
        
        contract = ResumeContract(**sample_data)
        logger.info(f"   ✅ Contract validated: {contract.personal_info.name}")
        
        logger.info("🎯 All individual components tested successfully!")
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {str(e)}")
        raise

async def main():
    """Main test runner."""
    logger.info("🚀 ExtractThinker Resume Parsing Pipeline Test")
    logger.info("=" * 60)
    logger.info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("resume_parser_test.log")
        ]
    )
    
    try:
        # Test individual components
        await test_individual_components()
        
        # Test the complete pipeline
        await test_resume_parsing()
        
        logger.info("\n🎉 All tests completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {str(e)}")
        logger.error("Stack trace:", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
