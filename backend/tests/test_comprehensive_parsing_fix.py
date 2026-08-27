#!/usr/bin/env python3
"""
Comprehensive test for resume parsing fixes
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_comprehensive_parsing():
    """Test comprehensive resume parsing with all fixes"""
    print("=== Testing Comprehensive Resume Parsing Fixes ===")
    
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
        
        print("Testing regex extractor with fixes...")
        result = await extractor.extract(sections)
        
        print(f"Personal info extracted: {result.get('personal_info', {})}")
        print(f"Education entries: {len(result.get('education', []))}")
        print(f"Experience entries: {len(result.get('experience', []))}")
        print(f"Skills extracted: {len(result.get('skills', []))}")
        
        # Show experience details
        for i, exp in enumerate(result.get('experience', [])):
            print(f"\nExperience {i+1}:")
            print(f"  Title: {exp.title if hasattr(exp, 'title') else 'N/A'}")
            print(f"  Company: {exp.company if hasattr(exp, 'company') else 'N/A'}")
            print(f"  Location: {exp.location if hasattr(exp, 'location') else 'N/A'}")
            print(f"  Dates: {exp.start_date if hasattr(exp, 'start_date') else 'N/A'} to {exp.end_date if hasattr(exp, 'end_date') else 'N/A'}")
            print(f"  Description: {exp.description[:200] if hasattr(exp, 'description') and exp.description else 'N/A'}...")
        
        # Show skills details
        if result.get('skills'):
            print(f"\nSkills extracted ({len(result.get('skills', []))}):")
            for i, skill in enumerate(result.get('skills', [])[:10]):  # Show first 10
                print(f"  {i+1}. {skill.name if hasattr(skill, 'name') else 'N/A'} ({skill.category if hasattr(skill, 'category') else 'N/A'})")
        
        # Validation checks
        experience_count = len(result.get('experience', []))
        skills_count = len(result.get('skills', []))
        education_count = len(result.get('education', []))
        
        print(f"\n=== VALIDATION RESULTS ===")
        print(f"Experience entries: {experience_count} (Expected: 2)")
        print(f"Skills extracted: {skills_count} (Expected: >10)")
        print(f"Education entries: {education_count} (Expected: 2)")
        
        # Check specific issues
        issues_found = []
        
        if experience_count != 2:
            issues_found.append(f"Expected 2 experience entries, got {experience_count}")
        
        if skills_count < 10:
            issues_found.append(f"Expected >10 skills, got {skills_count}")
        
        if education_count != 2:
            issues_found.append(f"Expected 2 education entries, got {education_count}")
        
        # Check experience titles
        experiences = result.get('experience', [])
        if len(experiences) >= 1:
            first_title = experiences[0].title if hasattr(experiences[0], 'title') else ''
            if 'Summer Associate - Data Analyst' not in first_title:
                issues_found.append(f"First experience title should contain 'Summer Associate - Data Analyst', got: {first_title}")
        
        if len(experiences) >= 2:
            second_title = experiences[1].title if hasattr(experiences[1], 'title') else ''
            if 'Data Analyst' not in second_title:
                issues_found.append(f"Second experience title should contain 'Data Analyst', got: {second_title}")
        
        # Check description formatting
        for i, exp in enumerate(experiences):
            description = exp.description if hasattr(exp, 'description') else ''
            if description and description.startswith('•'):
                issues_found.append(f"Experience {i+1} description still has bullet points")
        
        if issues_found:
            print(f"\n❌ Issues found:")
            for issue in issues_found:
                print(f"  - {issue}")
            return False
        else:
            print(f"\n✅ All validation checks passed!")
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_comprehensive_parsing())
    if success:
        print("\n🎉 All parsing issues resolved successfully!")
    else:
        print("\n⚠️ Some parsing issues remain") 