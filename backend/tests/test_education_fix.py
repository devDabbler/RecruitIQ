#!/usr/bin/env python3
"""
Test script to verify education extraction fix
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor

async def test_education_extraction_fix():
    """Test the education extraction fix"""
    print("=" * 80)
    print("TESTING EDUCATION EXTRACTION FIX")
    print("=" * 80)
    
    extractor = RegexExtractor()
    
    # Test case: The specific education section from the resume
    test_text = """
## Education

### University of Montana - Helena, MT (April 2014 - May 2021)
Ph. D. in Physics
"""
    
    print("Testing education extraction with University of Montana case:")
    print(f"Input text: {test_text}")
    
    # Extract education
    education_entries = await extractor._extract_education(test_text)
    
    print(f"\nExtracted {len(education_entries)} education entries:")
    for i, edu in enumerate(education_entries, 1):
        print(f"  {i}. Institution: {edu.institution}")
        print(f"     Degree: {edu.degree}")
        print(f"     Field: {edu.field_of_study}")
        print(f"     Location: {edu.location}")
        print(f"     Dates: {edu.start_date} to {edu.end_date}")
        print()
    
    # Check for issues
    issues = []
    
    # Check for duplicates
    institutions = [edu.institution.lower() for edu in education_entries]
    if len(institutions) != len(set(institutions)):
        issues.append("❌ DUPLICATE INSTITUTIONS FOUND")
    
    # Check for proper degree extraction
    for edu in education_entries:
        if edu.institution.lower() == "university of montana":
            if not edu.degree or edu.degree.lower() != "ph. d. in physics":
                issues.append(f"❌ INCORRECT DEGREE: '{edu.degree}' instead of 'Ph. D. in Physics'")
            if not edu.location or "helena" not in edu.location.lower():
                issues.append(f"❌ INCORRECT LOCATION: '{edu.location}' instead of 'Helena, MT'")
    
    # Check for proper date extraction
    for edu in education_entries:
        if edu.institution.lower() == "university of montana":
            if not edu.start_date or "april 2014" not in edu.start_date.lower():
                issues.append(f"❌ INCORRECT START DATE: '{edu.start_date}' instead of 'April 2014'")
            if not edu.end_date or "may 2021" not in edu.end_date.lower():
                issues.append(f"❌ INCORRECT END DATE: '{edu.end_date}' instead of 'May 2021'")
    
    if not issues:
        print("✅ ALL TESTS PASSED - Education extraction working correctly!")
    else:
        print("❌ ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    
    print("\n" + "=" * 80)
    print("EDUCATION EXTRACTION FIX TEST COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_education_extraction_fix()) 