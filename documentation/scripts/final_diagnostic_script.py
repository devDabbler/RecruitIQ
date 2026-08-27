#!/usr/bin/env python3
"""
Final diagnostic to see what sections are being detected and fix the issue
"""

import sys
import os
import re
from pathlib import Path

# Add the backend to the path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.utils.enhanced_resume_parser import EnhancedResumeParser

def final_diagnosis():
    """Diagnose exactly what's happening with section detection"""
    
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_file):
        print(f"❌ Resume file '{resume_file}' not found!")
        return
    
    print("🔍 FINAL DIAGNOSIS - SECTION DETECTION")
    print("=" * 50)
    
    # Initialize parser
    parser = EnhancedResumeParser()
    
    # Extract and process text
    text = parser._extract_text_from_file(resume_file)
    cleaned_text = parser._preprocess_text(text)
    
    # Test section detection
    sections = parser._split_into_sections(cleaned_text)
    
    print(f"✓ Found {len(sections)} sections: {list(sections.keys())}")
    
    # Show all section content
    for section_name, content in sections.items():
        print(f"\n{'='*20} {section_name.upper()} SECTION ({'='*20}")
        print(f"Length: {len(content)} characters")
        print("Content:")
        print(content)
        print(f"{'='*60}")
    
    # Test experience extraction
    print(f"\n🧪 TESTING EXPERIENCE EXTRACTION")
    print("-" * 40)
    
    try:
        experiences = parser._extract_experience(sections)
        print(f"✓ Extracted {len(experiences)} experience entries:")
        
        for i, exp in enumerate(experiences):
            print(f"\n  {i+1}. Title: '{exp.title}'")
            print(f"     Company: '{exp.company}'")
            print(f"     Location: '{exp.location}'")
            print(f"     Start: '{exp.start_date}'")
            print(f"     End: '{exp.end_date}'")
            print(f"     Description preview: {exp.description[:100]}...")
    
    except Exception as e:
        print(f"❌ Experience extraction failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Manual check for the work experience section
    print(f"\n🔍 MANUAL WORK EXPERIENCE SEARCH")
    print("-" * 40)
    
    # Look for "WORK EXPERIENCE" in the text
    work_exp_pattern = r'WORK\s+EXPERIENCE.*?(?=(?:[A-Z]{2,}\s*[A-Z]{2,}|$))'
    work_match = re.search(work_exp_pattern, cleaned_text, re.DOTALL | re.IGNORECASE)
    
    if work_match:
        work_content = work_match.group(0)
        print(f"✅ Found WORK EXPERIENCE section manually ({len(work_content)} chars):")
        print("-" * 40)
        print(work_content[:1000])  # Show first 1000 chars
        print("..." if len(work_content) > 1000 else "")
        
        # Test pipe format detection on this content
        print(f"\n🔧 TESTING PIPE FORMAT ON MANUAL SECTION:")
        company_location_pattern = r'([A-Z][A-Za-z.-]+(?:\s+[A-Za-z.-]+)*)\s*\|\s*([A-Z][A-Za-z\s,.-]+)'
        pipe_matches = list(re.finditer(company_location_pattern, work_content, re.IGNORECASE))
        
        print(f"Found {len(pipe_matches)} company|location matches:")
        for i, match in enumerate(pipe_matches):
            company = match.group(1).strip()
            location = match.group(2).strip()
            print(f"  {i+1}. '{company}' | '{location}'")
            
            # Look for title before this match
            title_search = work_content[max(0, match.start()-200):match.start()]
            title_lines = [line.strip() for line in title_search.split('\n') if line.strip()]
            
            print(f"     Potential titles from context:")
            for line in title_lines[-3:]:  # Last 3 lines before match
                if len(line) > 10 and not any(skip in line.lower() for skip in ['experience', 'work', 'skills']):
                    print(f"       - '{line}'")
    
    else:
        print("❌ Could not find WORK EXPERIENCE section manually")
        
        # Try a broader search
        print(f"\n🔍 BROADER SEARCH FOR WORK CONTENT:")
        
        # Look for company names
        for company in ['Fractal', 'Neal Analytics']:
            company_matches = list(re.finditer(re.escape(company), cleaned_text, re.IGNORECASE))
            print(f"\n'{company}' found {len(company_matches)} times:")
            
            for match in company_matches:
                start = max(0, match.start() - 100)
                end = min(len(cleaned_text), match.end() + 100)
                context = cleaned_text[start:end]
                print(f"  Context: ...{context}...")

if __name__ == "__main__":
    final_diagnosis()