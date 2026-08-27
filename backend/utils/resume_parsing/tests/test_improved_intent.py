#!/usr/bin/env python3
"""
Test script for the improved intent processor
Tests that the system now uses LLM responses instead of hard-coded ones
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.dynamic_intent_processor import get_dynamic_intent_processor

async def test_improved_intent_processor():
    """Test the improved intent processor with various queries"""
    
    print("🧪 Testing Improved Intent Processor")
    print("=" * 50)
    
    # Initialize the processor
    processor = get_dynamic_intent_processor()
    
    # Test cases that should now get LLM responses
    test_cases = [
        "What's the weather like today?",
        "Tell me a joke",
        "What's the capital of France?",
        "How do I make a cake?",
        "What are the best restaurants in New York?",
        "Can you explain quantum physics?",
        "What's the meaning of life?",
        "How do I knit a sweater?",
        "What's the best way to learn guitar?",
        "Can you help me with my taxes?"
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test_case}")
        print("-" * 40)
        
        try:
            # Detect intent
            intent = await processor.detect_intent(test_case)
            print(f"Detected Intent: {intent.name}")
            print(f"Confidence: {intent.confidence:.2f}")
            print(f"Entities: {intent.entities}")
            
            # Process intent
            result = await processor.process_intent(intent, test_case)
            print(f"Processed: {result.get('intent_processed', False)}")
            print(f"Response Type: {result.get('response_type', 'unknown')}")
            print(f"LLM Generated: {result.get('llm_generated', False)}")
            print(f"Fallback: {result.get('fallback', False)}")
            
            # Show first 100 characters of response
            response = result.get('message', 'No response')
            print(f"Response: {response[:100]}...")
            
            # Check if we're getting LLM responses instead of hard-coded ones
            if result.get('llm_generated', False):
                print("✅ LLM response generated")
            elif result.get('fallback', False):
                print("⚠️  Fallback response (LLM not available)")
            else:
                print("❌ Unexpected response type")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)

async def test_recruiting_specific_queries():
    """Test recruiting-specific queries to ensure they still work"""
    
    print("\n🎯 Testing Recruiting-Specific Queries")
    print("=" * 50)
    
    processor = get_dynamic_intent_processor()
    
    # Test recruiting-specific queries
    recruiting_queries = [
        "How many candidates are there in our database?",
        "Find me candidates with Python experience",
        "What's the market rate for software engineers?",
        "Help me plan travel for an interview in New York"
    ]
    
    for i, query in enumerate(recruiting_queries, 1):
        print(f"\n🎯 Recruiting Query {i}: {query}")
        print("-" * 40)
        
        try:
            # Detect intent
            intent = await processor.detect_intent(query)
            print(f"Detected Intent: {intent.name}")
            print(f"Confidence: {intent.confidence:.2f}")
            
            # Process intent
            result = await processor.process_intent(intent, query)
            print(f"Response Type: {result.get('response_type', 'unknown')}")
            print(f"LLM Generated: {result.get('llm_generated', False)}")
            
            # Show first 100 characters of response
            response = result.get('message', 'No response')
            print(f"Response: {response[:100]}...")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)

async def main():
    """Main test function"""
    print("🚀 Starting Improved Intent Processor Tests")
    print("=" * 60)
    
    await test_improved_intent_processor()
    await test_recruiting_specific_queries()
    
    print("\n✅ Tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 