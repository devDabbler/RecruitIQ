#!/usr/bin/env python3
"""
Comprehensive test suite for enhanced intent coverage implementation.
Tests all new intents and validates production readiness.
"""

import asyncio
import sys
import os
import logging
from typing import Dict, Any, List

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.intent_processor import IntentProcessor
from backend.services.llm_service import get_llm_service
from backend.services.web_search_service import get_web_search_service
from backend.routers.assistant import chat_with_assistant

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedIntentTester:
    """Comprehensive tester for enhanced intent coverage."""
    
    def __init__(self):
        self.llm_service = None
        self.web_search_service = None
        self.intent_processor = None
        self.test_results = {}
        
    async def initialize_services(self):
        """Initialize all required services."""
        try:
            logger.info("Initializing services...")
            self.llm_service = get_llm_service()
            self.web_search_service = get_web_search_service()
            self.intent_processor = IntentProcessor(self.llm_service)
            logger.info("Services initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            return False
    
    async def test_intent_detection(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test intent detection for various queries."""
        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "details": []
        }
        
        for test_case in test_cases:
            query = test_case["query"]
            expected_intent = test_case["expected_intent"]
            expected_entities = test_case.get("expected_entities", {})
            
            try:
                # Test intent detection
                intent_result = await self.intent_processor.detect_intent(query)
                detected_intent = intent_result.get("intent")
                detected_entities = intent_result.get("entities", {})
                confidence = intent_result.get("confidence", 0)
                
                # Check if intent matches
                intent_match = detected_intent == expected_intent
                
                # Check entity extraction - be more lenient
                entity_match = True
                if expected_entities:  # Only check if we expect entities
                    for entity_key, expected_value in expected_entities.items():
                        if entity_key not in detected_entities:
                            entity_match = False
                            break
                        detected_value = detected_entities[entity_key]
                        if expected_value and detected_value:
                            # More lenient matching - check if any part matches
                            expected_lower = expected_value.lower()
                            detected_lower = detected_value.lower()
                            if expected_lower not in detected_lower and detected_lower not in expected_lower:
                                entity_match = False
                                break
                
                test_passed = intent_match and entity_match and confidence > 0.3
                
                if test_passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append({
                    "query": query,
                    "expected_intent": expected_intent,
                    "detected_intent": detected_intent,
                    "expected_entities": expected_entities,
                    "detected_entities": detected_entities,
                    "confidence": confidence,
                    "passed": test_passed,
                    "intent_match": intent_match,
                    "entity_match": entity_match
                })
                
                logger.info(f"Test: '{query}' -> {detected_intent} (confidence: {confidence:.2f}) {'PASS' if test_passed else 'FAIL'}")
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "query": query,
                    "error": str(e),
                    "passed": False
                })
                logger.error(f"Error testing '{query}': {e}")
        
        return results
    
    async def test_end_to_end_flow(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test complete end-to-end flow including response generation."""
        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "details": []
        }
        
        for test_case in test_cases:
            query = test_case["query"]
            expected_intent = test_case["expected_intent"]
            
            try:
                # Test complete flow through assistant router
                response = await chat_with_assistant(
                    message=query,
                    conversation_history=[],
                    conversation_context={}
                )
                
                # Check if we got a valid response
                has_response = response and response.get("response")
                response_type = response.get("response_type", "unknown")
                
                # Check if the response contains meaningful content
                response_text = response.get("response", "")
                has_content = len(response_text.strip()) > 10
                
                test_passed = has_response and has_content
                
                if test_passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append({
                    "query": query,
                    "expected_intent": expected_intent,
                    "response_type": response_type,
                    "has_response": has_response,
                    "has_content": has_content,
                    "response_length": len(response_text),
                    "response_preview": response_text[:100] + "..." if len(response_text) > 100 else response_text,
                    "passed": test_passed
                })
                
                logger.info(f"E2E Test: '{query}' -> {response_type} {'PASS' if test_passed else 'FAIL'}")
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "query": query,
                    "error": str(e),
                    "passed": False
                })
                logger.error(f"Error in E2E test for '{query}': {e}")
        
        return results

def get_test_cases() -> List[Dict[str, Any]]:
    """Get comprehensive test cases for all enhanced intents."""
    return [
        # Cost of Living Tests
        {
            "query": "What's the cost of living in Seattle?",
            "expected_intent": "cost_of_living",
            "expected_entities": {"location": "Seattle"}
        },
        {
            "query": "How expensive is it to live in Boston?",
            "expected_intent": "cost_of_living",
            "expected_entities": {"location": "Boston"}
        },
        {
            "query": "Compare cost of living between Austin and Denver",
            "expected_intent": "cost_of_living",
            "expected_entities": {"location1": "Austin", "location2": "Denver"}
        },
        {
            "query": "What are housing costs in San Francisco?",
            "expected_intent": "cost_of_living",
            "expected_entities": {"location": "San Francisco"}
        },
        
        # Price Information Tests
        {
            "query": "What's the price of iPhone 15?",
            "expected_intent": "price_info",
            "expected_entities": {"item": "iPhone 15"}
        },
        {
            "query": "How much does a Tesla Model 3 cost?",
            "expected_intent": "price_info",
            "expected_entities": {"item": "Tesla Model 3"}
        },
        {
            "query": "Compare prices between iPhone and Samsung Galaxy",
            "expected_intent": "price_info",
            "expected_entities": {"item1": "iPhone", "item2": "Samsung Galaxy"}
        },
        {
            "query": "What's the current price of gold?",
            "expected_intent": "price_info",
            "expected_entities": {"item": "gold"}
        },
        
        # Schedule Information Tests
        {
            "query": "What are the business hours for Starbucks?",
            "expected_intent": "schedule_info",
            "expected_entities": {"business": "Starbucks"}
        },
        {
            "query": "When does Walmart open?",
            "expected_intent": "schedule_info",
            "expected_entities": {"business": "Walmart"}
        },
        {
            "query": "What time does the library close?",
            "expected_intent": "schedule_info",
            "expected_entities": {"business": "library"}
        },
        {
            "query": "Operating hours for McDonald's",
            "expected_intent": "schedule_info",
            "expected_entities": {"business": "McDonald's"}
        },
        
        # Recent Data Tests
        {
            "query": "What's the latest news about AI?",
            "expected_intent": "recent_data",
            "expected_entities": {"topic": "AI"}
        },
        {
            "query": "What's the current status of the stock market?",
            "expected_intent": "recent_data",
            "expected_entities": {"topic": "stock market"}
        },
        {
            "query": "Recent developments in renewable energy",
            "expected_intent": "recent_data",
            "expected_entities": {"topic": "renewable energy"}
        },
        {
            "query": "What's the latest information about Tesla?",
            "expected_intent": "recent_data",
            "expected_entities": {"topic": "Tesla"}
        },
        
        # Salary Information Tests (Critical)
        {
            "query": "How much do data scientists make in Seattle?",
            "expected_intent": "salary_info",
            "expected_entities": {"role": "data scientists", "location": "Seattle"}
        },
        {
            "query": "What's the average salary for software engineers?",
            "expected_intent": "salary_info",
            "expected_entities": {"role": "software engineers"}
        },
        {
            "query": "Salary for product managers in New York",
            "expected_intent": "salary_info",
            "expected_entities": {"role": "product managers", "location": "New York"}
        },
        
        # Edge Cases
        {
            "query": "What is the cost structure of Microsoft?",
            "expected_intent": "company_info",
            "expected_entities": {"company": "Microsoft"}
        },
        {
            "query": "Tell me about Google's company culture",
            "expected_intent": "company_info",
            "expected_entities": {"company": "Google"}
        }
    ]

async def main():
    """Run comprehensive tests."""
    tester = EnhancedIntentTester()
    
    # Initialize services
    if not await tester.initialize_services():
        logger.error("Failed to initialize services. Exiting.")
        return
    
    # Get test cases
    test_cases = get_test_cases()
    
    logger.info("=" * 80)
    logger.info("ENHANCED INTENT COVERAGE COMPREHENSIVE TEST SUITE")
    logger.info("=" * 80)
    
    # Test 1: Intent Detection
    logger.info("\n🔍 TESTING INTENT DETECTION...")
    intent_results = await tester.test_intent_detection(test_cases)
    
    logger.info(f"\nIntent Detection Results:")
    logger.info(f"  Total Tests: {intent_results['total_tests']}")
    logger.info(f"  Passed: {intent_results['passed']}")
    logger.info(f"  Failed: {intent_results['failed']}")
    logger.info(f"  Success Rate: {(intent_results['passed'] / intent_results['total_tests'] * 100):.1f}%")
    
    # Test 2: End-to-End Flow
    logger.info("\n🔄 TESTING END-TO-END FLOW...")
    e2e_results = await tester.test_end_to_end_flow(test_cases)
    
    logger.info(f"\nEnd-to-End Results:")
    logger.info(f"  Total Tests: {e2e_results['total_tests']}")
    logger.info(f"  Passed: {e2e_results['passed']}")
    logger.info(f"  Failed: {e2e_results['failed']}")
    logger.info(f"  Success Rate: {(e2e_results['passed'] / e2e_results['total_tests'] * 100):.1f}%")
    
    # Detailed Analysis
    logger.info("\n📊 DETAILED ANALYSIS...")
    
    # Group by intent type
    intent_groups = {}
    for detail in intent_results['details']:
        intent = detail.get('detected_intent', 'unknown')
        if intent not in intent_groups:
            intent_groups[intent] = {'passed': 0, 'failed': 0}
        if detail.get('passed', False):
            intent_groups[intent]['passed'] += 1
        else:
            intent_groups[intent]['failed'] += 1
    
    logger.info("\nIntent Detection by Type:")
    for intent, stats in intent_groups.items():
        total = stats['passed'] + stats['failed']
        success_rate = (stats['passed'] / total * 100) if total > 0 else 0
        logger.info(f"  {intent}: {stats['passed']}/{total} ({success_rate:.1f}%)")
    
    # Group E2E by intent type
    e2e_groups = {}
    for detail in e2e_results['details']:
        intent = detail.get('expected_intent', 'unknown')
        if intent not in e2e_groups:
            e2e_groups[intent] = {'passed': 0, 'failed': 0}
        if detail.get('passed', False):
            e2e_groups[intent]['passed'] += 1
        else:
            e2e_groups[intent]['failed'] += 1
    
    logger.info("\nEnd-to-End by Intent Type:")
    for intent, stats in e2e_groups.items():
        total = stats['passed'] + stats['failed']
        success_rate = (stats['passed'] / total * 100) if total > 0 else 0
        logger.info(f"  {intent}: {stats['passed']}/{total} ({success_rate:.1f}%)")
    
    # Show failed tests
    logger.info("\n❌ FAILED TESTS:")
    failed_intent = [d for d in intent_results['details'] if not d.get('passed', False)]
    failed_e2e = [d for d in e2e_results['details'] if not d.get('passed', False)]
    
    if failed_intent:
        logger.info("\nIntent Detection Failures:")
        for failure in failed_intent:
            logger.info(f"  '{failure['query']}' -> Expected: {failure.get('expected_intent')}, Got: {failure.get('detected_intent')}")
    
    if failed_e2e:
        logger.info("\nEnd-to-End Failures:")
        for failure in failed_e2e:
            logger.info(f"  '{failure['query']}' -> Error: {failure.get('error', 'No response generated')}")
    
    # Final Summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    
    overall_intent_success = (intent_results['passed'] / intent_results['total_tests'] * 100)
    overall_e2e_success = (e2e_results['passed'] / e2e_results['total_tests'] * 100)
    
    logger.info(f"Intent Detection Success Rate: {overall_intent_success:.1f}%")
    logger.info(f"End-to-End Success Rate: {overall_e2e_success:.1f}%")
    
    if overall_intent_success >= 90 and overall_e2e_success >= 80:
        logger.info("✅ SYSTEM READY FOR PRODUCTION")
    elif overall_intent_success >= 80 and overall_e2e_success >= 70:
        logger.info("⚠️  SYSTEM NEEDS MINOR FIXES")
    else:
        logger.info("❌ SYSTEM NEEDS MAJOR FIXES")
    
    return {
        "intent_results": intent_results,
        "e2e_results": e2e_results,
        "overall_success": overall_intent_success >= 90 and overall_e2e_success >= 80
    }

if __name__ == "__main__":
    asyncio.run(main())