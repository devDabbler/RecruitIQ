#!/usr/bin/env python3
"""
Test script to extract text from Alex Jones resume PDF and test the current parser.
"""

import sys
import os
import asyncio
import PyPDF2
from pathlib import Path

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

async def test_alex_jones_resume():
    """Test the parser on Alex Jones resume."""
    
    # Path to the PDF file
    pdf_path = "../Clint_Forest_Resume.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        return
    
    print("📄 Extracting text from Alex Jones resume PDF...")
    
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        print("❌ Failed to extract text from PDF")
        return
    
    print(f"✅ Extracted {len(text)} characters from PDF")
    print("\n" + "="*60)
    print("EXTRACTED TEXT:")
    print("="*60)
    print(text[:1000] + "..." if len(text) > 1000 else text)
    print("="*60)
    
    # Test the parser
    print("\n🧪 Testing current parser on Alex Jones resume...")
    
    extractor = RegexExtractor()
    
    try:
        # Extract experience
        experiences = await extractor._extract_experience(text)
        
        print(f"\n📊 PARSING RESULTS:")
        print(f"Found {len(experiences)} experience entries")
        
        for i, exp in enumerate(experiences, 1):
            print(f"\n{i}. {exp.title}")
            print(f"   Company: {exp.company}")
            print(f"   Location: {exp.location}")
            print(f"   Dates: {exp.start_date} - {exp.end_date}")
            print(f"   Description: {exp.description[:100]}..." if exp.description and len(exp.description) > 100 else f"   Description: {exp.description}")
        
        if len(experiences) == 0:
            print("\n❌ No experience entries found!")
            print("\n🔍 This indicates a parsing issue that needs to be addressed.")
            
    except Exception as e:
        print(f"\n❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_alex_jones_resume()) 