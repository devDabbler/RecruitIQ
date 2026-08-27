#!/usr/bin/env python3
"""
Final test script to verify all resume parsing fixes are working correctly
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.resume_parsing import create_resume_parser
from services.nebius_ai_service import NebiusAIService
from services.storage_service import StorageService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_final_resume_parsing():
    """Test the final resume parsing fixes with Jacob Smith's resume"""
    
    print("=" * 80)
    print("FINAL RESUME PARSING TEST - ALL FIXES VERIFICATION")
    print("=" * 80)
    
    # Initialize services
    storage_service = StorageService()
    nebius_service = NebiusAIService()
    
    # Create resume parser
    parser = create_resume_parser(
        storage_service=storage_service,
        nebius_ai_service=nebius_service
    )
    
    # Test with Jacob Smith's resume
    resume_path = "../Jacob_Smith_Resume.pdf"
    print(f"Testing with resume: {resume_path}")
    print("-" * 80)
    
    try:
        # Parse the resume
        result = await parser.parse(resume_path)
        
        print("FINAL PARSING RESULTS:")
        print("-" * 80)
        
        # Personal Information
        print("PERSONAL INFORMATION:")
        if result.personal_info:
            print(f"  Name: {result.personal_info.name}")
            print(f"  Email: {result.personal_info.email}")
            print(f"  Phone: {result.personal_info.phone}")
            print(f"  Location: {result.personal_info.location}")
            print(f"  LinkedIn: {result.personal_info.linkedin}")
        else:
            print("  ❌ No personal information extracted")
        
        print()
        
        # Education
        print("EDUCATION:")
        if result.education:
            for i, edu in enumerate(result.education, 1):
                print(f"  {i}. {edu.institution}")
                print(f"     Degree: {edu.degree}")
                print(f"     Field: {edu.field_of_study}")
                print(f"     Dates: {edu.start_date} - {edu.end_date}")
                print(f"     Location: {edu.location}")
        else:
            print("  ❌ No education extracted")
        
        print()
        
        # Work Experience
        print("WORK EXPERIENCE:")
        if result.experience:
            for i, exp in enumerate(result.experience, 1):
                print(f"  {i}. {exp.title}")
                print(f"     Company: {exp.company}")
                print(f"     Location: {exp.location}")
                print(f"     Dates: {exp.start_date} - {exp.end_date}")
                if exp.description:
                    desc_preview = exp.description[:100] + "..." if len(exp.description) > 100 else exp.description
                    print(f"     Description: {desc_preview}")
        else:
            print("  ❌ No experience extracted")
        
        print()
        
        # Skills
        print("SKILLS:")
        if result.skills:
            skill_names = [skill.name for skill in result.skills]
            print(f"  Found {len(skill_names)} skills:")
            print(f"  {', '.join(skill_names[:10])}{'...' if len(skill_names) > 10 else ''}")
            
            # Check for critical skills
            critical_skills = ['python', 'pytorch', 'sql', 'git', 'aws']
            found_critical = [skill for skill in skill_names if skill.lower() in critical_skills]
            if found_critical:
                print(f"  ✓ Found critical skills: {', '.join(found_critical)}")
            else:
                print("  ⚠️ Missing some critical skills")
        else:
            print("  ❌ No skills extracted")
        
        print()
        
        # Final Summary
        print("FINAL SUMMARY:")
        print("-" * 80)
        
        issues_found = []
        
        # Check personal info
        if result.personal_info and result.personal_info.name:
            print("  Personal Info: ✓")
        else:
            print("  Personal Info: ❌")
            issues_found.append("Missing personal information")
        
        # Check education
        if result.education and len(result.education) > 0:
            print("  Education: ✓")
            # Check for University of Montana
            um_found = any('montana' in edu.institution.lower() for edu in result.education)
            if um_found:
                print("  University of Montana: ✓")
            else:
                print("  University of Montana: ❌")
                issues_found.append("University of Montana not found")
        else:
            print("  Education: ❌")
            issues_found.append("No education extracted")
        
        # Check experience
        if result.experience and len(result.experience) > 0:
            print("  Experience: ✓")
            # Check for correct company names
            companies = [exp.company.lower() for exp in result.experience]
            if 'paypal' in companies:
                print("  Paypal: ✓")
            else:
                print("  Paypal: ❌")
                issues_found.append("Paypal not found")
            
            if 'udemy' in companies:
                print("  Udemy: ✓")
            else:
                print("  Udemy: ❌")
                issues_found.append("Udemy not found")
            
            if 'offer up' in companies or 'offerup' in companies:
                print("  Offer Up: ✓")
            else:
                print("  Offer Up: ❌")
                issues_found.append("Offer Up not found")
        else:
            print("  Experience: ❌")
            issues_found.append("No experience extracted")
        
        # Check skills
        if result.skills and len(result.skills) > 0:
            print("  Skills: ✓")
            skill_names = [skill.name.lower() for skill in result.skills]
            if 'pytorch' in skill_names:
                print("  pyTorch: ✓")
            else:
                print("  pyTorch: ❌")
                issues_found.append("pyTorch not found")
            
            if 'git' in skill_names:
                print("  git: ✓")
            else:
                print("  git: ❌")
                issues_found.append("git not found")
        else:
            print("  Skills: ❌")
            issues_found.append("No skills extracted")
        
        print()
        
        if issues_found:
            print("ISSUES FOUND:")
            for issue in issues_found:
                print(f"  ❌ {issue}")
        else:
            print("🎉 ALL ISSUES RESOLVED! Resume parsing is working correctly.")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_final_resume_parsing()) 