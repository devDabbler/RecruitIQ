#!/usr/bin/env python3
"""
Debug script to analyze why both parsers are finding 0 experience entries
This will help us understand the text structure and section detection issues
"""

import sys
import os
from pathlib import Path
import re

# Add the backend directory to the Python path
sys.path.append(str(Path(__file__).parent / "backend"))

def analyze_pdf_text():
    """Analyze the raw PDF text extraction"""
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_file):
        print("❌ Resume file not found!")
        return None
    
    try:
        from PyPDF2 import PdfReader
        
        print("🔍 ANALYZING PDF TEXT EXTRACTION")
        print("=" * 50)
        
        with open(resume_file, 'rb') as file:
            pdf_reader = PdfReader(file)
            
            full_text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n\n"
                    print(f"📄 Page {page_num + 1}: {len(page_text)} characters")
            
            print(f"\n📊 Total extracted text: {len(full_text)} characters")
            
            # Show first 1000 characters
            print(f"\n📋 First 1000 characters:")
            print("-" * 30)
            print(repr(full_text[:1000]))
            print("-" * 30)
            
            # Look for section headers
            print(f"\n🔍 SECTION HEADER ANALYSIS:")
            print("-" * 30)
            
            section_patterns = [
                r'(?i)WORK\s+EXPERIENCE',
                r'(?i)PROFESSIONAL\s+EXPERIENCE',
                r'(?i)EMPLOYMENT\s+HISTORY',
                r'(?i)EXPERIENCE',
                r'(?i)SIGNATURE\s+STRENGTHS',
                r'(?i)EDUCATION',
                r'(?i)SKILLS',
                r'(?i)SUMMARY',
                r'(?i)PROFILE'
            ]
            
            for pattern in section_patterns:
                matches = list(re.finditer(pattern, full_text))
                if matches:
                    for match in matches:
                        context_start = max(0, match.start() - 50)
                        context_end = min(len(full_text), match.end() + 100)
                        context = full_text[context_start:context_end]
                        context = context.replace('\n', '\\n')
                        print(f"✅ Found '{match.group()}' at position {match.start()}")
                        print(f"   Context: ...{context}...")
                else:
                    print(f"❌ NOT FOUND: {pattern}")
            
            # Look for job-like patterns
            print(f"\n💼 JOB PATTERN ANALYSIS:")
            print("-" * 30)
            
            job_patterns = [
                r'(?i)director',
                r'(?i)manager',
                r'(?i)lead',
                r'(?i)recruiting',
                r'(?i)fractal',
                r'(?i)neal analytics',
                r'(?i)army',
                r'\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current)',
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
            ]
            
            for pattern in job_patterns:
                matches = list(re.finditer(pattern, full_text))
                print(f"📍 Pattern '{pattern}': {len(matches)} matches")
                if matches:
                    for i, match in enumerate(matches[:3]):  # Show first 3
                        context_start = max(0, match.start() - 30)
                        context_end = min(len(full_text), match.end() + 30)
                        context = full_text[context_start:context_end].replace('\n', '\\n')
                        print(f"   Match {i+1}: ...{context}...")
            
            return full_text
            
    except Exception as e:
        print(f"❌ Error analyzing PDF: {e}")
        return None

def test_section_detection(text):
    """Test section detection logic"""
    if not text:
        return
    
    print(f"\n🔧 TESTING SECTION DETECTION")
    print("=" * 50)
    
    # Try the section patterns from the enhanced parser
    section_patterns = {
        'profile': [
            r'(?i)(?:^|\n)\s*(PROFILE)\s*(?:\n|$)',
        ],
        'summary': [
            r'(?i)(?:^|\n)\s*(PROFESSIONAL\s+SUMMARY|CAREER\s+SUMMARY|SUMMARY|OBJECTIVE)\s*(?:\n|$)',
        ],
        'work_experience': [
            r'(?i)(?:^|\n)\s*(WORK\s+EXPERIENCE)\s*(?:\n|$)',
        ],
        'experience': [
            r'(?i)(?:^|\n)\s*(PROFESSIONAL\s+EXPERIENCE|EMPLOYMENT\s+HISTORY|CAREER\s+HISTORY)\s*(?:\n|$)',
        ],
        'signature_strengths': [
            r'(?i)(?:^|\n)\s*(SIGNATURE\s+STRENGTHS)\s*(?:\n|$)',
        ],
        'education': [
            r'(?i)(?:^|\n)\s*(EDUCATION|EDUCATIONAL\s+BACKGROUND|ACADEMIC\s+BACKGROUND)\s*(?:\n|$)',
        ],
        'skills': [
            r'(?i)(?:^|\n)\s*(SKILLS|TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES)\s*(?:\n|$)',
        ]
    }
    
    found_sections = {}
    
    for section_type, patterns in section_patterns.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.MULTILINE))
            if matches:
                for match in matches:
                    header_text = match.group(1)
                    found_sections[section_type] = {
                        'header': header_text,
                        'start': match.start(),
                        'end': match.end()
                    }
                    print(f"✅ Found {section_type}: '{header_text}' at position {match.start()}")
                    break
        
        if section_type not in found_sections:
            print(f"❌ Not found: {section_type}")
    
    # Extract content for each found section
    sorted_sections = sorted(found_sections.items(), key=lambda x: x[1]['start'])
    
    print(f"\n📋 SECTION CONTENT PREVIEW:")
    print("-" * 30)
    
    for i, (section_name, section_info) in enumerate(sorted_sections):
        start_pos = section_info['end']
        
        # Find end position
        if i + 1 < len(sorted_sections):
            end_pos = sorted_sections[i + 1][1]['start']
        else:
            end_pos = len(text)
        
        content = text[start_pos:end_pos].strip()
        
        print(f"\n🔖 {section_name.upper()} ({len(content)} chars):")
        print(f"   Header: '{section_info['header']}'")
        print(f"   Content preview: {repr(content[:200])}...")
        
        # For experience sections, try to find job patterns
        if 'experience' in section_name.lower() or section_name == 'signature_strengths':
            print(f"   🔍 Looking for job patterns in {section_name}...")
            
            # Look for company names
            company_patterns = [
                r'([A-Z][A-Za-z\s&.,-]{3,50}?)\s*\|\s*([A-Z][A-Za-z\s,.-]{3,40}?)',
                r'(?i)(fractal|neal\s+analytics|army\s+national\s+guard)',
            ]
            
            for pattern in company_patterns:
                matches = list(re.finditer(pattern, content))
                if matches:
                    print(f"     ✅ Company pattern found: {len(matches)} matches")
                    for match in matches[:2]:
                        print(f"        '{match.group()}'")
                else:
                    print(f"     ❌ No matches for: {pattern}")

def test_experience_extraction_methods(text):
    """Test different experience extraction approaches"""
    if not text:
        return
    
    print(f"\n🎯 TESTING EXPERIENCE EXTRACTION METHODS")
    print("=" * 50)
    
    # Method 1: Look for pipe format (Company | Location)
    print(f"\n1️⃣ PIPE FORMAT TEST:")
    pipe_pattern = r'([A-Z][A-Za-z\s&.,-]{3,50}?)\s*\|\s*([A-Z][A-Za-z\s,.-]{3,40}?)'
    pipe_matches = list(re.finditer(pipe_pattern, text))
    print(f"   Found {len(pipe_matches)} pipe format matches:")
    for i, match in enumerate(pipe_matches[:5]):
        print(f"     {i+1}. '{match.group(1)}' | '{match.group(2)}'")
    
    # Method 2: Look for known company names
    print(f"\n2️⃣ KNOWN COMPANY TEST:")
    known_companies = ['fractal', 'neal analytics', 'army national guard']
    for company in known_companies:
        matches = list(re.finditer(re.escape(company), text, re.IGNORECASE))
        print(f"   '{company}': {len(matches)} matches")
        for match in matches:
            context_start = max(0, match.start() - 100)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end].replace('\n', ' ')
            print(f"     Context: ...{context}...")
    
    # Method 3: Look for job titles
    print(f"\n3️⃣ JOB TITLE TEST:")
    title_patterns = [
        r'(?i)(global\s+recruiting\s+[^.]*?lead)',
        r'(?i)(director\s+of\s+recruiting)',
        r'(?i)(head\s+of\s+recruiting)',
        r'(?i)(recruiting\s+manager)',
        r'(?i)(executive\s+officer)',
    ]
    
    for pattern in title_patterns:
        matches = list(re.finditer(pattern, text))
        print(f"   Pattern '{pattern}': {len(matches)} matches")
        for match in matches:
            print(f"     Found: '{match.group()}'")
    
    # Method 4: Look for date ranges
    print(f"\n4️⃣ DATE RANGE TEST:")
    date_patterns = [
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]\s*(?:Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
        r'\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current)',
    ]
    
    for pattern in date_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        print(f"   Date pattern: {len(matches)} matches")
        for match in matches[:3]:
            print(f"     Found: '{match.group()}'")

def main():
    """Main debug function"""
    print("🐛 RESUME PARSING DEBUG ANALYSIS")
    print("=" * 60)
    
    # Step 1: Analyze raw PDF text
    text = analyze_pdf_text()
    
    if text:
        # Step 2: Test section detection
        test_section_detection(text)
        
        # Step 3: Test experience extraction methods
        test_experience_extraction_methods(text)
        
        print(f"\n🎯 SUMMARY & RECOMMENDATIONS:")
        print("=" * 30)
        print("1. Check if section headers are being detected correctly")
        print("2. Look for experience content in the found sections")
        print("3. Verify that job patterns exist in the text")
        print("4. Consider if PDF extraction is losing critical formatting")
        
    else:
        print("❌ Could not extract text from PDF - check file path and permissions")

if __name__ == "__main__":
    main()