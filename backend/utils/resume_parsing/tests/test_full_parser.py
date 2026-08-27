#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script for the full resume parser with improved education extraction."""

import os
import sys
import logging
from utils.resume_parser import parse_resume

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test the full resume parser on a specific resume."""
    if len(sys.argv) != 2:
        logger.error("Usage: python test_full_parser.py <path_to_resume_file>")
        sys.exit(1)
    
    resume_path = sys.argv[1]
    if not os.path.exists(resume_path):
        logger.error(f"Resume file not found: {resume_path}")
        sys.exit(1)
        
    logger.info(f"Parsing resume: {resume_path}")
    
    try:
        # Parse the resume using the full parser
        parsed_data = parse_resume(resume_path)
        
        # Check if education was extracted
        education_data = parsed_data.get("education", [])
        
        if education_data:
            logger.info(f"Successfully extracted {len(education_data)} education entries:")
            for idx, edu in enumerate(education_data, 1):
                logger.info(f"Education #{idx}:")
                for key, value in edu.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("No education data was extracted from the resume")
            
        # Log all extracted data for debugging
        logger.info("Full parsed resume data:")
        for section, data in parsed_data.items():
            if section == "personal_info":
                logger.info(f"{section}:")
                for key, value in data.items():
                    if not key.startswith('_'):  # Skip internal fields
                        logger.info(f"  {key}: {value}")
            elif isinstance(data, list):
                logger.info(f"{section}: {len(data)} entries")
            else:
                logger.info(f"{section}: {data}")
                
    except Exception as e:
        logger.error(f"Error parsing resume: {e}", exc_info=True)
        sys.exit(1)
        
    logger.info("Resume parsing test completed successfully")

if __name__ == "__main__":
    main()
