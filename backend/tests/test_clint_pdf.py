#!/usr/bin/env python3
"""
Test the resume parsing with the actual Clint Forest PDF resume
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_clint_pdf():
    """Test the resume parsing with the actual Clint Forest PDF resume"""
    print("=== Testing Clint Forest PDF Resume Parsing ===")
    
    try:
        # Import the necessary components
        from utils.resume_parsing.processors.document_processor import DocumentProcessor
        from utils.resume_parsing.processors.section_processor import SectionProcessor
        from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
        
        # Path to the PDF file
        pdf_path = Path(__file__).parent.parent / "Clint_Forest_Resume.pdf"
        
        if not pdf_path.exists():
            print(f"❌ PDF file not found at: {pdf_path}")
            return False
        
        print(f"📄 Processing PDF: {pdf_path}")
        
        # Step 1: Extract text from PDF
        print("🔄 Extracting text from PDF...")
        document_processor = DocumentProcessor()
        text = await document_processor.process(str(pdf_path))
        
        if not text:
            print("❌ Failed to extract text from PDF")
            return False
        
        print(f"✅ Text extracted successfully! Length: {len(text)} characters")
        print(f"📝 Text preview: {text[:200]}...")
        print()
        
        # Step 2: Identify sections
        print("🔄 Identifying sections...")
        section_processor = SectionProcessor()
        sections = await section_processor.process(text)
        
        print(f"✅ Sections identified: {list(sections.keys())}")
        for section_name, section_text in sections.items():
            print(f"  {section_name}: {len(section_text)} characters")
        print()
        
        # Step 3: Extract information using regex extractor
        print("🔄 Extracting information...")
        extractor = RegexExtractor()
        
        # Add full_text to sections if not present
        if 'full_text' not in sections:
            sections['full_text'] = text
        
        result = await extractor.extract(sections)
        
        print("✅ Information extraction completed!")
        print()
        
        # Display results
        print("📋 PARSING RESULTS:")
        print("=" * 50)
        
        # Personal Info
        if result.get('personal_info'):
            personal_info = result['personal_info']
            print("👤 PERSONAL INFO:")
            print(f"  Name: {personal_info.name}")
            print(f"  Email: {personal_info.email}")
            print(f"  Phone: {personal_info.phone}")
            print(f"  Address: {personal_info.address}")
            print(f"  Location: {personal_info.location}")
            print(f"  LinkedIn: {personal_info.linkedin}")
            print()
        
        # Experience
        if result.get('experience'):
            print("💼 EXPERIENCE:")
            for i, exp in enumerate(result['experience'], 1):
                print(f"  {i}. {exp.title}")
                print(f"     Company: {exp.company}")
                print(f"     Location: {exp.location}")
                print(f"     Dates: {exp.start_date} to {exp.end_date}")
                if exp.description:
                    desc_preview = exp.description[:100] + "..." if len(exp.description) > 100 else exp.description
                    print(f"     Description: {desc_preview}")
                print()
        else:
            print("❌ No experience entries found")
        
        # Education
        if result.get('education'):
            print("🎓 EDUCATION:")
            for i, edu in enumerate(result['education'], 1):
                print(f"  {i}. {edu.institution}")
                print(f"     Degree: {edu.degree}")
                print(f"     Field: {edu.field_of_study}")
                print(f"     Dates: {edu.start_date} to {edu.end_date}")
                print(f"     Location: {edu.location}")
                print()
        else:
            print("❌ No education entries found")
        
        # Skills
        if result.get('skills'):
            print("🛠️ SKILLS:")
            skill_names = [skill.name for skill in result['skills']]
            print(f"  Found {len(skill_names)} skills:")
            for i, skill in enumerate(skill_names[:20], 1):  # Show first 20 skills
                print(f"    {i}. {skill}")
            if len(skill_names) > 20:
                print(f"    ... and {len(skill_names) - 20} more")
            print()
        else:
            print("❌ No skills found")
        
        # Summary
        print("📊 SUMMARY:")
        print(f"  Experience entries: {len(result.get('experience', []))}")
        print(f"  Education entries: {len(result.get('education', []))}")
        print(f"  Skills: {len(result.get('skills', []))}")
        print()
        
        # Check if we got the expected results
        expected_experience = 2  # Based on the test data
        expected_education = 2   # Based on the test data
        
        success = True
        if len(result.get('experience', [])) != expected_experience:
            print(f"⚠️ Expected {expected_experience} experience entries, got {len(result.get('experience', []))}")
            success = False
        
        if len(result.get('education', [])) != expected_education:
            print(f"⚠️ Expected {expected_education} education entries, got {len(result.get('education', []))}")
            success = False
        
        if success:
            print("✅ All expected data extracted successfully!")
        else:
            print("⚠️ Some data extraction issues detected")
        
        return success
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_clint_pdf()) 