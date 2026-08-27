"""
Debug test for the Nebius AI resume parsing implementation.

This test performs comprehensive debugging of the entire Nebius AI parsing pipeline,
testing each component individually to identify exactly where failures occur.

Usage:
    poetry run python -m backend.utils.resume_parsing.tests.test_nebius_parsing_debug <path/to/resume.pdf>
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable unnecessary logging from libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

class NebiusAIParsingDebugger:
    """Debug the Nebius AI parsing process by testing each component individually."""
    
    def __init__(self, resume_file_path: str):
        self.resume_file_path = resume_file_path
        self.resume_text = None
        self.results = {}
    
    async def run_tests(self):
        """Run all tests in sequence and collect results."""
        logger.info("=" * 80)
        logger.info("🔍 NEBIUS AI RESUME PARSING DEBUGGER")
        logger.info("=" * 80)
        
        logger.info(f"Testing with file: {self.resume_file_path}")
        
        # Test 1: Test environment setup
        await self.test_environment()
        
        # Test 2: Test text extraction
        await self.test_text_extraction()
        
        # Test 3: Test Nebius AI service initialization
        await self.test_nebius_service()
        
        # Test 4: Test NebiusAIResumeParser initialization
        await self.test_parser_initialization()
        
        # Test 5: Test direct calls to Nebius AI API
        await self.test_direct_api_call()
        
        # Test 6: Test the personal info extraction
        await self.test_personal_info_extraction()
        
        # Test 7: Test the experience extraction
        await self.test_experience_extraction()
        
        # Test 8: Test the full parse_resume method
        await self.test_full_parsing()
        
        # Print summary
        self.print_summary()
    
    async def test_environment(self):
        """Test 1: Check if environment is properly set up."""
        logger.info("\n📋 TEST 1: Environment Setup")
        
        try:
            # Check if file exists
            if not os.path.exists(self.resume_file_path):
                logger.error(f"❌ Resume file not found: {self.resume_file_path}")
                self.results["environment"] = False
                return
            
            # Check for API key
            api_key = os.environ.get("NEBIUS_API_KEY") or os.environ.get("NEBIUS_API_TOKEN")
            if not api_key:
                logger.error("❌ No Nebius API key found in environment variables (NEBIUS_API_KEY or NEBIUS_API_TOKEN)")
                self.results["environment"] = False
                return
            
            # Check file type
            file_ext = os.path.splitext(self.resume_file_path)[1].lower()
            if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
                logger.error(f"❌ Unsupported file type: {file_ext}")
                self.results["environment"] = False
                return
            
            logger.info("✅ Environment setup looks good")
            self.results["environment"] = True
            
        except Exception as e:
            logger.error(f"❌ Error in environment setup: {e}")
            self.results["environment"] = False
    
    async def test_text_extraction(self):
        """Test 2: Test text extraction from resume file."""
        logger.info("\n📋 TEST 2: Text Extraction")
        
        try:
            # Import necessary components
            from backend.utils.resume_parsing.resume_parser_main import ResumeParser
            
            # Create a parser instance
            parser = ResumeParser(verbose=True)
            
            # Extract text based on file type
            file_path = self.resume_file_path
            if file_path.lower().endswith('.pdf'):
                text = await parser._extract_text_from_pdf(file_path)
            elif file_path.lower().endswith(('.doc', '.docx')):
                text = await parser._extract_text_from_docx(file_path)
            elif file_path.lower().endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            else:
                raise ValueError(f"Unsupported file type: {file_path}")
            
            # Validate extracted text
            if not text or len(text.strip()) < 50:
                logger.error(f"❌ Insufficient text extracted: {len(text) if text else 0} characters")
                self.results["text_extraction"] = False
                return
            
            # Store the text for later tests
            self.resume_text = text
            
            logger.info(f"✅ Successfully extracted {len(text)} characters from resume")
            # Print the first 200 chars as a sample
            logger.info(f"Text sample: {text[:200]}...")
            self.results["text_extraction"] = True
            
        except Exception as e:
            logger.error(f"❌ Error in text extraction: {e}")
            self.results["text_extraction"] = False
    
    async def test_nebius_service(self):
        """Test 3: Test Nebius AI service initialization."""
        logger.info("\n📋 TEST 3: Nebius AI Service")
        
        try:
            # Import necessary components
            from backend.services.nebius_ai_service import get_nebius_ai_service, NebiusAIService
            
            # Get the Nebius AI service
            service = get_nebius_ai_service()
            
            if service is None:
                logger.error("❌ Failed to initialize Nebius AI service")
                self.results["nebius_service"] = False
                return
            
            # Verify service is initialized correctly
            if not isinstance(service, NebiusAIService):
                logger.error(f"❌ Wrong service type: {type(service).__name__}")
                self.results["nebius_service"] = False
                return
            
            # Check if API key is set
            if not service.api_key:
                logger.error("❌ Nebius AI service has no API key set")
                self.results["nebius_service"] = False
                return
            
            # Store service for later tests
            self.nebius_service = service
            
            logger.info(f"✅ Nebius AI service initialized with model: {service.model}")
            self.results["nebius_service"] = True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Nebius AI service: {e}")
            self.results["nebius_service"] = False
    
    async def test_parser_initialization(self):
        """Test 4: Test NebiusAIResumeParser initialization."""
        logger.info("\n📋 TEST 4: NebiusAIResumeParser Initialization")
        
        try:
            # Import necessary components
            from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIResumeParser
            
            if not hasattr(self, 'nebius_service'):
                logger.error("❌ Nebius AI service not initialized in previous test")
                self.results["parser_initialization"] = False
                return
            
            # Create parser
            parser = NebiusAIResumeParser(self.nebius_service)
            
            # Check parser attributes
            if not hasattr(parser, 'nebius_ai_service') or parser.nebius_ai_service is None:
                logger.error("❌ Parser has no nebius_ai_service attribute")
                self.results["parser_initialization"] = False
                return
            
            # Check for required methods
            required_methods = ['parse_resume', '_extract_personal_info', '_extract_experience_fast']
            missing_methods = []
            
            for method in required_methods:
                if not hasattr(parser, method) or not callable(getattr(parser, method)):
                    missing_methods.append(method)
            
            if missing_methods:
                logger.error(f"❌ Parser is missing required methods: {', '.join(missing_methods)}")
                self.results["parser_initialization"] = False
                return
            
            # Store parser for later tests
            self.parser = parser
            
            logger.info("✅ NebiusAIResumeParser initialized successfully")
            self.results["parser_initialization"] = True
            
        except Exception as e:
            logger.error(f"❌ Error initializing NebiusAIResumeParser: {e}")
            self.results["parser_initialization"] = False
    
    async def test_direct_api_call(self):
        """Test 5: Test direct API call to Nebius AI."""
        logger.info("\n📋 TEST 5: Direct API Call")
        
        try:
            if not hasattr(self, 'nebius_service'):
                logger.error("❌ Nebius AI service not initialized in previous test")
                self.results["direct_api_call"] = False
                return
            
            # Create a simple test prompt
            test_prompt = "Hello, my name is Assistant. Please respond with a JSON object containing: {\"response\": \"Hello, human!\"}"
            
            # Try different methods to see which one works
            methods_to_try = ['generate_completion', 'generate_text', '__call__']
            success = False
            
            for method_name in methods_to_try:
                if hasattr(self.nebius_service, method_name) and callable(getattr(self.nebius_service, method_name)):
                    try:
                        method = getattr(self.nebius_service, method_name)
                        logger.info(f"Trying method: {method_name}")
                        response = await method(test_prompt)
                        
                        logger.info(f"✅ Successfully called {method_name}")
                        logger.info(f"Response: {response[:100]}...")
                        
                        # Record the working method
                        self.working_method = method_name
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"Method {method_name} failed: {e}")
            
            if success:
                logger.info(f"✅ Direct API call successful using method: {self.working_method}")
                self.results["direct_api_call"] = True
            else:
                logger.error("❌ All API call methods failed")
                self.results["direct_api_call"] = False
            
        except Exception as e:
            logger.error(f"❌ Error in direct API call: {e}")
            self.results["direct_api_call"] = False
    
    async def test_personal_info_extraction(self):
        """Test 6: Test personal info extraction method."""
        logger.info("\n📋 TEST 6: Personal Info Extraction")
        
        try:
            if not hasattr(self, 'parser') or not hasattr(self, 'resume_text'):
                logger.error("❌ Parser or resume text not initialized in previous tests")
                self.results["personal_info"] = False
                return
            
            # Patch the parser if we found a working method
            if hasattr(self, 'working_method') and self.working_method != 'generate_completion':
                original_method = getattr(self.nebius_service, self.working_method)
                
                # Monkey patch the generate_completion method to use the working method
                async def patched_generate_completion(*args, **kwargs):
                    return await original_method(*args, **kwargs)
                
                # Apply the patch
                self.nebius_service.generate_completion = patched_generate_completion
                logger.info(f"Patched generate_completion to use {self.working_method}")
            
            # Call the personal info extraction method directly
            try:
                personal_info = await self.parser._extract_personal_info(self.resume_text, self.resume_file_path)
                
                # Check the results
                if personal_info.name and personal_info.name != "Parsing failed":
                    logger.info(f"✅ Successfully extracted name: {personal_info.name}")
                else:
                    logger.warning(f"⚠️ Extracted name might have issues: '{personal_info.name}'")
                
                # Log all extracted info
                logger.info(f"Personal Info: {personal_info.dict()}")
                
                self.results["personal_info"] = personal_info.name and personal_info.name != "Parsing failed"
                self.personal_info = personal_info
                
            except Exception as e:
                logger.error(f"❌ Error in personal info extraction: {e}")
                self.results["personal_info"] = False
                
        except Exception as e:
            logger.error(f"❌ Error setting up personal info test: {e}")
            self.results["personal_info"] = False
    
    async def test_experience_extraction(self):
        """Test 7: Test experience extraction method."""
        logger.info("\n📋 TEST 7: Experience Extraction")
        
        try:
            if not hasattr(self, 'parser') or not hasattr(self, 'resume_text'):
                logger.error("❌ Parser or resume text not initialized in previous tests")
                self.results["experience"] = False
                return
            
            # Call the experience extraction method
            try:
                experiences_data = await self.parser._extract_experience_fast(self.resume_text)
                
                # Check if we got any experiences
                if experiences_data and len(experiences_data) > 0:
                    logger.info(f"✅ Successfully extracted {len(experiences_data)} experience entries")
                    
                    # Log first experience
                    if len(experiences_data) > 0:
                        exp = experiences_data[0]
                        logger.info(f"First experience: {json.dumps(exp, indent=2)}")
                        
                    self.results["experience"] = True
                else:
                    logger.warning("⚠️ No experiences extracted")
                    self.results["experience"] = False
                
                self.experiences_data = experiences_data
                
            except Exception as e:
                logger.error(f"❌ Error in experience extraction: {e}")
                self.results["experience"] = False
                
        except Exception as e:
            logger.error(f"❌ Error setting up experience test: {e}")
            self.results["experience"] = False
    
    async def test_full_parsing(self):
        """Test 8: Test the full parse_resume method."""
        logger.info("\n📋 TEST 8: Full Resume Parsing")
        
        try:
            if not hasattr(self, 'parser') or not hasattr(self, 'resume_text'):
                logger.error("❌ Parser or resume text not initialized in previous tests")
                self.results["full_parsing"] = False
                return
            
            # Call the full parse_resume method
            try:
                resume_data = await self.parser.parse_resume(self.resume_text, self.resume_file_path)
                
                # Check if we got valid data
                if resume_data:
                    name = resume_data.personal_info.name if resume_data.personal_info else "Unknown"
                    exp_count = len(resume_data.experience) if resume_data.experience else 0
                    
                    if name and name != "Parsing failed":
                        logger.info(f"✅ Successfully parsed resume for: {name}")
                        logger.info(f"Found {exp_count} experiences")
                        self.results["full_parsing"] = True
                    else:
                        logger.warning("⚠️ Resume parsing failed or returned minimal data")
                        self.results["full_parsing"] = False
                else:
                    logger.error("❌ Resume parsing returned no data")
                    self.results["full_parsing"] = False
                
                # Store the full result
                self.resume_data = resume_data
                
            except Exception as e:
                logger.error(f"❌ Error in full resume parsing: {e}")
                self.results["full_parsing"] = False
                
        except Exception as e:
            logger.error(f"❌ Error setting up full parsing test: {e}")
            self.results["full_parsing"] = False
    
    def print_summary(self):
        """Print a summary of all test results."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        
        all_passed = True
        for test_name, result in self.results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            logger.info("\n✅ SUCCESS: All tests passed!")
        else:
            logger.error("\n❌ FAILURE: Some tests failed. See details above.")
        
        # Check for critical failures and suggest fixes
        self._suggest_fixes()
    
    def _suggest_fixes(self):
        """Suggest fixes based on test results."""
        logger.info("\n" + "=" * 80)
        logger.info("SUGGESTED FIXES")
        logger.info("=" * 80)
        
        if not self.results.get("environment", True):
            logger.info("🔧 Make sure NEBIUS_API_KEY environment variable is set")
            logger.info("🔧 Ensure the resume file exists and is in a supported format (PDF, DOCX, TXT)")
        
        if not self.results.get("nebius_service", True):
            logger.info("🔧 Check the Nebius AI service initialization in backend/services/nebius_ai_service.py")
            logger.info("🔧 Verify the API key is being loaded correctly")
        
        if not self.results.get("direct_api_call", True):
            if hasattr(self, 'working_method'):
                logger.info(f"🔧 The method 'generate_completion' failed, but '{self.working_method}' works.")
                logger.info(f"🔧 Update NebiusAIResumeParser to use '{self.working_method}' instead of 'generate_completion'")
            else:
                logger.info("🔧 All API call methods failed. Check the API key and connection.")
        
        if not self.results.get("personal_info", True):
            logger.info("🔧 The personal info extraction is failing. Check the _extract_personal_info method.")
            logger.info("🔧 Ensure the JSON response from Nebius AI is being parsed correctly.")
        
        if not self.results.get("experience", True):
            logger.info("🔧 The experience extraction is failing. Check the _extract_experience_fast method.")
            logger.info("🔧 Review the regex patterns for detecting job experiences.")
            
        if not self.results.get("full_parsing", True):
            if self.results.get("personal_info", True) and self.results.get("experience", True):
                logger.info("🔧 Individual components work but full parsing fails. Check the parse_resume method.")
            else:
                logger.info("🔧 Full parsing is failing due to issues in the individual components.")

async def main():
    """Main entry point for the script."""
    # Get the resume file path from command line arguments
    if len(sys.argv) > 1:
        resume_file = sys.argv[1]
    else:
        # Try to find a resume in the current directory
        resume_files = list(Path('.').glob('*.pdf')) + list(Path('.').glob('*.docx'))
        if resume_files:
            resume_file = str(resume_files[0])
            logger.info(f"No resume file specified, using: {resume_file}")
        else:
            logger.error("No resume file specified and none found in current directory")
            logger.error("Usage: poetry run python -m backend.utils.resume_parsing.tests.test_nebius_parsing_debug <path/to/resume.pdf>")
            return 1
    
    # Run the debugging tests
    debugger = NebiusAIParsingDebugger(resume_file)
    await debugger.run_tests()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
