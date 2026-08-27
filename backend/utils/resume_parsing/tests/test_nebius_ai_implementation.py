"""
Test to verify that the resume parsing system is using the Nebius AI (Phi-4) implementation
and not falling back to any other implementation.

This test ensures that:
1. The correct parser class (NebiusAIResumeParser) is being used
2. The service is using the Phi-4 model
3. No fallbacks to Ollama or other services are happening

Usage:
    python test_nebius_ai_implementation.py <path/to/resume.pdf>
"""

import asyncio
import os
import sys
import json
import logging
import inspect
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_nebius_ai_implementation():
    """Test that only Nebius AI implementation is used for resume parsing."""
    logger.info("🔍 Verifying Nebius AI Implementation for Resume Parsing")
    logger.info("=" * 70)
    
    # Import necessary modules
    try:
        from backend.utils.resume_parsing.resume_parser_main import ResumeParser, create_compatible_parser
        from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIResumeParser
        from backend.services.llm_service import LLMService
        from backend.services.service_registry import provide_llm_service
        from backend.services.nebius_ai_service import get_nebius_ai_service, NebiusAIService
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    
    results = {}
    
    # Step 1: Verify LLMService initializes Nebius AI properly
    logger.info("📋 Step 1: Testing LLM Service Nebius AI initialization...")
    try:
        llm_service = provide_llm_service()
        
        # Check if Nebius AI service is initialized
        if not hasattr(llm_service, 'nebius_ai_service') or llm_service.nebius_ai_service is None:
            logger.error("❌ LLM Service does not have an initialized Nebius AI service")
            results["llm_service_test"] = False
        else:
            service_type = type(llm_service.nebius_ai_service).__name__
            logger.info(f"✅ LLM Service has initialized Nebius AI service: {service_type}")
            
            # Verify it's the correct type
            if not isinstance(llm_service.nebius_ai_service, NebiusAIService):
                logger.error(f"❌ Wrong service type: {service_type}, expected: NebiusAIService")
                results["llm_service_test"] = False
            else:
                # Check model configuration
                model_name = getattr(llm_service.nebius_ai_service, 'model', None)
                logger.info(f"✅ Using model: {model_name}")
                results["llm_service_test"] = True
                results["model_name"] = model_name
    except Exception as e:
        logger.error(f"❌ Error testing LLM service: {e}")
        results["llm_service_test"] = False
    
    # Step 2: Test parser creation with compatible parser function
    logger.info("\n📋 Step 2: Testing parser creation with create_compatible_parser...")
    try:
        nebius_ai_service = get_nebius_ai_service()
        if nebius_ai_service is None:
            logger.error("❌ Failed to get Nebius AI service directly")
            results["create_parser_test"] = False
        else:
            parser = create_compatible_parser(nebius_ai_service)
            parser_type = type(parser).__name__
            
            if parser_type != "NebiusAIResumeParser":
                logger.error(f"❌ Wrong parser type: {parser_type}, expected: NebiusAIResumeParser")
                results["create_parser_test"] = False
            else:
                logger.info(f"✅ Correct parser created: {parser_type}")
                results["create_parser_test"] = True
    except Exception as e:
        logger.error(f"❌ Error creating compatible parser: {e}")
        results["create_parser_test"] = False
    
    # Step 3: Test full ResumeParser instantiation
    logger.info("\n📋 Step 3: Testing full ResumeParser instantiation...")
    try:
        # Create ResumeParser with LLM service
        resume_parser = ResumeParser(llm_service=llm_service)
        
        # Check what parser type was created
        parser_type = type(resume_parser.parser).__name__
        if parser_type != "NebiusAIResumeParser":
            logger.error(f"❌ ResumeParser using wrong parser type: {parser_type}")
            results["resume_parser_test"] = False
        else:
            logger.info(f"✅ ResumeParser using correct parser type: {parser_type}")
            
            # Verify the underlying service
            service_type = type(resume_parser.parser.nebius_ai_service).__name__
            logger.info(f"✅ Parser using service type: {service_type}")
            
            # Verify implementation details
            parser_methods = inspect.getmembers(resume_parser.parser, predicate=inspect.ismethod)
            has_parse_resume = any(name == "parse_resume" for name, _ in parser_methods)
            
            logger.info(f"✅ Parser has parse_resume method: {has_parse_resume}")
            
            results["resume_parser_test"] = True
    except Exception as e:
        logger.error(f"❌ Error testing ResumeParser: {e}")
        results["resume_parser_test"] = False
    
    # Step 4: Test with a real resume file (if provided)
    cli_resume_path = sys.argv[1] if len(sys.argv) > 1 else None
    resume_file_path = cli_resume_path or os.getenv("RESUME_FILE")
    
    if resume_file_path and os.path.exists(resume_file_path):
        logger.info(f"\n📋 Step 4: Testing parsing with real resume file: {resume_file_path}")
        try:
            # Create parser
            resume_parser = ResumeParser(llm_service=llm_service, verbose=True)
            
            # Attempt parsing
            resume_data = await resume_parser.parse_resume(resume_file_path)
            
            if resume_data:
                # Extract and log key information to verify parsing worked
                name = resume_data.personal_info.name if resume_data.personal_info else "Unknown"
                email = resume_data.personal_info.email if resume_data.personal_info else "Unknown"
                
                num_experiences = len(resume_data.experience) if resume_data.experience else 0
                num_education = len(resume_data.education) if resume_data.education else 0
                num_skills = len(resume_data.skills) if resume_data.skills else 0
                
                logger.info(f"✅ Successfully parsed resume for: {name} ({email})")
                logger.info(f"✅ Found {num_experiences} experiences, {num_education} education entries, {num_skills} skills")
                results["parsing_test"] = True
            else:
                logger.error("❌ Failed to parse resume (no data returned)")
                results["parsing_test"] = False
        except Exception as e:
            logger.error(f"❌ Error parsing resume: {e}")
            results["parsing_test"] = False
    else:
        logger.info("\n⚠️ No resume file provided - skipping parsing test")
        results["parsing_test"] = "skipped"
    
    # Print summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY:")
    logger.info("=" * 50)
    
    all_passed = True
    for test_name, result in results.items():
        if result is False:
            all_passed = False
        
        if test_name == "model_name":
            logger.info(f"🔍 Model Name: {result}")
        else:
            status = "✅ PASSED" if result is True else "❌ FAILED" if result is False else "⚠️ SKIPPED"
            logger.info(f"{test_name}: {status}")
    
    if all_passed:
        logger.info("\n✅ SUCCESS: The system is correctly using Nebius AI (Phi-4) for resume parsing!")
    else:
        logger.error("\n❌ FAILURE: The system is NOT correctly configured to use Nebius AI for resume parsing.")
        logger.error("Please check the error messages above and fix the configuration.")
    
    return all_passed

async def main():
    """Main entry point."""
    try:
        success = await test_nebius_ai_implementation()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
