#!/usr/bin/env python3
"""
Poetry-aware wrapper for running candidate cleanup scripts.
This ensures the scripts run within the correct Poetry environment.
"""

import sys
import subprocess
import os
from pathlib import Path

def check_poetry_environment():
    """Check if we're running in a Poetry environment"""
    virtual_env = os.getenv('VIRTUAL_ENV')
    poetry_active = os.getenv('POETRY_ACTIVE')
    
    if virtual_env and 'pypoetry' in virtual_env.lower():
        return True
    if poetry_active:
        return True
    
    return False

def run_with_poetry(script_name, args):
    """Run script using poetry run"""
    cmd = ['poetry', 'run', 'python', script_name] + args
    print(f"🚀 Running: {' '.join(cmd)}")
    return subprocess.run(cmd)

def run_direct(script_name, args):
    """Run script directly (assuming we're in Poetry shell)"""
    cmd = ['python', script_name] + args
    print(f"🚀 Running: {' '.join(cmd)}")
    return subprocess.run(cmd)

def main():
    print("🧹 RecruitIQ Candidate Cleanup Tool")
    print("=" * 50)
    
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_cleanup.py safe [--live] [--force]     # Run safe script (recommended)")
        print("  python run_cleanup.py basic [--force]            # Run basic script")
        print("  python run_cleanup.py config                     # Edit configuration")
        print("\nExamples:")
        print("  python run_cleanup.py safe                       # Dry-run analysis")
        print("  python run_cleanup.py safe --live                # Live deletion")
        print("  python run_cleanup.py basic                      # Basic script")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Handle config command
    if command == 'config':
        config_file = Path('cleanup_config.py')
        if config_file.exists():
            print(f"📝 Edit configuration file: {config_file.absolute()}")
            print("\nUpdate your database credentials in cleanup_config.py")
        else:
            print("❌ Configuration file not found!")
            print("Make sure cleanup_config.py exists in the current directory.")
        sys.exit(0)
    
    # Determine script to run
    if command == 'safe':
        script_name = 'cleanup_all_candidates_safe.py'
        print("🛡️  Running SAFE cleanup script")
        if '--live' not in args:
            print("🔍 DRY-RUN mode (no data will be deleted)")
        else:
            print("⚠️  LIVE mode (data WILL be deleted)")
    elif command == 'basic':
        script_name = 'cleanup_all_candidates.py'
        print("⚡ Running BASIC cleanup script")
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'safe', 'basic', or 'config'")
        sys.exit(1)
    
    # Check if script exists
    script_path = Path(script_name)
    if not script_path.exists():
        print(f"❌ Script not found: {script_name}")
        print("Make sure all cleanup scripts are in the current directory.")
        sys.exit(1)
    
    # Check Poetry environment and run appropriately
    if check_poetry_environment():
        print("✅ Poetry environment detected")
        result = run_direct(script_name, args)
    else:
        print("🔧 Running with 'poetry run'")
        result = run_with_poetry(script_name, args)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main() 