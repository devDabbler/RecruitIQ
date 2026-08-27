#!/usr/bin/env python
"""
Script to create and train a custom resume parser model with Ollama.
This handles the end-to-end process of generating training data, creating the model,
and setting up the local parser.
"""
import os
import logging
import asyncio
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_ollama_available():
    """Check if Ollama is available on the system."""
    try:
        # Try to run 'ollama list' command
        result = subprocess.run(['ollama', 'list'], 
                               capture_output=True, 
                               text=True,
                               check=False)
        
        if result.returncode == 0:
            logger.info("Ollama is available.")
            return True
        else:
            logger.error(f"Ollama check failed: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.error("Ollama not found. Please install Ollama first.")
        return False
    except Exception as e:
        logger.error(f"Error checking Ollama: {str(e)}")
        return False

async def generate_training_data(num_samples=100):
    """Generate training data from existing resumes."""
    logger.info(f"Generating training data from {num_samples} resume samples...")
    
    try:
        # Import data generation script
        from backend.scripts.create_parsing_dataset import create_parsing_dataset
        
        # Run the data generation
        result = await create_parsing_dataset(num_samples=num_samples)
        
        logger.info(f"Training data generation complete: {result['train_examples']} training examples")
        logger.info(f"Test data generation complete: {result['test_examples']} test examples")
        
        return result
    except Exception as e:
        logger.error(f"Error generating training data: {str(e)}")
        logger.error("Make sure the database contains parsed resumes.")
        return None

async def train_resume_parser():
    """Create and train the resume parsing model with Ollama."""
    # Paths
    base_dir = Path(".")
    model_dir = base_dir / "training_data" / "parsing"
    model_file = model_dir / "Modelfile"
    
    # Check if Modelfile exists
    if not model_file.exists():
        logger.error(f"Modelfile not found at {model_file}")
        return False
        
    logger.info("Creating resume-parser model with Ollama...")
    
    try:
        # Create the model
        result = subprocess.run(
            ["ollama", "create", "resume-parser", "-f", str(model_file)],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Error creating model: {result.stderr}")
            return False
            
        logger.info("Resume parser model created successfully!")
        
        # Check if training file exists
        training_file = model_dir / "resume_parsing.txt"
        if training_file.exists():
            logger.info(f"Training file found at {training_file}")
            logger.info("You can modify the model with: ollama create resume-parser -f ./training_data/parsing/Modelfile")
        
        return True
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        return False

async def pull_llama_model():
    """Check for an existing Llama 3 model to use as a base."""
    logger.info("Checking for Llama 3 model...")
    
    try:
        # Check if model already exists
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False
        )
        
        # First check for llama3:latest (which we saw in the user's installation)
        if "llama3:latest" in result.stdout:
            logger.info("Llama 3 model (latest) already available.")
            return True
        # Then check for other llama3 variations
        elif "llama3:8b" in result.stdout:
            logger.info("Llama 3 8B model already available.")
            return True
        elif "llama3" in result.stdout:
            logger.info("Llama 3 model already available.")
            return True
            
        # Pull the model - try latest first
        logger.info("No Llama 3 model found. Attempting to download llama3:latest...")
        result = subprocess.run(
            ["ollama", "pull", "llama3:latest"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Error pulling Llama model: {result.stderr}")
            return False
            
        logger.info("Llama 3 model pulled successfully!")
        return True
    except Exception as e:
        logger.error(f"Error pulling Llama model: {str(e)}")
        return False

async def test_model():
    """Test the created model with a sample resume."""
    logger.info("Testing resume parser model...")
    
    try:
        # Import local model service
        from backend.services.local_model_service import get_local_model_service
        
        # Sample resume text
        sample_resume = """
        John Doe
        San Francisco, CA | (123) 456-7890 | john.doe@example.com
        
        EXPERIENCE
        Senior Software Engineer, ABC Tech (2020-Present)
        - Led development of payment processing system using Python and FastAPI
        - Managed a team of 5 developers
        
        Software Developer, XYZ Corp (2018-2020)
        - Implemented RESTful APIs using Django
        - Improved system performance by 30%
        
        EDUCATION
        Stanford University (2014-2018)
        Bachelor of Science in Computer Science
        
        SKILLS
        Python, JavaScript, SQL, AWS, Docker, Kubernetes
        """
        
        # Get local model service
        local_model_service = get_local_model_service()
        
        # Parse the sample resume
        result = await local_model_service.parse_resume(sample_resume)
        
        if result:
            logger.info("Model test successful!")
            logger.info(f"Parsed result: {result}")
            return True
        else:
            logger.error("Model test failed - empty result returned")
            return False
    except Exception as e:
        logger.error(f"Error testing model: {str(e)}")
        return False

async def main():
    """Run the training pipeline."""
    print("\n===== RESUME PARSER TRAINING PIPELINE =====\n")
    
    # Step 1: Check if Ollama is available
    if not await check_ollama_available():
        print("\nERROR: Ollama not available. Please install Ollama first.")
        print("Visit https://ollama.com/download for installation instructions.")
        return
    
    # Step 2: Pull base model if needed
    print("\n----- Step 1: Pulling Base Model -----")
    if not await pull_llama_model():
        print("\nERROR: Failed to pull Llama model. Check your internet connection.")
        return
    
    # Step 3: Generate training data
    print("\n----- Step 2: Generating Training Data -----")
    data_result = await generate_training_data(num_samples=50)  # Start with a smaller sample for testing
    if not data_result:
        print("\nERROR: Failed to generate training data.")
        return
    
    # Step 4: Create and train the model
    print("\n----- Step 3: Creating Resume Parser Model -----")
    if not await train_resume_parser():
        print("\nERROR: Failed to create resume parser model.")
        return
    
    # Step 5: Test the model
    print("\n----- Step 4: Testing Resume Parser Model -----")
    if not await test_model():
        print("\nWARNING: Model test failed. The model may need additional training.")
    
    # Success message
    print("\n===== TRAINING PIPELINE COMPLETE =====")
    print("""
Next steps:
1. Run `python -m backend.scripts.evaluate_parsing_models` to compare model performance
2. The local model will automatically be used by the parse service when available
3. You can retrain the model anytime by running this script again
4. To improve model performance:
   - Add more training examples
   - Adjust the model parameters in the Modelfile
   - Consider using a larger base model (e.g., llama3:70b)
""")

if __name__ == "__main__":
    asyncio.run(main())
