#!/usr/bin/env python3
"""
RecruitIQ Frontend Startup Script
Run this script from the root directory to start the frontend application.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Start the RecruitIQ frontend application."""
    # Get the root directory (where this script is located)
    root_dir = Path(__file__).parent
    frontend_dir = root_dir / "frontend"
    app_file = frontend_dir / "app.py"
    
    # Check if frontend directory and app.py exist
    if not frontend_dir.exists():
        print("❌ Frontend directory not found!")
        print(f"Expected: {frontend_dir}")
        print("Make sure you're running this script from the RecruitIQ root directory.")
        sys.exit(1)
    
    if not app_file.exists():
        print("❌ app.py not found in frontend directory!")
        print(f"Expected: {app_file}")
        sys.exit(1)
    
    # Check if streamlit is available
    try:
        subprocess.check_call([sys.executable, "-c", "import streamlit"], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
        print("✅ streamlit is available")
    except subprocess.CalledProcessError:
        print("⚠️  streamlit not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
            print("✅ streamlit installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install streamlit: {e}")
            print("Please install streamlit manually: pip install streamlit")
            sys.exit(1)
    
    print("🚀 Starting RecruitIQ Frontend Application...")
    print(f"📁 Working directory: {frontend_dir}")
    print("\n🌐 Application will be available at:")
    print("   • Local URL: http://localhost:8501")
    print("   • Network URL: http://localhost:8501")
    print("\n💡 To stop the application, press Ctrl+C")
    print("=" * 50)
    
    try:
        # Change to frontend directory and start streamlit
        os.chdir(frontend_dir)
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port=8501",
            "--server.address=localhost"
        ])
    except KeyboardInterrupt:
        print("\n\n🛑 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 