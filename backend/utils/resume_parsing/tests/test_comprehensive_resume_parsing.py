#!/usr/bin/env python3
"""
Comprehensive test to verify resume parsing with real PDF resumes.
This test uses actual resume files to ensure parsing works correctly
with both Nebius AI and regex extraction methods.
"""
import sys
import os
import asyncio
import logging
import json
import PyPDF2
from pathlib import Path
sys.path.append('.')

from utils.resume_parsing.nebius_ai_parser import NebiusAIResumeParser
from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from frontend.utils.ui_helpers import fix_merged_text
from backend.services.nebius_ai_service import NebiusAIService

def load_config():
    """Load configuration from config.json with environment variable substitution"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
    default_config = {
        "ollama_endpoint": "http://localhost:11434/api/generate",
        "model": "resume-parser:latest",
        "timeout": 30.0,
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            try:
                loaded_config = json.load(f)
                # Handle environment variable substitution
                for key, value in loaded_config.items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]  # Remove ${ and }
                        loaded_config[key] = os.environ.get(env_var, "")
                        logging.info(f"Substituted {key} with environment variable {env_var}")
                default_config.update(loaded_config)
                logging.info(f"Loaded configuration from {config_path}")
            except json.JSONDecodeError:
                logging.error(f"Error parsing config file {config_path}")
    else:
        logging.warning(f"Config file not found at {config_path}, using defaults")
        
    return default_config

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""

def find_resume_files() -> list:
    """Find specific resume files for testing."""
    resume_files = []
    current_dir = Path.cwd()
    
    # Look specifically for Roger Waters resume
    target_files = ["Roger Waters Resume.pdf"]
    
    for target_file in target_files:
        file_path = current_dir / target_file
        if file_path.exists():
            resume_files.append(str(file_path))
        else:
            # If specific file not found, look for any PDF with "Roger" in the name
            for pdf_file in current_dir.rglob("*.pdf"):
                if "roger" in pdf_file.name.lower():
                    resume_files.append(str(pdf_file))
                    break
    
    # If still no files found, get just the first few PDF files
    if not resume_files:
        pdf_files = list(current_dir.rglob("*.pdf"))
        # Skip obvious non-resume files
        for pdf_file in pdf_files[:3]:  # Only test first 3 files
            filename = pdf_file.name.lower()
            if any(skip in filename for skip in ['invoice', 'receipt', 'contract', 'manual', 'guide']):
                continue
            resume_files.append(str(pdf_file))
    
    return resume_files

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_comprehensive_resume_parsing():
    """Test comprehensive resume parsing with real PDF resumes."""
    
    print("🧪 Testing Comprehensive Resume Parsing with Real PDF Resumes")
    print("=" * 70)
    
    # Find resume files
    resume_files = find_resume_files()
    if not resume_files:
        print("❌ No PDF resume files found in current directory or subdirectories")
        print("   Please ensure you have PDF resume files available for testing")
        return
    
    print(f"📁 Found {len(resume_files)} potential resume files:")
    for i, file_path in enumerate(resume_files, 1):
        print(f"   {i}. {os.path.basename(file_path)}")
    
    # Initialize Nebius AI service
    config = load_config()
    nebius_service = NebiusAIService(config)
    
    # Initialize parsers
    nebius_parser = NebiusAIResumeParser(nebius_service)
    regex_extractor = RegexExtractor()
    
    # Test each resume file
    for i, resume_file in enumerate(resume_files, 1):
        print(f"\n{'='*80}")
        print(f"📄 Testing Resume {i}/{len(resume_files)}: {os.path.basename(resume_file)}")
        print(f"{'='*80}")
        
        # Extract text from PDF
        print(f"\n📖 Extracting text from PDF...")
        resume_text = extract_text_from_pdf(resume_file)
        
        if not resume_text.strip():
            print("   ❌ Failed to extract text from PDF")
            continue
        
        print(f"   ✅ Extracted {len(resume_text)} characters of text")
        print(f"   📝 Preview: {resume_text[:200]}...")
        
        # Test 1: Direct regex extraction
        print(f"\n📋 Test 1: Direct Regex Extraction")
        print("-" * 50)
        
        try:
            # Test regex extraction on the full resume text
            experience = await regex_extractor._extract_experience(resume_text)
            
            if experience:
                print(f"   ✅ Found {len(experience)} experience entries")
                for j, exp in enumerate(experience, 1):
                    print(f"   📝 Experience {j}: {exp.title} at {exp.company}")
                    print(f"      Description length: {len(exp.description) if exp.description else 0}")
                    print(f"      Bullet points count: {exp.get_bullet_count()}")
                    
                    bullet_points = exp.get_bullet_points()
                    if bullet_points:
                        print(f"      Bullet points extracted:")
                        for k, bullet in enumerate(bullet_points[:3], 1):  # Show first 3 bullets
                            print(f"        {k}. {bullet[:80]}{'...' if len(bullet) > 80 else ''}")
                        if len(bullet_points) > 3:
                            print(f"        ... and {len(bullet_points) - 3} more")
                    else:
                        print(f"      ⚠️  No bullet points extracted")
            else:
                print(f"   ❌ No experience entries found")
                
        except Exception as e:
            print(f"   ❌ Error during regex extraction: {e}")
        
        # Test 2: Full Nebius AI parsing
        print(f"\n📋 Test 2: Full Nebius AI Parsing")
        print("-" * 50)
        
        try:
            # Parse the full resume with Nebius AI with timeout
            import asyncio
            resume_data = await asyncio.wait_for(
                nebius_parser.parse_resume_fast(resume_text),
                timeout=60.0  # 60 second timeout
            )
            
            print(f"   ✅ Nebius AI parsing completed successfully")
            print(f"   📊 Parsing Results:")
            
            # Personal Info
            if resume_data.personal_info:
                print(f"      - Name: {resume_data.personal_info.name or 'Not found'}")
                print(f"      - Email: {resume_data.personal_info.email or 'Not found'}")
                print(f"      - Phone: {resume_data.personal_info.phone or 'Not found'}")
                print(f"      - Location: {resume_data.personal_info.location or 'Not found'}")
            else:
                print(f"      - Personal Info: None extracted")
            
            # Experience
            print(f"      - Experience entries: {len(resume_data.experience)}")
            for j, exp in enumerate(resume_data.experience, 1):
                print(f"        {j}. {exp.title} at {exp.company}")
                print(f"           Description length: {len(exp.description) if exp.description else 0}")
                print(f"           Bullet points count: {exp.get_bullet_count()}")
                
                bullet_points = exp.get_bullet_points()
                if bullet_points:
                    print(f"           Bullet points extracted:")
                    for k, bullet in enumerate(bullet_points[:2], 1):  # Show first 2 bullets
                        print(f"             {k}. {bullet[:60]}{'...' if len(bullet) > 60 else ''}")
                    if len(bullet_points) > 2:
                        print(f"             ... and {len(bullet_points) - 2} more")
                else:
                    print(f"           ⚠️  No bullet points extracted")
            
            # Education
            print(f"      - Education entries: {len(resume_data.education)}")
            for j, edu in enumerate(resume_data.education, 1):
                print(f"        {j}. {edu.degree} from {edu.institution}")
            
            # Skills
            print(f"      - Skills: {len(resume_data.skills)}")
            if resume_data.skills:
                skill_names = [skill.name for skill in resume_data.skills[:5]]  # Show first 5
                print(f"        Sample skills: {', '.join(skill_names)}")
                if len(resume_data.skills) > 5:
                    print(f"        ... and {len(resume_data.skills) - 5} more")
                    
        except asyncio.TimeoutError:
            print(f"   ❌ Nebius AI parsing timed out after 60 seconds")
        except Exception as e:
            print(f"   ❌ Error during Nebius AI parsing: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Compare extraction methods
        print(f"\n📋 Test 3: Method Comparison")
        print("-" * 50)
        
        try:
            # Get regex results
            regex_experience = await regex_extractor._extract_experience(resume_text)
            regex_count = len(regex_experience) if regex_experience else 0
            
            # Get Nebius AI results with timeout
            try:
                nebius_data = await asyncio.wait_for(
                    nebius_parser.parse_resume_fast(resume_text),
                    timeout=60.0
                )
                nebius_count = len(nebius_data.experience) if nebius_data and nebius_data.experience else 0
            except asyncio.TimeoutError:
                print(f"   ⚠️  Nebius AI comparison timed out")
                nebius_count = 0
            
            print(f"   📊 Comparison Results:")
            print(f"      - Regex extraction found: {regex_count} experience entries")
            print(f"      - Nebius AI found: {nebius_count} experience entries")
            
            if regex_count > 0 and nebius_count > 0:
                print(f"      - ✅ Both methods found experience data")
            elif regex_count > 0:
                print(f"      - ⚠️  Only regex extraction found experience data")
            elif nebius_count > 0:
                print(f"      - ⚠️  Only Nebius AI found experience data")
            else:
                print(f"      - ❌ Neither method found experience data")
                
        except Exception as e:
            print(f"   ❌ Error during comparison: {e}")
        
        print(f"\n✅ Completed testing for {os.path.basename(resume_file)}")
    
    print(f"\n{'='*80}")
    print(f"🎉 Completed comprehensive testing of {len(resume_files)} resume files")
    print(f"{'='*80}")

def test_text_cleaning_on_full_resume():
    """Test text cleaning functionality on real resume text."""
    print("\n🧹 Testing Text Cleaning on Real Resume")
    print("=" * 50)
    
    resume_files = find_resume_files()
    if not resume_files:
        print("❌ No PDF resume files found for text cleaning test")
        return
    
    # Use the first resume file for text cleaning test
    resume_file = resume_files[0]
    print(f"📄 Using: {os.path.basename(resume_file)}")
    
    # Extract text
    raw_text = extract_text_from_pdf(resume_file)
    if not raw_text.strip():
        print("❌ Failed to extract text from PDF")
        return
    
    print(f"📖 Raw text length: {len(raw_text)} characters")
    print(f"📝 Raw text preview: {raw_text[:300]}...")
    
    # Apply text cleaning
    try:
        cleaned_text = fix_merged_text(raw_text)
        print(f"\n🧹 Cleaned text length: {len(cleaned_text)} characters")
        print(f"📝 Cleaned text preview: {cleaned_text[:300]}...")
        
        # Show differences
        if len(raw_text) != len(cleaned_text):
            print(f"📊 Text length changed: {len(raw_text)} → {len(cleaned_text)} characters")
        else:
            print(f"📊 Text length unchanged: {len(raw_text)} characters")
            
    except Exception as e:
        print(f"❌ Error during text cleaning: {e}")

if __name__ == "__main__":
    asyncio.run(test_comprehensive_resume_parsing())
    test_text_cleaning_on_full_resume() 