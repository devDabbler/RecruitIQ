#!/usr/bin/env python3
"""
Setup Verification Script
Checks if all components are properly configured
"""

import os
import sys
from pathlib import Path
import importlib.util

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking Dependencies...")
    
    required_packages = [
        'pypdf', 'PyPDF2', 'docx2txt', 'pydantic', 'yaml', 'spacy'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: poetry install")
        return False
    
    return True

def check_config_files():
    """Check if YAML config files exist"""
    print("\n🔍 Checking Configuration Files...")
    
    config_dir = Path("backend/config")
    required_configs = [
        'common_words.yaml',
        'skill_categories.yaml',
        'experience_keywords.yaml',
        'section_patterns.yaml',
        'job_extraction_patterns.yaml',
        'resume_patterns.yaml'
    ]
    
    missing_configs = []
    for config_file in required_configs:
        config_path = config_dir / config_file
        if config_path.exists():
            print(f"  ✅ {config_file}")
        else:
            print(f"  ❌ {config_file} - MISSING")
            missing_configs.append(config_file)
    
    if missing_configs:
        print(f"\n❌ Missing config files: {', '.join(missing_configs)}")
        print("These will be created automatically on first run.")
    
    return len(missing_configs) == 0

def check_parser_imports():
    """Check if parser can be imported"""
    print("\n🔍 Checking Parser Imports...")
    
    try:
        sys.path.insert(0, str(Path("backend")))
        from utils.enhanced_resume_parser import EnhancedResumeParser
        print("  ✅ EnhancedResumeParser imported successfully")
        
        # Try to initialize
        parser = EnhancedResumeParser()
        print("  ✅ Parser initialized successfully")
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Initialization error: {e}")
        return False

def check_resume_file():
    """Check if test resume file exists"""
    print("\n🔍 Checking Test Resume File...")
    
    resume_paths = [
        "Sean B. Collins Resume - Recruiting Leader.pdf",
        "backend/test_data/Sean B. Collins Resume - Recruiting Leader.pdf",
        "test_data/Sean B. Collins Resume - Recruiting Leader.pdf"
    ]
    
    for path in resume_paths:
        if os.path.exists(path):
            print(f"  ✅ Resume found: {path}")
            return path
    
    print("  ❌ Test resume file not found")
    print("  Expected locations:")
    for path in resume_paths:
        print(f"    - {path}")
    
    return None

def check_api_server():
    """Check if API server is running"""
    print("\n🔍 Checking API Server...")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            print("  ✅ API server is running on port 8000")
            return True
        else:
            print(f"  ❌ API server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  ❌ API server is not running")
        print("  Start with: poetry run uvicorn backend.main:app --reload")
        return False
    except ImportError:
        print("  ⚠️  requests not installed (needed for API tests)")
        return False
    except Exception as e:
        print(f"  ❌ Error checking API server: {e}")
        return False

def main():
    """Main verification function"""
    print("🧪 RECRUITIQ SETUP VERIFICATION")
    print("=" * 40)
    
    # Run all checks
    checks = [
        ("Dependencies", check_dependencies),
        ("Configuration Files", check_config_files),
        ("Parser Imports", check_parser_imports),
        ("Test Resume File", check_resume_file),
        ("API Server", check_api_server)
    ]
    
    results = {}
    for check_name, check_func in checks:
        results[check_name] = check_func()
    
    # Summary
    print("\n📋 VERIFICATION SUMMARY")
    print("=" * 25)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check_name}: {status}")
        if not passed:
            all_passed = False
    
    # Recommendations
    print("\n🔧 RECOMMENDATIONS")
    print("=" * 20)
    
    if not results.get("Dependencies"):
        print("1. Install dependencies: poetry install")
    
    if not results.get("Parser Imports"):
        print("2. Fix import issues - check Python path and dependencies")
    
    if not results.get("Test Resume File"):
        print("3. Place test resume file in project root or test_data/ folder")
        print("   You can use any PDF resume for testing")
    
    if not results.get("API Server"):
        print("4. Start API server: poetry run uvicorn backend.main:app --reload")
        print("   (Only needed for API tests)")
    
    if all_passed:
        print("🎉 ALL CHECKS PASSED! Ready to run tests.")
        print("\nAvailable test commands:")
        print("  - Direct parser test: poetry run python backend/scripts/test_enhanced_parser_direct.py")
        print("  - API test: poetry run python backend/scripts/test_enhanced_api.py")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")

if __name__ == "__main__":
    main()