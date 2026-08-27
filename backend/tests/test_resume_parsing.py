"""
Comprehensive tests for the refactored resume parser implementation.
Tests the entire parsing pipeline including processors, extractors, and the main parser.
"""

import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch
import logging
import json
from pathlib import Path

# Configure logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import the actual parser and services
from backend.utils.resume_parsing.resume_parser_main import ResumeParser
from backend.services.service_registry import provide_llm_service
from backend.services.minio_storage_service import MinioStorageService

class TestRealResumeParsing(unittest.TestCase):
    """Test cases for parsing real resumes with actual output display."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Get the path to the Roger Waters resume
        self.resume_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Roger Waters Resume.pdf')
        # Alternative path if the above doesn't work
        if not os.path.exists(self.resume_path):
            self.resume_path = "Roger Waters Resume.pdf"
        if not os.path.exists(self.resume_path):
            self.skipTest(f"Roger Waters resume not found at {self.resume_path}")
        
        # Initialize real services (no mocking)
        self.llm_service = provide_llm_service()
        self.storage_service = MinioStorageService()
        
        # Initialize the parser with real services
        self.parser = ResumeParser(llm_service=self.llm_service, verbose=True)
    
    async def test_parse_roger_waters_resume_production(self):
        """Test parsing the actual Roger Waters resume with real services and display all extracted data."""
        print("\n" + "="*80)
        print("PRODUCTION RESUME PARSING TEST - ROGER WATERS RESUME")
        print("="*80)
        
        try:
            # Parse the resume with real services
            print(f"\nParsing resume: {self.resume_path}")
            print(f"File exists: {os.path.exists(self.resume_path)}")
            print(f"File size: {os.path.getsize(self.resume_path)} bytes")
            
            result = await self.parser.parse_resume(self.resume_path)
            
            # Display the extracted data in a comprehensive format
            print("\n" + "="*80)
            print("COMPLETE EXTRACTION RESULTS")
            print("="*80)
            
            # Personal Information
            print("\n📋 PERSONAL INFORMATION:")
            print("-" * 50)
            if result.personal_info:
                pi = result.personal_info
                print(f"Name: {pi.name}")
                print(f"Email: {pi.email}")
                print(f"Phone: {pi.phone}")
                print(f"Location: {pi.location}")
                print(f"Address: {pi.address}")
                print(f"LinkedIn: {pi.linkedin}")
                print(f"Website: {pi.website}")
                print(f"Summary: {pi.summary}")
            else:
                print("❌ No personal information extracted")
            
            # Education
            print("\n🎓 EDUCATION:")
            print("-" * 50)
            if result.education:
                for i, edu in enumerate(result.education, 1):
                    print(f"\nEducation {i}:")
                    print(f"  Institution: {edu.institution}")
                    print(f"  Degree: {edu.degree}")
                    print(f"  Field of Study: {edu.field_of_study}")
                    print(f"  Start Date: {edu.start_date}")
                    print(f"  End Date: {edu.end_date}")
                    print(f"  Location: {edu.location}")
                    print(f"  Description: {edu.description}")
            else:
                print("❌ No education information extracted")
            
            # Experience
            print("\n💼 EXPERIENCE:")
            print("-" * 50)
            if result.experience:
                for i, exp in enumerate(result.experience, 1):
                    print(f"\nExperience {i}:")
                    print(f"  Title: {exp.title}")
                    print(f"  Company: {exp.company}")
                    print(f"  Location: {exp.location}")
                    print(f"  Start Date: {exp.start_date}")
                    print(f"  End Date: {exp.end_date}")
                    print(f"  Description: {exp.description}")
            else:
                print("❌ No experience information extracted")
            
            # Skills
            print("\n🛠️ SKILLS:")
            print("-" * 50)
            if result.skills:
                skill_names = [skill.name for skill in result.skills]
                print(f"Total skills extracted: {len(skill_names)}")
                print("Skills:", ", ".join(skill_names))
            else:
                print("❌ No skills extracted")
            
            # Projects
            print("\n📁 PROJECTS:")
            print("-" * 50)
            if result.projects:
                for i, proj in enumerate(result.projects, 1):
                    print(f"\nProject {i}:")
                    print(f"  Name: {proj.name}")
                    print(f"  Description: {proj.description}")
                    print(f"  Technologies: {proj.technologies}")
                    print(f"  URL: {proj.url}")
            else:
                print("❌ No projects extracted")
            
            # Certifications
            print("\n🏆 CERTIFICATIONS:")
            print("-" * 50)
            if result.certifications:
                for i, cert in enumerate(result.certifications, 1):
                    print(f"\nCertification {i}:")
                    print(f"  Name: {cert.name}")
                    print(f"  Issuer: {cert.issuer}")
                    print(f"  Date: {cert.date}")
                    print(f"  Description: {cert.description}")
            else:
                print("❌ No certifications extracted")
            
            # Languages
            print("\n🌍 LANGUAGES:")
            print("-" * 50)
            if result.languages:
                for i, lang in enumerate(result.languages, 1):
                    print(f"\nLanguage {i}:")
                    print(f"  Language: {lang.language}")
                    print(f"  Proficiency: {lang.proficiency}")
            else:
                print("❌ No languages extracted")
            
            # Raw text summary
            print("\n📄 RAW TEXT SUMMARY:")
            print("-" * 50)
            if result.raw_text:
                print(f"Raw text length: {len(result.raw_text)} characters")
                print(f"First 200 characters: {result.raw_text[:200]}...")
                print(f"Last 200 characters: ...{result.raw_text[-200:]}")
            else:
                print("❌ No raw text extracted")
            
            # Validation checks
            print("\n" + "="*80)
            print("VALIDATION CHECKS")
            print("="*80)
            
            # Check if we got meaningful data
            has_personal_info = bool(result.personal_info and result.personal_info.name and result.personal_info.name != "Unknown")
            has_experience = bool(result.experience and len(result.experience) > 0)
            has_education = bool(result.education and len(result.education) > 0)
            has_skills = bool(result.skills and len(result.skills) > 0)
            
            print(f"✅ Personal Info Extracted: {has_personal_info}")
            print(f"✅ Experience Extracted: {has_experience}")
            print(f"✅ Education Extracted: {has_education}")
            print(f"✅ Skills Extracted: {has_skills}")
            
            # Roger Waters specific checks
            print("\n🎸 ROGER WATERS SPECIFIC CHECKS:")
            print("-" * 50)
            
            # Check raw text for Roger Waters
            raw_text_lower = result.raw_text.lower()
            print(f"Raw text contains 'roger': {'roger' in raw_text_lower}")
            print(f"Raw text contains 'waters': {'waters' in raw_text_lower}")
            print(f"Raw text contains 'roger waters': {'roger waters' in raw_text_lower}")
            
            if has_personal_info:
                name = result.personal_info.name.lower()
                print(f"Extracted name contains 'roger': {'roger' in name}")
                print(f"Extracted name contains 'waters': {'waters' in name}")
            
            if has_experience:
                experience_text = " ".join([exp.title.lower() + " " + exp.company.lower() for exp in result.experience])
                print(f"Experience mentions 'pink floyd': {'pink floyd' in experience_text}")
                print(f"Experience mentions 'music': {'music' in experience_text}")
                print(f"Experience mentions 'bass': {'bass' in experience_text}")
            
            # Check for tech skills in raw text
            tech_skills = ['python', 'ruby', 'rails', 'react', 'javascript', 'aws', 'docker', 'kubernetes']
            found_skills = [skill for skill in tech_skills if skill in raw_text_lower]
            print(f"Tech skills found in raw text: {found_skills}")
            
            # Overall assessment
            print("\n" + "="*80)
            print("OVERALL ASSESSMENT")
            print("="*80)
            
            total_fields = 4
            extracted_fields = sum([has_personal_info, has_experience, has_education, has_skills])
            success_rate = (extracted_fields / total_fields) * 100
            
            print(f"Extraction Success Rate: {success_rate:.1f}% ({extracted_fields}/{total_fields} fields)")
            
            if success_rate >= 75:
                print("🎉 EXCELLENT: Resume parsing is working well!")
            elif success_rate >= 50:
                print("✅ GOOD: Resume parsing is working, but could be improved")
            elif success_rate >= 25:
                print("⚠️ FAIR: Resume parsing needs improvement")
            else:
                print("❌ POOR: Resume parsing is not working effectively")
            
            # Assertions for the test
            self.assertIsNotNone(result, "Resume parsing should return a result")
            self.assertIsNotNone(result.raw_text, "Raw text should be extracted")
            self.assertGreater(len(result.raw_text), 100, "Raw text should be substantial")
            
            # If we have personal info, it should contain Roger Waters
            if has_personal_info:
                name = result.personal_info.name.lower()
                self.assertTrue('roger' in name or 'waters' in name, 
                               f"Name should contain 'Roger' or 'Waters', got: {result.personal_info.name}")
            
            print("\n" + "="*80)
            print("TEST COMPLETED SUCCESSFULLY")
            print("="*80)
            
        except Exception as e:
            print(f"\n❌ ERROR during parsing: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

def run_tests():
    """Run the resume parsing tests."""
    # Create test suite
    suite = unittest.TestSuite()
    suite.addTest(TestRealResumeParsing('test_parse_roger_waters_resume_production'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    # Run the async test
    async def main():
        test = TestRealResumeParsing()
        test.setUp()
        await test.test_parse_roger_waters_resume_production()
    
    asyncio.run(main())
