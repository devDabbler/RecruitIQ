"""
Test script to verify the direct Nebius AI implementation works without circular imports.
"""
import asyncio
import logging
import os
import sys
import dotenv
from pathlib import Path

# Load environment variables from .env file
dotenv.load_dotenv(dotenv_path=Path(os.path.dirname(__file__)) / '..' / '.env')
# Print loaded env vars for debugging (without showing actual API keys)
print("Loaded environment variables:")
for key in os.environ:
    if 'API_KEY' in key or 'TOKEN' in key:
        print(f"  {key}: {'*' * 8}[hidden]")
    else:
        print(f"  {key}: {os.environ[key]}")


# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

async def test_direct_nebius():
    """Test direct Nebius AI implementation"""
    print("\n=== TESTING DIRECT NEBIUS AI IMPLEMENTATION ===\n")
    
    # Import the DirectNebiusAI class directly
    from backend.services.llm_service import DirectNebiusAI, ModelType
    from backend.services.llm_service import get_llm_service
    
    # Get API key from environment
    nebius_api_key = os.environ.get('NEBIUS_API_KEY', '') or os.environ.get('NEBIUS_API_TOKEN', '')
    if not nebius_api_key:
        print("ERROR: No Nebius API key found in environment variables")
        return
        
    print("1. Testing direct Nebius AI class...")
    try:
        # Create the direct service
        direct_nebius = DirectNebiusAI(
            api_key=nebius_api_key,
            model="microsoft/phi-4",
            temperature=0.1,
            max_tokens=500
        )
        print("   - DirectNebiusAI initialized successfully")
        
        # Test a completion
        prompt = "Extract skills from this resume snippet: Senior Software Engineer with Python, JavaScript"
        result = await direct_nebius.generate_completion(prompt, task_type="skill_extraction")
        print(f"   - Generated completion (first 50 chars): {result[:50]}...")
        print("   - Direct Nebius AI test successful!")
    except Exception as e:
        print(f"   - Error testing direct Nebius: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n2. Testing LLM service with direct Nebius integration...")
    try:
        # Get LLM service 
        llm_service = get_llm_service()
        print("   - LLM service initialized")
        
        # Test resume parsing prompt
        resume_prompt = "Extract structured data from this resume: John Smith, Software Engineer with experience in Python"
        result = await llm_service.generate_text(prompt=resume_prompt, task_type="resume_parsing")
        print(f"   - Generated text for resume parsing (first 50 chars): {result[:50]}...")
        
        # Test quality assessment prompt
        quality_prompt = "Analyze this resume quality: John Smith, Software Engineer with experience in Python"
        result = await llm_service.generate_text(prompt=quality_prompt, task_type="resume_quality")
        print(f"   - Generated text for resume quality (first 50 chars): {result[:50]}...")
        print("   - LLM service with direct Nebius integration working!")
    except Exception as e:
        print(f"   - Error testing LLM service: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n=== TESTS COMPLETE ===\n")

if __name__ == "__main__":
    asyncio.run(test_direct_nebius())
