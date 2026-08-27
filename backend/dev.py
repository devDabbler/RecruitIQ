#!/usr/bin/env python3
"""
Development script to start the RecruitIQ backend server.
This script handles dependency checks and starts the FastAPI server.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_and_install_uvicorn():
    """Check if uvicorn is installed and install it if missing."""
    try:
        import uvicorn
        print("✓ uvicorn is available")
        return True
    except ImportError:
        print("⚠ uvicorn not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]"])
            print("✓ uvicorn installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install uvicorn: {e}")
            return False

def start_server():
    """Start the FastAPI server using uvicorn."""
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Check dependencies
    if not check_and_install_uvicorn():
        print("Cannot start server without uvicorn")
        sys.exit(1)
    
    print("Starting RecruitIQ backend server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--reload", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ])
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server() 