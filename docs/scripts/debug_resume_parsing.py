"""
Enhanced debug script for testing resume parsing with local Ollama models.
This script provides more detailed diagnostics and debugging information.
"""
import os
import sys
import json
import logging
import asyncio
from pathlib import Path
import traceback
import time

# Add the backend directory to the Python path
sys.path.append(str(Path(__file__).parent))

# Configure very verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('debug_parsing.log')  # Also save to file
    ]
)
logger = logging.getLogger(__name__)

# Extra debug for httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

async def test_ollama_connection():
    """Test basic connectivity to the Ollama service."""
    try:
        # Import here to handle path issues
        from backend.services.local_model_service import get_local_model_service
        import httpx
        
        logger.info("====== TESTING OLLAMA CONNECTION ======")
        
        # Try a direct API call
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                logger.info("Making direct request to Ollama API /api/tags")
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [model["name"] for model in models]
                    logger.info(f"✅ Ollama is responding. Available models: {model_names}")
                    for model in models:
                        logger.info(f"  - {model['name']} ({model.get('modified', 'unknown')})")
                else:
                    logger.error(f"❌ Ollama API responded with status code {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Failed to connect directly to Ollama API: {str(e)}")
            return False
            
        # Initialize the local model service
        logger.info("Initializing local model service...")
        local_model_service = get_local_model_service()
        
        # Check if Ollama is available via the service
        if await local_model_service.is_available():
            logger.info("✅ Ollama service is available via LocalModelService")
            return True
        else:
            logger.error("❌ Ollama service not available via LocalModelService")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing Ollama connection: {str(e)}")
        traceback.print_exc()
        return False

async def check_model_response_time(model_name="resume_parser:latest"):
    """Test basic model response time with a simple prompt."""
    try:
        from backend.services.local_model_service import get_local_model_service
        
        local_model_service = get_local_model_service()
        
        logger.info(f"====== TESTING BASIC MODEL RESPONSE: {model_name} ======")
        logger.info("Sending a simple prompt to test response time...")
        
        # Simple test prompt
        test_prompt = "Hello, please respond with a simple 'Hello, I am working properly' message if you can read this."
        
        # Time the response
        start_time = time.time()
        
        try:
            response = await local_model_service._generate_response(
                model_name=model_name,
                prompt=test_prompt,
                temperature=0.1,
                max_tokens=100
            )
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Received response in {elapsed:.2f} seconds")
            logger.info(f"Response: {response[:100]}...")
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Failed to get response after {elapsed:.2f} seconds: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing model response: {str(e)}")
        traceback.print_exc()
        return False

async def test_incremental_parsing(resume_path, chunk_percentage=100):
    """
    Test resume parsing with part of the resume to find size-related issues.
    
    Args:
        resume_path: Path to the resume file
        chunk_percentage: Percentage of the resume text to test (1-100)
    """
    try:
        from backend.services.local_model_service import get_local_model_service
        
        # Initialize the local model service
        local_model_service = get_local_model_service()
        
        # Load the resume text from PDF
        import PyPDF2
        with open(resume_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        
        # Calculate text to use based on chunk percentage
        text_length = len(full_text)
        use_length = int(text_length * (chunk_percentage / 100))
        resume_text = full_text[:use_length]
        
        logger.info(f"====== TESTING WITH {chunk_percentage}% OF RESUME ======")
        logger.info(f"Using {len(resume_text)} out of {text_length} characters")
        
        # Parse the resume using the local model
        logger.info(f"Parsing resume chunk with local model...")
        result = await local_model_service.parse_resume(resume_text)
        
        # Log the results
        if result:
            if result.get('personal_info', {}).get('name'):
                logger.info(f"✅ Successfully extracted name: {result['personal_info']['name']}")
            else:
                logger.warning("⚠️ No name extracted")
                
            skills_count = len(result.get('skills', []))
            education_count = len(result.get('education', []))
            experience_count = len(result.get('experience', []))
            
            logger.info(f"✅ Extracted {skills_count} skills, {education_count} education entries, {experience_count} experience entries")
            
            return True, result
        else:
            logger.error("❌ Failed to parse resume - empty result")
            return False, {}
            
    except Exception as e:
        logger.error(f"❌ Error during resume parsing: {str(e)}")
        traceback.print_exc()
        return False, {}

async def main():
    """Run the debug tests."""
    try:
        # Check ollama connection first
        ollama_available = await test_ollama_connection()
        if not ollama_available:
            logger.critical("❌ Ollama service is not available. Please start it and try again.")
            return
        
        # Check basic model response time
        model_responsive = await check_model_response_time()
        if not model_responsive:
            logger.warning("⚠️ Basic model response test failed. Continuing with other tests...")
        
        # Path to the PDF resume
        resume_path = Path(r"C:/Users/seaso/RecruitIQ/Jane_Smith_Resume.pdf")
        
        if not resume_path.exists():
            logger.critical(f"❌ Resume file not found: {resume_path}")
            return
            
        logger.info(f"Testing with resume: {resume_path}")
        
        # Try incremental parsing tests if full parsing is failing
        test_percentages = [100]
        
        for percentage in test_percentages:
            success, result = await test_incremental_parsing(resume_path, percentage)
            
            if success:
                # Only save results from successful parsing
                output_file = f"parsing_results_{percentage}pct.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Results for {percentage}% test saved to: {output_file}")
        
    except Exception as e:
        logger.critical(f"Critical error in main: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
