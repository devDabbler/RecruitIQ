#!/usr/bin/env python3
"""
Test script for the flexible intent processor
Tests edge cases and unknown queries to ensure they get handled gracefully
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.dynamic_intent_processor import get_dynamic_intent_processor
from services.llm_service import get_llm_service

async def test_flexible_intent_processor():
    """Test the flexible intent processor with various edge cases"""
    
    print("🧪 Testing Flexible Intent Processor")
    print("=" * 50)
    
    # Initialize the processor
    processor = get_dynamic_intent_processor()
    
    # Test cases that should trigger flexible responses
    test_cases = [
        "How many candidates are there in our database?",
        "Out of the 22 candidates, how many are females?",
        "What is the work commute like in Mexico City?",
        "Can you help me with my resume?",
        "What's the weather like today?",
        "Tell me a joke",
        "What's the capital of France?",
        "How do I make a cake?",
        "What are the best restaurants in New York?",
        "Can you explain quantum physics?"
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
            print(f"Response: {result.get('message', 'No response')[:100]}...")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)

async def test_unknown_intent_processing():
    """Test the unknown intent processing specifically"""
    
    print("\n🔍 Testing Unknown Intent Processing")
    print("=" * 50)
    
    processor = get_dynamic_intent_processor()
    
    # Test unknown intents
    unknown_queries = [
        "What's the meaning of life?",
        "How do I knit a sweater?",
        "What's the best way to learn guitar?",
        "Can you help me with my taxes?",
        "What's the population of Tokyo?"
    ]
    
    for i, query in enumerate(unknown_queries, 1):
        print(f"\n🔍 Unknown Query {i}: {query}")
        print("-" * 40)
        
        try:
            # Use the process_unknown_intent method directly
            result = await processor.process_unknown_intent(query)
            print(f"Processed: {result.get('intent_processed', False)}")
            print(f"Response Type: {result.get('response_type', 'unknown')}")
            print(f"LLM Generated: {result.get('llm_generated', False)}")
            print(f"Response: {result.get('message', 'No response')[:150]}...")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)

async def main():
    """Main test function"""
    print("🚀 Starting Flexible Intent Processor Tests")
    print("=" * 60)
    
    # Test 1: General flexible intent processing
    await test_flexible_intent_processor()
    
    # Test 2: Unknown intent processing
    await test_unknown_intent_processing()
    
    print("\n✅ Tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 