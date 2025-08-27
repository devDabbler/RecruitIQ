#!/usr/bin/env python
# backend/scripts/download_spacy_model.py
"""
Script to download the spaCy model required for resume parsing.
Run this script during setup to ensure the model is available.
"""

import os
import sys
import subprocess
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_spacy_model(model_name="en_core_web_lg"):
    """
    Download the specified spaCy model if it's not already installed.
    
    Args:
        model_name (str): Name of the spaCy model to download. Defaults to 'en_core_web_lg'.
        
    Returns:
        bool: True if model is successfully installed, False otherwise.
    """
    try:
        import spacy
        # Check if the model is already installed
        try:
            logger.info(f"Checking if spaCy model '{model_name}' is installed...")
            spacy.load(model_name)
            logger.info(f"spaCy model '{model_name}' is already installed.")
            return True
        except OSError:
            # Model is not installed, download it
            logger.info(f"Downloading spaCy model '{model_name}'...")
            max_retries = 3
            retry_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
                    logger.info(f"Successfully downloaded spaCy model '{model_name}'.")
                    return True
                except subprocess.CalledProcessError as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to download model after {max_retries} attempts: {e}")
                        return False
    except Exception as e:
        logger.error(f"Error downloading spaCy model: {e}")
        return False

if __name__ == "__main__":
    # Get model name from command line argument or use default
    model_name = sys.argv[1] if len(sys.argv) > 1 else "en_core_web_lg"
    
    success = download_spacy_model(model_name)
    if not success:
        sys.exit(1) 