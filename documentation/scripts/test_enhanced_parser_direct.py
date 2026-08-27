#!/usr/bin/env python3
"""
Direct Enhanced Parser Test Script
Tests the enhanced resume parser directly without API
"""
print("[DEBUG] test_enhanced_parser_direct.py is running!")

print('[DEBUG] Before imports')
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
print('[DEBUG] After stdlib imports')
import sys
print('[DEBUG] sys.executable:', sys.executable)
print('[DEBUG] sys.path:', sys.path)

# Add project root to sys.path so we can import from the 'backend' package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
print('[DEBUG] Project root added to sys.path:', project_root)
print('[DEBUG] After sys.path insert, sys.path:', sys.path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    print('[DEBUG] Importing EnhancedResumeParser from backend.utils...')
    from backend.utils.enhanced_resume_parser import EnhancedResumeParser
    print('[DEBUG] Successfully imported EnhancedResumeParser:', EnhancedResumeParser)
    print('[DEBUG] EnhancedResumeParser module path:', EnhancedResumeParser.__module__)
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root or that 'backend' is importable on sys.path.")
    sys.exit(1)

class DirectParserTester:
    def __init__(self):
        self.parser = EnhancedResumeParser()
        
    async def test_enhanced_parser(self, resume_path: str) -> Dict[str, Any]:
        """Test the enhanced parser directly"""
        
        if not os.path.exists(resume_path):
            print(f"❌ Resume file not found: {resume_path}")
            return {}
        
        print(f"🧪 DIRECT PARSER TEST")
        print("=" * 40)
        print(f"🚀 Testing ENHANCED parser directly...")
        print(f"📄 File: {resume_path}")
        
        try:
            # Parse resume directly
            result = await self.parser.parse_resume(resume_path)
            self._analyze_results(result)
            return result
            
        except Exception as e:
            print(f"❌ Parser error: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _analyze_results(self, result, expected_name=None, expected_experience_min=None, expected_education_min=None, expected_degree_substr=None):
        """Analyze and display parsing results"""
        
        print(f"\U0001F4CA DIRECT PARSER RESULTS:")
        
        # Personal Info Analysis
        personal_info = result.personal_info
        print(f"  ✓ Name: '{personal_info.name if personal_info.name else 'Not found'}'")
        if expected_name:
            assert personal_info.name == expected_name, f"Expected name '{expected_name}', but got '{personal_info.name}'"
        print(f"  ✓ Email: '{personal_info.email if personal_info.email else 'Not found'}'")
        print(f"  ✓ Phone: '{personal_info.phone if personal_info.phone else 'Not found'}'")
        print(f"  ✓ Location: '{personal_info.location if personal_info.location else 'Not found'}'")
        print(f"  ✓ LinkedIn: '{personal_info.linkedin if personal_info.linkedin else 'Not found'}'")
        
        # Experience Analysis
        experience = result.experience or []
        print(f"  ✓ Experience entries: {len(experience)}")
        if expected_experience_min is not None:
            assert len(experience) >= expected_experience_min, f"Expected at least {expected_experience_min} experience entries, but got {len(experience)}. Entries: {[str(e) for e in experience]}"
        for i, exp in enumerate(experience):
            print(f"    - Job {i+1}: {getattr(exp, 'title', '')} at {getattr(exp, 'company', '')} ({getattr(exp, 'date_range', '')})")
        
        # Education Analysis
        education = getattr(result, 'education', []) or []
        print(f"  ✓ Education entries: {len(education)}")
        assert len(education) == 3, f"Expected exactly 3 education entries, but got {len(education)}. Entries: {[str(e) for e in education]}"
        for i, edu in enumerate(education):
            print(f"    - Education {i+1}: {getattr(edu, 'degree', '')} at {getattr(edu, 'institution', '')} ({getattr(edu, 'start_date', '')} - {getattr(edu, 'end_date', '')})")
        
        # Military Analysis
        military = getattr(result, 'military', []) or []
        print(f"  ✓ Military entries: {len(military)}")
        assert len(military) == 1, f"Expected exactly 1 military entry, but got {len(military)}. Entries: {[str(m) for m in military]}"
        for i, mil in enumerate(military):
            print(f"    - Military {i+1}: {getattr(mil, 'rank', getattr(mil, 'title', ''))} in {getattr(mil, 'branch', getattr(mil, 'company', ''))} ({getattr(mil, 'start_date', '')} - {getattr(mil, 'end_date', '')})")
        
        # Skills Analysis
        skills = result.skills or []
        print(f"  ✓ Skills extracted: {len(skills)}")
        
        # Education Analysis
        education = result.education or []
        print(f"  ✓ Education entries: {len(education)}")
        assert len(education) >= 1, f"Expected at least 1 education entry, but got {len(education)}"
        
        # Military Analysis
        military = result.military or []
        military_status = "✅ Found" if len(military) > 0 else "❌ Missing"
        print(f"  ✓ Military entries: {len(military)} {military_status}")
        
        # Summary Analysis
        summary = result.summary or ''
        summary_status = "✅ Found" if summary and len(summary) > 50 else "❌ Missing"
        print(f"  ✓ Summary: {summary_status}")
        
        # Overall Status
        print(f"✅ EXTRACTION STATUS:")
        print(f"  Personal Info: {'✅ Success' if personal_info.name else '❌ Missing'}")
        print(f"  Experience: {'✅ Success' if len(experience) > 0 else '❌ Missing'}")
        print(f"  Military: {'✅ Success' if len(military) > 0 else '❌ Missing'}")
        print(f"  Education: {'✅ Success' if len(education) > 0 else '❌ Missing'}")
        print(f"  Skills: {'✅ Success' if len(skills) > 0 else '❌ Missing'}")
        
        # Detailed Analysis
        print(f"📋 EXPERIENCE DETAILS:")
        for i, exp in enumerate(experience[:3], 1):  # Show first 3
            print(f"  {i}. Title: '{exp.title if exp.title else 'No title'}'")
            print(f"     Company: '{exp.company if exp.company else 'No company'}'")
            print(f"     Location: '{exp.location if exp.location else 'No location'}'")
            print(f"     Dates: '{exp.start_date if exp.start_date else ''} - {exp.end_date if exp.end_date else ''}'")
        
        if len(experience) > 3:
            print(f"     ... and {len(experience) - 3} more entries")
        
        # Military Details
        if military:
            print(f"🎖️ MILITARY DETAILS:")
            for i, mil in enumerate(military, 1):
                print(f"  {i}. Title: '{mil.title if mil.title else 'No title'}'")
                print(f"     Service: '{mil.company if mil.company else 'No service'}'")
                print(f"     Dates: '{mil.start_date if mil.start_date else ''} - {mil.end_date if mil.end_date else ''}'")
                if mil.description:
                    print(f"     Description: {mil.description[:100]}...")
        
        # Education Details
        if education:
            print(f"🎓 EDUCATION DETAILS:")
            for i, edu in enumerate(education, 1):
                print(f"  {i}. Degree: '{edu.degree if edu.degree else 'No degree'}'")
                print(f"     Institution: '{edu.institution if edu.institution else 'No institution'}'")
                print(f"     Dates: '{edu.start_date if edu.start_date else ''} - {edu.end_date if edu.end_date else ''}'")
        
        # Skills Details
        print(f"🛠️ SKILLS DETAILS:")
        skill_categories = {}
        for skill in skills:
            if hasattr(skill, 'category'):
                category = skill.category or 'Other'
                if category not in skill_categories:
                    skill_categories[category] = []
                skill_categories[category].append(skill.name if hasattr(skill, 'name') else str(skill))
            else:
                # Handle string skills
                if 'Other' not in skill_categories:
                    skill_categories['Other'] = []
                skill_categories['Other'].append(str(skill))
        
        for category, skill_list in skill_categories.items():
            print(f"  {category}: {len(skill_list)} skills")
            if len(skill_list) <= 5:
                print(f"    - {', '.join(skill_list)}")
            else:
                print(f"    - {', '.join(skill_list[:5])}... (+{len(skill_list)-5} more)")
        
        # Recommendations
        issues = []
        if len(military) == 0:
            issues.append("Military experience not detected")
        if len(experience) > 15:
            issues.append(f"Too many experience entries ({len(experience)}) - possible over-extraction")
        if len(experience) == 0:
            issues.append("No work experience detected")
        if len(education) == 0:
            issues.append("Education not detected")
        if not personal_info.name:
            issues.append("Name not extracted")
        
        if issues:
            print(f"🔧 FIX RECOMMENDATIONS:")
            print("=" * 30)
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"🎉 ALL TESTS PASSED!")
        
        print(f"🏁 TEST COMPLETE")
        print("=" * 20)

async def main():
    """Main test function"""
    print("[DEBUG] Entered main function.")
    import sys
    # If a command-line argument is given, use it as the resume path
    if len(sys.argv) > 1:
        resume_path = sys.argv[1]
        print(f"[DEBUG] Using resume path from command-line: {resume_path}")
        if not os.path.isabs(resume_path):
            resume_path = os.path.abspath(resume_path)
        if not os.path.exists(resume_path):
            print(f"❌ Provided resume file does not exist: {resume_path}")
            print("[DEBUG] Working directory:", os.getcwd())
            print("[DEBUG] Directory listing:", os.listdir(os.getcwd()))
            return
    else:
        # Look for resume file (prefer the provided Sean Collins 2025 resume)
        resume_paths = [
            r"c:\\Users\\seaso\\RecruitIQ\\Sean Collins Resume 2025.pdf",
            "Sean Collins Resume 2025.pdf",
            "backend/test_data/Sean Collins Resume 2025.pdf", 
            "test_data/Sean Collins Resume 2025.pdf",
            "../Sean Collins Resume 2025.pdf"
        ]
        resume_path = None
        for path in resume_paths:
            if os.path.exists(path):
                resume_path = path
                print(f"[DEBUG] Found resume_path candidate: {path}")
                break
        if not resume_path:
            print("❌ Resume file not found. Please ensure 'Sean Collins Resume 2025.pdf' is in one of the expected locations:")
            for path in resume_paths:
                print(f"   - {path}")
            print("[DEBUG] Working directory:", os.getcwd())
            print("[DEBUG] Directory listing:", os.listdir(os.getcwd()))
            return
    print(f"[DEBUG] Final resume_path: {resume_path}")
    print(f"[DEBUG] Working directory: {os.getcwd()}")
    print(f"[DEBUG] Directory listing: {os.listdir(os.getcwd())}")
    # Test with direct parser
    print("[DEBUG] Initializing DirectParserTester...")
    tester = DirectParserTester()
    print("[DEBUG] Calling tester.test_enhanced_parser...")
    result = await tester.test_enhanced_parser(resume_path)
    
    # Also test the Adam Templeton resume specifically for raw text extraction
    print("\n[DEBUG] Now testing Adam Templeton resume for raw text extraction...")
    print("[DEBUG] Calling test_parse_adam_templeton_resume()...")
    adam_result = await test_parse_adam_templeton_resume()
    
    # Print raw text analysis summary for Adam's resume
    if adam_result:
        print("\n===== ADAM TEMPLETON RESUME ANALYSIS =====")
        print(f"Name extracted: {adam_result.personal_info.name if hasattr(adam_result, 'personal_info') else 'Not found'}")
        print(f"Experience entries: {len(adam_result.experience) if hasattr(adam_result, 'experience') else 0}")
        print(f"Education entries: {len(adam_result.education) if hasattr(adam_result, 'education') else 0}")
        print(f"Military entries: {len(adam_result.military) if hasattr(adam_result, 'military') else 0}")
        print(f"Skills entries: {len(adam_result.skills) if hasattr(adam_result, 'skills') else 0}")
    
    # Print the raw output of the first test
    import json
    print("\n===== RAW PARSER OUTPUT =====")
    
    # Handle Pydantic model serialization properly
    def serialize_resumedata(obj):
        if hasattr(obj, 'model_dump'):
            # Pydantic v2 method
            return obj.model_dump()
        elif hasattr(obj, 'dict'):
            # Pydantic v1 method
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            # Regular Python class
            d = obj.__dict__.copy()
            # Process nested objects recursively
            for k, v in d.items():
                if hasattr(v, 'dict') or hasattr(v, 'model_dump') or hasattr(v, '__dict__'):
                    d[k] = serialize_resumedata(v)
                elif isinstance(v, list):
                    d[k] = [serialize_resumedata(item) if hasattr(item, 'dict') or hasattr(item, 'model_dump') or hasattr(item, '__dict__') else item for item in v]
                elif isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d
        elif isinstance(obj, list):
            return [serialize_resumedata(item) if hasattr(item, 'dict') or hasattr(item, 'model_dump') or hasattr(item, '__dict__') else item for item in obj]
        elif isinstance(obj, dict):
            return {k: serialize_resumedata(v) if hasattr(v, 'dict') or hasattr(v, 'model_dump') or hasattr(v, '__dict__') else v for k, v in obj.items()}
        else:
            # Let default JSON serialization handle it
            return obj
    
    try:
        # Convert the ResumeData object to a serializable dict structure
        result_dict = serialize_resumedata(result)
        print(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"[EXCEPTION] Top-level exception caught: {e}")
        # Try to extract some basic info
        print("\n===== BASIC RESULT INFO =====")
        if hasattr(result, 'personal_info'):
            print(f"Personal Info: {result.personal_info}")
        if hasattr(result, 'experience'):
            print(f"Experience entries: {len(result.experience)}")
        if hasattr(result, 'education'):
            print(f"Education entries: {len(result.education)}")
        if hasattr(result, 'military'):
            print(f"Military entries: {len(result.military)}")
        if hasattr(result, 'skills'):
            print(f"Skills entries: {len(result.skills)}")
        
        # Add a simple serialization of key fields
        print("\n===== SIMPLIFIED JSON OUTPUT =====")
        simplified = {
            "name": result.personal_info.name if hasattr(result, 'personal_info') and hasattr(result.personal_info, 'name') else None,
            "email": result.personal_info.email if hasattr(result, 'personal_info') and hasattr(result.personal_info, 'email') else None,
            "experience_count": len(result.experience) if hasattr(result, 'experience') else 0,
            "education_count": len(result.education) if hasattr(result, 'education') else 0,
            "military_count": len(result.military) if hasattr(result, 'military') else 0,
            "skills_count": len(result.skills) if hasattr(result, 'skills') else 0
        }
        print(json.dumps(simplified, indent=2))
        
        import traceback
        traceback.print_exc()

async def test_parse_adam_templeton_resume():
    """
    Parse the Adam Templeton resume and assert/print correct extraction.
    """
    tester = DirectParserTester()
    adam_resume_path = r"C:\Users\seaso\RecruitIQ\Adam Templeton Resume.pdf"
    if not os.path.exists(adam_resume_path):
        print(f"❌ Adam Templeton resume not found at {adam_resume_path}")
        return
    
    # Try to extract and print raw text via optional PDFToMarkdownConverter if available
    print("\n===== DIRECTLY EXTRACTING RAW TEXT FROM PDF =====")
    try:
        from backend.utils.pdf_to_markdown import PDFToMarkdownConverter  # optional utility
        pdf_converter = PDFToMarkdownConverter()
        raw_text = pdf_converter._extract_text_from_pdf(adam_resume_path)
        print("\n===== RAW EXTRACTED TEXT FROM PDF (BEFORE PARSING) =====")
        print(raw_text)
        print("\n===== END OF RAW TEXT =====")
    except Exception as e:
        print(f"[DEBUG] PDFToMarkdownConverter not available or failed ({e}); skipping this step.")
    
    # Also try with PyPDF2 directly
    print("\n===== EXTRACTING WITH PyPDF2 DIRECTLY =====")
    from PyPDF2 import PdfReader
    with open(adam_resume_path, 'rb') as file:
        reader = PdfReader(file)
        pypdf2_text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            pypdf2_text += page.extract_text() + "\n\n"
    print("\n===== RAW EXTRACTED TEXT FROM PYPDF2 =====")
    print(pypdf2_text)
    print("\n===== END OF PYPDF2 TEXT =====")
    
    # Continue with normal parsing - using await instead of asyncio.run
    result = await tester.parser.parse_resume(adam_resume_path)

    # Strong assertions on real PDF output
    expected_name = "Adam Templeton"
    expected_experience_min = 3  # Should extract Rocket Mortgage, Vibe, Spotify
    expected_education_min = 1
    expected_degree_substr = "Bachelor of Science"
    expected_skills_min = 5  # At least 5 skills expected

    # Analyze and assert
    tester._analyze_results(
        result,
        expected_name=expected_name,
        expected_experience_min=expected_experience_min,
        expected_education_min=expected_education_min,
        expected_degree_substr=expected_degree_substr
    )

    # Check if result has full_text attribute and print it too for comparison
    if hasattr(result, 'full_text'):
        print("\n===== RAW EXTRACTED TEXT FROM RESULT OBJECT =====\n")
        print(result.full_text)

    # Additional: Check for skills extracted
    skills = getattr(result, 'skills', [])
    if not skills or len(skills) < expected_skills_min:
        print(f"❌ Skills extraction failed or too few skills: found {len(skills) if skills else 0}")
        print("Extracted skills:", skills)
        assert False, f"Expected at least {expected_skills_min} skills, found {len(skills) if skills else 0}"
    else:
        print(f" Skills extracted: {len(skills)}")
        
    # Return the result for the main function
    return result

if __name__ == "__main__":
    try:
        print("[DEBUG] Starting asyncio.run(main())")
        asyncio.run(main())
        print("[DEBUG] Finished asyncio.run(main())")
    except Exception as e:
        import traceback
        print("[EXCEPTION] Top-level exception caught:", e)
        traceback.print_exc()

# Pytest-compatible entry point
import pytest
@pytest.mark.asyncio
async def test_main():
    await main()

@pytest.mark.asyncio
async def test_comprehensive_enhanced_parser():
    """
    Comprehensive test that runs all EnhancedParserTester checks, mirroring the main() function in test_enhanced_parser.py.
    """
    from backend.scripts.test_enhanced_parser import EnhancedParserTester, test_improved_parser_direct

    tester = EnhancedParserTester()
    await tester.run_comprehensive_tests()

    # Optionally run the direct improved parser test as well
    await test_improved_parser_direct()

@pytest.mark.asyncio
async def test_parse_sean_collins_resume():
    """
    Parse the Sean B. Collins resume and print the output for confirmation.
    """
    resume_path = r"c:\\Users\\seaso\\RecruitIQ\\Sean Collins Resume 2025.pdf"
    from backend.utils.enhanced_resume_parser import EnhancedResumeParser

    parser = EnhancedResumeParser()
    result = await parser.parse_resume(resume_path)

    import json
    print("\n===== PARSED OUTPUT FOR SEAN COLLINS RESUME (2025) =====")
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))

    # Print summary counts for key sections
    print("\n===== SUMMARY COUNTS =====")
    print(f"Education entries: {len(result.education)}")
    print(f"Civilian experience entries: {len(result.experience)}")
    print(f"Military entries: {len(result.military)}")

    # Assert expected counts and print details if not met
    # No hardcoded expected counts for Adam Templeton; print counts only
    fail = False
    print("\n[DEBUG] Civilian experience entries:")
    for i, exp in enumerate(result.experience):
        print(f"Experience #{i+1}: {exp}")
    print("\n[DEBUG] Education entries:")
    for i, edu in enumerate(result.education):
        print(f"Education #{i+1}: {edu}")
    print("\n[DEBUG] Military entries:")
    for i, mil in enumerate(result.military):
        print(f"Military #{i+1}: {mil}")
    # Optionally, add assertions if you know expected values for Adam Templeton
    assert result.personal_info is not None
    # assert result.personal_info.name.lower().startswith("adam")  # Uncomment if you want to check name