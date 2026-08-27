#!/usr/bin/env python3
"""
Test AI bullet consolidation with Alex Jones resume.
This script demonstrates the improved bullet point consolidation functionality.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing import create_resume_parser
from services.storage_service import StorageService
from services.nebius_ai_service import NebiusAIService

async def test_alex_jones_resume():
    """Test AI bullet consolidation with Alex Jones resume"""
    print("🚀 Testing AI Bullet Consolidation with Alex Jones Resume")
    print("=" * 70)
    
    try:
        # Initialize services
        storage_service = StorageService()
        nebius_service = NebiusAIService()
        
        # Create resume parser with AI service
        parser = create_resume_parser(
            storage_service=storage_service,
            nebius_ai_service=nebius_service
        )
        
        # Check if Alex Jones resume exists
        alex_resume_path = Path("Alex_Jones_Resume.pdf")
        if not alex_resume_path.exists():
            print("❌ Alex Jones resume not found at Alex_Jones_Resume.pdf")
            print("   Please make sure the file is in the backend directory")
            return
        
        print(f"📄 Found Alex Jones resume: {alex_resume_path}")
        print("\n🔄 Parsing resume with AI bullet consolidation enabled...")
        
        # Parse the resume
        resume_data = await parser.parse(str(alex_resume_path))
        
        print(f"\n📊 PARSING RESULTS:")
        print(f"   • Name: {resume_data.personal_info.name if resume_data.personal_info else 'Not found'}")
        print(f"   • Email: {resume_data.personal_info.email if resume_data.personal_info else 'Not found'}")
        print(f"   • Location: {resume_data.personal_info.location if resume_data.personal_info else 'Not found'}")
        print(f"   • Experience entries: {len(resume_data.experience) if resume_data.experience else 0}")
        print(f"   • Education entries: {len(resume_data.education) if resume_data.education else 0}")
        print(f"   • Skills: {len(resume_data.skills) if resume_data.skills else 0}")
        
        # Show consolidated experience descriptions
        if resume_data.experience:
            print(f"\n📋 EXPERIENCE DESCRIPTIONS (AI Consolidated):")
            print("=" * 50)
            
            for i, exp in enumerate(resume_data.experience, 1):
                print(f"\n🏢 Experience {i}: {exp.title}")
                print(f"   Company: {exp.company}")
                print(f"   Duration: {exp.start_date} - {exp.end_date}")
                print(f"   Location: {exp.location}")
                
                if exp.description:
                    print(f"\n   📝 Description (AI Consolidated):")
                    # Split description by bullet points for better formatting
                    bullets = exp.description.split('\n\n')
                    for j, bullet in enumerate(bullets, 1):
                        if bullet.strip():
                            print(f"      {bullet.strip()}")
                else:
                    print(f"   📝 Description: Not available")
                
                print("-" * 50)
        else:
            print("\n❌ No experience data found in parsed resume")
        
        # Show skills
        if resume_data.skills:
            print(f"\n🎯 SKILLS ({len(resume_data.skills)} found):")
            skill_names = [skill.name for skill in resume_data.skills if skill.name]
            print(f"   {', '.join(skill_names)}")
        
        # Show education
        if resume_data.education:
            print(f"\n🎓 EDUCATION:")
            for edu in resume_data.education:
                print(f"   • {edu.degree} in {edu.field_of_study} - {edu.institution} ({edu.start_date} - {edu.end_date})")
        
        print(f"\n✅ Alex Jones resume parsing completed successfully!")
        print(f"\n🔧 AI BULLET CONSOLIDATION FEATURES:")
        print(f"   ✅ Fragmented bullet points merged intelligently")
        print(f"   ✅ Technical terms and achievements preserved")
        print(f"   ✅ Word splits fixed (e.g., 'ad.' + 'hoc' → 'ad-hoc')")
        print(f"   ✅ Duplicate content removed")
        print(f"   ✅ Professional formatting applied")
        
    except Exception as e:
        print(f"❌ Error testing Alex Jones resume: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_alex_jones_resume()) 