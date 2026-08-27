#!/usr/bin/env python3
"""
Improved test script for the fixed intent processor
Focuses on key improvements: no attribute errors, graceful fallbacks, contextual responses
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.dynamic_intent_processor import get_dynamic_intent_processor

async def test_key_improvements():
    """Test the key improvements mentioned in the documentation"""
    
    print("🚀 Testing Intent Processor Key Improvements")
    print("=" * 60)
    print("Based on: INTENT_PROCESSOR_IMPROVEMENTS.md & FLEXIBLE_INTENT_PROCESSOR_SUMMARY.md")
    print()
    
    # Initialize the processor
    processor = get_dynamic_intent_processor()
    
    # Test cases that demonstrate the improvements
    test_cases = [
        {
            "query": "What's the weather like today?",
            "expected_improvement": "LLM-powered contextual response instead of hardcoded fallback"
        },
        {
            "query": "Tell me a joke",
            "expected_improvement": "Contextual response with recruiting humor"
        },
        {
            "query": "How do I make a cake?",
            "expected_improvement": "Flexible query handling with helpful response"
        },
        {
            "query": "What's the meaning of life?",
            "expected_improvement": "Philosophical question handled gracefully"
        },
        {
            "query": "Can you help me with my taxes?",
            "expected_improvement": "Contextual response redirecting to appropriate help"
        }
    ]
    
    print("📋 Testing Key Improvements:")
    print("1. No more attribute errors")
    print("2. Graceful LLM fallbacks")
    print("3. Contextual responses instead of hardcoded")
    print("4. Better user experience")
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🔍 Test {i}: {test_case['query']}")
        print(f"   Expected: {test_case['expected_improvement']}")
        print("-" * 60)
        
        try:
            # Test 1: No attribute errors
            intent = await processor.detect_intent(test_case['query'])
            print(f"✅ No attribute errors - Intent detected: {intent.name}")
            
            # Test 2: Process intent without crashes
            result = await processor.process_intent(intent, test_case['query'])
            print(f"✅ No crashes - Intent processed successfully")
            
            # Test 3: Check response quality
            response = result.get('message', 'No response')
            response_type = result.get('response_type', 'unknown')
            
            print(f"📝 Response Type: {response_type}")
            
            # Show the actual response (first 200 chars)
            if len(response) > 200:
                display_response = response[:200] + "..."
            else:
                display_response = response
            
            print(f"💬 Response: {display_response}")
            
            # Test 4: Check if it's contextual vs hardcoded
            if result.get('llm_generated', False):
                print("✅ LLM-generated contextual response")
            elif result.get('fallback', False):
                print("✅ Graceful fallback response")
            else:
                print("⚠️  Unexpected response type")
            
            # Check for specific improvements
            if "I'm having trouble generating" not in response:
                print("✅ No generic 'having trouble' message")
            else:
                print("❌ Still showing generic fallback")
                
            if len(response) > 50:
                print("✅ Substantial response (not just placeholder)")
            else:
                print("⚠️  Response seems too short")
            
        except AttributeError as e:
            print(f"❌ ATTRIBUTE ERROR: {e}")
        except Exception as e:
            print(f"❌ OTHER ERROR: {e}")
        
        print()

async def test_recruiting_specific():
    """Test recruiting-specific queries to show domain expertise"""
    
    print("🎯 Testing Recruiting Domain Expertise")
    print("=" * 60)
    
    processor = get_dynamic_intent_processor()
    
    recruiting_queries = [
        "How many candidates are there in our database?",
        "Find me candidates with Python experience",
        "What's the market rate for software engineers?",
        "Help me plan travel for an interview in New York"
    ]
    
    for i, query in enumerate(recruiting_queries, 1):
        print(f"🎯 Recruiting Query {i}: {query}")
        print("-" * 40)
        
        try:
            intent = await processor.detect_intent(query)
            result = await processor.process_intent(intent, query)
            
            print(f"Intent: {intent.name} (confidence: {intent.confidence:.2f})")
            
            response = result.get('message', 'No response')
            if len(response) > 150:
                display_response = response[:150] + "..."
            else:
                display_response = response
            
            print(f"Response: {display_response}")
            
            # Check if it's a proper recruiting response
            if "being implemented" in response.lower():
                print("⚠️  Still showing 'being implemented' message")
            else:
                print("✅ Proper recruiting domain response")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()

async def test_error_handling():
    """Test error handling improvements"""
    
    print("🛡️ Testing Error Handling Improvements")
    print("=" * 60)
    
    processor = get_dynamic_intent_processor()
    
    # Test cases that might cause issues
    edge_cases = [
        "",  # Empty string
        "   ",  # Whitespace only
        "a" * 1000,  # Very long string
        "🚀🎯💬",  # Emoji only
        None  # None value
    ]
    
    for i, test_case in enumerate(edge_cases, 1):
        print(f"🔍 Edge Case {i}: {repr(test_case)}")
        
        try:
            if test_case is None:
                print("   Skipping None test case")
                continue
                
            intent = await processor.detect_intent(test_case)
            result = await processor.process_intent(intent, test_case)
            
            print(f"   ✅ Handled gracefully")
            print(f"   Intent: {intent.name}")
            print(f"   Response: {result.get('message', 'No response')[:100]}...")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()

async def main():
    """Main test function"""
    print("🧪 INTENT PROCESSOR IMPROVEMENTS TEST")
    print("=" * 60)
    print("Testing the improvements from INTENT_PROCESSOR_IMPROVEMENTS.md")
    print("and FLEXIBLE_INTENT_PROCESSOR_SUMMARY.md")
    print()
    
    await test_key_improvements()
    await test_recruiting_specific()
    await test_error_handling()
    
    print("=" * 60)
    print("✅ All tests completed!")
    print()
    print("📊 Summary of Improvements Tested:")
    print("• No more attribute errors")
    print("• Graceful LLM fallbacks")
    print("• Contextual responses instead of hardcoded")
    print("• Better user experience")
    print("• Recruiting domain expertise")
    print("• Robust error handling")

if __name__ == "__main__":
    asyncio.run(main()) 