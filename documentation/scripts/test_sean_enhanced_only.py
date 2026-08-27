#!/usr/bin/env python3
"""
Sean B. Collins Resume - Enhanced Parser Test
Simple test script to validate the enhanced parser works with Sean's resume.
"""

import os
import sys
import asyncio
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import enhanced parser components
from utils.enhanced_resume_parser import EnhancedResumeParser
from services.enhanced_parse_service import EnhancedParseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_enhanced_parser():
    """Test the enhanced parser with Sean's resume"""
    resume_path = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_path):
        print(f"❌ Error: Resume file not found: {resume_path}")
        print("Please ensure the resume file is in the current directory.")
        return False
    
    print(f"🔍 Testing Enhanced Parser with {resume_path}")
    print("=" * 60)
    
    try:
        # Initialize enhanced parser
        parser = EnhancedResumeParser()
        
        # Parse the resume
        start_time = time.time()
        result = parser.parse_resume(resume_path)
        end_time = time.time()
        
        parsing_time = round(end_time - start_time, 3)
        
        print(f"✅ Parsing completed in {parsing_time} seconds")
        print("\n📊 EXTRACTION RESULTS:")
        print("-" * 40)
        
        # Personal Information
        if result.personal_info:
            print("👤 Personal Information:")
            print(f"   Name: {result.personal_info.name or 'Not found'}")
            print(f"   Email: {result.personal_info.email or 'Not found'}")
            print(f"   Phone: {result.personal_info.phone or 'Not found'}")
            print(f"   Location: {result.personal_info.location or 'Not found'}")
            print(f"   LinkedIn: {result.personal_info.linkedin or 'Not found'}")
            print(f"   GitHub: {result.personal_info.github or 'Not found'}")
        
        # Professional Summary
        print(f"\n📝 Professional Summary:")
        if result.summary and len(result.summary.strip()) > 20:
            print(f"   ✅ Found ({len(result.summary)} characters)")
            print(f"   Preview: {result.summary[:100]}...")
        else:
            print("   ❌ Not found or too short")
        
        # Work Experience
        print(f"\n💼 Work Experience:")
        if result.experience:
            print(f"   ✅ Found {len(result.experience)} experience entries")
            for i, exp in enumerate(result.experience, 1):
                print(f"   {i}. {exp.title or 'No title'} at {exp.company or 'No company'}")
                if hasattr(exp, 'description') and exp.description:
                    print(f"      Description: {len(exp.description)} characters")
                if hasattr(exp, 'achievements') and exp.achievements:
                    print(f"      Achievements: {len(exp.achievements)} found")
                if hasattr(exp, 'technologies') and exp.technologies:
                    print(f"      Technologies: {len(exp.technologies)} found")
        else:
            print("   ❌ No experience entries found")
        
        # Skills
        print(f"\n🔧 Skills:")
        if result.skills:
            print(f"   ✅ Found {len(result.skills)} skills")
            
            # Group by category
            skills_by_category = {}
            for skill in result.skills:
                category = skill.category or "Other"
                if category not in skills_by_category:
                    skills_by_category[category] = []
                skills_by_category[category].append(skill.name)
            
            print(f"   📂 Categories: {len(skills_by_category)}")
            for category, skills in skills_by_category.items():
                print(f"      {category}: {len(skills)} skills")
                if len(skills) <= 5:
                    print(f"         {', '.join(skills)}")
                else:
                    print(f"         {', '.join(skills[:3])}... and {len(skills)-3} more")
        else:
            print("   ❌ No skills found")
        
        # Education
        print(f"\n🎓 Education:")
        if result.education:
            print(f"   ✅ Found {len(result.education)} education entries")
            for i, edu in enumerate(result.education, 1):
                print(f"   {i}. {edu.degree or 'No degree'} from {edu.institution or 'No institution'}")
        else:
            print("   ❌ No education entries found")
        
        print("\n" + "=" * 60)
        print("🎉 Enhanced parser test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced parser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_enhanced_service():
    """Test the enhanced parser service"""
    resume_path = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_path):
        print(f"❌ Error: Resume file not found: {resume_path}")
        return False
    
    print(f"\n🔍 Testing Enhanced Parser Service with {resume_path}")
    print("=" * 60)
    
    try:
        # Initialize enhanced service
        service = EnhancedParseService()
        
        # Parse the resume
        start_time = time.time()
        result = await service.parse_resume_from_file(resume_path)
        end_time = time.time()
        
        parsing_time = round(end_time - start_time, 3)
        
        # Get parsing statistics
        stats = service.get_parsing_stats(result)
        
        print(f"✅ Service parsing completed in {parsing_time} seconds")
        print(f"📈 Extraction confidence: {stats['extraction_confidence']:.2f}")
        print(f"📊 Personal info completeness: {stats['personal_info_completeness']:.2f}")
        print(f"🏆 Overall stats: {stats}")
        
        print("\n🎉 Enhanced service test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("🚀 Sean B. Collins Resume - Enhanced Parser Testing")
    print("=" * 60)
    
    # Test 1: Core enhanced parser
    core_success = test_enhanced_parser()
    
    # Test 2: Enhanced service (async)
    service_success = asyncio.run(test_enhanced_service())
    
    # Summary
    print(f"\n📋 TEST SUMMARY:")
    print("-" * 30)
    print(f"Enhanced Parser (Core): {'✅ PASS' if core_success else '❌ FAIL'}")
    print(f"Enhanced Service:       {'✅ PASS' if service_success else '❌ FAIL'}")
    
    if core_success and service_success:
        print(f"\n🎉 All tests passed! Enhanced parser is working correctly.")
        return 0
    else:
        print(f"\n❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 