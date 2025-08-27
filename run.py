import os
import subprocess
import sys
import logging
from pathlib import Path
import time
import requests

def setup_logging(debug_mode=False):
    """Set up logging configuration for the application."""
    log_level = logging.DEBUG if debug_mode else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('recruitiq.log')
        ]
    )
    
    # Create logger for this script
    logger = logging.getLogger('run')
    
    # Set more verbose logging for specific modules if in debug mode
    if debug_mode:
        logging.getLogger('backend').setLevel(logging.DEBUG)
        logging.getLogger('frontend').setLevel(logging.DEBUG)
    else:
        # Keep third-party libraries quiet in normal mode
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('streamlit').setLevel(logging.WARNING)
    
    return logger

def download_spacy_model():
    """Download the spaCy model required for resume parsing."""
    logger.info("Checking spaCy model...")
    spacy_cmd = ["poetry", "run", "python", "backend/scripts/download_spacy_model.py", "en_core_web_lg"]
    subprocess.run(spacy_cmd, check=True)
    logger.info("spaCy model check completed.")

def run_backend():
    """Run the FastAPI backend server."""
    logger.info("Starting backend server...")
    # Pass debug flag to backend if specified
    backend_cmd = ["poetry", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
    
    if debug_mode:
        backend_cmd.append("--log-level=debug")
        logger.debug(f"Backend command: {' '.join(backend_cmd)}")
    
    # Use shell=True on Windows to avoid subprocess issues
    if os.name == 'nt':  # Windows
        cmd_str = " ".join(backend_cmd)
        logger.debug(f"Running backend with shell=True: {cmd_str}")
        return subprocess.Popen(cmd_str, shell=True)
    else:
        return subprocess.Popen(backend_cmd)

def run_frontend():
    """Run the Streamlit frontend."""
    logger.info("Starting frontend...")
    
    # Set Streamlit debug mode using environment variables
    if debug_mode:
        os.environ["STREAMLIT_DEBUG"] = "true"
        os.environ["STREAMLIT_LOG_LEVEL"] = "debug"
        logger.debug("Set Streamlit debug environment variables")
    
    frontend_cmd = ["poetry", "run", "streamlit", "run", "frontend/app.py"]
    logger.debug(f"Frontend command: {' '.join(frontend_cmd)}")
    
    return subprocess.Popen(frontend_cmd)

def main():
    """Run both the backend and frontend."""
    try:
        # Download spaCy model if needed
        download_spacy_model()
        
        # Start the backend
        backend_process = run_backend()

        # Wait for backend health endpoint to be ready
        backend_ready = False
        max_wait = 90  # seconds
        poll_interval = 1
        health_url = "http://localhost:8000/health"
        logger.info(f"Waiting for backend health at {health_url} ...")
        for _ in range(max_wait):
            try:
                resp = requests.get(health_url, timeout=1)
                if resp.status_code == 200:
                    backend_ready = True
                    logger.info("Backend is healthy!")
                    break
            except Exception as e:
                logger.debug(f"Backend health check failed: {e}")
            time.sleep(poll_interval)
        if not backend_ready:
            logger.error(f"Backend did not become healthy at {health_url} after {max_wait} seconds. Exiting.")
            try:
                backend_process.terminate()
            except Exception:
                pass
            sys.exit(1)

        # Start the frontend
        frontend_process = run_frontend()
        
        logger.info("RecruitIQ is now running!")
        logger.info("Backend URL: http://localhost:8000")
        logger.info("Frontend URL: http://localhost:8501")
        
        # Keep the script running
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        try:
            backend_process.terminate()
            frontend_process.terminate()
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
        logger.info("Application stopped.")
        sys.exit(0)

if __name__ == "__main__":
    # Check for debug flag
    debug_mode = "--debug" in sys.argv
    
    # Setup logging
    logger = setup_logging(debug_mode)
    
    if debug_mode:
        logger.info("Running in DEBUG mode")
    
    main() 