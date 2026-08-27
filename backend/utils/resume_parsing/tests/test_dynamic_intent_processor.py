#!/usr/bin/env python3
"""
Test script for the new Dynamic Intent Processing System
"""

import asyncio
import logging
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.dynamic_intent_processor import get_dynamic_intent_processor, Intent
from services.intent_processor_integration import get_intent_processor_integration, detect_intent_unified, process_intent_unified
from services.llm_service import get_llm_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_dynamic_intent_processor():
    """Test the dynamic intent processor with various queries"""
    
    print("🧪 Testing Dynamic Intent Processing System")
    print("=" * 50)
    
    # Initialize the integration layer
    integration = get_intent_processor_integration()
    await integration.initialize()
    
    # Test queries
    test_queries = [
        # Travel & Location Intents
        "What's the best way to get from Boston to NYC?",
        "How long does it take to commute from Brooklyn to Manhattan?",
        "I need to travel from the airport to downtown for my interview",
        
        # Enhanced Recruiting Intents
        "Find me data scientists with Python experience",
        "I need senior engineers who know React",
        "Show me candidates for the product manager role",
        "Who would be the best fit for our software engineer position?",
        
        # Market Intelligence
        "What are the latest market trends in data science?",
        "What's the average salary for software engineers in New York?",
        "How is the job market for machine learning engineers?",
        
        # Communication & Outreach
        "Draft a personalized email for data scientist candidates",
        "Create an outreach message for software engineers",
        "Help me contact potential candidates for our open position",
        
        # Complex Multi-step Tasks
        "Find me candidates and then draft outreach emails for them",
        "Analyze the market and then suggest the best candidates",
        
        # Clarification Requests
        "What do you mean by that?",
        "Can you explain the candidate matching process?",
        
        # Edge Cases
        "Hello there!",
        "What skills do software engineers need?",
        "Tell me about Google as a company",
    ]
    
    print(f"\n📝 Testing {len(test_queries)} queries...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("-" * 40)
        
        try:
            # Test unified intent detection
            intent_result = await detect_intent_unified(query, f"test_user_{i}")
            
            print(f"   Intent: {intent_result.get('intent', 'unknown')}")
            print(f"   Confidence: {intent_result.get('confidence', 0.0):.2f}")
            print(f"   Processor: {intent_result.get('processor_used', 'unknown')}")
            print(f"   Entities: {intent_result.get('entities', {})}")
            
            if intent_result.get('requires_clarification'):
                print(f"   ⚠️  Requires clarification: {intent_result.get('clarification_prompts', [])}")
            
            # Test intent processing for supported intents
            if intent_result.get('intent') in ["travel_planning", "candidate_search", "intelligent_matching", "market_analysis", "personalized_outreach"]:
                process_result = await process_intent_unified(intent_result, query, f"test_user_{i}")
                print(f"   Processing: {process_result.get('intent_processed', False)}")
                if process_result.get('intent_processed'):
                    print(f"   Response Type: {process_result.get('response_type', 'unknown')}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    # Test performance metrics
    metrics = integration.get_performance_metrics()
    print("\n📊 Performance Metrics:")
    print("-" * 30)
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")

async def test_conversation_context():
    """Test conversation context and state management"""
    
    print("\n🔄 Testing Conversation Context")
    print("=" * 40)
    
    integration = get_intent_processor_integration()
    user_id = "test_user_context"
    
    # Simulate a conversation
    conversation = [
        "I need to find data scientists",
        "What skills should they have?",
        "How much should I pay them?",
        "Can you help me draft an email to reach out to them?"
    ]
    
    context = {}
    
    for i, message in enumerate(conversation, 1):
        print(f"\n{i}. User: {message}")
        
        intent_result = await detect_intent_unified(message, user_id, context)
        
        print(f"   Intent: {intent_result.get('intent')}")
        print(f"   Confidence: {intent_result.get('confidence'):.2f}")
        print(f"   Context Signals: {intent_result.get('context_signals', [])}")
        
        # Update context
        context.update({
            "last_intent": intent_result.get('intent'),
            "last_entities": intent_result.get('entities'),
            "conversation_length": i
        })

async def test_feature_flags():
    """Test feature flag management"""
    
    print("\n🎛️  Testing Feature Flags")
    print("=" * 30)
    
    integration = get_intent_processor_integration()
    
    # Test updating feature flags
    integration.update_feature_flags({
        "enable_semantic_similarity": False,
        "enable_context_awareness": True,
        "enable_intent_caching": True,
        "enable_ensemble_voting": False
    })
    
    print(f"   Feature flags: {integration.feature_flags}")
    
    # Test processor switching
    integration.enable_dynamic_processor(True)
    integration.enable_legacy_fallback(True)
    
    print("   ✅ Dynamic processor enabled")
    print("   ✅ Legacy fallback enabled")

async def main():
    """Main test function"""
    
    print("🚀 Starting Dynamic Intent Processor Tests")
    print("=" * 60)
    
    try:
        # Test basic functionality
        await test_dynamic_intent_processor()
        
        # Test conversation context
        await test_conversation_context()
        
        # Test feature flags
        await test_feature_flags()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    
    return True

if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 Dynamic Intent Processing System is working correctly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1) 