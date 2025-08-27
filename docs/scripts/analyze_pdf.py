"""
Analyze PDF specifically for font change issues in the resume.
"""
import os
import sys
import re
from pathlib import Path
from PyPDF2 import PdfReader

# Find the resume file
resume_path = Path("Sean B. Collins Resume - Recruiting Leader.pdf")
if not resume_path.exists():
    print(f"Resume file not found at {resume_path}")
    sys.exit(1)

print(f"Found resume file at {resume_path}")

# Extract raw text directly using PyPDF2
with open(resume_path, 'rb') as file:
    pdf_reader = PdfReader(file)
    page_count = len(pdf_reader.pages)
    print(f"PDF has {page_count} pages")
    
    for i in range(page_count):
        page = pdf_reader.pages[i]
        raw_text = page.extract_text()
        
        # Check for problematic characters
        if "39.9" in raw_text:
            print(f"\n===== Found '39.9' on Page {i+1} =====")
            idx = raw_text.find("39.9")
            context_start = max(0, idx - 30)
            context_end = min(len(raw_text), idx + 80)
            
            print(f"Context around '39.9':")
            # Print safe version of the text
            safe_text = raw_text[context_start:context_end].encode('ascii', 'replace').decode('ascii')
            print(safe_text)
            
            print("\nDetailed character analysis (20 chars before and after '39.9'):")
            for j in range(idx-20, idx+25):
                if j < 0 or j >= len(raw_text):
                    continue
                char = raw_text[j]
                try:
                    char_repr = repr(char).strip("'")
                    print(f"Position {j-idx:+3d}: '{char_repr}' (ASCII: {ord(char)})")
                except UnicodeEncodeError:
                    print(f"Position {j-idx:+3d}: <non-ascii character> (ASCII: {ord(char)})")
            
            # Look for missing spaces specifically
            print("\nAnalyzing spaces around numbers and words:")
            segment = raw_text[idx-15:idx+40]
            words = re.findall(r'[a-zA-Z0-9.]+', segment)
            print(f"Words found: {words}")
            
            print("\nTesting replacements:")
            # Test common problematic patterns
            patterns = [
                (r'(\$?\s*39\.9\s*M)in', r'\1 in'),
                (r'(\$?\s*39\.9\s*M\s*in)revenue', r'\1 revenue'),
                (r'revenue(impact)', r'revenue \1'),
                (r'impact(through)', r'impact \1'),
                (r'through(strategic)', r'through \1')
            ]
            
            for pattern, replacement in patterns:
                test_result = re.sub(pattern, replacement, segment)
                if test_result != segment:
                    print(f"Pattern '{pattern}' applies: '{test_result}'")
                else:
                    print(f"Pattern '{pattern}' does not apply")
            
            # Additional analysis to find word boundaries
            print("\nWord boundary analysis:")
            possible_boundaries = []
            for j in range(len(segment)-1):
                c1, c2 = segment[j], segment[j+1]
                if (c1.islower() and c2.isupper()) or (c1.isdigit() and c2.isalpha()) or (c1.isalpha() and c2.isdigit()):
                    possible_boundaries.append((j, c1, c2))
            
            for pos, c1, c2 in possible_boundaries:
                print(f"Possible word boundary at position {pos}: '{c1}{c2}' -> '{c1} {c2}'")
                
            # Extract the problematic phrase more precisely
            print("\nProblematic phrase extraction:")
            match = re.search(r'generating\s+(\$?39\.9M?\s*.*?(?:hires|initiatives))', raw_text)
            if match:
                phrase = match.group(1)
                print(f"Full phrase: '{phrase}'")
                print("Character by character:")
                for idx, c in enumerate(phrase):
                    print(f"{idx}: '{c}' ({ord(c)})")
                
                # Create improved version for testing
                improved = phrase
                improved = re.sub(r'(\$?39\.9M?)in', r'\1 in', improved)
                improved = re.sub(r'inrevenue', r'in revenue', improved)
                improved = re.sub(r'revenueimpact', r'revenue impact', improved)
                improved = re.sub(r'impactthrough', r'impact through', improved)
                improved = re.sub(r'throughstrategic', r'through strategic', improved)
                
                print(f"\nImproved version: '{improved}'")
                
                # Include Python bytes representation to troubleshoot any hidden chars
                print("\nBytes representation of original phrase:")
                print(phrase.encode('utf-8')) 