#!/usr/bin/env python3
"""
Start script for the RecruitIQ backend server.
This script starts the FastAPI server using uvicorn.
"""

import subprocess
import sys
import os
from pathlib import Path

def start_backend():
    """Start the FastAPI backend server."""
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("🚀 Starting RecruitIQ Backend Server...")
    print("📁 Working directory:", backend_dir)
    
    # Check if uvicorn is available
    try:
        import uvicorn
        print("✅ uvicorn is available")
    except ImportError:
        print("❌ uvicorn not found. Please install it with: pip install uvicorn")
        sys.exit(1)
    
    print("\n🌐 Server will be available at:")
    print("   • Main API: http://localhost:8000")
    print("   • Documentation: http://localhost:8000/docs")
    print("   • Interactive docs: http://localhost:8000/redoc")
    print("\n💡 To stop the server, press Ctrl+C")
    print("=" * 50)
    
    try:
        # Start the server using uvicorn
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
    start_backend() 