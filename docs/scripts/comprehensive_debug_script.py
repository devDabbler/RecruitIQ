#!/usr/bin/env python3
"""
Comprehensive debug script to find where the actual work experience data is
"""

import sys
import os
import re
from pathlib import Path

# Add the backend to the path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.utils.enhanced_resume_parser import EnhancedResumeParser

def comprehensive_debug():
    """Find where the actual work experience data is hiding"""
    
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    if not os.path.exists(resume_file):
        print(f"❌ Resume file '{resume_file}' not found!")
        return
    
    print("🔍 COMPREHENSIVE DEBUG - FINDING WORK EXPERIENCE DATA")
    print("=" * 60)
    
    # Initialize parser
    parser = EnhancedResumeParser()
    
    # Extract and process text
    text = parser._extract_text_from_file(resume_file)
    cleaned_text = parser._preprocess_text(text)
    
    print(f"✓ Text length: {len(text)} -> {len(cleaned_text)} characters")
    
    # Search for known company names in the full text
    print("\n🏢 SEARCHING FOR KNOWN COMPANY NAMES:")
    print("-" * 40)
    
    companies_to_find = [
        "Fractal",
        "Neal Analytics", 
        "Army National Guard",
        "Analytics",
        "Fractal Analytics",
        "Guard"
    ]
    
    for company in companies_to_find:
        matches = []
        for match in re.finditer(re.escape(company), cleaned_text, re.IGNORECASE):
            start = max(0, match.start() - 100)
            end = min(len(cleaned_text), match.end() + 100)
            context = cleaned_text[start:end]
            matches.append((match.start(), context))
        
        print(f"\n'{company}': Found {len(matches)} matches")
        for i, (pos, context) in enumerate(matches):
            print(f"  Match {i+1} (pos {pos}): ...{context}...")
    
    # Search for job titles
    print("\n💼 SEARCHING FOR JOB TITLES:")
    print("-" * 40)
    
    job_titles_to_find = [
        "Recruiting",
        "Director",
        "Manager", 
        "Lead",
        "Head of",
        "Global",
        "Talent Acquisition"
    ]
    
    for title in job_titles_to_find:
        matches = list(re.finditer(re.escape(title), cleaned_text, re.IGNORECASE))
        print(f"'{title}': Found {len(matches)} matches")
        
        for i, match in enumerate(matches[:3]):  # Show first 3 matches
            start = max(0, match.start() - 50)
            end = min(len(cleaned_text), match.end() + 50)
            context = cleaned_text[start:end]
            print(f"  Match {i+1}: ...{context}...")
    
    # Search for date patterns
    print("\n📅 SEARCHING FOR DATE PATTERNS:")
    print("-" * 40)
    
    date_patterns = [
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
        r'(\d{4})\s*[-–—]\s*(\d{4}|Present|Current)',
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]\s*(?:Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}))'
    ]
    
    for i, pattern in enumerate(date_patterns):
        matches = list(re.finditer(pattern, cleaned_text, re.IGNORECASE))
        print(f"Date pattern {i+1}: Found {len(matches)} matches")
        
        for j, match in enumerate(matches):
            start = max(0, match.start() - 100)
            end = min(len(cleaned_text), match.end() + 100)
            context = cleaned_text[start:end]
            print(f"  Match {j+1}: {match.group(0)} -> ...{context}...")
    
    # Search for pipe patterns anywhere in text
    print("\n🔍 SEARCHING FOR PIPE PATTERNS IN FULL TEXT:")
    print("-" * 40)
    
    pipe_patterns = [
        r'([^|\n]+)\s*\|\s*([^|\n]+)\s*\|\s*([^|\n]+)',  # Any text | text | text
        r'([A-Z][^|\n]*)\s*\|\s*([A-Z][^|\n]*)\s*\|\s*([^|\n]*)',  # Capitalized | Capitalized | anything
    ]
    
    for i, pattern in enumerate(pipe_patterns):
        matches = list(re.finditer(pattern, cleaned_text))
        print(f"Pipe pattern {i+1}: Found {len(matches)} matches")
        
        for j, match in enumerate(matches[:5]):  # Show first 5 matches
            print(f"  Match {j+1}: '{match.group(1).strip()}' | '{match.group(2).strip()}' | '{match.group(3).strip()}'")
    
    # Look for section headers we might have missed
    print("\n📂 ALL POTENTIAL SECTION HEADERS:")
    print("-" * 40)
    
    section_header_patterns = [
        r'(?:^|\n)\s*([A-Z][A-Z\s&]+[A-Z])\s*(?:\n|:)',  # ALL CAPS headers
        r'(?:^|\n)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:\n|:)',  # Title Case headers
    ]
    
    all_headers = set()
    for pattern in section_header_patterns:
        matches = re.findall(pattern, cleaned_text, re.MULTILINE)
        for match in matches:
            all_headers.add(match.strip())
    
    for header in sorted(all_headers):
        print(f"  - '{header}'")
    
    # Show the actual sections detected
    print("\n📋 DETECTED SECTIONS CONTENT:")
    print("-" * 40)
    
    sections = parser._split_into_sections(cleaned_text)
    for section_name, content in sections.items():
        print(f"\n=== {section_name.upper()} SECTION ({len(content)} chars) ===")
        print(content[:500])
        if len(content) > 500:
            print("... (truncated)")
        print()
    
    # Try to find the missing work experience manually
    print("\n🕵️ MANUAL WORK EXPERIENCE DETECTION:")
    print("-" * 40)
    
    # Look for patterns that suggest work experience entries
    work_indicators = [
        r'(Fractal[^|\n]*\|[^|\n]*\|[^|\n]*(?:20\d{2}|Present))',
        r'(Neal[^|\n]*\|[^|\n]*\|[^|\n]*(?:20\d{2}|Present))',
        r'([A-Z][^|\n]{10,}\|[^|\n]+\|[^|\n]*(?:20\d{2}|Present))',
    ]
    
    for pattern in work_indicators:
        matches = list(re.finditer(pattern, cleaned_text, re.IGNORECASE))
        print(f"Work indicator pattern found {len(matches)} matches:")
        for match in matches:
            print(f"  - {match.group(1)}")

if __name__ == "__main__":
    comprehensive_debug()