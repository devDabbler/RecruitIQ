"""
Enhanced resume extraction with robust JSON handling.

This module provides improved JSON extraction for resume parsing,
fixing the issues with the local model integration.
"""
import logging
import json
import re
import asyncio
import traceback
from typing import Dict, List, Any, Optional

from backend.models.resume import Experience, Education, Skill, PersonalInfo
from backend.services.local_model_service import get_local_model_service
from backend.patches.robust_json_extractor import extract_json_robustly, extract_structured_data, clean_and_standardize_entries

# Configure logging
logger = logging.getLogger(__name__)

async def extract_with_model(model_service, prompt, entry_type="experience", model_name='resume-parser-code'):
    """
    Extract structured data with robust JSON handling.
    """
    enhanced_prompt = f"""{prompt}
    
IMPORTANT: Format your response ONLY as valid JSON. No explanatory text or code blocks.
Example: [{{"title": "Software Engineer", "company": "Acme Inc."}}]"""

    try:
        # Get response from Ollama with timeout
        try:
            response_task = model_service._generate_response(
                model_name,
                enhanced_prompt,
                temperature=0.1,
                max_tokens=2000
            )
            response_text = await asyncio.wait_for(response_task, timeout=15.0)
            logger.info("Successfully received response from model")
        except asyncio.TimeoutError:
            logger.error("Model API call timed out")
            return [{"title": "Parsing Timeout", "company": "Unknown", "description": "Model timed out"}]
        
        # Process with robust extraction
        try:
            entries = extract_structured_data(response_text, entry_type)
            standardized = clean_and_standardize_entries(entries, entry_type)
            logger.info(f"Successfully extracted {len(standardized)} {entry_type} entries")
            return standardized
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return [{"title": "Processing Error", "company": "Unknown", "description": str(e)}]
    
    except Exception as e:
        logger.error(f"Model extraction error: {str(e)}")
        return [{"title": "Error", "company": "Unknown", "description": str(e)}]

def run_sync(async_func, *args, timeout=15, **kwargs):
    """Run async function synchronously with timeout."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(async_func(*args, **kwargs))
        return loop.run_until_complete(asyncio.wait_for(task, timeout=timeout))
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Error in async operation: {str(e)}")
        return None
    finally:
        loop.close()

def parse_resume_with_robust_extraction(parser, file_path):
    """
    Parse resume with robust JSON extraction.
    
    This function replaces ResumeParser.parse to use improved JSON handling.
    """
    try:
        # Get text from file (use existing method)
        if file_path.lower().endswith('.pdf'):
            parser._extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            parser._extract_text_from_docx(file_path)
        else:
            logger.error(f"Unsupported file type: {file_path}")
            return None
            
        if not parser.text:
            logger.error("Failed to extract text from resume")
            return None
            
        # Create NLP doc
        parser.doc = parser.nlp(parser.text)
        
        # Extract personal info (use existing method)
        personal_info = parser._extract_personal_info()
        
        # Extract experience with robust handling
        model_service = get_local_model_service()
        
        # Experience extraction
        experience_prompt = f"""Extract ALL work experience from this resume:
{parser.text[:5000]}"""
        
        experience_entries = run_sync(
            extract_with_model,
            model_service, 
            experience_prompt,
            "experience",
            timeout=15
        )
        
        if not experience_entries or len(experience_entries) == 0:
            logger.warning("Robust experience extraction failed, using fallback")
            experience_entries = [{"title": "Experience parsing failed", "company": "Unknown", "description": ""}]
        
        # Education extraction
        education_prompt = f"""Extract ALL education entries from this resume:
{parser.text[:5000]}"""
        
        education_entries = run_sync(
            extract_with_model,
            model_service,
            education_prompt,
            "education",
            timeout=15
        )
        
        if not education_entries or len(education_entries) == 0:
            logger.warning("Robust education extraction failed, using fallback")
            education_entries = [{"degree": "", "institution": "", "description": ""}]
        
        # Skills extraction
        skills_prompt = f"""Extract ALL technical and professional skills from this resume as a JSON array:
{parser.text[:5000]}"""
        
        skills_result = run_sync(
            extract_with_model,
            model_service,
            skills_prompt,
            "skills",
            timeout=10
        )
        
        skills_list = []
        if skills_result and isinstance(skills_result, list):
            for item in skills_result:
                if isinstance(item, dict) and "name" in item:
                    skill_name = item["name"]
                    if isinstance(skill_name, str) and skill_name.strip():
                        skills_list.append(skill_name.strip().lower())
        
        if not skills_list:
            logger.warning("Robust skills extraction failed, using fallback")
            # Extract some common skills as fallback
            common_skills = ["python", "java", "javascript", "sql", "ai", "data analysis"]
            text_lower = parser.text.lower()
            skills_list = [skill for skill in common_skills if skill in text_lower]
            
        # Convert to model objects
        experience_objs = [Experience(**exp) for exp in experience_entries]
        education_objs = [Education(**edu) for edu in education_entries]
        skill_objs = [Skill(name=skill, category="technical") for skill in skills_list]
        
        # Create and return ResumeData object
        from backend.models.resume import ResumeData
        resume_data = ResumeData(
            personal_info=personal_info,
            experience=experience_objs,
            education=education_objs,
            skills=skill_objs,
            summary=None
        )
        
        return resume_data
        
    except Exception as e:
        logger.error(f"Error in robust resume parsing: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def apply_robust_extraction_patch():
    return # Effectively disable this patch
    """
    Apply the robust extraction patch to the resume parser.
    """
    logger.info("Applying robust JSON extraction patch to resume parser")
    
    # Store original parse method
    # original_parse = ResumeParser.parse
    
    # Replace with robust version
    # ResumeParser.parse = parse_resume_with_robust_extraction
    
    logger.info("Successfully applied robust extraction patch")

# Apply the patch
apply_robust_extraction_patch()
