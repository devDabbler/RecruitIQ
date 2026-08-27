#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple test for NebiusAIParser education degree extraction."""

import os
import sys
import json
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Test NebiusAIParser education extraction."""
    from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser
    from PyPDF2 import PdfReader
    
    if len(sys.argv) != 2:
        logger.error("Usage: python test_nebius_parser_education.py <path_to_resume_file>")
        sys.exit(1)
    
    resume_path = sys.argv[1]
    if not os.path.exists(resume_path):
        logger.error(f"Resume file not found: {resume_path}")
        sys.exit(1)
    
    logger.info(f"Testing NebiusAIParser education extraction on: {resume_path}")
    
    try:
        # Extract text from PDF
        text = ""
        with open(resume_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        if not text or len(text) < 100:
            logger.error(f"Failed to extract sufficient text from PDF: {len(text) if text else 0} characters")
            sys.exit(1)
            
        logger.info(f"Successfully extracted {len(text)} characters from {resume_path}")
        
        # Initialize parser
        parser = NebiusAIParser()
        
        # Parse resume
        logger.info("Parsing resume with NebiusAIParser...")
        result = await parser.parse_resume(text, resume_path)
        
        # Check for education entries
        education_data = result.get("education", [])
        if education_data:
            logger.info(f"Found {len(education_data)} education entries:")
            for idx, edu in enumerate(education_data, 1):
                logger.info(f"Education #{idx}:")
                for key, value in sorted(edu.items()):
                    logger.info(f"  {key}: {value}")
                
                # Specifically check for degree field
                if "degree" in edu:
                    logger.info(f"  ✓ DEGREE FOUND: {edu['degree']}")
                else:
                    logger.error(f"  ✗ NO DEGREE FOUND in education entry #{idx}")
            
            # Show raw JSON to frontend
            logger.info("\nEducation data that would be sent to frontend:")
            logger.info(json.dumps(education_data, indent=2))
        else:
            logger.error("No education data found in parsing result!")
            
        logger.info("\nComplete parsing result structure:")
        logger.info(", ".join(result.keys()))
        
    except Exception as e:
        logger.error(f"Error testing parser: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
