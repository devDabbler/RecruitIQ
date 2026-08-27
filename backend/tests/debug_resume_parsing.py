#!/usr/bin/env python3
"""
Debug script for resume parsing issues
"""
import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing.resume_parser import ResumeParser
from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from utils.resume_parsing.extractors.nlp_extractor import NLPExtractor
from utils.resume_parsing.extractors.ai_extractor import AIExtractor
from services.storage_service import StorageService
from services.nebius_ai_service import NebiusAIService

# Set up logging to both file and console
log_filename = f"resume_parsing_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def test_resume_parsing():
    """Test resume parsing with Jacob Smith's resume"""
    
    # Path to Jacob Smith's resume
    resume_path = "../Jacob_Smith_Resume.pdf"
    
    if not os.path.exists(resume_path):
        logger.error(f"Error: Resume file not found at {resume_path}")
        return
    
    logger.info("=" * 80)
    logger.info("TESTING RESUME PARSING WITH JACOB SMITH'S RESUME")
    logger.info("=" * 80)
    
    try:
        # Create real services
        storage_service = StorageService()
        nebius_ai_service = NebiusAIService()
        
        # Initialize the resume parser
        parser = ResumeParser(storage_service, nebius_ai_service)
        
        # Parse the resume
        logger.info(f"Parsing resume: {resume_path}")
        result = await parser.parse(resume_path)
        
        # Print the results
        logger.info("=" * 80)
        logger.info("PARSING RESULTS")
        logger.info("=" * 80)
        
        # Personal Info
        if result.personal_info:
            logger.info("📧 PERSONAL INFO:")
            logger.info(f"  Name: {result.personal_info.name}")
            logger.info(f"  Email: {result.personal_info.email}")
            logger.info(f"  Phone: {result.personal_info.phone}")
            logger.info(f"  Address: {result.personal_info.address}")
            logger.info(f"  Location: {result.personal_info.location}")
            logger.info(f"  LinkedIn: {result.personal_info.linkedin}")
        else:
            logger.warning("❌ No personal info extracted")
        
        # Experience
        if result.experience:
            logger.info(f"💼 EXPERIENCE ({len(result.experience)} entries):")
            for i, exp in enumerate(result.experience, 1):
                logger.info(f"  {i}. {exp.title} at {exp.company}")
                logger.info(f"     Location: {exp.location}")
                logger.info(f"     Duration: {exp.start_date} - {exp.end_date}")
                logger.info(f"     Description: {exp.description[:100]}...")
        else:
            logger.warning("❌ No experience extracted")
        
        # Education
        if result.education:
            logger.info(f"🎓 EDUCATION ({len(result.education)} entries):")
            for i, edu in enumerate(result.education, 1):
                logger.info(f"  {i}. {edu.degree} from {edu.institution}")
                logger.info(f"     Location: {edu.location}")
                logger.info(f"     Duration: {edu.start_date} - {edu.end_date}")
        else:
            logger.warning("❌ No education extracted")
        
        # Skills
        if result.skills:
            logger.info(f"🛠️ SKILLS ({len(result.skills)} skills):")
            skill_names = [skill.name for skill in result.skills]
            logger.info(f"  {', '.join(skill_names[:10])}{'...' if len(skill_names) > 10 else ''}")
        else:
            logger.warning("❌ No skills extracted")
        
        # Test individual extractors
        logger.info("=" * 80)
        logger.info("INDIVIDUAL EXTRACTOR TESTING")
        logger.info("=" * 80)
        
        # Get the text content
        try:
            import PyPDF2
            with open(resume_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text()
        except ImportError:
            logger.warning("PyPDF2 not available, trying to read as text file...")
            with open(resume_path, 'rb') as f:
                text_content = f.read().decode('utf-8', errors='ignore')
        
        logger.info(f"Extracted text length: {len(text_content)} characters")
        logger.info(f"First 200 characters: {text_content[:200]}...")
        
        # Test Regex Extractor
        logger.info("🔍 TESTING REGEX EXTRACTOR:")
        try:
            regex_extractor = RegexExtractor()
            regex_result = await regex_extractor.extract(text_content)
            
            logger.info(f"  Personal Info: {regex_result.get('personal_info', 'Not found')}")
            logger.info(f"  Experience: {len(regex_result.get('experience', []))} entries")
            logger.info(f"  Education: {len(regex_result.get('education', []))} entries")
            logger.info(f"  Skills: {len(regex_result.get('skills', []))} skills")
            
        except Exception as e:
            logger.error(f"  ❌ Regex extractor failed: {e}")
        
        # Test NLP Extractor
        logger.info("🧠 TESTING NLP EXTRACTOR:")
        try:
            nlp_extractor = NLPExtractor(nebius_ai_service)
            nlp_result = await nlp_extractor.extract(text_content)
            
            logger.info(f"  Personal Info: {nlp_result.get('personal_info', 'Not found')}")
            logger.info(f"  Experience: {len(nlp_result.get('experience', []))} entries")
            logger.info(f"  Education: {len(nlp_result.get('education', []))} entries")
            logger.info(f"  Skills: {len(nlp_result.get('skills', []))} skills")
            
        except Exception as e:
            logger.error(f"  ❌ NLP extractor failed: {e}")
        
        # Test AI Extractor
        logger.info("🤖 TESTING AI EXTRACTOR:")
        try:
            ai_extractor = AIExtractor(nebius_ai_service)
            ai_result = await ai_extractor.extract(text_content)
            
            logger.info(f"  Personal Info: {ai_result.get('personal_info', 'Not found')}")
            logger.info(f"  Experience: {len(ai_result.get('experience', []))} entries")
            logger.info(f"  Education: {len(ai_result.get('education', []))} entries")
            logger.info(f"  Skills: {len(ai_result.get('skills', []))} skills")
            
        except Exception as e:
            logger.error(f"  ❌ AI extractor failed: {e}")
        
        logger.info("=" * 80)
        logger.info("TESTING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Log file saved to: {log_filename}")
        
    except Exception as e:
        logger.error(f"Error during parsing: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_resume_parsing()) 