"""
Development server with hot reloading for both frontend and backend
"""
import subprocess
import sys
import os
from pathlib import Path
import webbrowser
from threading import Thread
import time

# Get the absolute path of the project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

def run_backend():
    """Run the backend server with hot reloading"""
    backend_dir = PROJECT_ROOT / "backend"
    os.chdir(backend_dir)
    subprocess.run([sys.executable, "dev.py"])

def run_frontend():
    """Run the frontend server with hot reloading"""
    frontend_dir = PROJECT_ROOT / "frontend"
    os.chdir(frontend_dir)
    subprocess.run([sys.executable, "app.py"])

def open_browser():
    """Open the browser after a short delay"""
    time.sleep(2)  # Wait for servers to start
    webbrowser.open("http://localhost:5000")  # Frontend URL

if __name__ == "__main__":
    # Start backend in a separate thread
    backend_thread = Thread(target=run_backend)
    backend_thread.daemon = True
    backend_thread.start()

    # Start frontend in a separate thread
    frontend_thread = Thread(target=run_frontend)
    frontend_thread.daemon = True
    frontend_thread.start()

    # Open browser
    browser_thread = Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down development servers...")
        sys.exit(0) 