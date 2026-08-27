#!/usr/bin/env python3
"""
Debug script to test the enhanced resume parser directly
"""

import logging
import sys
import os

# Add the backend directory to Python path
sys.path.append('backend')

from utils.enhanced_resume_parser import EnhancedResumeParser

# Set up logging to see debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def debug_resume_parsing():
    """Debug the resume parsing process"""
    
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_file):
        print(f"❌ Resume file '{resume_file}' not found")
        return False
    
    try:
        # Initialize the enhanced parser
        parser = EnhancedResumeParser()
        
        print("=== Starting Enhanced Resume Parser Debug ===")
        
        # Parse the resume
        resume_data = parser.parse_resume(resume_file)
        
        print("\n=== Parsing Results ===")
        print(f"Name: {resume_data.personal_info.name}")
        print(f"Email: {resume_data.personal_info.email}")
        print(f"Phone: {resume_data.personal_info.phone}")
        print(f"Location: {resume_data.personal_info.location}")
        print(f"LinkedIn: {resume_data.personal_info.linkedin}")
        print(f"Experience entries: {len(resume_data.experience)}")
        print(f"Skills: {len(resume_data.skills)}")
        print(f"Summary length: {len(resume_data.summary)}")
        
        # Show experience details
        if resume_data.experience:
            print("\n=== Experience Details ===")
            for i, exp in enumerate(resume_data.experience, 1):
                print(f"Job {i}:")
                print(f"  Title: {exp.title}")
                print(f"  Company: {exp.company}")
                print(f"  Location: {exp.location}")
                print(f"  Start Date: {exp.start_date}")
                print(f"  End Date: {exp.end_date}")
                print(f"  Description length: {len(exp.description)}")
        else:
            print("\n❌ No experience entries found")
        
        # Show summary
        if resume_data.summary:
            print(f"\n=== Summary ===")
            print(f"{resume_data.summary[:300]}...")
        else:
            print("\n❌ No summary found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_resume_parsing()
    exit(0 if success else 1) 