#!/usr/bin/env python3
"""
Test script to simulate the exact production flow
"""

import asyncio
import logging
import sys
import os
import tempfile
from pathlib import Path
from fastapi import UploadFile

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from backend.services.agent_framework.agents.resume_processing_agent import ResumeProcessingAgent
from backend.services.service_registry import get_registry

async def test_production_flow():
    """Test the exact production flow"""
    print("🔍 Testing Production Flow")
    print("=" * 50)
    
    try:
        # Get the registry (same as production)
        registry = get_registry()
        
        # Create the agent (same as production)
        agent = ResumeProcessingAgent(
            resume_service=registry.resume_service,
            storage_service=registry.storage_service,
            llm_service=registry.llm_service,
            web_search_service=registry.web_search_service,
            job_service=registry.job_service
        )
        
        print("✅ Agent created successfully")
        
        # Create a test file (simulating upload)
        test_content = """
        ROGER WATERS
        765-874-8773 - roger.waters@mail.com
        Spokane, WA
        
        EXPERIENCE
        Senior Software Engineer at Coupang - Sunnyvale, CA (September 2022 - Present)
        Tech Stack: Ruby on Rails, React, MySQL, JavaScript, Redis, CSS, HTML, HAML, AWS, JWT, OIDC
        Demonstrated proficiency in Ruby on Rails, actively contributing to the codebase, and utilizing test-driven development practices to ensure software quality and reliability.
        
        Software Engineer at LG - Portland, OR (July 2018 - August 2022)
        Built and improved Command Line Interface for device monitoring system (CX-3003) based on Net-SNMP.
        
        EDUCATION
        San Jose State University - San Jose, CA (January 2016 - June 2018)
        Master of Science in Software Engineering
        
        SKILLS
        Python, Ruby on Rails, React, JavaScript, MySQL, Redis, CSS, HTML, HAML, AWS
        """
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Create a mock UploadFile
            with open(temp_path, 'rb') as file:
                content = file.read()
            
            # Create UploadFile object
            upload_file = UploadFile(
                filename="Roger Waters Resume Test.txt",
                file=open(temp_path, 'rb')
            )
            # Set content type using the headers attribute
            upload_file.headers = {"content-type": "text/plain"}
            
            print("✅ Created mock upload file")
            
            # Test the agent's processing method
            print("\n🧪 Testing agent processing...")
            result = await agent._process_single_file(upload_file, target_job_title=None)
            
            print("✅ Agent processing completed!")
            print(f"✅ Status: {result.get('status', 'Unknown')}")
            
            # Check the parsed data
            data = result.get('data', {})
            personal_info = data.get('personal_info', {})
            experience = data.get('experience', [])
            education = data.get('education', [])
            skills = data.get('skills', [])
            
            print(f"✅ Name: {personal_info.get('name', 'Not found')}")
            print(f"✅ Experience count: {len(experience)}")
            print(f"✅ Education count: {len(education)}")
            print(f"✅ Skills count: {len(skills)}")
            
            if experience:
                print(f"✅ First experience: {experience[0].get('title', 'No title')} at {experience[0].get('company', 'No company')}")
            
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_production_flow()) 