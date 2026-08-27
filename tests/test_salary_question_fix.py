#!/usr/bin/env python3
"""
Focused test for the salary question fix to ensure it works properly in production.
Tests the specific issue: "How much do data scientists make in Seattle?"
"""

import asyncio
import sys
import os
import logging
from typing import Dict, Any

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.intent_processor import IntentProcessor
from backend.services.llm_service import get_llm_service
from backend.services.web_search_service import get_web_search_service
from backend.services.market_research_service import MarketResearchService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SalaryQuestionTester:
    """Focused tester for salary question functionality."""
    
    def __init__(self):
        self.llm_service = None
        self.web_search_service = None
        self.intent_processor = None
        self.market_service = None
        
    async def initialize_services(self):
        """Initialize all required services."""
        try:
            logger.info("Initializing services for salary question testing...")
            self.llm_service = get_llm_service()
            self.web_search_service = get_web_search_service()
            self.intent_processor = IntentProcessor(self.llm_service)
            self.market_service = MarketResearchService(self.web_search_service, self.llm_service)
            logger.info("Services initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            return False
    
    async def test_salary_intent_detection(self, query: str) -> Dict[str, Any]:
        """Test intent detection for salary questions."""
        try:
            logger.info(f"Testing intent detection for: '{query}'")
            intent_result = await self.intent_processor.detect_intent(query)
            
            detected_intent = intent_result.get("intent")
            detected_entities = intent_result.get("entities", {})
            confidence = intent_result.get("confidence", 0)
            
            logger.info(f"Detected intent: {detected_intent}")
            logger.info(f"Detected entities: {detected_entities}")
            logger.info(f"Confidence: {confidence}")
            
            return {
                "success": True,
                "intent": detected_intent,
                "entities": detected_entities,
                "confidence": confidence,
                "is_salary_intent": detected_intent == "salary_info",
                "has_role": "role" in detected_entities and detected_entities["role"],
                "has_location": "location" in detected_entities and detected_entities["location"]
            }
            
        except Exception as e:
            logger.error(f"Error in intent detection: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def test_salary_data_retrieval(self, role: str, location: str = None) -> Dict[str, Any]:
        """Test salary data retrieval using MarketResearchService."""
        try:
            logger.info(f"Testing salary data retrieval for {role} in {location or 'United States'}")
            
            salary_data = await self.market_service.get_comprehensive_salary_benchmark(
                job_title=role,
                location=location or "United States",
                experience_level=None
            )
            
            logger.info(f"Salary data status: {salary_data.get('status')}")
            logger.info(f"Salary data keys: {list(salary_data.keys())}")
            
            if salary_data.get('status') == 'success' and 'data' in salary_data:
                analysis_data = salary_data['data']
                logger.info(f"Analysis data type: {type(analysis_data)}")
                logger.info(f"Analysis data keys: {list(analysis_data.keys()) if isinstance(analysis_data, dict) else 'Not a dict'}")
                
                return {
                    "success": True,
                    "status": salary_data.get('status'),
                    "has_data": 'data' in salary_data,
                    "data_type": type(analysis_data).__name__,
                    "data_keys": list(analysis_data.keys()) if isinstance(analysis_data, dict) else None,
                    "raw_data": salary_data
                }
            else:
                return {
                    "success": False,
                    "status": salary_data.get('status'),
                    "message": salary_data.get('message', 'No message'),
                    "raw_data": salary_data
                }
                
        except Exception as e:
            logger.error(f"Error in salary data retrieval: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def test_complete_salary_flow(self, query: str) -> Dict[str, Any]:
        """Test the complete salary question flow."""
        try:
            logger.info(f"Testing complete salary flow for: '{query}'")
            
            # Step 1: Intent Detection
            intent_result = await self.test_salary_intent_detection(query)
            if not intent_result.get("success"):
                return {
                    "success": False,
                    "step": "intent_detection",
                    "error": intent_result.get("error")
                }
            
            if not intent_result.get("is_salary_intent"):
                return {
                    "success": False,
                    "step": "intent_detection",
                    "error": f"Expected salary_info intent, got {intent_result.get('intent')}"
                }
            
            # Step 2: Extract entities
            entities = intent_result.get("entities", {})
            role = entities.get("role")
            location = entities.get("location")
            
            if not role:
                return {
                    "success": False,
                    "step": "entity_extraction",
                    "error": "No role extracted from query"
                }
            
            # Step 3: Data Retrieval
            data_result = await self.test_salary_data_retrieval(role, location)
            if not data_result.get("success"):
                return {
                    "success": False,
                    "step": "data_retrieval",
                    "error": data_result.get("error", data_result.get("message"))
                }
            
            # Step 4: Response Formatting (simulate assistant router logic)
            raw_data = data_result.get("raw_data", {})
            if raw_data.get('status') == 'success' and 'data' in raw_data:
                analysis_data = raw_data['data']
                
                if isinstance(analysis_data, dict):
                    response_parts = [f"**Salary Benchmark for {role} in {location or 'United States'}**\n"]
                    
                    # Add salary ranges by experience level
                    for level, data in analysis_data.items():
                        if isinstance(data, dict) and 'salary_range' in data:
                            response_parts.append(f"**{level.title()} Level:** {data['salary_range']}")
                    
                    response_text = "\n".join(response_parts)
                else:
                    response_text = f"Salary benchmark data retrieved for {role} in {location or 'United States'}."
            else:
                response_text = raw_data.get('message', 'Salary information retrieved successfully.')
            
            return {
                "success": True,
                "intent_detection": intent_result,
                "data_retrieval": data_result,
                "formatted_response": response_text,
                "response_length": len(response_text),
                "has_meaningful_content": len(response_text.strip()) > 20
            }
            
        except Exception as e:
            logger.error(f"Error in complete salary flow: {e}")
            return {
                "success": False,
                "step": "complete_flow",
                "error": str(e)
            }

async def main():
    """Run focused salary question tests."""
    tester = SalaryQuestionTester()
    
    # Initialize services
    if not await tester.initialize_services():
        logger.error("Failed to initialize services. Exiting.")
        return
    
    logger.info("=" * 80)
    logger.info("SALARY QUESTION FIX VALIDATION TEST")
    logger.info("=" * 80)
    
    # Test cases for salary questions
    test_cases = [
        "How much do data scientists make in Seattle?",
        "What's the average salary for software engineers?",
        "Salary for product managers in New York",
        "How much do data analysts earn in San Francisco?",
        "What's the typical pay for UX designers?"
    ]
    
    results = []
    
    for query in test_cases:
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING: {query}")
        logger.info(f"{'='*60}")
        
        result = await tester.test_complete_salary_flow(query)
        results.append({
            "query": query,
            "result": result
        })
        
        if result.get("success"):
            logger.info("✅ SUCCESS")
            logger.info(f"Response: {result.get('formatted_response', 'No response')[:200]}...")
        else:
            logger.error("❌ FAILED")
            logger.error(f"Error: {result.get('error')}")
            logger.error(f"Step: {result.get('step')}")
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}")
    
    successful_tests = [r for r in results if r["result"].get("success")]
    failed_tests = [r for r in results if not r["result"].get("success")]
    
    logger.info(f"Total Tests: {len(results)}")
    logger.info(f"Successful: {len(successful_tests)}")
    logger.info(f"Failed: {len(failed_tests)}")
    logger.info(f"Success Rate: {(len(successful_tests) / len(results) * 100):.1f}%")
    
    if failed_tests:
        logger.info("\nFailed Tests:")
        for test in failed_tests:
            logger.info(f"  - {test['query']}: {test['result'].get('error')}")
    
    # Test the specific question mentioned in the issue
    logger.info(f"\n{'='*80}")
    logger.info("SPECIFIC ISSUE TEST: 'How much do data scientists make in Seattle?'")
    logger.info(f"{'='*80}")
    
    specific_result = await tester.test_complete_salary_flow("How much do data scientists make in Seattle?")
    
    if specific_result.get("success"):
        logger.info("✅ THE SPECIFIC SALARY QUESTION IS NOW WORKING!")
        logger.info(f"Response: {specific_result.get('formatted_response')}")
        logger.info("✅ SALARY FIX VALIDATION: SUCCESS")
    else:
        logger.error("❌ THE SPECIFIC SALARY QUESTION IS STILL NOT WORKING")
        logger.error(f"Error: {specific_result.get('error')}")
        logger.error("❌ SALARY FIX VALIDATION: FAILED")
    
    return {
        "overall_success": len(successful_tests) == len(results),
        "specific_question_working": specific_result.get("success"),
        "results": results
    }

if __name__ == "__main__":
    asyncio.run(main())
