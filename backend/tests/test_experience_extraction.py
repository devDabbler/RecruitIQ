#!/usr/bin/env python3
"""
Focused test for experience extraction improvements
Tests the specific fixes made to section detection and experience parsing.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from utils.resume_parsing.resume_parser_main import ResumeParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_experience_extraction():
    """Test experience extraction with sample resume text"""
    
    # Sample resume text with clear experience section
    sample_resume = """
John Doe
Software Engineer
john.doe@email.com
(555) 123-4567

EXPERIENCE

Senior Software Engineer at Google
Mountain View, CA | 2020 - Present
• Developed scalable web applications using Python and React
• Led a team of 5 engineers on microservices architecture
• Implemented CI/CD pipelines reducing deployment time by 50%

Software Engineer at Microsoft
Seattle, WA | 2018 - 2020
• Built cloud-based solutions using Azure and .NET
• Collaborated with cross-functional teams on product development
• Optimized database queries improving performance by 30%

Junior Developer at Startup Inc
San Francisco, CA | 2016 - 2018
• Created RESTful APIs using Node.js and Express
• Worked on front-end development with JavaScript and HTML/CSS
• Participated in agile development processes

EDUCATION

Bachelor of Science in Computer Science
Stanford University | 2012 - 2016

SKILLS

Programming Languages: Python, JavaScript, Java, C++
Frameworks: React, Angular, Django, Flask
Tools: Git, Docker, Kubernetes, AWS
"""

    logger.info("🧪 Testing Experience Extraction...")
    
    # Test with RegexExtractor directly
    extractor = RegexExtractor()
    
    try:
        # Extract experiences
        result = extractor.extract(sample_resume, "test_resume.txt")
        
        experiences = result.get('experience', [])
        skills = result.get('skills', [])
        
        logger.info(f"📊 Extraction Results:")
        logger.info(f"   Experiences found: {len(experiences)}")
        logger.info(f"   Skills found: {len(skills)}")
        
        # Analyze experience quality
        valid_experiences = 0
        for i, exp in enumerate(experiences):
            company = exp.get('company', 'Unknown')
            title = exp.get('title', 'Unknown')
            location = exp.get('location', '')
            
            logger.info(f"   Experience {i+1}:")
            logger.info(f"     Company: {company}")
            logger.info(f"     Title: {title}")
            logger.info(f"     Location: {location}")
            
            # Check if this is a valid experience (not fragmented)
            if (company != 'Unknown' and 
                title != 'Unknown' and 
                len(company) > 2 and 
                len(title) > 2 and
                not company.startswith('•') and
                not title.startswith('•')):
                valid_experiences += 1
            
        # Analyze skills quality
        valid_skills = 0
        fragmented_skills = []
        categorized_skills = 0
        
        for skill in skills:
            skill_name = skill.get('name', '')
            skill_category = skill.get('category')
            
            # Check for fragmented skills
            if len(skill_name) <= 2 or skill_name in ['P', 'L', 'ython', 'ambda']:
                fragmented_skills.append(skill_name)
            else:
                valid_skills += 1
            
            if skill_category:
                categorized_skills += 1
        
        logger.info(f"   Valid experiences: {valid_experiences}/{len(experiences)}")
        logger.info(f"   Valid skills: {valid_skills}/{len(skills)}")
        logger.info(f"   Categorized skills: {categorized_skills}/{len(skills)}")
        
        if fragmented_skills:
            logger.warning(f"   Fragmented skills found: {fragmented_skills[:10]}")  # Show first 10
        
        # Calculate success rates
        exp_success_rate = (valid_experiences / max(len(experiences), 1)) * 100
        skill_success_rate = (valid_skills / max(len(skills), 1)) * 100
        categorization_rate = (categorized_skills / max(len(skills), 1)) * 100
        
        logger.info(f"📈 Success Rates:")
        logger.info(f"   Experience quality: {exp_success_rate:.1f}%")
        logger.info(f"   Skill quality: {skill_success_rate:.1f}%")
        logger.info(f"   Skill categorization: {categorization_rate:.1f}%")
        
        # Overall assessment
        overall_success = (exp_success_rate >= 80 and 
                          skill_success_rate >= 80 and 
                          categorization_rate >= 50)
        
        logger.info(f"🎯 Overall Result: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        return False

async def test_full_pipeline():
    """Test the full resume parsing pipeline"""
    
    logger.info("🧪 Testing Full Pipeline...")
    
    # Create a temporary resume file
    resume_content = """
Jane Smith
Data Scientist
jane.smith@email.com

PROFESSIONAL EXPERIENCE

Senior Data Scientist at Netflix
Los Gatos, CA | 2021 - Present
• Developed machine learning models for recommendation systems
• Analyzed user behavior data using Python and SQL
• Collaborated with engineering teams on model deployment

Data Analyst at Spotify
Stockholm, Sweden | 2019 - 2021
• Built dashboards using Tableau and Power BI
• Performed statistical analysis on streaming data
• Created automated reporting pipelines

EDUCATION

Master of Science in Data Science
MIT | 2017 - 2019

SKILLS

Python, R, SQL, Machine Learning, Deep Learning, TensorFlow, PyTorch
"""
    
    resume_file = "temp_resume.txt"
    
    try:
        # Write resume to file
        with open(resume_file, 'w') as f:
            f.write(resume_content)
        
        # Create parser and parse
        parser = ResumeParser()
        result = await parser.parse_resume(resume_file)
        
        logger.info(f"📊 Full Pipeline Results:")
        logger.info(f"   Experiences: {len(result.experience) if result.experience else 0}")
        logger.info(f"   Education: {len(result.education) if result.education else 0}")
        logger.info(f"   Skills: {len(result.skills) if result.skills else 0}")
        
        # Check for expected content
        has_netflix = any('Netflix' in str(exp.company) for exp in (result.experience or []))
        has_spotify = any('Spotify' in str(exp.company) for exp in (result.experience or []))
        has_mit = any('MIT' in str(edu.institution) for edu in (result.education or []))
        
        logger.info(f"   Found Netflix: {has_netflix}")
        logger.info(f"   Found Spotify: {has_spotify}")
        logger.info(f"   Found MIT: {has_mit}")
        
        success = has_netflix and has_spotify and has_mit
        logger.info(f"🎯 Pipeline Result: {'✅ PASS' if success else '❌ FAIL'}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Pipeline test failed: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(resume_file):
            os.remove(resume_file)

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Resume Parsing Tests...")
    
    # Test 1: Experience extraction
    test1_result = test_experience_extraction()
    
    # Test 2: Full pipeline
    test2_result = await test_full_pipeline()
    
    # Summary
    total_tests = 2
    passed_tests = sum([test1_result, test2_result])
    
    logger.info("=" * 50)
    logger.info("📊 FINAL RESULTS")
    logger.info("=" * 50)
    logger.info(f"Tests passed: {passed_tests}/{total_tests}")
    logger.info(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("🎉 All tests passed!")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above.")

if __name__ == "__main__":
    asyncio.run(main())
