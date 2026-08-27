#!/usr/bin/env python3
"""
Debug script for Academic/Research format parsing issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor

async def debug_academic_format():
    """Debug the Academic/Research format parsing issue."""
    
    # Test case that's failing
    test_text = """
## Professional Experience
Research Scientist at OpenAI - San Francisco, CA (2020 - Present)
• Conducted research on large language models and their applications
• Published 5 papers in top-tier conferences (NeurIPS, ICML)
• Developed novel architectures for transformer models

Postdoctoral Researcher at Stanford University - Stanford, CA (2018 - 2020)
• Investigated deep learning approaches for computer vision
• Collaborated with international research teams
• Supervised 3 graduate students in their research projects
"""
    
    print("🔍 DEBUGGING ACADEMIC/RESEARCH FORMAT")
    print("=" * 50)
    print()
    
    # Initialize extractor
    extractor = RegexExtractor()
    
    # Test section detection
    print("1. Testing section detection:")
    exp_text = extractor._find_experience_section(test_text)
    print(f"   Found experience section: {len(exp_text)} characters")
    print(f"   Section content: {repr(exp_text[:200])}...")
    print()
    
    # Test job block splitting
    print("2. Testing job block splitting:")
    job_blocks = extractor._split_into_job_blocks_enhanced(exp_text)
    print(f"   Found {len(job_blocks)} job blocks")
    for i, block in enumerate(job_blocks):
        print(f"   Block {i+1}: {repr(block[:100])}...")
    print()
    
    # Test individual job parsing
    print("3. Testing individual job parsing:")
    for i, block in enumerate(job_blocks):
        print(f"   Parsing block {i+1}:")
        print(f"     Block content: {repr(block)}")
        
        # Debug the parsing step by step
        lines = block.strip().split('\n')
        print(f"     Lines: {len(lines)}")
        for j, line in enumerate(lines):
            print(f"       Line {j}: {repr(line)}")
        
        experience = extractor._parse_job_block_enhanced(block)
        if experience:
            print(f"     ✅ SUCCESS:")
            print(f"       Title: {experience.title}")
            print(f"       Company: {experience.company}")
            print(f"       Location: {experience.location}")
        else:
            print(f"     ❌ FAILED to parse")
        print()
    
    # Test full extraction
    print("4. Testing full extraction:")
    experiences = await extractor._extract_experience(test_text)
    print(f"   Found {len(experiences)} experiences")
    for i, exp in enumerate(experiences):
        print(f"   {i+1}. {exp.title} at {exp.company} ({exp.location})")

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_academic_format()) 