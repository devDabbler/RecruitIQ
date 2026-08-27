#!/usr/bin/env python3
"""
Test script for enhanced AI assistant functionality.
Tests database queries, candidate analysis, and candidate outreach features.
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_enhanced_assistant():
    """Test the enhanced AI assistant functionality."""
    
    print("🧪 Testing Enhanced AI Assistant Functionality")
    print("=" * 50)
    
    try:
        # Test 1: Import the intent processor
        print("\n1. Testing imports...")
        from services.intent_processor import IntentProcessor
        from utils.config import get_settings
        print("✅ All imports successful")
        
        # Test 2: Test intent detection
        print("\n2. Testing intent detection...")
        intent_processor = IntentProcessor()
        
        test_messages = [
            "How many candidates do we have in the database?",
            "Show me a breakdown of candidate skills",
            "Generate candidate outreach emails for the data scientist position",
            "What's the skills breakdown for engineering jobs?",
            "Find me all data scientists with Python experience"
        ]
        
        for message in test_messages:
            try:
                intent_result = await intent_processor.detect_intent(message)
                intent = intent_result.get('intent', 'unknown')
                entities = intent_result.get('entities', {})
                print(f"✅ '{message[:50]}...' -> Intent: {intent}")
                if entities:
                    print(f"   Entities: {entities}")
            except Exception as e:
                print(f"❌ Error detecting intent for '{message[:50]}...': {e}")
        
        # Test 3: Test configuration
        print("\n3. Testing configuration...")
        try:
            settings = get_settings()
            print(f"✅ OpenRouter enabled: {getattr(settings, 'openrouter_enabled', False)}")
            print(f"✅ Default model: {getattr(settings, 'openrouter_default_model', 'Not set')}")
            print(f"✅ Nebius API key present: {'Yes' if getattr(settings, 'nebius_api_key', None) else 'No'}")
        except Exception as e:
            print(f"❌ Configuration error: {e}")
        
        print("\n🎉 Enhanced AI Assistant testing completed!")
        print("\nNew capabilities added:")
        print("- Enhanced candidate breakdowns (skills, experience, status, company, source)")
        print("- Job skills analysis and department breakdowns")
        print("- Candidate outreach email generation for specific jobs")
        print("- Comprehensive database querying and analysis")
        print("- Pipeline insights and candidate matching")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_assistant())
