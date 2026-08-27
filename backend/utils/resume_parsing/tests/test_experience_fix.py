#!/usr/bin/env python3
"""
Test script to verify that the experience not specified fix is working correctly.
"""
import sys
sys.path.append('.')
from services.matching_enhancer import MatchingEnhancer
from services.matching_integrator import MatchingIntegrator
from services.rag_service import RAGService
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_experience_extraction():
    """Test the experience extraction logic with various inputs."""
    enhancer = MatchingEnhancer()
    
    test_cases = [
        ("", "Empty string"),
        ("Not specified", "Not specified text"),
        ("Experience not specified", "Experience not specified text"),
        ("Software Engineer", "Normal position"),
        ("Senior Software Engineer", "Senior position"),
        ("Junior Developer", "Junior position"),
        ("Summer Associate", "Entry level position"),
        ("Intern", "Intern position"),
    ]
    
    print("Testing experience extraction logic:")
    print("=" * 50)
    
    for text, description in test_cases:
        level, years = enhancer.extract_experience_level(text)
        print(f"{description:25} | Level: {level:12} | Years: {years}")
    
    print("\n" + "=" * 50)

def test_experience_match_scoring():
    """Test the experience match scoring with not_specified cases."""
    enhancer = MatchingEnhancer()
    
    test_cases = [
        ("entry", 2, "not_specified", 0, "Entry level job vs not specified"),
        ("junior", 3, "not_specified", 0, "Junior job vs not specified"),
        ("mid", 5, "not_specified", 0, "Mid level job vs not specified"),
        ("senior", 7, "not_specified", 0, "Senior job vs not specified"),
        ("lead", 10, "not_specified", 0, "Lead job vs not specified"),
    ]
    
    print("Testing experience match scoring with not_specified:")
    print("=" * 60)
    
    for job_level, job_years, candidate_level, candidate_years, description in test_cases:
        score = enhancer.calculate_experience_match_score(
            job_level, job_years, candidate_level, candidate_years
        )
        print(f"{description:35} | Score: {score:.1f}%")
    
    print("\n" + "=" * 60)

def test_normal_experience_matching():
    """Test normal experience matching to ensure it still works."""
    enhancer = MatchingEnhancer()
    
    test_cases = [
        ("entry", 2, "entry", 1, "Entry vs Entry"),
        ("mid", 5, "senior", 8, "Mid vs Senior (overqualified)"),
        ("senior", 7, "junior", 3, "Senior vs Junior (underqualified)"),
        ("lead", 10, "lead", 12, "Lead vs Lead (perfect match)"),
    ]
    
    print("Testing normal experience matching:")
    print("=" * 50)
    
    for job_level, job_years, candidate_level, candidate_years, description in test_cases:
        score = enhancer.calculate_experience_match_score(
            job_level, job_years, candidate_level, candidate_years
        )
        print(f"{description:30} | Score: {score:.1f}%")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    print("🧪 Testing Experience Not Specified Fix")
    print("=" * 50)
    
    test_experience_extraction()
    test_experience_match_scoring()
    test_normal_experience_matching()
    
    print("\n✅ All tests completed!")
    print("\nThe fix should now properly handle:")
    print("- Candidates with no position data")
    print("- Candidates with 'not specified' experience")
    print("- Proper scoring for different job levels")
    print("- Frontend display of 'Experience not specified'") 