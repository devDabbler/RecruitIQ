#!/usr/bin/env python3
"""
Comprehensive test script to verify all education extraction fixes
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor

async def test_comprehensive_education_fix():
    """Test all education extraction fixes"""
    print("=" * 80)
    print("COMPREHENSIVE EDUCATION EXTRACTION FIX TEST")
    print("=" * 80)
    
    extractor = RegexExtractor()
    
    # Test case: The specific education section from the resume
    test_text = """
## Education

### University of Montana - Helena, MT (April 2014 - May 2021)
Ph. D. in Physics

## Work Experience
Lead Product Data Scientist at Paypal - Palo Alto, CA (July 2023 - Present)
"""
    
    print("Testing education extraction with University of Montana case:")
    print(f"Input text:\n{test_text}")
    
    # Extract education
    education_entries = await extractor._extract_education(test_text)
    
    print(f"\nExtracted {len(education_entries)} education entries:")
    
    # Check for issues
    issues_found = []
    
    if len(education_entries) > 1:
        issues_found.append(f"❌ TOO MANY ENTRIES: Found {len(education_entries)} entries, expected 1")
    
    if len(education_entries) == 0:
        issues_found.append("❌ NO ENTRIES: No education entries extracted")
    
    for i, entry in enumerate(education_entries, 1):
        print(f"  {i}. Institution: {entry.institution}")
        print(f"     Degree: {entry.degree}")
        print(f"     Field: {entry.field_of_study}")
        print(f"     Location: {entry.location}")
        print(f"     Dates: {entry.start_date} to {entry.end_date}")
        print()
        
        # Check for specific issues
        if entry.degree == "Ma":
            issues_found.append(f"❌ INCORRECT DEGREE: 'Ma' instead of 'Ph.D. in Physics'")
        
        if not entry.degree or entry.degree == "":
            issues_found.append(f"❌ MISSING DEGREE: Empty degree field")
        
        if entry.degree != "Ph.D. in Physics" and "Ph.D." in entry.degree:
            issues_found.append(f"❌ INCOMPLETE DEGREE: '{entry.degree}' instead of 'Ph.D. in Physics'")
        
        if entry.location != "Helena, MT":
            issues_found.append(f"❌ INCORRECT LOCATION: '{entry.location}' instead of 'Helena, MT'")
        
        if entry.institution != "University of Montana":
            issues_found.append(f"❌ INCORRECT INSTITUTION: '{entry.institution}' instead of 'University of Montana'")
    
    # Check for duplicates
    institutions = [entry.institution for entry in education_entries]
    if len(institutions) != len(set(institutions)):
        issues_found.append("❌ DUPLICATE INSTITUTIONS FOUND")
    
    # Summary
    print("=" * 80)
    if issues_found:
        print("❌ ISSUES FOUND:")
        for issue in issues_found:
            print(f"  {issue}")
    else:
        print("✅ ALL TESTS PASSED - Education extraction working correctly!")
    
    print("=" * 80)
    print("COMPREHENSIVE EDUCATION EXTRACTION FIX TEST COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_comprehensive_education_fix()) 