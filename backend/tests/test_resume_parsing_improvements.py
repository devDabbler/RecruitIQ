#!/usr/bin/env python3
"""
Test script for resume parsing improvements
Tests NER-enhanced education extraction, LLM array field enforcement, and confidence scoring
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from services.ollama_service import OllamaService
from utils.resume_parsing.resume_parser_main import ResumeParser
from utils.resume_parsing.models.resume_schema import ResumeData, PersonalInfo, Education, Experience, Skill

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample resume text for testing
SAMPLE_RESUME_TEXT = """
John Doe
Software Engineer
john.doe@email.com | (555) 123-4567 | linkedin.com/in/johndoe
San Francisco, CA

SUMMARY
Experienced software engineer with 5+ years developing scalable web applications using Python, JavaScript, and cloud technologies.

EDUCATION
Stanford University
Bachelor of Science in Computer Science
2015 - 2019
GPA: 3.8/4.0

University of California, Berkeley
Master of Science in Software Engineering
2019 - 2021
GPA: 3.9/4.0

EXPERIENCE
Senior Software Engineer
TechCorp Inc.
January 2021 - Present
San Francisco, CA
• Led development of microservices architecture serving 1M+ users
• Implemented CI/CD pipelines reducing deployment time by 60%
• Mentored 3 junior developers and conducted code reviews

Software Engineer
StartupXYZ
June 2019 - December 2020
Palo Alto, CA
• Developed RESTful APIs using Python Flask and PostgreSQL
• Built responsive frontend using React.js and TypeScript
• Collaborated with product team to deliver features on time

SKILLS
Programming Languages: Python, JavaScript, TypeScript, Java, SQL
Frameworks: React, Node.js, Flask, Django, Spring Boot
Cloud & DevOps: AWS, Docker, Kubernetes, Jenkins, Git
Databases: PostgreSQL, MongoDB, Redis
"""

async def test_ner_enhanced_education_extraction():
    """Test NER-enhanced education extraction"""
    logger.info("Testing NER-enhanced education extraction...")
    
    try:
        extractor = RegexExtractor()
        
        # Test with sample resume text
        education_text = """
        EDUCATION
        Stanford University
        Bachelor of Science in Computer Science
        2015 - 2019
        GPA: 3.8/4.0
        
        University of California, Berkeley
        Master of Science in Software Engineering
        2019 - 2021
        GPA: 3.9/4.0
        """
        
        # Test NER-enhanced extraction
        education_entries = await extractor._extract_education_with_ner(education_text)
        
        logger.info(f"NER-enhanced extraction found {len(education_entries)} education entries")
        
        for i, edu in enumerate(education_entries):
            logger.info(f"Education {i+1}: {edu.institution} - {edu.degree} ({edu.start_date} - {edu.end_date})")
            logger.info(f"  Field of study: {edu.field_of_study}")
            logger.info(f"  GPA: {edu.gpa}")
            logger.info(f"  Location: {edu.location}")
        
        # Verify we found both institutions
        institutions = [edu.institution for edu in education_entries]
        expected_institutions = ["Stanford University", "University of California, Berkeley"]
        
        for expected in expected_institutions:
            if expected in institutions:
                logger.info(f"✅ Found expected institution: {expected}")
            else:
                logger.warning(f"❌ Missing expected institution: {expected}")
        
        return len(education_entries) >= 2
        
    except Exception as e:
        logger.error(f"NER-enhanced education extraction test failed: {e}")
        return False

async def test_llm_array_field_enforcement():
    """Test LLM array field enforcement"""
    logger.info("Testing LLM array field enforcement...")
    
    try:
        ollama_service = OllamaService()
        
        # Test data with missing arrays and single objects
        test_data = {
            "personal_info": {
                "name": "John Doe",
                "email": "john@example.com"
            },
            "experience": {  # Single object instead of array
                "company": "TechCorp",
                "title": "Engineer"
            },
            "education": None,  # None instead of array
            "skills": ["Python", "JavaScript"],  # Already correct array
            "projects": "Project A"  # String instead of array
        }
        
        # Apply array field enforcement
        corrected_data = ollama_service._ensure_array_fields(test_data)
        
        logger.info("Original data structure:")
        logger.info(f"  experience type: {type(test_data['experience'])}")
        logger.info(f"  education type: {type(test_data['education'])}")
        logger.info(f"  projects type: {type(test_data['projects'])}")
        
        logger.info("Corrected data structure:")
        logger.info(f"  experience type: {type(corrected_data['experience'])}")
        logger.info(f"  education type: {type(corrected_data['education'])}")
        logger.info(f"  projects type: {type(corrected_data['projects'])}")
        
        # Verify corrections
        assert isinstance(corrected_data['experience'], list), "Experience should be array"
        assert isinstance(corrected_data['education'], list), "Education should be array"
        assert isinstance(corrected_data['projects'], list), "Projects should be array"
        assert isinstance(corrected_data['skills'], list), "Skills should remain array"
        
        # Verify single object was wrapped in array
        assert len(corrected_data['experience']) == 1, "Single experience should be wrapped in array"
        assert corrected_data['experience'][0]['company'] == "TechCorp", "Experience data should be preserved"
        
        # Verify None was converted to empty array
        assert len(corrected_data['education']) == 0, "None should be converted to empty array"
        
        # Verify string was wrapped in array
        assert len(corrected_data['projects']) == 1, "String project should be wrapped in array"
        assert corrected_data['projects'][0] == "Project A", "Project data should be preserved"
        
        logger.info("✅ All array field enforcement tests passed")
        return True
        
    except Exception as e:
        logger.error(f"LLM array field enforcement test failed: {e}")
        return False

async def test_confidence_scoring():
    """Test confidence scoring functionality"""
    logger.info("Testing confidence scoring...")
    
    try:
        # Create a mock ResumeParser instance
        class MockStorageService:
            pass
        
        class MockLLMService:
            pass
        
        class MockNebiusAIService:
            pass
        
        parser = ResumeParser(
            storage_service=MockStorageService(),
            llm_service=MockLLMService(),
            nebius_ai_service=MockNebiusAIService()
        )
        
        # Create test resume data with various completeness levels
        from utils.resume_parsing.models.resume_schema import PersonalInfo, Education, Experience, Skill
        
        # Test case 1: Complete resume
        complete_resume = ResumeData(
            personal_info=PersonalInfo(
                name="John Doe",
                email="john@example.com",
                phone="555-123-4567",
                location="San Francisco, CA"
            ),
            education=[
                Education(
                    institution="Stanford University",
                    degree="Bachelor of Science",
                    field_of_study="Computer Science",
                    start_date="2015",
                    end_date="2019"
                )
            ],
            experience=[
                Experience(
                    company="TechCorp",
                    title="Software Engineer",
                    start_date="2020",
                    end_date="2023",
                    description="Developed web applications"
                )
            ],
            skills=[
                Skill(name="Python", category="Programming"),
                Skill(name="JavaScript", category="Programming"),
                Skill(name="React", category="Frontend"),
                Skill(name="Node.js", category="Backend"),
                Skill(name="AWS", category="Cloud")
            ]
        )
        
        # Test case 2: Incomplete resume
        incomplete_resume = ResumeData(
            personal_info=PersonalInfo(
                name="Jane Smith"
                # Missing email, phone, location
            ),
            education=[],  # No education
            experience=[],  # No experience
            skills=[]  # No skills
        )
        
        # Calculate confidence scores
        complete_confidence = parser._calculate_confidence_score(complete_resume)
        incomplete_confidence = parser._calculate_confidence_score(incomplete_resume)
        
        logger.info("Complete resume confidence:")
        logger.info(f"  Overall score: {complete_confidence['overall']:.2f}")
        logger.info(f"  Section scores: {complete_confidence['sections']}")
        logger.info(f"  Warnings: {complete_confidence['warnings']}")
        
        logger.info("Incomplete resume confidence:")
        logger.info(f"  Overall score: {incomplete_confidence['overall']:.2f}")
        logger.info(f"  Section scores: {incomplete_confidence['sections']}")
        logger.info(f"  Warnings: {incomplete_confidence['warnings']}")
        
        # Verify confidence scoring logic
        assert complete_confidence['overall'] > incomplete_confidence['overall'], "Complete resume should have higher confidence"
        assert len(complete_confidence['warnings']) < len(incomplete_confidence['warnings']), "Complete resume should have fewer warnings"
        assert 'personal_info' in complete_confidence['sections'], "Personal info section should be scored"
        assert 'experience' in complete_confidence['sections'], "Experience section should be scored"
        assert 'education' in complete_confidence['sections'], "Education section should be scored"
        assert 'skills' in complete_confidence['sections'], "Skills section should be scored"
        
        logger.info("✅ All confidence scoring tests passed")
        return True
        
    except Exception as e:
        logger.error(f"Confidence scoring test failed: {e}")
        return False

async def test_full_integration():
    """Test full integration of all improvements"""
    logger.info("Testing full integration...")
    
    try:
        # Create a mock ResumeParser instance
        class MockStorageService:
            pass
        
        class MockLLMService:
            pass
        
        class MockNebiusAIService:
            pass
        
        parser = ResumeParser(
            storage_service=MockStorageService(),
            llm_service=MockLLMService(),
            nebius_ai_service=MockNebiusAIService()
        )
        
        # Test with sample resume text
        resume_data = ResumeData(
            personal_info=PersonalInfo(
                name="John Doe",
                email="john@example.com",
                phone="555-123-4567",
                location="San Francisco, CA"
            ),
            education=[
                Education(
                    institution="Stanford University",
                    degree="Bachelor of Science",
                    field_of_study="Computer Science",
                    start_date="2015",
                    end_date="2019"
                )
            ],
            experience=[
                Experience(
                    company="TechCorp",
                    title="Software Engineer",
                    start_date="2020",
                    end_date="2023",
                    description="Developed web applications"
                )
            ],
            skills=[
                Skill(name="Python", category="Programming"),
                Skill(name="JavaScript", category="Programming")
            ]
        )
        
        # Calculate confidence score
        confidence = parser._calculate_confidence_score(resume_data)
        resume_data.confidence = confidence
        
        # Verify confidence data structure
        assert 'overall' in confidence, "Confidence should have overall score"
        assert 'sections' in confidence, "Confidence should have section scores"
        assert 'warnings' in confidence, "Confidence should have warnings"
        assert 'missing_fields' in confidence, "Confidence should have missing fields"
        
        # Verify all sections are scored
        expected_sections = ['personal_info', 'experience', 'education', 'skills']
        for section in expected_sections:
            assert section in confidence['sections'], f"Section {section} should be scored"
        
        # Verify resume data has confidence attached
        assert hasattr(resume_data, 'confidence'), "ResumeData should have confidence attribute"
        assert resume_data.confidence == confidence, "Confidence should be properly attached"
        
        logger.info("✅ Full integration test passed")
        return True
        
    except Exception as e:
        logger.error(f"Full integration test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting resume parsing improvement tests...")
    
    test_results = []
    
    # Test 1: NER-enhanced education extraction
    logger.info("\n" + "="*50)
    logger.info("TEST 1: NER-Enhanced Education Extraction")
    logger.info("="*50)
    result1 = await test_ner_enhanced_education_extraction()
    test_results.append(("NER-Enhanced Education Extraction", result1))
    
    # Test 2: LLM array field enforcement
    logger.info("\n" + "="*50)
    logger.info("TEST 2: LLM Array Field Enforcement")
    logger.info("="*50)
    result2 = await test_llm_array_field_enforcement()
    test_results.append(("LLM Array Field Enforcement", result2))
    
    # Test 3: Confidence scoring
    logger.info("\n" + "="*50)
    logger.info("TEST 3: Confidence Scoring")
    logger.info("="*50)
    result3 = await test_confidence_scoring()
    test_results.append(("Confidence Scoring", result3))
    
    # Test 4: Full integration
    logger.info("\n" + "="*50)
    logger.info("TEST 4: Full Integration")
    logger.info("="*50)
    result4 = await test_full_integration()
    test_results.append(("Full Integration", result4))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All resume parsing improvements are working correctly!")
        return True
    else:
        logger.error("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 