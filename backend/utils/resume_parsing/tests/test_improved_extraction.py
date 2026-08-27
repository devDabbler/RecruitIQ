"""
Test script to verify improved resume extraction
"""
import os
import asyncio
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from backend.services.nebius_ai_service import NebiusAIService
from backend.utils.resume_parsing.resume_parser import ResumeParser
from backend.services.storage_service import StorageService

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Requires Jane_Smith_Resume.pdf at the repo root, which is not committed "
        "(real resumes are excluded by policy - see spec section 6). Rewrite against "
        "a synthetic fixture in Phase 1."
    )
)

@pytest.mark.asyncio
async def test_improved_extraction(file_path=None):
    """Test resume extraction with a sample resume file."""
    try:
        # Initialize services
        config = {
            "temperature": 0.1,
            "max_tokens": 2000,
            "timeout": 120.0,
            "api_key": os.environ.get("NEBIUS_API_KEY", "")
        }
        nebius_service = NebiusAIService(config)
        storage_service = StorageService()
        
        # Initialize resume parser
        parser = ResumeParser(storage_service, nebius_service)
        
        # Use the specified resume file or default
        if file_path:
            test_file = Path(file_path)
        else:
            test_file = Path(r"c:\Users\seaso\RecruitIQ\Jane_Smith_Resume.pdf")
            
        if not test_file.exists():
            raise FileNotFoundError(f"Resume file not found at: {test_file}")
        logger.info(f"\nTesting resume file: {test_file}")
        
        # Parse resume using main parser
        resume_data = await parser.parse(test_file)
        
        # Basic assertions about the resume data structure
        assert resume_data is not None, "Resume data should not be None"
        assert hasattr(resume_data, 'personal_info'), "Resume data should have personal_info"
        assert hasattr(resume_data, 'experience'), "Resume data should have experience"
        
        # Personal info assertions
        personal_info = resume_data.personal_info
        assert personal_info.name.strip() != "", "Name should not be empty"
        assert personal_info.email.strip() != "", "Email should not be empty"
        assert personal_info.phone.strip() != "", "Phone should not be empty"
        
        # Experience assertions
        assert len(resume_data.experience) > 0, "Should have at least one work experience"
        for exp in resume_data.experience:
            assert exp.company.strip() != "", "Company name should not be empty"
            assert exp.title.strip() != "", "Job title should not be empty"
            assert exp.start_date is not None, "Start date should be provided"
            
        # Education assertions
        assert len(resume_data.education) > 0, "Education section should be extracted"
        for edu in resume_data.education:
            assert edu.institution.strip() != "", "Institution name should not be empty"
            assert edu.degree.strip() != "", "Degree should not be empty"
        
        # Skills assertions (if skills section exists in the resume)
        if len(resume_data.skills) > 0:
            assert any(skill.name.strip() != "" for skill in resume_data.skills), "At least one skill should have a name"
        
        # Log extracted data with clear formatting
        print("\n" + "="*80)
        print("RESUME PARSING RESULTS")
        print("="*80)
        
        print("\nPERSONAL INFORMATION:")
        print("-" * 40)
        print(f"Name: {resume_data.personal_info.name or 'Not found'}")
        print(f"Email: {resume_data.personal_info.email or 'Not found'}")
        print(f"Phone: {resume_data.personal_info.phone or 'Not found'}")
        print(f"Location: {resume_data.personal_info.location or 'Not found'}")
        print(f"LinkedIn: {resume_data.personal_info.linkedin or 'Not found'}")
        print(f"GitHub: {resume_data.personal_info.github or 'Not found'}")
        print(f"Website: {resume_data.personal_info.website or 'Not found'}")
        
        print("\nEXPERIENCE:")
        print("-" * 40)
        if not resume_data.experience:
            print("No work experience found")
        else:
            for i, exp in enumerate(resume_data.experience, 1):
                print(f"\n[{i}] {exp.title or 'No title'}")
                print(f"   Company: {exp.company or 'Not specified'}")
                print(f"   Location: {exp.location or 'Not specified'}")
                print(f"   Duration: {exp.start_date or 'N/A'} to {exp.end_date or 'Present'}")
                if exp.highlights:
                    print("   Achievements:")
                    for highlight in exp.highlights:
                        print(f"    - {highlight}")
        
        print("\nSKILLS:")
        print("-" * 40)
        if not resume_data.skills:
            print("No skills found")
        else:
            skills_by_category = {}
            for skill in resume_data.skills:
                category = skill.category or 'General'
                if category not in skills_by_category:
                    skills_by_category[category] = []
                skills_by_category[category].append(skill.name)
            
            for category, skills in skills_by_category.items():
                print(f"\n{category}:")
                print(", ".join(skills))

        print("\nEDUCATION:")
        print("-" * 40)
        if not resume_data.education:
            print("No education information found")
        else:
            for edu in resume_data.education:
                print(f"\nInstitution: {edu.institution or 'Not specified'}")
                if edu.degree:
                    print(f"Degree: {edu.degree}" + 
                          (f" in {edu.field_of_study}" if edu.field_of_study else ""))
                print(f"Dates: {edu.start_date or 'N/A'} to {edu.end_date or 'Present'}")
                if edu.gpa:
                    print(f"GPA: {edu.gpa}")

        # Save results with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"extraction_results_{timestamp}.json"

        with open(output_file, "w") as f:
            json.dump(resume_data.dict(), f, indent=2)

        print(f"\n\nDetailed results have been saved to: {output_file}")
        print("="*80 + "\n")

        # Comprehensive quality check
        quality_metrics = {
            'personal_info': {
                'weight': 0.2,
                'score': 0,
                'checks': [
                    (bool(resume_data.personal_info.name), 0.4, "Name present"),
                    (bool(resume_data.personal_info.email), 0.3, "Email present"),
                    (bool(resume_data.personal_info.phone), 0.2, "Phone present"),
                    (bool(resume_data.personal_info.location), 0.1, "Location present")
                ]
            },
            'experience': {
                'weight': 0.3,
                'score': 0,
                'checks': [
                    (len(resume_data.experience) > 0, 0.2, "Has experience entries"),
                    (all(exp.title and exp.company for exp in resume_data.experience), 0.3, "Complete job entries"),
                    (all(exp.start_date and exp.end_date for exp in resume_data.experience), 0.2, "Complete dates"),
                    (all(len(exp.highlights) > 0 for exp in resume_data.experience), 0.3, "Has job highlights")
                ]
            },
            'education': {
                'weight': 0.25,
                'score': 0,
                'checks': [
                    (len(resume_data.education) > 0, 0.3, "Has education entries"),
                    (all(edu.institution and edu.degree for edu in resume_data.education), 0.4, "Complete education info"),
                    (all(edu.start_date or edu.end_date for edu in resume_data.education), 0.3, "Has education dates")
                ]
            },
            'skills': {
                'weight': 0.25,
                'score': 0,
                'checks': [
                    (len(resume_data.skills) >= 5, 0.4, "Has sufficient skills"),
                    (any(skill.category for skill in resume_data.skills), 0.3, "Has categorized skills"),
                    (len(set(skill.name for skill in resume_data.skills)) == len(resume_data.skills), 0.3, "No duplicate skills")
                ]
            }
        }

        # Calculate section scores
        logger.info("\nQuality Assessment:")
        total_score = 0

        for section, metrics in quality_metrics.items():
            section_score = 0
            logger.info(f"\n{section.title()}:")

            for check, weight, description in metrics['checks']:
                passed = check
                section_score += weight if passed else 0
                logger.info(f"{description}: {'✓' if passed else '✗'}")

            metrics['score'] = section_score
            weighted_score = section_score * metrics['weight']
            total_score += weighted_score
            
            logger.info(f"Section Score: {section_score * 100:.1f}%")
        
        logger.info(f"\nOverall Quality Score: {total_score * 100:.1f}%")
        
        # Warnings for low scores
        if total_score < 0.7:
            logger.warning("\nQuality Warnings:")
            for section, metrics in quality_metrics.items():
                if metrics['score'] < 0.6:
                    logger.warning(f"- Low quality {section} extraction")
        
        return resume_data
            
    except Exception as e:
        print("\n" + "!"*40)
        print(f"ERROR DURING EXTRACTION: {str(e)}")
        print("!"*40 + "\n")
        import traceback
        traceback.print_exc()
        raise


@pytest.mark.asyncio
async def test_with_sample_text():
    """Test extraction with sample resume text"""
    sample_text = """
    JOHN DOE
    123 Main St, San Francisco, CA 94105
    (123) 456-7890 | john.doe@email.com | linkedin.com/in/johndoe

    PROFESSIONAL SUMMARY
    Senior Software Engineer with 5+ years of experience in full-stack development...

    EXPERIENCE
    Senior Software Engineer - ABC Tech, San Francisco, CA (Jan 2020 - Present)
    • Led a team of 5 developers to build a scalable microservices architecture
    • Implemented CI/CD pipelines reducing deployment time by 60%

    Software Engineer - XYZ Corp, San Francisco, CA (Jun 2017 - Dec 2019)
    • Developed RESTful APIs using Python and FastAPI
    • Improved application performance by 40% through query optimization

    EDUCATION
    Master of Science in Computer Science
    Stanford University, Stanford, CA (2015 - 2017)
    GPA: 3.8/4.0

    Bachelor of Science in Computer Science
    University of California, Berkeley, CA (2011 - 2015)
    GPA: 3.7/4.0

    SKILLS
    • Programming: Python, JavaScript, Java, SQL
    • Frameworks: FastAPI, React, Node.js
    • Tools: Git, Docker, AWS, Kubernetes
    """
    
    try:
        # Initialize services
        config = {
            "temperature": 0.1,
            "max_tokens": 2000,
            "timeout": 120.0,
            "api_key": os.environ.get("NEBIUS_API_KEY", "")
        }
        nebius_service = NebiusAIService(config)
        
        # Test direct extraction
        result = await nebius_service.extract_resume_data(sample_text)
        
        # Log results
        logger.info("\n========== SAMPLE TEXT EXTRACTION TEST ==========")
        logger.info(f"Extracted name: {result.get('personal_info', {}).get('name')}")
        logger.info(f"Extracted email: {result.get('personal_info', {}).get('email')}")
        logger.info(f"Number of experience entries: {len(result.get('experience', []))}")
        logger.info(f"Number of skills: {len(result.get('skills', []))}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in sample text extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            asyncio.run(test_improved_extraction(file_path))
        else:
            # Run both tests
            asyncio.run(test_improved_extraction())
            asyncio.run(test_with_sample_text())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)