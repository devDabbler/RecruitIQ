#!/usr/bin/env python3
"""
Debug script to test which parser is being used in production
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from backend.services.service_registry import get_registry

async def test_parser():
    """Test which parser is being used"""
    print("🔍 Testing Parser Configuration")
    print("=" * 50)
    
    try:
        # Initialize services using the service registry
        print("📦 Initializing services...")
        registry = get_registry()
        resume_service = registry.resume_service
        
        print(f"✅ ResumeService created: {type(resume_service).__name__}")
        print(f"✅ Resume parser type: {type(resume_service.resume_parser).__name__}")
        
        # Check the Nebius AI parser
        if hasattr(resume_service.resume_parser, 'nebius_ai_parser'):
            nebius_parser = resume_service.resume_parser.nebius_ai_parser
            print(f"✅ Nebius AI parser type: {type(nebius_parser).__name__}")
            print(f"✅ Nebius AI service type: {type(nebius_parser.nebius_ai_service).__name__}")
        else:
            print("❌ No Nebius AI parser found!")
            
        # Test with a simple text
        print("\n🧪 Testing parser with sample text...")
        sample_text = """
        ROGER WATERS
        765-874-8773 - roger.waters@mail.com
        Spokane, WA
        
        EXPERIENCE
        Senior Software Engineer at Coupang - Sunnyvale, CA (September 2022 - Present)
        """
        
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_text)
            temp_path = f.name
        
        try:
            # Test parsing
            result = await resume_service.resume_parser.parse_resume(temp_path, strategy='fast')
            print(f"✅ Parsing successful!")
            print(f"✅ Name: {result.personal_info.name if result.personal_info.name else 'Not found'}")
            print(f"✅ Experience count: {len(result.experience)}")
            print(f"✅ Education count: {len(result.education)}")
            print(f"✅ Skills count: {len(result.skills)}")
            
        except Exception as e:
            print(f"❌ Parsing failed: {e}")
        finally:
            os.unlink(temp_path)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_parser()) 