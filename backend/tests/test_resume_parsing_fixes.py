#!/usr/bin/env python3
"""
Test script for resume parsing fixes
Tests the improvements made to institution validation, block splitting, LLM integration, and caching.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from backend.utils.resume_parsing.resume_parser_main import ResumeParser
from backend.utils.resume_parsing.models.resume_schema import ResumeData

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResumeParsingTestSuite:
    def __init__(self):
        self.regex_extractor = RegexExtractor()
        self.test_results = []
        
    def test_institution_validation(self):
        """Test the improved institution validation"""
        logger.info("🧪 Testing institution validation...")
        
        # Test cases that should be REJECTED (false positives from before)
        invalid_institutions = [
            "Northwestern University - Boston",  # Contains job-related term
            "Summer Associate - Data",           # Job title
            "Consumer Products Goods",           # Company name
            "Bachelor of Science, Computer Science",  # Degree only
            "Data Analyst",                      # Job title
            "Associate - Data",                  # Job title
            "VA Collaborated",                   # Action verb
            "Consumer Lending and Credit Card Portfolio",  # Company description
            "Education Lending Models",          # Company name
            "Cognizant - Chennai",               # Company with location
            "Google",                            # Company name
            "Amazon",                            # Company name
            "Azure",                             # Tool name
            "MS Office",                         # Tool name
            "Python",                            # Programming language
            "Java",                              # Programming language
            "2020",                              # Year
            "January",                           # Month
            "Summer",                            # Season
            "Associate",                         # Job level
            "Analyst",                           # Job title
            "Manager",                           # Job title
            "Director",                          # Job title
            "Intern",                            # Job title
            "Consultant",                        # Job title
            "Developer",                         # Job title
            "Specialist",                        # Job title
            "Coordinator",                       # Job title
            "Administrator",                     # Job title
            "Collaborated",                      # Action verb
            "Developed",                         # Action verb
            "Managed",                           # Action verb
            "Created",                           # Action verb
            "Implemented",                       # Action verb
            "Designed",                          # Action verb
            "Analyzed",                          # Action verb
            "Built",                             # Action verb
            "Led",                               # Action verb
            "Conducted",                         # Action verb
        ]
        
        # Test cases that should be ACCEPTED (valid institutions)
        valid_institutions = [
            "Northwestern University",
            "Georgia Institute of Technology", 
            "Stanford University",
            "Harvard University",
            "MIT",
            "University of California, Berkeley",
            "Columbia University",
            "Yale University",
            "Princeton University",
            "University of Michigan",
            "University of Texas at Austin",
            "Carnegie Mellon University",
            "University of Illinois at Urbana-Champaign",
            "University of Washington",
            "University of Pennsylvania",
            "Cornell University",
            "University of Wisconsin-Madison",
            "University of Maryland",
            "University of Minnesota",
            "University of Virginia",
            "University of North Carolina at Chapel Hill",
            "University of Florida",
            "University of Arizona",
            "University of Colorado Boulder",
            "University of Utah",
            "University of Oregon",
            "University of Iowa",
            "University of Kansas",
            "University of Missouri",
            "University of Nebraska-Lincoln",
            "University of Oklahoma",
            "University of Arkansas",
            "University of Mississippi",
            "University of Alabama",
            "University of Kentucky",
            "University of Tennessee",
            "University of South Carolina",
            "University of Georgia",
            "University of Louisiana at Lafayette",
            "University of New Mexico",
            "University of Nevada, Las Vegas",
            "University of Hawaii at Manoa",
            "University of Alaska Fairbanks",
            "University of Delaware",
            "University of Rhode Island",
            "University of Connecticut",
            "University of Maine",
            "University of New Hampshire",
            "University of Vermont",
            "University of Massachusetts Amherst",
            "University of New York",
            "University of New Jersey",
            "University of Pennsylvania",
            "University of Maryland",
            "University of Virginia",
            "University of North Carolina",
            "University of South Carolina",
            "University of Georgia",
            "University of Florida",
            "University of Alabama",
            "University of Mississippi",
            "University of Louisiana",
            "University of Arkansas",
            "University of Tennessee",
            "University of Kentucky",
            "University of Missouri",
            "University of Kansas",
            "University of Oklahoma",
            "University of Texas",
            "University of New Mexico",
            "University of Arizona",
            "University of Nevada",
            "University of Utah",
            "University of Colorado",
            "University of Wyoming",
            "University of Montana",
            "University of Idaho",
            "University of Washington",
            "University of Oregon",
            "University of California",
            "University of Alaska",
            "University of Hawaii",
            "University of Nevada",
            "University of Arizona",
            "University of New Mexico",
            "University of Texas",
            "University of Oklahoma",
            "University of Kansas",
            "University of Missouri",
            "University of Arkansas",
            "University of Louisiana",
            "University of Mississippi",
            "University of Alabama",
            "University of Georgia",
            "University of Florida",
            "University of South Carolina",
            "University of North Carolina",
            "University of Virginia",
            "University of Maryland",
            "University of Delaware",
            "University of Pennsylvania",
            "University of New Jersey",
            "University of New York",
            "University of Connecticut",
            "University of Rhode Island",
            "University of Massachusetts",
            "University of Vermont",
            "University of New Hampshire",
            "University of Maine",
            "University of Alaska",
            "University of Hawaii",
            "University of California",
            "University of Oregon",
            "University of Washington",
            "University of Idaho",
            "University of Montana",
            "University of Wyoming",
            "University of Colorado",
            "University of Utah",
            "University of Nevada",
            "University of Arizona",
            "University of New Mexico",
            "University of Texas",
            "University of Oklahoma",
            "University of Kansas",
            "University of Missouri",
            "University of Arkansas",
            "University of Louisiana",
            "University of Mississippi",
            "University of Alabama",
            "University of Georgia",
            "University of Florida",
            "University of South Carolina",
            "University of North Carolina",
            "University of Virginia",
            "University of Maryland",
            "University of Delaware",
            "University of Pennsylvania",
            "University of New Jersey",
            "University of New York",
            "University of Connecticut",
            "University of Rhode Island",
            "University of Massachusetts",
            "University of Vermont",
            "University of New Hampshire",
            "University of Maine",
        ]
        
        # Test invalid institutions
        invalid_failures = []
        for inst in invalid_institutions:
            if self.regex_extractor._is_valid_institution(inst):
                invalid_failures.append(inst)
                logger.error(f"❌ Invalid institution ACCEPTED: {inst}")
        
        # Test valid institutions
        valid_failures = []
        for inst in valid_institutions:
            if not self.regex_extractor._is_valid_institution(inst):
                valid_failures.append(inst)
                logger.error(f"❌ Valid institution REJECTED: {inst}")
        
        # Report results
        total_invalid_tests = len(invalid_institutions)
        total_valid_tests = len(valid_institutions)
        invalid_success_rate = (total_invalid_tests - len(invalid_failures)) / total_invalid_tests * 100
        valid_success_rate = (total_valid_tests - len(valid_failures)) / total_valid_tests * 100
        
        logger.info(f"📊 Institution Validation Results:")
        logger.info(f"   Invalid institutions: {total_invalid_tests - len(invalid_failures)}/{total_invalid_tests} correctly rejected ({invalid_success_rate:.1f}%)")
        logger.info(f"   Valid institutions: {total_valid_tests - len(valid_failures)}/{total_valid_tests} correctly accepted ({valid_success_rate:.1f}%)")
        
        if invalid_failures:
            logger.warning(f"⚠️  Invalid institutions that were incorrectly accepted: {invalid_failures}")
        if valid_failures:
            logger.warning(f"⚠️  Valid institutions that were incorrectly rejected: {valid_failures}")
        
        self.test_results.append({
            'test': 'institution_validation',
            'invalid_success_rate': invalid_success_rate,
            'valid_success_rate': valid_success_rate,
            'invalid_failures': invalid_failures,
            'valid_failures': valid_failures
        })
        
        return invalid_success_rate >= 95 and valid_success_rate >= 95

    def test_education_block_extraction(self):
        """Test the improved education block extraction"""
        logger.info("🧪 Testing education block extraction...")
        
        # Test cases with problematic text that should be handled better
        test_cases = [
            {
                'name': 'Clint Forest Resume Style',
                'text': """
## Education
Georgia Technical Institute - Atlanta, GA (January 2016 - December 2023)
### Bachelor of Science, Computer Science

Northwestern University - Boston, MA (January 2020 - January 2022)
### Masters of Science, Information Systems

## Work Experience
### Summer Associate - Data Analyst (May 2023 - August 2023)
### Credit Union - Alexandria, VA
Collaborated with the Lending Analytics team...
                """,
                'expected_institutions': ['Georgia Technical Institute', 'Northwestern University'],
                'expected_rejected': ['Summer Associate - Data', 'Credit Union']
            },
            {
                'name': 'Mixed Content Test',
                'text': """
Bachelor of Science, Computer Science
Consumer Products Goods (C.P.G.) at Consumer Products Goods
Data Analyst (January at Cognizant - Chennai
Northwestern University - Boston, MA
Georgia Institute of Technology - Atlanta, GA
                """,
                'expected_institutions': ['Northwestern University', 'Georgia Institute of Technology'],
                'expected_rejected': ['Consumer Products Goods', 'Data Analyst', 'Cognizant']
            }
        ]
        
        results = []
        for test_case in test_cases:
            logger.info(f"   Testing: {test_case['name']}")
            
            # Extract education blocks
            from backend.utils.resume_parsing.extractors.regex_extractor import extract_education_from_section
            extracted_blocks = extract_education_from_section(test_case['text'])
            
            # Extract institution names
            extracted_institutions = [block.get('institution', '') for block in extracted_blocks if block.get('institution')]
            
            # Check for expected institutions
            found_expected = [inst for inst in test_case['expected_institutions'] 
                            if any(inst.lower() in ext_inst.lower() for ext_inst in extracted_institutions)]
            
            # Check for rejected institutions (should NOT be found)
            found_rejected = [inst for inst in test_case['expected_rejected'] 
                            if any(inst.lower() in ext_inst.lower() for ext_inst in extracted_institutions)]
            
            success = (len(found_expected) == len(test_case['expected_institutions']) and 
                      len(found_rejected) == 0)
            
            logger.info(f"     Found institutions: {extracted_institutions}")
            logger.info(f"     Expected found: {found_expected}/{test_case['expected_institutions']}")
            logger.info(f"     Rejected found: {found_rejected} (should be 0)")
            logger.info(f"     Result: {'✅ PASS' if success else '❌ FAIL'}")
            
            results.append({
                'name': test_case['name'],
                'success': success,
                'found_expected': found_expected,
                'found_rejected': found_rejected,
                'extracted_institutions': extracted_institutions
            })
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        logger.info(f"📊 Education Block Extraction Results: {success_rate:.1f}% success rate")
        
        self.test_results.append({
            'test': 'education_block_extraction',
            'success_rate': success_rate,
            'results': results
        })
        
        return success_rate >= 80

    def test_llm_response_validation(self):
        """Test the LLM response validation"""
        logger.info("🧪 Testing LLM response validation...")
        
        # Mock LLM responses for testing
        test_responses = [
            {
                'name': 'Valid Education Response',
                'response': {
                    'education': [
                        {'institution': 'Stanford University', 'degree': 'BS', 'field_of_study': 'Computer Science'}
                    ]
                },
                'field': 'education',
                'expected': True
            },
            {
                'name': 'Invalid Education Response - Missing List',
                'response': {
                    'education': 'Stanford University'
                },
                'field': 'education',
                'expected': False
            },
            {
                'name': 'Invalid Education Response - Missing Field',
                'response': {
                    'universities': ['Stanford University']
                },
                'field': 'education',
                'expected': False
            },
            {
                'name': 'Valid Experience Response',
                'response': {
                    'experience': [
                        {'title': 'Software Engineer', 'company': 'Google', 'start_date': '2020', 'end_date': '2023'}
                    ]
                },
                'field': 'experience',
                'expected': True
            },
            {
                'name': 'Invalid Experience Response - Not Dict',
                'response': ['Software Engineer at Google'],
                'field': 'experience',
                'expected': False
            },
            {
                'name': 'Valid Skills Response',
                'response': {
                    'skills': [
                        {'name': 'Python'},
                        {'name': 'JavaScript'}
                    ]
                },
                'field': 'skills',
                'expected': True
            }
        ]
        
        results = []
        for test_case in test_responses:
            # Create a mock parser instance to test validation
            mock_parser = ResumeParser(None, None, None)
            is_valid = mock_parser._validate_llm_response(test_case['response'], test_case['field'])
            
            success = is_valid == test_case['expected']
            logger.info(f"   {test_case['name']}: {'✅ PASS' if success else '❌ FAIL'} (Expected: {test_case['expected']}, Got: {is_valid})")
            
            results.append({
                'name': test_case['name'],
                'success': success,
                'expected': test_case['expected'],
                'got': is_valid
            })
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        logger.info(f"📊 LLM Response Validation Results: {success_rate:.1f}% success rate")
        
        self.test_results.append({
            'test': 'llm_response_validation',
            'success_rate': success_rate,
            'results': results
        })
        
        return success_rate >= 90

    def test_text_cleaning(self):
        """Test the text cleaning functions"""
        logger.info("🧪 Testing text cleaning functions...")
        
        # Test cases for text cleaning
        test_cases = [
            {
                'name': 'Excessive Whitespace',
                'input': '  Hello    World  \n\n  Test  ',
                'expected': 'Hello World Test'
            },
            {
                'name': 'JSON Characters',
                'input': 'Text with {brackets} and [square] brackets',
                'expected': 'Text with brackets and square brackets'
            },
            {
                'name': 'Bullet Points',
                'input': '• Item 1\n- Item 2\n* Item 3',
                'expected': 'Item 1\nItem 2\nItem 3'
            },
            {
                'name': 'Mixed Cleaning',
                'input': '  • Hello {World}  \n\n  - Test  ',
                'expected': 'Hello World\nTest'
            }
        ]
        
        # Create a mock parser instance
        mock_parser = ResumeParser(None, None, None)
        
        results = []
        for test_case in test_cases:
            cleaned = mock_parser._clean_section_for_llm(test_case['input'])
            success = cleaned.strip() == test_case['expected'].strip()
            
            logger.info(f"   {test_case['name']}: {'✅ PASS' if success else '❌ FAIL'}")
            if not success:
                logger.info(f"     Expected: '{test_case['expected']}'")
                logger.info(f"     Got: '{cleaned}'")
            
            results.append({
                'name': test_case['name'],
                'success': success,
                'expected': test_case['expected'],
                'got': cleaned
            })
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        logger.info(f"📊 Text Cleaning Results: {success_rate:.1f}% success rate")
        
        self.test_results.append({
            'test': 'text_cleaning',
            'success_rate': success_rate,
            'results': results
        })
        
        return success_rate >= 90

    def test_token_truncation(self):
        """Test the token-based truncation"""
        logger.info("🧪 Testing token truncation...")
        
        # Test cases for token truncation
        test_cases = [
            {
                'name': 'Short Text (No Truncation)',
                'input': 'This is a short text that should not be truncated.',
                'max_tokens': 100,
                'should_truncate': False
            },
            {
                'name': 'Long Text (Should Truncate)',
                'input': 'This is a very long text that should be truncated. ' * 1000,  # ~6000 tokens
                'max_tokens': 100,
                'should_truncate': True
            }
        ]
        
        # Create a mock parser instance
        mock_parser = ResumeParser(None, None, None)
        
        results = []
        for test_case in test_cases:
            truncated = mock_parser._truncate_by_tokens(test_case['input'], test_case['max_tokens'])
            
            # Check if truncation occurred
            was_truncated = len(truncated) < len(test_case['input'])
            success = was_truncated == test_case['should_truncate']
            
            logger.info(f"   {test_case['name']}: {'✅ PASS' if success else '❌ FAIL'}")
            if test_case['should_truncate']:
                logger.info(f"     Original length: {len(test_case['input'])} chars")
                logger.info(f"     Truncated length: {len(truncated)} chars")
            
            results.append({
                'name': test_case['name'],
                'success': success,
                'was_truncated': was_truncated,
                'should_truncate': test_case['should_truncate']
            })
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        logger.info(f"📊 Token Truncation Results: {success_rate:.1f}% success rate")
        
        self.test_results.append({
            'test': 'token_truncation',
            'success_rate': success_rate,
            'results': results
        })
        
        return success_rate >= 90

    def test_file_hash_generation(self):
        """Test the file hash generation for caching"""
        logger.info("🧪 Testing file hash generation...")
        
        # Create a temporary test file
        test_content = "This is a test resume content for hash generation."
        test_file_path = "test_resume.txt"
        
        try:
            with open(test_file_path, 'w') as f:
                f.write(test_content)
            
            # Create a mock parser instance
            mock_parser = ResumeParser(None, None, None)
            
            # Generate hash
            hash1 = mock_parser._get_file_hash(test_file_path)
            hash2 = mock_parser._get_file_hash(test_file_path)
            
            # Test that same content produces same hash
            success = hash1 == hash2 and len(hash1) == 32  # MD5 hash length
            
            logger.info(f"   Hash consistency: {'✅ PASS' if success else '❌ FAIL'}")
            logger.info(f"     Hash: {hash1}")
            logger.info(f"     Length: {len(hash1)} characters")
            
            # Test with different content
            with open(test_file_path, 'w') as f:
                f.write("Different content")
            
            hash3 = mock_parser._get_file_hash(test_file_path)
            different_content_success = hash1 != hash3
            
            logger.info(f"   Different content produces different hash: {'✅ PASS' if different_content_success else '❌ FAIL'}")
            
            overall_success = success and different_content_success
            
        except Exception as e:
            logger.error(f"   Error during hash testing: {e}")
            overall_success = False
        finally:
            # Clean up
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
        
        logger.info(f"📊 File Hash Generation Results: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        self.test_results.append({
            'test': 'file_hash_generation',
            'success': overall_success
        })
        
        return overall_success

    def run_all_tests(self):
        """Run all tests and report results"""
        logger.info("🚀 Starting Resume Parsing Fixes Test Suite")
        logger.info("=" * 60)
        
        tests = [
            ('Institution Validation', self.test_institution_validation),
            ('Education Block Extraction', self.test_education_block_extraction),
            ('LLM Response Validation', self.test_llm_response_validation),
            ('Text Cleaning', self.test_text_cleaning),
            ('Token Truncation', self.test_token_truncation),
            ('File Hash Generation', self.test_file_hash_generation),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n📋 Running {test_name}...")
            try:
                if test_func():
                    passed_tests += 1
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    logger.error(f"❌ {test_name} FAILED")
            except Exception as e:
                logger.error(f"❌ {test_name} FAILED with exception: {e}")
        
        # Final report
        logger.info("\n" + "=" * 60)
        logger.info("📊 FINAL TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Tests Passed: {passed_tests}/{total_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED! Resume parsing fixes are working correctly.")
        else:
            logger.warning(f"⚠️  {total_tests - passed_tests} tests failed. Please review the issues above.")
        
        # Detailed results
        logger.info("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            if 'success_rate' in result:
                logger.info(f"   {result['test']}: {result['success_rate']:.1f}%")
            elif 'success' in result:
                logger.info(f"   {result['test']}: {'PASS' if result['success'] else 'FAIL'}")
        
        return passed_tests == total_tests

def main():
    """Main test runner"""
    test_suite = ResumeParsingTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n🎉 All resume parsing fixes are working correctly!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    exit(main()) 