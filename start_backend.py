#!/usr/bin/env python3
"""
RecruitIQ Backend Startup Script
Run this script from the root directory to start the backend server.
"""

import subprocess
import sys
import os

# Ensure all agents are registered at startup
import backend.services.agent_framework.agents

from pathlib import Path

def main():
    """Start the RecruitIQ backend server."""
    # Get the root directory (where this script is located)
    root_dir = Path(__file__).parent
    backend_dir = root_dir / "backend"
    
    # Check if backend directory exists
    if not backend_dir.exists():
        print("❌ Backend directory not found!")
        print(f"Expected: {backend_dir}")
        print("Make sure you're running this script from the RecruitIQ root directory.")
        sys.exit(1)
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    print("🚀 Starting RecruitIQ Backend Server...")
    print(f"📁 Working directory: {backend_dir}")
    
    # Check if uvicorn is available
    try:
        subprocess.check_call([sys.executable, "-c", "import uvicorn"], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        print("✅ uvicorn is available")
    except subprocess.CalledProcessError:
        print("⚠️  uvicorn not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]"])
            print("✅ uvicorn installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install uvicorn: {e}")
            print("Please install uvicorn manually: pip install uvicorn[standard]")
            sys.exit(1)
    
    print("\n🌐 Server will be available at:")
    print("   • Main API: http://localhost:8000")  
    print("   • Documentation: http://localhost:8000/docs")
    print("   • Interactive docs: http://localhost:8000/redoc")
    print("\n💡 To stop the server, press Ctrl+C")
    print("=" * 50)
    
    try:
        # Start the server using the main.py file in backend directory
        # Start the server with verbose output
        command = [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "localhost",
            "--port", "8000",
            "--reload"
        ]
        print(f"\n▶️  Running command: {' '.join(command)}\n")
        subprocess.run(command)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except FileNotFoundError:
        print("❌ main.py not found in backend directory")
        print("Make sure the backend/main.py file exists")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 