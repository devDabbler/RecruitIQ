#!/usr/bin/env python
"""
Simple script to test the local resume parser with a sample resume.
"""
import asyncio
import logging
from pathlib import Path
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import local model service
from backend.services.local_model_service import get_local_model_service

# Sample resume text
SAMPLE_RESUME = """
John Doe
Senior Software Engineer
john.doe@example.com | (555) 123-4567 | San Francisco, CA
LinkedIn: linkedin.com/in/johndoe

PROFESSIONAL SUMMARY
Experienced software engineer with 8+ years of expertise in Python, JavaScript, and cloud technologies. 
Proven track record of delivering scalable applications and leading technical teams.

EXPERIENCE
Senior Software Engineer, ABC Tech Inc.
Jan 2020 - Present | San Francisco, CA
• Led development of microservices architecture using FastAPI and Docker
• Implemented CI/CD pipelines reducing deployment time by 40%
• Managed a team of 5 engineers and mentored junior developers

Software Developer, XYZ Solutions
Mar 2017 - Dec 2019 | San Jose, CA
• Built RESTful APIs and backend services using Django and PostgreSQL
• Optimized database queries resulting in 30% performance improvement
• Collaborated with product and design teams on new feature implementation

Junior Developer, Startup Co.
Jul 2015 - Feb 2017 | Oakland, CA
• Developed responsive web applications using React and Node.js
• Implemented authentication system using OAuth and JWT
• Participated in daily Scrum meetings and biweekly sprint planning

EDUCATION
University of California, Berkeley
Bachelor of Science in Computer Science | 2011-2015
GPA: 3.8/4.0

SKILLS
• Languages: Python, JavaScript, TypeScript, SQL, HTML/CSS
• Frameworks: Django, FastAPI, React, Express, Flask
• Tools: Docker, Kubernetes, AWS, Git, Jenkins, Terraform
• Databases: PostgreSQL, MongoDB, Redis, Neo4j
"""

async def test_local_parser():
    """Test the local resume parser with a sample resume."""
    try:
        # Get local model service
        local_model_service = get_local_model_service()
        
        # Check if Ollama is available
        if not await local_model_service.is_available():
            logger.error("Ollama service is not available")
            return
        
        logger.info("Testing resume parser model with sample resume...")
        
        # Parse the sample resume
        result = await local_model_service.parse_resume(SAMPLE_RESUME)
        
        if result:
            logger.info("Resume parsing successful!")
            print("\n===== PARSED RESUME RESULT =====\n")
            print(json.dumps(result, indent=2))
            
            # Check if we have all expected sections
            sections = ["personal_info", "skills", "education", "experience"]
            missing = [s for s in sections if s not in result or not result[s]]
            
            if missing:
                logger.warning(f"Missing or empty sections: {', '.join(missing)}")
            else:
                logger.info("All expected sections are present and populated")
                
            # Basic validation
            if "personal_info" in result and result["personal_info"].get("name"):
                logger.info(f"Successfully extracted name: {result['personal_info']['name']}")
            
            if "skills" in result and result["skills"]:
                logger.info(f"Extracted {len(result['skills'])} skills")
            
            if "education" in result and result["education"]:
                logger.info(f"Extracted {len(result['education'])} education entries")
            
            if "experience" in result and result["experience"]:
                logger.info(f"Extracted {len(result['experience'])} experience entries")
        else:
            logger.error("Parser returned empty result")
    except Exception as e:
        logger.error(f"Error testing local parser: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_local_parser())
