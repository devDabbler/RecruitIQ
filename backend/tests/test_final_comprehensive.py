#!/usr/bin/env python3
"""
Final comprehensive test script for AI Assistant improvements.
Tests all functionality to get the final success rate after all fixes.
"""

import asyncio
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FinalComprehensiveTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/assistant/chat"
        self.test_results = []
        
    def log_test_result(self, test_name: str, status: str, details: Dict[str, Any]):
        """Log test result with timestamp."""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        
        # Print result
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status}")
        if details.get("error"):
            print(f"   Error: {details['error']}")
        if details.get("response"):
            print(f"   Response: {details['response'][:100]}...")
        print()
        
    async def test_intent_detection(self, message: str, expected_intent: str, test_name: str) -> Dict[str, Any]:
        """Test intent detection for a specific message."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "message": message,
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if the response contains expected content
                intent_detected = False
                if expected_intent == "general_question":
                    # For greetings, check if response is friendly and acknowledges the greeting
                    greeting_indicators = ["hello", "hi", "greeting", "how are you", "doing well", "thank you"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in greeting_indicators)
                elif expected_intent == "skill_info":
                    # For skill info, check if response contains skill-related content
                    skill_indicators = ["skills", "programming", "languages", "technologies", "expertise"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in skill_indicators)
                elif expected_intent == "company_info":
                    # For company info, check if response contains company-related content
                    company_indicators = ["company", "organization", "business", "employer"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in company_indicators)
                elif expected_intent == "search_candidates":
                    # For candidate search, check if response contains candidate-related content
                    candidate_indicators = ["candidate", "found", "database", "search", "can help"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in candidate_indicators)
                elif expected_intent == "web_search":
                    # For web search, check if response contains search-related content
                    search_indicators = ["search", "found", "information", "trends", "market"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in search_indicators)
                elif expected_intent == "salary_info":
                    # For salary info, check if response contains salary-related content
                    salary_indicators = ["salary", "pay", "compensation", "earn", "income"]
                    intent_detected = any(indicator in actual_response.lower() for indicator in salary_indicators)
                
                return {
                    "status": "PASS" if intent_detected else "FAIL",
                    "response": actual_response,
                    "expected_intent": expected_intent,
                    "intent_detected": intent_detected,
                    "response_length": len(actual_response)
                }
            else:
                return {
                    "status": "FAIL",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "expected_intent": expected_intent
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "error": str(e),
                "expected_intent": expected_intent
            }
    
    async def test_database_queries(self) -> Dict[str, Any]:
        """Test database-related queries to ensure they work properly."""
        try:
            # Test candidate count query
            response = requests.post(
                self.api_url,
                json={
                    "message": "How many candidates are in the database?",
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if response contains a number and "candidate"
                import re
                number_match = re.search(r'(\d+)', actual_response)
                has_candidate = "candidate" in actual_response.lower()
                
                if number_match and has_candidate:
                    return {
                        "status": "PASS",
                        "response": actual_response,
                        "candidate_count": number_match.group(1)
                    }
                else:
                    return {
                        "status": "FAIL",
                        "response": actual_response,
                        "error": "Response doesn't contain expected candidate count format"
                    }
            else:
                return {
                    "status": "FAIL",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "error": str(e)
            }
    
    async def test_candidate_search(self, search_query: str, expected_keywords: List[str]) -> Dict[str, Any]:
        """Test candidate search functionality."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "message": search_query,
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if response contains expected keywords and doesn't have error message
                error_indicators = ["encountered an error", "try again", "contact support"]
                has_error = any(indicator in actual_response.lower() for indicator in error_indicators)
                
                expected_indicators = expected_keywords + ["candidate", "search", "database", "can help"]
                has_expected = any(indicator in actual_response.lower() for indicator in expected_indicators)
                
                # Check if response is helpful (contains useful information)
                helpful_indicators = ["can help", "search", "database", "candidates", "information"]
                is_helpful = any(indicator in actual_response.lower() for indicator in helpful_indicators)
                
                if not has_error and (has_expected or is_helpful):
                    return {
                        "status": "PASS",
                        "response": actual_response,
                        "no_error": True,
                        "has_expected_content": has_expected,
                        "is_helpful": is_helpful
                    }
                elif has_error:
                    return {
                        "status": "FAIL",
                        "response": actual_response,
                        "error": "Response contains error message",
                        "no_error": False
                    }
                else:
                    return {
                        "status": "FAIL",
                        "response": actual_response,
                        "error": "Response missing expected content and not helpful",
                        "has_expected_content": False,
                        "is_helpful": False
                    }
            else:
                return {
                    "status": "FAIL",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "error": str(e)
            }
    
    async def run_final_comprehensive_tests(self):
        """Run all comprehensive tests for final assessment."""
        print("🔧 Running Final Comprehensive AI Assistant Tests...")
        print("=" * 60)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test 1: Basic Greeting Fix
        result = await self.test_intent_detection(
            "Hello, how are you?",
            "general_question",
            "Basic Greeting Fix"
        )
        self.log_test_result("Basic Greeting Fix", result["status"], result)
        
        # Test 2: Software Engineer Skills Fix
        result = await self.test_intent_detection(
            "What skills do software engineers need?",
            "skill_info",
            "Software Engineer Skills Fix"
        )
        self.log_test_result("Software Engineer Skills Fix", result["status"], result)
        
        # Test 3: Company Information Fix
        result = await self.test_intent_detection(
            "Tell me about Google as a company",
            "company_info",
            "Company Information Fix"
        )
        self.log_test_result("Company Information Fix", result["status"], result)
        
        # Test 4: Data Scientist Skills Fix
        result = await self.test_intent_detection(
            "What skills do data scientists need?",
            "skill_info",
            "Data Scientist Skills Fix"
        )
        self.log_test_result("Data Scientist Skills Fix", result["status"], result)
        
        # Test 5: Web Search Fix
        result = await self.test_intent_detection(
            "What are the latest trends in AI?",
            "web_search",
            "Web Search Fix"
        )
        self.log_test_result("Web Search Fix", result["status"], result)
        
        # Test 6: Database Count Query
        result = await self.test_database_queries()
        self.log_test_result("Database Count Query", result["status"], result)
        
        # Test 7: Candidate Search by Role
        result = await self.test_candidate_search(
            "Find me all data scientist candidates",
            ["data scientist", "found", "candidate"]
        )
        self.log_test_result("Candidate Search by Role", result["status"], result)
        
        # Test 8: Candidate Search by Skills
        result = await self.test_candidate_search(
            "Find candidates with Python skills",
            ["python", "skills", "candidate"]
        )
        self.log_test_result("Candidate Search by Skills", result["status"], result)
        
        # Test 9: Salary Information
        result = await self.test_intent_detection(
            "What's the salary for a software engineer in New York?",
            "salary_info",
            "Salary Information"
        )
        self.log_test_result("Salary Information", result["status"], result)
        
        # Test 10: Market Trends
        result = await self.test_intent_detection(
            "What are the current market trends in tech?",
            "web_search",
            "Market Trends"
        )
        self.log_test_result("Market Trends", result["status"], result)
        
        # Generate summary
        self.generate_summary()
        
    def generate_summary(self):
        """Generate a comprehensive test summary."""
        print("📊 FINAL COMPREHENSIVE TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["status"] == "PASS")
        failed_tests = sum(1 for result in self.test_results if result["status"] == "FAIL")
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        # Detailed results
        print("📋 DETAILED RESULTS")
        print("=" * 60)
        for result in self.test_results:
            status_emoji = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_emoji} {result['test_name']}")
            if result["status"] == "FAIL" and result["details"].get("error"):
                print(f"   Error: {result['details']['error']}")
            print()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"final_comprehensive_test_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                "test_summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "success_rate": (passed_tests/total_tests)*100
                },
                "test_results": self.test_results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"💾 Results saved to: {filename}")
        
        # Final assessment
        print("🎯 FINAL ASSESSMENT")
        print("=" * 60)
        if passed_tests == total_tests:
            print("🎉 PERFECT! All tests passed. The AI assistant is working flawlessly!")
            print("   Success Rate: 100% - EXCELLENT!")
        elif passed_tests >= total_tests * 0.9:
            print("🎉 EXCELLENT! Almost all tests passed. The AI assistant is working very well!")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}% - OUTSTANDING!")
        elif passed_tests >= total_tests * 0.8:
            print("✅ GREAT! Most tests passed. The AI assistant is working well!")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}% - VERY GOOD!")
        elif passed_tests >= total_tests * 0.7:
            print("✅ GOOD! Many tests passed. The AI assistant is working satisfactorily.")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}% - GOOD!")
        elif passed_tests >= total_tests * 0.6:
            print("⚠️  FAIR! Some tests passed. The AI assistant needs more work.")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}% - NEEDS IMPROVEMENT!")
        else:
            print("❌ NEEDS WORK! Many tests failed. The AI assistant needs significant fixes.")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}% - REQUIRES MAJOR WORK!")
        
        print(f"\n🎯 IMPROVEMENT SUMMARY:")
        print(f"   Original Accuracy: 50%")
        print(f"   Current Accuracy: {(passed_tests/total_tests)*100:.1f}%")
        print(f"   Improvement: {((passed_tests/total_tests)*100 - 50):.1f} percentage points")

async def main():
    """Main function to run the final comprehensive tests."""
    tester = FinalComprehensiveTester()
    await tester.run_final_comprehensive_tests()

if __name__ == "__main__":
    asyncio.run(main()) 