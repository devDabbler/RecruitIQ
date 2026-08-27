#!/usr/bin/env python3
"""
Debug script to test personal info extraction specifically
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor

async def debug_personal_info():
    """Debug personal info extraction"""
    
    # Sample text from the resume (based on the debug output)
    sample_text = """425-098-5467 - clint.forest@email.com
- www.linkedin.com/profile4
453 Jones Blvd Bothell, WA
Results-driven data analyst and machine learning practitioner with a strong
academic foundation and hands-on experience in both industry and research
settings."""
    
    # Create regex extractor
    extractor = RegexExtractor()
    
    # Test personal info extraction
    sections = {'full_text': sample_text}
    
    print("Testing personal info extraction...")
    print("Sample text:")
    print(sample_text)
    print("\n" + "="*50)
    
    try:
        personal_info = await extractor._extract_personal_info(sections)
        print("Extracted personal info:")
        print(f"Name: '{personal_info.name}'")
        print(f"Email: '{personal_info.email}'")
        print(f"Phone: '{personal_info.phone}'")
        print(f"Location: '{personal_info.location}'")
        print(f"LinkedIn: '{personal_info.linkedin}'")
        print(f"Website: '{personal_info.website}'")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_personal_info()) 