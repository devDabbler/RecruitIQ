"""
Test script to verify Nebius AI is used for all resume-related tasks.
"""
import asyncio
import logging
import sys

# Configure logging to see which LLM is being used
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Import the LLM service
from services.llm_service import get_llm_service

async def test_resume_tasks():
    """Test various resume-related tasks to ensure they all use Nebius AI."""
    print("\n=== TESTING NEBIUS AI USAGE FOR ALL RESUME-RELATED TASKS ===\n")
    
    # Get LLM service
    llm_service = get_llm_service()
    
    # Test different resume-related tasks
    tasks = [
        {
            "name": "Resume Parsing",
            "prompt": "Extract structured data from this resume: John Smith, Software Engineer...",
            "task_type": "resume_parsing"
        },
        {
            "name": "Resume Quality Assessment",
            "prompt": "Analyze this resume and provide quality feedback for: John Smith, Software Engineer...",
            "task_type": "resume_quality"
        },
        {
            "name": "Skill Extraction",
            "prompt": "Extract skills from this resume: John Smith, Software Engineer with Python, JavaScript...",
            "task_type": "skill_extraction"
        },
        {
            "name": "Resume Formatting",
            "prompt": "Provide formatting suggestions for this resume: John Smith, Software Engineer...",
            "task_type": "resume_format"
        }
    ]
    
    # Run each task and observe which LLM is used
    for task in tasks:
        print(f"\nTesting task: {task['name']} with task_type: {task['task_type']}")
        try:
            result = await llm_service.generate_text(
                prompt=task["prompt"],
                task_type=task["task_type"]
            )
            print(f"Result (truncated): {result[:100]}...\n")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_resume_tasks())
