"""
Test script for Nebius AI integration with microsoft/phi-4 model.
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.services.nebius_ai_service import NebiusAIService

async def test_nebius_ai():
    """Test the Nebius AI API with a simple prompt."""
    print("Testing Nebius AI with microsoft/phi-4 model...")
    
    # Check for API key
    api_key = os.environ.get("NEBIUS_API_KEY")
    print(f"API key found: {'Yes' if api_key else 'No'}")
    if api_key:
        # Print first few characters for verification (never print full API key)
        masked_key = api_key[:4] + '*' * (len(api_key) - 4) if len(api_key) > 4 else '****'
        print(f"API key starts with: {api_key[:4]} (masked: {masked_key})")
    
    if not api_key:
        print("ERROR: NEBIUS_API_KEY not found in .env file or environment variables.")
        print("Please add your Nebius API key to the .env file:")
        print("  NEBIUS_API_KEY=your-api-key")
        return
    
    # Initialize the service with custom config
    config = {
        "nebius_base_url": "https://api.studio.nebius.com/v1/",
        "model": "microsoft/phi-4",
        "api_key": api_key,
        "timeout": 120.0,
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    service = NebiusAIService(config)
    
    try:
        # Test resume parsing with a sample resume snippet
        sample_resume = """
        John Doe
        Software Engineer
        john.doe@example.com | (123) 456-7890 | Seattle, WA
        
        SUMMARY
        Experienced software engineer with 5+ years of experience in full-stack development,
        specializing in Python, React, and cloud technologies.
        
        EXPERIENCE
        Senior Software Engineer | TechCorp Inc. | Seattle, WA | 2020-Present
        - Led development of microservices architecture using Python and FastAPI
        - Implemented CI/CD pipelines reducing deployment time by 40%
        - Mentored junior developers and conducted code reviews
        
        Software Engineer | WebSolutions LLC | Portland, OR | 2018-2020
        - Developed responsive web applications using React and Node.js
        - Optimized database queries resulting in 30% performance improvement
        
        EDUCATION
        University of Washington | Seattle, WA
        M.S. Computer Science | 2018
        
        Oregon State University | Corvallis, OR
        B.S. Computer Science | 2016
        
        SKILLS
        Languages: Python, JavaScript, TypeScript, SQL
        Frameworks: React, FastAPI, Express, Django
        Tools: Git, Docker, Kubernetes, AWS, Azure
        """
        
        print("\nTesting resume parsing...")
        
        # Define the schema prompt for the model
        schema_prompt = """
Extract the following information from the resume text and return it as a valid JSON object.

The JSON object must follow this structure:
{
  "personal_info": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string"
  },
  "experience": [
    {
      "title": "string",
      "company": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string",
      "description": "string"
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "end_date": "string"
    }
  ],
  "skills": [
    { "name": "string" }
  ]
}

CRITICAL INSTRUCTIONS:
1.  Each entry in the 'experience' array must be an object with 'title', 'company', and 'description'.
2.  Each entry in the 'skills' array must be an object with a 'name' key.
3.  Your response must be ONLY the JSON object, with no extra text, explanations, or markdown.
"""

        start_time = asyncio.get_event_loop().time()
        resume_data = await service.parse_resume(sample_resume, schema_prompt)
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        print(f"\nResume parsing completed in {elapsed_time:.2f} seconds:")
        print("-" * 80)
        print(json.dumps(resume_data.model_dump(), indent=2))
        print("-" * 80)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_nebius_ai())
