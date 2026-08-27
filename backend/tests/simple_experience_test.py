#!/usr/bin/env python3
"""
Simple test for the regex experience extractor
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.resume_parsing.extractors.regex_extractor import _MiniExperienceParser

def test_roger_waters_format():
    """Test the experience extraction with Roger Waters resume format."""
    # Sample text in Roger Waters format
    roger_waters_text = """
EXPERIENCE

Full Stack Developer at TechCorp - San Francisco, CA (2020 - Present)
Tech Stack: JavaScript, React, Node.js, MongoDB
• Built full-stack web applications using React.js and Node.js
• Implemented RESTful APIs for mobile and web applications
• Optimized MongoDB database queries improving performance by 30%

Software Engineer at DataSystems - Austin, TX (2018 - 2020)
Tech Stack: Python, Django, PostgreSQL, Docker
• Developed backend services using Django REST framework
• Containerized applications with Docker and deployed on AWS
• Created automated testing pipelines using pytest and GitHub Actions
"""

    # Create parser and extract experiences
    parser = _MiniExperienceParser()
    experiences = parser.parse(roger_waters_text)
    
    # Print results
    print(f"\nFound {len(experiences)} experiences:")
    for i, exp in enumerate(experiences):
        print(f"\nExperience {i+1}:")
        print(f"  Title: {exp.title}")
        print(f"  Company: {exp.company}")
        print(f"  Location: {exp.location}")
        print(f"  Dates: {exp.start_date} - {exp.end_date}")
        if exp.description:
            print(f"  Description: {exp.description[:100]}...")
    
    # Verify expectations
    assert len(experiences) >= 2, f"Expected at least 2 experiences, got {len(experiences)}"
    
    # Check first experience
    assert experiences[0].title == "Full Stack Developer", f"Expected 'Full Stack Developer', got '{experiences[0].title}'"
    assert experiences[0].company == "TechCorp", f"Expected 'TechCorp', got '{experiences[0].company}'"
    assert experiences[0].location == "San Francisco, CA", f"Expected 'San Francisco, CA', got '{experiences[0].location}'"
    assert experiences[0].start_date == "2020", f"Expected '2020', got '{experiences[0].start_date}'"
    assert experiences[0].end_date == "Present", f"Expected 'Present', got '{experiences[0].end_date}'"
    
    # Check second experience
    assert experiences[1].title == "Software Engineer", f"Expected 'Software Engineer', got '{experiences[1].title}'"
    assert experiences[1].company == "DataSystems", f"Expected 'DataSystems', got '{experiences[1].company}'"
    assert experiences[1].location == "Austin, TX", f"Expected 'Austin, TX', got '{experiences[1].location}'"
    assert experiences[1].start_date == "2018", f"Expected '2018', got '{experiences[1].start_date}'"
    assert experiences[1].end_date == "2020", f"Expected '2020', got '{experiences[1].end_date}'"
    
    print("\nAll assertions passed! The Roger Waters format is correctly parsed.")

def test_multiple_formats():
    """Test multiple different resume formats."""
    multi_format_text = """
WORK EXPERIENCE

Senior Developer at Google - Mountain View, CA (2021 - Present)
• Led a team of 5 developers on cloud infrastructure projects
• Implemented microservices architecture using Kubernetes

Product Manager | Apple Inc. | Cupertino (2018 - 2021)
• Managed the development of iOS features across multiple releases
• Collaborated with design and engineering teams to deliver products

Software Engineer - Microsoft - Seattle, WA (2015 - 2018)
• Developed .NET applications for enterprise clients
• Created automated testing frameworks

Amazon Web Services
Cloud Solutions Architect
2013 - 2015
• Designed cloud migration strategies for Fortune 500 clients
• Optimized AWS infrastructure costs by 25%
"""

    # Create parser and extract experiences
    parser = _MiniExperienceParser()
    experiences = parser.parse(multi_format_text)
    
    # Print results
    print(f"\nFound {len(experiences)} experiences:")
    for i, exp in enumerate(experiences):
        print(f"\nExperience {i+1}:")
        print(f"  Title: {exp.title}")
        print(f"  Company: {exp.company}")
        print(f"  Location: {exp.location}")
        print(f"  Dates: {exp.start_date} - {exp.end_date}")
        if exp.description:
            print(f"  Description: {exp.description[:100]}...")
    
    # Verify we found at least 4 experiences with different formats
    assert len(experiences) >= 4, f"Expected at least 4 experiences, got {len(experiences)}"
    
    # Basic format checks
    companies = [exp.company for exp in experiences]
    assert "Google" in companies, "Failed to extract Google experience"
    assert "Apple Inc." in companies, "Failed to extract Apple experience"
    assert "Microsoft" in companies, "Failed to extract Microsoft experience"
    assert "Amazon Web Services" in companies, "Failed to extract AWS experience"
    
    print("\nAll assertions passed! Multiple formats are correctly parsed.")

if __name__ == "__main__":
    print("Testing Roger Waters format...")
    test_roger_waters_format()
    
    print("\nTesting multiple formats...")
    test_multiple_formats()
    
    print("\nAll tests passed! The experience extraction is working correctly.")
