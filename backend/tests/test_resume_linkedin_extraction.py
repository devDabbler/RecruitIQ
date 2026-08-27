import unittest
import sys
import os
import asyncio

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from services.agent_framework.agents.resume_processing_agent import ResumeProcessingAgent


class TestResumeLinkedInExtraction(unittest.TestCase):
    """Test the LinkedIn URL extraction enhancements."""
    
    def setUp(self):
        self.extractor = RegexExtractor()

    def test_extract_linkedin_url_simple(self):
        """Test LinkedIn extraction with a simple URL."""
        test_text = """
        John Doe
        johndoe@gmail.com
        Phone: 555-123-4567
        linkedin.com/in/johndoe
        """
        
        result = self.extractor._extract_personal_info(test_text)
        self.assertIn('linkedin', result)
        self.assertEqual(result['linkedin'], 'https://www.linkedin.com/in/johndoe')
        self.assertNotIn('website', result)

    def test_extract_linkedin_url_with_space(self):
        """Test LinkedIn extraction with OCR spacing issues."""
        test_text = """
        Jane Smith
        janesmith@gmail.com
        Phone: 555-123-4567
        linked in.com/in/janesmith
        """
        
        result = self.extractor._extract_personal_info(test_text)
        self.assertIn('linkedin', result)
        # The URL will be normalized to include https, so we test differently
        self.assertIn('janesmith', result['linkedin'])
        self.assertIn('linkedin.com', result['linkedin'])

    def test_website_extraction_excludes_email_domain(self):
        """Test that website extraction doesn't include email domains."""
        test_text = """
        John Doe
        johndoe@gmail.com
        Phone: 555-123-4567
        example.com
        """
        
        # We can't test the full agent here, but we can check that the extractor
        # doesn't include gmail.com as a website
        result = self.extractor._extract_personal_info(test_text)
        if 'website' in result:
            self.assertNotEqual(result.get('website', ''), 'gmail.com')

    def test_website_extraction_with_linkedin(self):
        """Test that LinkedIn URLs are not categorized as websites."""
        test_text = """
        John Doe
        johndoe@gmail.com
        Phone: 555-123-4567
        linkedin.com/in/johndoe
        example.com
        """
        
        result = self.extractor._extract_personal_info(test_text)
        self.assertIn('linkedin', result)
        if 'website' in result:
            self.assertNotEqual(result.get('website', ''), 'linkedin.com/in/johndoe')


if __name__ == '__main__':
    unittest.main()
