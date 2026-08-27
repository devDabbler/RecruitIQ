#!/usr/bin/env python3
"""
Simple verification test for description cleaning
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_simple_verification():
    """Simple test to verify description cleaning"""
    print("=== Simple Verification Test ===")
    
    # Simple test case
    sample_text = """### Summer Associate - Data Analyst (May 2023 - August 2023)
### Credit Union - Alexandria, VA
• Collaborated with the Lending Analytics team to develop Tableau dashboards, analyzing
Consumer Lending and Credit Card Portfolio models for NFCU's Capital Plan stress testing.
• Delivered data-driven insights influencing over 50% of revenue from loan originations,
facilitating informed decision-making by NFCU management."""
    
    try:
        from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
        
        extractor = RegexExtractor()
        sections = {'full_text': sample_text}
        
        print("Testing simple case...")
        result = await extractor.extract(sections)
        
        experiences = result.get('experience', [])
        if experiences:
            exp = experiences[0]
            description = exp.description if hasattr(exp, 'description') else ''
            print(f"Description: {description}")
            
            if '•' in description:
                print("❌ Still contains bullet points")
                return False
            else:
                print("✅ No bullet points found!")
                return True
        else:
            print("❌ No experiences found")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_verification())
    if success:
        print("\n🎉 Description cleaning is working!")
    else:
        print("\n⚠️ Description cleaning needs work") 