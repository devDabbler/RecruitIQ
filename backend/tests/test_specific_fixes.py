#!/usr/bin/env python3
"""
Focused test script for the specific AI Assistant fixes.
Tests the remaining 3 failing tests to verify they now work.
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

class SpecificFixTester:
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
            print(f"   Response: {details['response'][:150]}...")
        print()
        
    async def test_salary_intent_detection(self) -> Dict[str, Any]:
        """Test salary information intent detection."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "message": "What's the salary for a software engineer in New York?",
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if response contains salary-related content
                salary_indicators = ["salary", "pay", "compensation", "earn", "income", "new york", "software engineer"]
                intent_detected = any(indicator in actual_response.lower() for indicator in salary_indicators)
                
                return {
                    "status": "PASS" if intent_detected else "FAIL",
                    "response": actual_response,
                    "intent_detected": intent_detected,
                    "response_length": len(actual_response)
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
    
    async def test_candidate_search_by_role(self) -> Dict[str, Any]:
        """Test candidate search by role functionality."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "message": "Find me all data scientist candidates",
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if response contains expected content and provides helpful information
                error_indicators = ["encountered an error", "try again", "contact support"]
                has_error = any(indicator in actual_response.lower() for indicator in error_indicators)
                
                expected_indicators = ["data scientist", "candidate", "found", "search", "database"]
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
    
    async def test_candidate_search_by_skills(self) -> Dict[str, Any]:
        """Test candidate search by skills functionality."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "message": "Find candidates with Python skills",
                    "conversation_history": [],
                    "conversation_context": {}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                actual_response = data.get("response", "")
                
                # Check if response contains expected content and provides helpful information
                error_indicators = ["encountered an error", "try again", "contact support"]
                has_error = any(indicator in actual_response.lower() for indicator in error_indicators)
                
                expected_indicators = ["python", "skills", "candidate", "found", "search", "database"]
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
    
    async def run_specific_tests(self):
        """Run the specific tests for the remaining failing functionality."""
        print("🔧 Testing Specific AI Assistant Fixes...")
        print("=" * 60)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test 1: Salary Information Intent Detection
        result = await self.test_salary_intent_detection()
        self.log_test_result("Salary Information Intent Detection", result["status"], result)
        
        # Test 2: Candidate Search by Role
        result = await self.test_candidate_search_by_role()
        self.log_test_result("Candidate Search by Role", result["status"], result)
        
        # Test 3: Candidate Search by Skills
        result = await self.test_candidate_search_by_skills()
        self.log_test_result("Candidate Search by Skills", result["status"], result)
        
        # Generate summary
        self.generate_summary()
        
    def generate_summary(self):
        """Generate a test summary."""
        print("📊 SPECIFIC FIX TEST SUMMARY")
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
        filename = f"specific_fix_test_{timestamp}.json"
        
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
            print("🎉 EXCELLENT! All specific fixes are working perfectly.")
            print("   The AI assistant should now have 100% success rate!")
        elif passed_tests >= total_tests * 0.8:
            print("✅ GOOD! Most specific fixes are working.")
            print("   The AI assistant is performing well with minor issues.")
        elif passed_tests >= total_tests * 0.6:
            print("⚠️  FAIR! Some specific fixes are working.")
            print("   The AI assistant needs more work on specific areas.")
        else:
            print("❌ NEEDS WORK! Many specific fixes are still failing.")
            print("   The AI assistant needs significant additional fixes.")

async def main():
    """Main function to run the specific tests."""
    tester = SpecificFixTester()
    await tester.run_specific_tests()

if __name__ == "__main__":
    asyncio.run(main()) 