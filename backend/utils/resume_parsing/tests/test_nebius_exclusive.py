"""
Test script to verify ONLY Nebius AI is used for resume-related tasks and Meta Llama is completely disabled.
"""
import asyncio
import logging
import sys

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Set specific loggers to DEBUG level for more detailed information
logging.getLogger('backend.services.llm_service').setLevel(logging.DEBUG)
logging.getLogger('backend.services.nebius_ai_service').setLevel(logging.DEBUG)

# Import services
from services.llm_service import get_llm_service, verify_llm_connections

async def test_meta_llama_disabled():
    """Test that Meta Llama is completely disabled and Nebius AI is used for resume tasks."""
    print("\n=== TESTING NEBIUS AI EXCLUSIVE USAGE ===\n")
    
    # Get LLM service
    llm_service = get_llm_service()
    
    # Check connection status - Meta Llama should be FALSE
    print("\n1. Checking LLM connection status (Meta Llama should be FALSE):")
    connection_status = verify_llm_connections(llm_service)
    print(f"   Meta Llama enabled: {connection_status.get('meta_llama', 'Unknown')}")
    print(f"   Nebius AI enabled: {connection_status.get('nebius_ai', 'Unknown')}")
    
    # Try to initialize Meta Llama directly - should log warning and return False
    print("\n2. Attempting to initialize Meta Llama directly (should fail):")
    result = llm_service._initialize_meta_llama()
    print(f"   Meta Llama initialization result: {result}")
    print(f"   Meta Llama model available: {llm_service.meta_llama_model is not None}")
    
    # Test a resume quality task - should use Nebius AI
    print("\n3. Testing resume quality assessment task (should use Nebius AI):")
    try:
        resume_prompt = "Analyze this resume summary for quality: John Smith, Senior Software Engineer..."
        result = await llm_service.generate_text(
            prompt=resume_prompt, 
            task_type="resume_quality"
        )
        print(f"   Result received, first 50 chars: {result[:50]}...")
    except Exception as e:
        print(f"   Error: {str(e)}")
    
    print("\n=== TEST COMPLETE ===\n")

if __name__ == "__main__":
    asyncio.run(test_meta_llama_disabled())
