import sys
import logging
from pathlib import Path

# Configure basic logging to see output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] # Ensure output to stdout
)
logger = logging.getLogger(__name__)

logger.info("Attempting to set up sys.path...")
# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
logger.info(f"sys.path prepended with: {backend_dir}")
logger.info(f"Current sys.path: {sys.path}")

import spacy

try:
    logger.info("Attempting to load spaCy model en_core_web_lg...")
    nlp = spacy.load('en_core_web_lg')
    logger.info("Successfully loaded spaCy model en_core_web_lg.")
    logger.info("Test script completed successfully.")
    
except Exception as e:
    logger.error(f"Exception during spaCy model loading: {e}", exc_info=True)
    logger.error("This indicates an issue with the spaCy installation or the model itself.")
