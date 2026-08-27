#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to directly call StructuredExtractor on a resume."""

import os
import sys
import asyncio
import json
import logging
from typing import Dict, Any

from PyPDF2 import PdfReader

from backend.utils.resume_parsing.extractors.structured_extractor import StructuredExtractor
from backend.services.nebius_ai_service import get_nebius_ai_service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

async def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        text = ""
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""

async def main():
    """Test the StructuredExtractor directly."""
    if len(sys.argv) != 2:
        logger.error("Usage: python test_structured_extraction.py <path_to_resume_file>")
        sys.exit(1)
    
    resume_path = sys.argv[1]
    if not os.path.exists(resume_path):
        logger.error(f"Resume file not found: {resume_path}")
        sys.exit(1)
        
    logger.info(f"Testing StructuredExtractor on: {resume_path}")
    
    try:
        # Extract text from PDF
        text = await extract_text_from_pdf(resume_path)
        if not text or len(text) < 100:
            logger.error(f"Failed to extract sufficient text from PDF: {len(text) if text else 0} characters")
            sys.exit(1)
            
        logger.info(f"Successfully extracted {len(text)} characters from {resume_path}")
        
        # Initialize the StructuredExtractor
        try:
            nebius_service = get_nebius_ai_service()
            structured_extractor = StructuredExtractor(nebius_service)
            logger.info("Successfully initialized StructuredExtractor with Nebius AI service")
        except Exception as e:
            logger.error(f"Failed to initialize StructuredExtractor: {e}")
            sys.exit(1)
        
        # Call the extractor
        logger.info("Calling StructuredExtractor.extract()...")
        result = await structured_extractor.extract(text, resume_path)
        
        # Log the raw result
        logger.info("Raw extraction result:")
        logger.info(json.dumps(result, indent=2))
        
        # Specifically check the education data
        education_data = result.get("education", [])
        if education_data:
            logger.info(f"Found {len(education_data)} education entries:")
            for idx, edu in enumerate(education_data, 1):
                logger.info(f"Education #{idx}:")
                for key, value in edu.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("No education data was found in the extracted result")
            
    except Exception as e:
        logger.error(f"Error during extraction: {e}", exc_info=True)
        sys.exit(1)
        
    logger.info("Test completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
