#!/usr/bin/env python3
"""
Test script to parse a real resume using the new resume parsing system.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing import create_resume_parser
from services.storage_service import StorageService
from services.nebius_ai_service import NebiusAIService


async def test_real_resume_parsing():
    """Test parsing a real resume file."""
    
    # Initialize services
    storage_service = StorageService()
    nebius_ai_service = NebiusAIService()
    
    # Create resume parser
    parser = create_resume_parser(storage_service, nebius_ai_service)
    
    # Path to the test resume
    resume_path = "../Clint_Forest_Resume.pdf"
    
    if not os.path.exists(resume_path):
        print(f"Error: Resume file not found at {resume_path}")
        return
    
    print(f"Testing resume parsing with: {resume_path}")
    print("=" * 60)
    
    try:
        # Parse the resume
        print("Starting resume parsing...")
        resume_data = await parser.parse(resume_path)
        
        print("\n✅ Resume parsing completed successfully!")
        print("\n" + "=" * 60)
        print("EXTRACTION RESULTS:")
        print("=" * 60)
        
        # Display personal information
        print("\n📋 PERSONAL INFORMATION:")
        print("-" * 30)
        if resume_data.personal_info:
            pi = resume_data.personal_info
            print(f"Name: {pi.name or 'Not found'}")
            print(f"Email: {pi.email or 'Not found'}")
            print(f"Phone: {pi.phone or 'Not found'}")
            print(f"Location: {pi.location or 'Not found'}")
            print(f"LinkedIn: {pi.linkedin or 'Not found'}")
            print(f"Website: {pi.website or 'Not found'}")
        
        # Display education
        print(f"\n🎓 EDUCATION ({len(resume_data.education)} entries):")
        print("-" * 30)
        for i, edu in enumerate(resume_data.education, 1):
            print(f"{i}. Institution: {edu.institution or 'Not found'}")
            print(f"   Degree: {edu.degree or 'Not found'}")
            print(f"   Field: {edu.field_of_study or 'Not found'}")
            print(f"   Dates: {edu.start_date or 'Not found'} - {edu.end_date or 'Not found'}")
            print(f"   Description: {edu.description or 'Not found'}")
            print()
        
        # Display experience
        print(f"\n💼 EXPERIENCE ({len(resume_data.experience)} entries):")
        print("-" * 30)
        for i, exp in enumerate(resume_data.experience, 1):
            print(f"{i}. Title: {exp.title or 'Not found'}")
            print(f"   Company: {exp.company or 'Not found'}")
            print(f"   Location: {exp.location or 'Not found'}")
            print(f"   Dates: {exp.start_date or 'Not found'} - {exp.end_date or 'Not found'}")
            print(f"   Description: {exp.description or 'Not found'}")
            print()
        
        # Display skills
        print(f"\n🛠️ SKILLS ({len(resume_data.skills)} entries):")
        print("-" * 30)
        for i, skill in enumerate(resume_data.skills, 1):
            print(f"{i}. {skill.name or 'Not found'}")
        
        # Display projects
        print(f"\n📁 PROJECTS ({len(resume_data.projects)} entries):")
        print("-" * 30)
        for i, project in enumerate(resume_data.projects, 1):
            print(f"{i}. Name: {project.name or 'Not found'}")
            print(f"   Description: {project.description or 'Not found'}")
            print(f"   Technologies: {project.technologies or 'Not found'}")
            print()
        
        # Display certifications
        print(f"\n🏆 CERTIFICATIONS ({len(resume_data.certifications)} entries):")
        print("-" * 30)
        for i, cert in enumerate(resume_data.certifications, 1):
            print(f"{i}. Name: {cert.name or 'Not found'}")
            print(f"   Issuer: {cert.issuer or 'Not found'}")
            print(f"   Date: {cert.date or 'Not found'}")
            print()
        
        # Display languages
        print(f"\n🌍 LANGUAGES ({len(resume_data.languages)} entries):")
        print("-" * 30)
        for i, lang in enumerate(resume_data.languages, 1):
            print(f"{i}. Language: {lang.language or 'Not found'}")
            print(f"   Proficiency: {lang.proficiency or 'Not found'}")
            print()
        
        # Display summary
        print(f"\n📝 SUMMARY:")
        print("-" * 30)
        print(resume_data.personal_info.summary or "Not found")
        
        # Display confidence scores
        if hasattr(resume_data, 'metadata') and resume_data.metadata:
            print(f"\n📊 CONFIDENCE SCORES:")
            print("-" * 30)
            confidence = resume_data.metadata.get('confidence_scores', {})
            if confidence:
                print(f"Overall Confidence: {confidence.get('overall', 'N/A')}")
                print("\nSection Scores:")
                for section, score in confidence.get('sections', {}).items():
                    print(f"  {section}: {score}")
                
                print("\nWarnings:")
                for warning in confidence.get('warnings', []):
                    print(f"  ⚠️ {warning}")
        
        # Save results to JSON file for detailed inspection
        output_file = "clint_forest_resume_parsed.json"
        with open(output_file, 'w') as f:
            json.dump(resume_data.model_dump(), f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Resume parsing failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_direct_regex_extraction():
    """Test direct regex extraction on education section."""
    
    print("Testing DIRECT regex extraction on education section...")
    print("=" * 60)
    
    # Initialize services
    storage_service = StorageService()
    nebius_ai_service = NebiusAIService()
    
    # Create resume parser
    parser = create_resume_parser(storage_service, nebius_ai_service)
    
    # Path to the test resume
    resume_path = "../Clint_Forest_Resume.pdf"
    
    if not os.path.exists(resume_path):
        print(f"Error: Resume file not found at {resume_path}")
        return
    
    try:
        # Get the raw text first
        text = await parser._process_document(resume_path)
        
        # Get sections
        from utils.resume_parsing.processors.section_processor import SectionProcessor
        section_processor = SectionProcessor()
        sections = await section_processor.process(text)
        
        # Test direct regex extraction on education section
        if 'education' in sections:
            print("EDUCATION SECTION CONTENT:")
            print("-" * 40)
            print(sections['education'])
            print("-" * 40)
            
            from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
            regex_extractor = RegexExtractor()
            
            # Test education extraction directly
            education_entries = await regex_extractor._extract_education(sections['education'])
            print(f"\nDIRECT REGEX EXTRACTION RESULTS ({len(education_entries)} entries):")
            print("-" * 40)
            for i, edu in enumerate(education_entries, 1):
                print(f"{i}. Institution: {edu.institution or 'Not found'}")
                print(f"   Degree: {edu.degree or 'Not found'}")
                print(f"   Field: {edu.field_of_study or 'Not found'}")
                print(f"   Dates: {edu.start_date or 'Not found'} - {edu.end_date or 'Not found'}")
                print(f"   Location: {edu.location or 'Not found'}")
                print()
        else:
            print("No education section found!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Test both approaches
    print("=== TESTING DIRECT REGEX EXTRACTION ===")
    asyncio.run(test_direct_regex_extraction())
    
    print("\n" + "=" * 60)
    print("=== TESTING FULL PIPELINE ===")
    asyncio.run(test_real_resume_parsing()) 