#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Clear Redis cache for a specific resume and re-parse it to ensure fresh data.
"""

import sys
import os
import asyncio
import logging
import redis
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

async def clear_cache_and_reparse():
    """Clear Redis cache for resume data and re-parse the resume."""
    if len(sys.argv) < 2:
        logger.error("Usage: python clear_cache_and_reparse.py <path_to_resume_file>")
        sys.exit(1)
    
    resume_path = sys.argv[1]
    if not os.path.exists(resume_path):
        logger.error(f"Resume file not found: {resume_path}")
        sys.exit(1)
    
    # Initialize Redis connection
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()  # Check if Redis is running
        logger.info("Connected to Redis server")
    except redis.ConnectionError:
        logger.error("Could not connect to Redis server. Make sure Redis is running.")
        sys.exit(1)
    
    # Clear all keys related to resume parsing
    try:
        # Get all keys with resume parsing patterns
        resume_keys = []
        resume_keys.extend(r.keys("resume:parser:*"))
        resume_keys.extend(r.keys("resume:data:*"))
        resume_keys.extend(r.keys("resume:result:*"))
        resume_keys.extend(r.keys("streamlit:cache:*resume*"))
        
        if resume_keys:
            logger.info(f"Found {len(resume_keys)} resume-related cache keys")
            for key in resume_keys:
                r.delete(key)
            logger.info("Successfully cleared resume cache keys")
        else:
            logger.info("No resume-related cache keys found")
    except Exception as e:
        logger.error(f"Error clearing Redis cache: {e}")
    
    # Import required modules
    from backend.services.nebius_ai_service import get_nebius_ai_service
    from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser
    from PyPDF2 import PdfReader
    
    # Extract text from the resume
    text = ""
    with open(resume_path, 'rb') as f:
        pdf_reader = PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text()
    
    # Initialize parser
    parser = NebiusAIParser()
    
    # Parse resume
    logger.info(f"Re-parsing resume from {resume_path}...")
    result = await parser.parse_resume(text, resume_path)
    
    # Save parsed result to file for inspection
    output_path = Path(resume_path).stem + "_parsed.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved parsed result to {output_path}")
    
    # Check education data
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
        
        logger.info("\nVerify this data is correctly displayed in the frontend.")
        logger.info("Steps to check:")
        logger.info("1. Upload this same resume file in the web interface")
        logger.info("2. Check if the degree is displayed in the education section")
        logger.info("3. If not, there might be a frontend display issue")
    else:
        logger.error("No education data found in parsing result!")

if __name__ == "__main__":
    asyncio.run(clear_cache_and_reparse())
