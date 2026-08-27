#!/usr/bin/env python3
"""
Test the full resume parsing with experience extraction
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_full_parsing():
    """Test the full resume parsing with experience extraction"""
    print("=== Testing Full Resume Parsing ===")
    
    # Sample resume text in the user's format
    sample_resume_text = """### Clint Forest
425-098-5467 - clint.forest@email.com
- www.linkedin.com/profile4
453 Jones Blvd Bothell, WA

## Profile
Results-driven data analyst and machine learning practitioner with a strong
academic foundation and hands-on experience in both industry and research
settings.

## Work Experience

### Summer Associate - Data Analyst (May 2023 - August 2023)
### Credit Union - Alexandria, VA
Collaborated with the Lending Analytics team to develop Tableau dashboards, analyzing
Consumer Lending and Credit Card Portfolio models for NFCU's Capital Plan stress testing.
Delivered data-driven insights influencing over 50% of revenue from loan originations,
facilitating informed decision-making by NFCU management.

### Data Analyst (July 2020 - August 2022)
### Cognizant - Chennai, India
Implemented supervised machine learning in Python to create a price optimization tool for
Consumer Products Goods (C.P.G.) during promotional periods.
Applied statistical models, including linear mixed effects regression and Bayesian hierarchical
modeling on Azure, leading to a 1% sales increase in the pet care segment.

## Education
Georgia Technical Institute - Atlanta, GA (January 2016 - December 2023)
### Bachelor of Science, Computer Science

### Northwestern University - Boston, MA (January 2020 - January 2022)
### Masters of Science, Information Systems

## Skills
Python, SQL, T-SQL, PL/SQL, Java, C++, Talend Data Integration, XSV, Snowflake
Alteryx, Elasticsearch, Kibana, Trifacta, Tableau, Azure ML Studio, Hadoop
SSIS, PySpark, MS PowerBI, Salesforce Einstein Analytics, MS Office, Teradata,
Excel (Pivot and VLookup)
"""
    
    try:
        # Test the regex extractor directly
        from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
        
        extractor = RegexExtractor()
        sections = {'full_text': sample_resume_text}
        
        print("Testing regex extractor...")
        result = await extractor.extract(sections)
        
        print(f"Personal info extracted: {result.get('personal_info', {})}")
        print(f"Education entries: {len(result.get('education', []))}")
        print(f"Experience entries: {len(result.get('experience', []))}")
        print(f"Skills extracted: {len(result.get('skills', []))}")
        
        # Show experience details
        for i, exp in enumerate(result.get('experience', [])):
            print(f"Experience {i+1}:")
            print(f"  Title: {exp.title if hasattr(exp, 'title') else 'N/A'}")
            print(f"  Company: {exp.company if hasattr(exp, 'company') else 'N/A'}")
            print(f"  Location: {exp.location if hasattr(exp, 'location') else 'N/A'}")
            print(f"  Dates: {exp.start_date if hasattr(exp, 'start_date') else 'N/A'} to {exp.end_date if hasattr(exp, 'end_date') else 'N/A'}")
            print(f"  Description: {exp.description[:100] if hasattr(exp, 'description') and exp.description else 'N/A'}...")
            print()
        
        if len(result.get('experience', [])) > 0:
            print("✅ Experience extraction is working!")
        else:
            print("❌ No experience entries found")
            
        return len(result.get('experience', [])) > 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_full_parsing()) 