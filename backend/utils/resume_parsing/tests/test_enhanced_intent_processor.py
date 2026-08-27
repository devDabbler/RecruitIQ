"""Test the enhanced intent processor for all edge cases."""

import asyncio
import logging
from typing import Dict, Any
import sys
import os
import json
import re

# Add the backend directory to the path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.insert(0, backend_dir)

from backend.services.intent_processor import IntentProcessor
from backend.services.llm_service import LLMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockLLMService:
    """Mock LLM service for testing."""
    
    def _extract_role_from_message(self, message: str) -> str:
        """Extract role from message for testing."""
        message_lower = message.lower()
        
        # Common role patterns with case preservation
        role_patterns = [
            ("gen ai", r"gen ai"),
            ("AI engineer", r"ai engineer"),
            ("data scientist", r"data scientist"),
            ("software engineer", r"software engineer"),
            ("marketing", r"marketing"),
            ("sales", r"sales"),
            ("product manager", r"product manager"),
            ("devops engineer", r"devops engineer"),
            ("frontend developer", r"frontend developer"),
            ("backend developer", r"backend developer"),
            ("full stack developer", r"full stack developer"),
            ("machine learning engineer", r"machine learning engineer"),
            ("data analyst", r"data analyst"),
            ("business analyst", r"business analyst"),
            ("project manager", r"project manager")
        ]
        
        for role_name, pattern in role_patterns:
            if pattern in message_lower:
                return role_name
        
        # Fallback to common roles if no specific match
        if "gen ai" in message_lower or "ai" in message_lower:
            return "gen ai"
        elif "software" in message_lower or "developer" in message_lower:
            return "software engineer"
        elif "data" in message_lower:
            return "data scientist"
        elif "marketing" in message_lower:
            return "marketing"
        else:
            return "data scientist"  # Default fallback
    
    async def generate_text_async(self, prompt: str, system_message: str = None, **kwargs):
        """Mock text generation that returns a structured response based on the prompt."""
        # Extract the original message from the prompt
        message_match = re.search(r"User message: (.+?)(?:\n|$)", prompt)
        original_message = message_match.group(1) if message_match else ""
        
        if "recruiter outreach email" in prompt.lower() or "recruiter" in prompt.lower():
            role = self._extract_role_from_message(original_message)
            return json.dumps({
                "intent": "recruiter_outreach_email",
                "entities": {"role": role},
                "confidence": 0.9,
                "reasoning": "User asked for recruiter outreach email to candidates"
            })
        elif "candidate pitch email" in prompt.lower() or "candidate" in prompt.lower():
            role = self._extract_role_from_message(original_message)
            return json.dumps({
                "intent": "candidate_pitch_email", 
                "entities": {"role": role},
                "confidence": 0.9,
                "reasoning": "User asked for candidate pitch email to company"
            })
        else:
            return json.dumps({
                "intent": "general_question",
                "entities": {},
                "confidence": 0.5,
                "reasoning": "General query"
            })
    
    async def generate_text(self, prompt: str, **kwargs):
        """Mock text generation for email content."""
        if "recruiter" in prompt.lower():
            return """Subject: Exciting Data Scientist Opportunity at [Company Name]

Dear [Candidate Name],

I hope this message finds you well. I'm reaching out because I believe your background in data science would be a perfect fit for an exciting opportunity we have at [Company Name].

We're looking for a talented Data Scientist to join our growing team and help us build innovative solutions that drive business impact. Your experience with machine learning, statistical analysis, and data visualization would be invaluable to our mission.

What makes this role special:
• Work on cutting-edge projects with real-world impact
• Collaborative team environment with opportunities for growth
• Competitive compensation and benefits package
• Flexible work arrangements

Would you be interested in learning more about this opportunity? I'd love to schedule a brief call to discuss how this role aligns with your career goals.

Best regards,
[Your Name]
Senior Recruiter
[Company Name]"""
        else:
            return "Generated email content"

async def test_intent_detection():
    """Test intent detection for various scenarios."""
    
    # Initialize the intent processor with mock LLM service
    mock_llm = MockLLMService()
    intent_processor = IntentProcessor(llm_service=mock_llm)
    
    # Test cases for email generation intents
    test_cases = [
        {
            "message": "Can you create a recruiter outreach email sent to prospective candidates for the gen ai job?",
            "expected_intent": "recruiter_outreach_email",
            "expected_role": "gen ai",
            "description": "Recruiter outreach email request"
        },
        {
            "message": "Generate a candidate pitch email for a software engineer position",
            "expected_intent": "candidate_pitch_email", 
            "expected_role": "software engineer",
            "description": "Candidate pitch email request"
        },
        {
            "message": "Write a recruiter email to potential data scientist candidates",
            "expected_intent": "recruiter_outreach_email",
            "expected_role": "data scientist",
            "description": "Recruiter email to candidates"
        },
        {
            "message": "Create a pitch email from a candidate to a company for a marketing role",
            "expected_intent": "candidate_pitch_email",
            "expected_role": "marketing",
            "description": "Candidate pitch to company"
        },
        {
            "message": "Draft an outreach email from a recruiter to candidates for the AI engineer position",
            "expected_intent": "recruiter_outreach_email",
            "expected_role": "AI engineer",
            "description": "Recruiter outreach for AI engineer"
        }
    ]
    
    print("Testing Intent Detection:")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Message: {test_case['message']}")
        
        try:
            # Test intent detection
            intent_result = await intent_processor.detect_intent(test_case['message'])
            detected_intent = intent_result.get('intent', 'unknown')
            detected_entities = intent_result.get('entities', {})
            detected_role = detected_entities.get('role', '')
            confidence = intent_result.get('confidence', 0)
            
            print(f"Detected Intent: {detected_intent}")
            print(f"Expected Intent: {test_case['expected_intent']}")
            print(f"Detected Role: {detected_role}")
            print(f"Expected Role: {test_case['expected_role']}")
            print(f"Confidence: {confidence}")
            
            # Check if intent matches
            intent_correct = detected_intent == test_case['expected_intent']
            role_correct = (test_case['expected_role'].lower() in detected_role.lower() or 
                           detected_role.lower() in test_case['expected_role'].lower())
            
            if intent_correct and role_correct:
                print("✅ PASS")
            else:
                print("❌ FAIL")
                if not intent_correct:
                    print(f"  - Intent mismatch: expected {test_case['expected_intent']}, got {detected_intent}")
                if not role_correct:
                    print(f"  - Role mismatch: expected {test_case['expected_role']}, got {detected_role}")
                    
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")

async def test_email_generation():
    """Test email generation functionality."""
    
    print("\n\nTesting Email Generation:")
    print("=" * 50)
    
    # Initialize the intent processor with mock LLM service
    mock_llm = MockLLMService()
    intent_processor = IntentProcessor(llm_service=mock_llm)
    
    # Test recruiter outreach email generation
    print("\nTest: Recruiter Outreach Email Generation")
    try:
        result = await intent_processor.process_intent(
            "recruiter_outreach_email",
            {"role": "data scientist"},
            "Create a recruiter outreach email for data scientist candidates"
        )
        
        if result.get("intent_processed", False):
            email_content = result.get("outreach_email", "")
            print("✅ Email generated successfully")
            print(f"Email length: {len(email_content)} characters")
            print("First 200 characters:")
            print(email_content[:200] + "...")
        else:
            print("❌ Failed to generate email")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
    
    # Test candidate pitch email generation
    print("\nTest: Candidate Pitch Email Generation")
    try:
        result = await intent_processor.process_intent(
            "candidate_pitch_email",
            {"role": "software engineer"},
            "Create a candidate pitch email for software engineer position"
        )
        
        if result.get("intent_processed", False):
            email_content = result.get("pitch_email", "")
            print("✅ Email generated successfully")
            print(f"Email length: {len(email_content)} characters")
            print("First 200 characters:")
            print(email_content[:200] + "...")
        else:
            print("❌ Failed to generate email")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

async def test_pattern_matching():
    """Test pattern matching for edge cases."""
    
    print("\n\nTesting Pattern Matching:")
    print("=" * 50)
    
    # Initialize the intent processor
    intent_processor = IntentProcessor()
    
    # Test cases for pattern matching
    pattern_test_cases = [
        {
            "message": "generate a recruiter outreach email sent to prospective candidates for the gen ai job",
            "expected_intent": "recruiter_outreach_email",
            "description": "Pattern match for recruiter outreach"
        },
        {
            "message": "create a candidate pitch email for software engineer",
            "expected_intent": "candidate_pitch_email",
            "description": "Pattern match for candidate pitch"
        },
        {
            "message": "write a recruiter email to potential data scientist candidates",
            "expected_intent": "recruiter_outreach_email", 
            "description": "Alternative recruiter outreach pattern"
        },
        {
            "message": "draft an outreach email from a recruiter to candidates for the AI engineer position",
            "expected_intent": "recruiter_outreach_email",
            "description": "Complex recruiter outreach pattern"
        }
    ]
    
    for i, test_case in enumerate(pattern_test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Message: {test_case['message']}")
        
        try:
            # Test pattern matching
            intent, entities = intent_processor._match_patterns(test_case['message'])
            
            print(f"Detected Intent: {intent}")
            print(f"Expected Intent: {test_case['expected_intent']}")
            print(f"Entities: {entities}")
            
            if intent == test_case['expected_intent']:
                print("✅ PASS")
            else:
                print("❌ FAIL")
                print(f"  - Expected {test_case['expected_intent']}, got {intent}")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")

async def main():
    """Run all tests."""
    print("Enhanced Intent Processor Test Suite")
    print("=" * 60)
    
    await test_intent_detection()
    await test_email_generation()
    await test_pattern_matching()
    
    print("\n\nTest Suite Complete!")

if __name__ == "__main__":
    asyncio.run(main())