import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import streamlit as st
from modules import assistant

def run_comprehensive_search_test():
    """
    Comprehensive test for the AI Assistant's search/response capabilities.
    This test covers a variety of question types to ensure robust handling.
    """
    test_cases = [
        # Salary queries
        ("What is the current salary for a software engineer in the UK?", "Current Salary Ranges for Software Engineer (UK)"),
        ("Show me historical salaries for data scientists in Germany.", "Historical Salary Ranges for Data Scientist (Germany)"),
        ("What's the average pay for a product manager in India?", "Estimated Salary Ranges for Product Manager (India)"),
        ("How much does a designer earn in the US?", "Estimated Salary Ranges for Designer (US/Other)"),
        ("What is the latest salary for a software engineer?", "Current Salary Ranges for Software Engineer (US/Other)"),
        ("And for a data scientist?", "Current Salary Ranges for Data Scientist (US/Other)"),
        ("What about in the past?", "Historical Salary Ranges for Data Scientist (US/Other)"),
        # Job description
        ("Can you write a job description for a backend developer?", "Here's a draft job description"),
        # Screening questions
        ("Give me some screening questions for a frontend engineer.", "Here are some screening questions"),
        # Interview questions
        ("Suggest interview questions for a product manager.", "Here are some interview questions"),
        # Resume analysis
        ("Can you analyze this resume?", "Based on the resume you shared, here's my analysis"),
        # Assessment
        ("Create a technical assessment for a full-stack developer.", "Here's a suggested technical assessment"),
        # Company info
        ("Tell me about Google as a workplace.", "Company Insights for Google"),
        ("What is the culture at Amazon?", "Company Insights for Amazon"),
        # General
        ("How are you today?", "I'm here to help with your recruiting needs!"),
    ]

    passed = 0
    failed = 0
    for idx, (query, expected_snippet) in enumerate(test_cases):
        response = assistant.generate_response(query)
        if expected_snippet.lower() in response.lower():
            print(f"[PASS] Test {idx+1}: '{query}'")
            passed += 1
        else:
            print(f"[FAIL] Test {idx+1}: '{query}'\n  Expected: {expected_snippet}\n  Got: {response[:80]}...")
            failed += 1
    print(f"\nComprehensive Search Test Results: {passed} passed, {failed} failed, {len(test_cases)} total.")

if __name__ == "__main__":
    run_comprehensive_search_test()
