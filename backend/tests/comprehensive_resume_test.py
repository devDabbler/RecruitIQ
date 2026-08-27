#!/usr/bin/env python3
"""
Comprehensive test suite for resume parsing across various formats and styles.
This test covers different resume layouts, formatting styles, and edge cases.
"""

import sys
import os
import asyncio
import json
from typing import List, Dict, Any
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from utils.resume_parsing.models.resume_schema import Experience, Education, PersonalInfo, Skill

class ResumeTestCase:
    def __init__(self, name: str, text: str, expected_results: Dict[str, Any]):
        self.name = name
        self.text = text
        self.expected_results = expected_results

async def run_comprehensive_tests():
    """Run comprehensive tests across various resume formats."""
    
    # Initialize the extractor
    extractor = RegexExtractor()
    
    # Define test cases
    test_cases = [
        # Test Case 1: Standard format with "at" pattern
        ResumeTestCase(
            name="Standard 'at' format",
            text="""
## Work Experience
Senior Software Engineer at Google - Mountain View, CA (January 2020 - Present)
• Developed scalable microservices using Python and Go
• Led a team of 5 engineers to deliver high-impact features
• Improved system performance by 40% through optimization

Software Engineer at Microsoft - Seattle, WA (June 2018 - December 2019)
• Built full-stack web applications using React and Node.js
• Collaborated with cross-functional teams to deliver products
• Implemented CI/CD pipelines reducing deployment time by 60%
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Google", "Microsoft"],
                "titles": ["Senior Software Engineer", "Software Engineer"],
                "locations": ["Mountain View, CA", "Seattle, WA"]
            }
        ),
        
        # Test Case 2: Dash-separated format
        ResumeTestCase(
            name="Dash-separated format",
            text="""
## Professional Experience
Data Scientist - Amazon - Seattle, WA (March 2019 - December 2021)
• Built machine learning models for recommendation systems
• Analyzed large datasets using Python and SQL
• Presented findings to executive leadership

Product Manager - Facebook - Menlo Park, CA (January 2017 - February 2019)
• Led product strategy for mobile applications
• Managed product roadmap and feature prioritization
• Coordinated with engineering and design teams
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Amazon", "Facebook"],
                "titles": ["Data Scientist", "Product Manager"],
                "locations": ["Seattle, WA", "Menlo Park, CA"]
            }
        ),
        
        # Test Case 3: Compact format with dates in parentheses
        ResumeTestCase(
            name="Compact format with parentheses",
            text="""
## Experience
Lead Developer (2021-Present)
Netflix - Los Gatos, CA
• Architected streaming platform improvements
• Mentored junior developers and conducted code reviews

Senior Developer (2019-2021)
Twitter - San Francisco, CA
• Developed real-time data processing systems
• Optimized database queries and improved performance
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Netflix", "Twitter"],
                "titles": ["Lead Developer", "Senior Developer"],
                "locations": ["Los Gatos, CA", "San Francisco, CA"]
            }
        ),
        
        # Test Case 4: Multi-line format with complex descriptions
        ResumeTestCase(
            name="Multi-line with complex descriptions",
            text="""
## Work History
Senior Data Engineer at Uber - San Francisco, CA (January 2020 - Present)
Designed and implemented data pipelines processing 100TB+ of daily data using Apache Spark and Airflow.
Led the migration from legacy systems to modern cloud infrastructure, resulting in 50% cost reduction.
Mentored 3 junior engineers and established best practices for data engineering across the organization.

Data Engineer at Lyft - San Francisco, CA (March 2018 - December 2019)
Built real-time analytics dashboards using Kafka, Elasticsearch, and Grafana.
Developed ETL processes that improved data quality by 90% and reduced processing time by 70%.
Collaborated with product teams to define data requirements and implement tracking solutions.
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Uber", "Lyft"],
                "titles": ["Senior Data Engineer", "Data Engineer"],
                "locations": ["San Francisco, CA", "San Francisco, CA"]
            }
        ),
        
        # Test Case 5: Minimal format
        ResumeTestCase(
            name="Minimal format",
            text="""
EXPERIENCE
Software Engineer, Apple, Cupertino, CA (2019-2021)
• iOS app development
• Performance optimization

Developer, Tesla, Palo Alto, CA (2017-2019)
• Backend systems
• Database design
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Apple", "Tesla"],
                "titles": ["Software Engineer", "Developer"],
                "locations": ["Cupertino, CA", "Palo Alto, CA"]
            }
        ),
        
        # Test Case 6: Academic/Research format
        ResumeTestCase(
            name="Academic/Research format",
            text="""
## Professional Experience
Research Scientist at OpenAI - San Francisco, CA (2020 - Present)
• Conducted research on large language models and their applications
• Published 5 papers in top-tier conferences (NeurIPS, ICML)
• Developed novel architectures for transformer models

Postdoctoral Researcher at Stanford University - Stanford, CA (2018 - 2020)
• Investigated deep learning approaches for computer vision
• Collaborated with international research teams
• Supervised 3 graduate students in their research projects
""",
            expected_results={
                "experience_count": 2,
                "companies": ["OpenAI", "Stanford University"],
                "titles": ["Research Scientist", "Postdoctoral Researcher"],
                "locations": ["San Francisco, CA", "Stanford, CA"]
            }
        ),
        
        # Test Case 7: International format
        ResumeTestCase(
            name="International format",
            text="""
## Employment History
Senior Software Engineer | Spotify | Stockholm, Sweden (2019-2021)
• Developed music recommendation algorithms
• Led international team of 8 engineers

Software Engineer | SAP | Berlin, Germany (2017-2019)
• Built enterprise software solutions
• Implemented cloud migration strategies
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Spotify", "SAP"],
                "titles": ["Senior Software Engineer", "Software Engineer"],
                "locations": ["Stockholm, Sweden", "Berlin, Germany"]
            }
        ),
        
        # Test Case 8: Startup/Consulting format
        ResumeTestCase(
            name="Startup/Consulting format",
            text="""
## Professional Experience
CTO & Co-founder at TechStartup Inc. - San Francisco, CA (2020 - Present)
• Founded and scaled technology startup from 0 to 50 employees
• Raised $5M in Series A funding from top-tier VCs
• Built and deployed cloud-native applications serving 100K+ users

Senior Consultant at McKinsey & Company - New York, NY (2018 - 2020)
• Led digital transformation projects for Fortune 500 companies
• Developed strategic roadmaps for technology adoption
• Managed client relationships worth $10M+ in annual revenue
""",
            expected_results={
                "experience_count": 2,
                "companies": ["TechStartup Inc.", "McKinsey & Company"],
                "titles": ["CTO & Co-founder", "Senior Consultant"],
                "locations": ["San Francisco, CA", "New York, NY"]
            }
        ),
        
        # Test Case 9: Government/Military format
        ResumeTestCase(
            name="Government/Military format",
            text="""
## Work Experience
Senior Systems Engineer at NASA - Houston, TX (2019 - Present)
• Developed mission-critical software for space exploration
• Led teams of engineers in high-stakes projects
• Implemented safety protocols and quality assurance measures

Software Engineer at Department of Defense - Washington, DC (2017 - 2019)
• Built secure communication systems for military applications
• Maintained classified information systems
• Collaborated with international defense partners
""",
            expected_results={
                "experience_count": 2,
                "companies": ["NASA", "Department of Defense"],
                "titles": ["Senior Systems Engineer", "Software Engineer"],
                "locations": ["Houston, TX", "Washington, DC"]
            }
        ),
        
        # Test Case 10: Creative/Design format
        ResumeTestCase(
            name="Creative/Design format",
            text="""
## Professional Experience
Senior UX Designer at Adobe - San Jose, CA (2020 - Present)
• Designed user interfaces for creative software applications
• Conducted user research and usability testing
• Created design systems and component libraries

Product Designer at Figma - San Francisco, CA (2018 - 2020)
• Designed collaborative design tools and features
• Worked closely with engineering teams to implement designs
• Led design workshops and training sessions
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Adobe", "Figma"],
                "titles": ["Senior UX Designer", "Product Designer"],
                "locations": ["San Jose, CA", "San Francisco, CA"]
            }
        ),
        
        # Test Case 11: Edge case - No dates
        ResumeTestCase(
            name="No dates format",
            text="""
## Experience
Software Engineer at GitHub
San Francisco, CA
• Built developer tools and platforms
• Open source contributions

Developer at GitLab
Remote
• Full-stack development
• DevOps implementation
""",
            expected_results={
                "experience_count": 2,
                "companies": ["GitHub", "GitLab"],
                "titles": ["Software Engineer", "Developer"],
                "locations": ["San Francisco, CA", "Remote"]
            }
        ),
        
        # Test Case 12: Edge case - Very long titles
        ResumeTestCase(
            name="Very long titles",
            text="""
## Work Experience
Senior Principal Software Engineer - Machine Learning Infrastructure at Google - Mountain View, CA (2020 - Present)
• Built large-scale machine learning infrastructure
• Led architecture decisions for ML platforms

Distinguished Engineer - Cloud Computing and Distributed Systems at Amazon Web Services - Seattle, WA (2018 - 2020)
• Designed cloud computing solutions
• Architected distributed systems
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Google", "Amazon Web Services"],
                "titles": ["Senior Principal Software Engineer - Machine Learning Infrastructure", "Distinguished Engineer - Cloud Computing and Distributed Systems"],
                "locations": ["Mountain View, CA", "Seattle, WA"]
            }
        ),
        
        # Test Case 13: Edge case - Special characters in company names
        ResumeTestCase(
            name="Special characters in company names",
            text="""
## Experience
Software Engineer at AT&T - Dallas, TX (2019 - Present)
• Telecommunications software development
• Network optimization

Developer at C++ Consulting Group - Austin, TX (2017 - 2019)
• C++ development and consulting
• Performance optimization
""",
            expected_results={
                "experience_count": 2,
                "companies": ["AT&T", "C++ Consulting Group"],
                "titles": ["Software Engineer", "Developer"],
                "locations": ["Dallas, TX", "Austin, TX"]
            }
        ),
        
        # Test Case 14: Edge case - Multiple locations
        ResumeTestCase(
            name="Multiple locations",
            text="""
## Work Experience
Global Product Manager at Microsoft - Redmond, WA / Seattle, WA (2020 - Present)
• Managed global product strategy
• Coordinated with international teams

Regional Director at Salesforce - San Francisco, CA / New York, NY (2018 - 2020)
• Led regional sales operations
• Managed multiple office locations
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Microsoft", "Salesforce"],
                "titles": ["Global Product Manager", "Regional Director"],
                "locations": ["Redmond, WA / Seattle, WA", "San Francisco, CA / New York, NY"]
            }
        ),
        
        # Test Case 15: Edge case - Freelance/Contract work
        ResumeTestCase(
            name="Freelance/Contract work",
            text="""
## Professional Experience
Senior Software Engineer (Contract) at Apple - Cupertino, CA (2020 - Present)
• iOS app development and optimization
• Performance tuning and debugging

Freelance Developer at Various Clients - Remote (2018 - 2020)
• Full-stack web development
• Mobile app development
• Database design and optimization
""",
            expected_results={
                "experience_count": 2,
                "companies": ["Apple", "Various Clients"],
                "titles": ["Senior Software Engineer (Contract)", "Freelance Developer"],
                "locations": ["Cupertino, CA", "Remote"]
            }
        )
    ]
    
    # Run tests
    print("🧪 COMPREHENSIVE RESUME PARSING TEST SUITE")
    print("=" * 60)
    print()
    
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}/{total_tests}: {test_case.name}")
        print("-" * 40)
        
        try:
            # Extract experience
            experiences = await extractor._extract_experience(test_case.text)
            
            # Validate results
            results = validate_test_case(experiences, test_case.expected_results)
            
            if results["passed"]:
                print("✅ PASSED")
                passed_tests += 1
            else:
                print("❌ FAILED")
                print(f"   Expected: {test_case.expected_results}")
                print(f"   Actual: {results['actual']}")
                failed_tests.append({
                    "test_case": test_case.name,
                    "expected": test_case.expected_results,
                    "actual": results["actual"],
                    "errors": results["errors"]
                })
            
            print(f"   Found {len(experiences)} experiences")
            for j, exp in enumerate(experiences):
                print(f"   {j+1}. {exp.title} at {exp.company} ({exp.location})")
            print()
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            failed_tests.append({
                "test_case": test_case.name,
                "error": str(e)
            })
            print()
    
    # Summary
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    print()
    
    if failed_tests:
        print("❌ FAILED TESTS:")
        for failure in failed_tests:
            print(f"  - {failure['test_case']}")
            if "error" in failure:
                print(f"    Error: {failure['error']}")
            else:
                print(f"    Expected: {failure['expected']}")
                print(f"    Actual: {failure['actual']}")
        print()
    
    # Save detailed results to file
    save_test_results(test_cases, failed_tests, passed_tests, total_tests)
    
    return passed_tests == total_tests

def validate_test_case(experiences: List[Experience], expected: Dict[str, Any]) -> Dict[str, Any]:
    """Validate test case results against expected outcomes."""
    actual = {
        "experience_count": len(experiences),
        "companies": [exp.company for exp in experiences],
        "titles": [exp.title for exp in experiences],
        "locations": [exp.location for exp in experiences]
    }
    
    errors = []
    passed = True
    
    # Check experience count
    if actual["experience_count"] != expected["experience_count"]:
        errors.append(f"Experience count mismatch: expected {expected['experience_count']}, got {actual['experience_count']}")
        passed = False
    
    # Check companies
    if len(actual["companies"]) >= len(expected["companies"]):
        for i, expected_company in enumerate(expected["companies"]):
            if i < len(actual["companies"]):
                actual_company = actual["companies"][i]
                if expected_company.lower() not in actual_company.lower() and actual_company.lower() not in expected_company.lower():
                    errors.append(f"Company mismatch at position {i}: expected '{expected_company}', got '{actual_company}'")
                    passed = False
    else:
        errors.append(f"Not enough companies: expected {len(expected['companies'])}, got {len(actual['companies'])}")
        passed = False
    
    # Check titles
    if len(actual["titles"]) >= len(expected["titles"]):
        for i, expected_title in enumerate(expected["titles"]):
            if i < len(actual["titles"]):
                actual_title = actual["titles"][i]
                if expected_title.lower() not in actual_title.lower() and actual_title.lower() not in expected_title.lower():
                    errors.append(f"Title mismatch at position {i}: expected '{expected_title}', got '{actual_title}'")
                    passed = False
    else:
        errors.append(f"Not enough titles: expected {len(expected['titles'])}, got {len(actual['titles'])}")
        passed = False
    
    return {
        "passed": passed,
        "actual": actual,
        "errors": errors
    }

def save_test_results(test_cases: List[ResumeTestCase], failed_tests: List[Dict], passed_tests: int, total_tests: int):
    """Save detailed test results to a JSON file."""
    results = {
        "summary": {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": len(failed_tests),
            "success_rate": (passed_tests/total_tests)*100
        },
        "failed_tests": failed_tests,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    with open("resume_parsing_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"📄 Detailed results saved to: resume_parsing_test_results.json")

if __name__ == "__main__":
    # Run the comprehensive test suite
    success = asyncio.run(run_comprehensive_tests())
    
    if success:
        print("🎉 All tests passed! The parser is robust and ready for production.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please review the results and fix any issues.")
        sys.exit(1) 