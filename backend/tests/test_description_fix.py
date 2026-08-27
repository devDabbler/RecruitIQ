#!/usr/bin/env python3
"""
Test description cleaning fix
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_description_cleaning():
    """Test that description cleaning is working"""
    print("=== Testing Description Cleaning ===")
    
    # Sample resume text with bullet points
    sample_resume_text = """### Clint Forest
425-098-5467 - clint.forest@email.com
- www.linkedin.com/profile4
453 Jones Blvd Bothell, WA

## Work Experience

### Summer Associate - Data Analyst (May 2023 - August 2023)
### Credit Union - Alexandria, VA
• Collaborated with the Lending Analytics team to develop Tableau dashboards, analyzing
Consumer Lending and Credit Card Portfolio models for NFCU's Capital Plan stress testing.
• Delivered data-driven insights influencing over 50% of revenue from loan originations,
facilitating informed decision-making by NFCU management.

### Data Analyst (July 2020 - August 2022)
### Cognizant - Chennai, India
• Implemented supervised machine learning in Python to create a price optimization tool for
Consumer Products Goods (C.P.G.) during promotional periods.
• Applied statistical models, including linear mixed effects regression and Bayesian hierarchical
modeling on Azure, leading to a 1% sales increase in the pet care segment.
"""
    
    try:
        from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
        
        extractor = RegexExtractor()
        sections = {'full_text': sample_resume_text}
        
        print("Testing description cleaning...")
        result = await extractor.extract(sections)
        
        experiences = result.get('experience', [])
        print(f"Found {len(experiences)} experiences")
        
        for i, exp in enumerate(experiences):
            print(f"\nExperience {i+1}:")
            print(f"  Title: {exp.title if hasattr(exp, 'title') else 'N/A'}")
            print(f"  Company: {exp.company if hasattr(exp, 'company') else 'N/A'}")
            print(f"  Description: {exp.description[:100] if hasattr(exp, 'description') and exp.description else 'N/A'}...")
            
            # Check for bullet points
            description = exp.description if hasattr(exp, 'description') else ''
            if '•' in description:
                print(f"  ❌ Still contains bullet points!")
                return False
            else:
                print(f"  ✅ No bullet points found!")
        
        print("\n✅ All descriptions cleaned successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_description_cleaning())
    if success:
        print("\n🎉 Description cleaning is working!")
    else:
        print("\n⚠️ Description cleaning needs more work") 