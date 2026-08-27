#!/usr/bin/env python3
"""
Debug script to examine the actual resume content and see what sections look like
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing import create_resume_parser
from services.storage_service import StorageService
from services.nebius_ai_service import NebiusAIService

async def debug_resume_content():
    """Debug resume content extraction"""
    
    # Initialize services
    storage_service = StorageService()
    nebius_ai_service = NebiusAIService()
    
    # Create resume parser
    parser = create_resume_parser(storage_service, nebius_ai_service)
    
    # Path to the test resume
    resume_path = "../Clint_Forest_Resume.pdf"
    
    if not os.path.exists(resume_path):
        print(f"Error: Resume file not found at {resume_path}")
        return
    
    print(f"Examining resume content from: {resume_path}")
    print("=" * 60)
    
    try:
        # Get the raw text first
        text = await parser._process_document(resume_path)
        
        print("RAW RESUME TEXT:")
        print("=" * 60)
        print(text)
        print("\n" + "=" * 60)
        
        # Now let's see what sections are identified
        from utils.resume_parsing.processors.section_processor import SectionProcessor
        section_processor = SectionProcessor()
        sections = await section_processor.process(text)
        
        print("IDENTIFIED SECTIONS:")
        print("=" * 60)
        for section_name, section_content in sections.items():
            print(f"\n--- {section_name.upper()} ---")
            print(section_content[:500] + "..." if len(section_content) > 500 else section_content)
            print("-" * 40)
        
        # Let's also test the regex extractor directly on the experience section
        if 'experience' in sections:
            print("\nTESTING REGEX EXTRACTOR ON EXPERIENCE SECTION:")
            print("=" * 60)
            from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
            regex_extractor = RegexExtractor()
            
            # Test experience extraction directly
            experience_entries = await regex_extractor._extract_experience(sections['experience'])
            print(f"Found {len(experience_entries)} experience entries:")
            for i, exp in enumerate(experience_entries, 1):
                print(f"\nEntry {i}:")
                print(f"  Title: {exp.title}")
                print(f"  Company: {exp.company}")
                print(f"  Location: {exp.location}")
                print(f"  Start Date: {exp.start_date}")
                print(f"  End Date: {exp.end_date}")
                print(f"  Description: {exp.description[:200]}...")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_resume_content()) 