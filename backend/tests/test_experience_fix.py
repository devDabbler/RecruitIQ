#!/usr/bin/env python3
"""
Simple test to verify experience extraction fix
"""

import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_experience_patterns():
    """Test that the experience patterns match the user's resume format"""
    print("=== Testing Experience Pattern Fix ===")
    
    # Sample resume text in the user's format
    sample_resume_text = """
## Work Experience

### Summer Associate - Data Analyst (May 2023 - August 2023)
### Credit Union - Alexandria, VA
Collaborated with the Lending Analytics team to develop Tableau dashboards, analyzing
Consumer Lending and Credit Card Portfolio models for NFCU's Capital Plan stress testing.

### Data Analyst (July 2020 - August 2022)
### Cognizant - Chennai, India
Implemented supervised machine learning in Python to create a price optimization tool for
Consumer Products Goods (C.P.G.) during promotional periods.
"""
    
    import re
    
    # Test the patterns that should match
    patterns = [
        # Pattern 1: ### Job Title - Company (Date Range) - YOUR RESUME FORMAT
        r'(?:^|\n)\s*###\s*([^-]+?)\s*[-–—]\s*([^(]+?)\s*\(([^)]+)\)',
        # Pattern 2: ### Job Title (Date Range)
        r'(?:^|\n)\s*###\s*([^(]+?)\s*\(([^)]+)\)',
        # Pattern 3: ### Company - Location (for company line)
        r'(?:^|\n)\s*###\s*([^-]+?)\s*[-–—]\s*([^-]+?)(?:\s*$|\n)',
    ]
    
    print("Testing patterns against sample resume text...")
    
    for i, pattern in enumerate(patterns, 1):
        matches = list(re.finditer(pattern, sample_resume_text, re.MULTILINE | re.DOTALL))
        print(f"Pattern {i}: Found {len(matches)} matches")
        for j, match in enumerate(matches):
            groups = match.groups()
            print(f"  Match {j+1}: {groups}")
    
    print("✅ Experience pattern test completed")
    return True

if __name__ == "__main__":
    test_experience_patterns() 