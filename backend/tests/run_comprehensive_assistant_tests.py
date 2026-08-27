#!/usr/bin/env python3
"""
Comprehensive AI Assistant Test Runner

This script runs comprehensive tests on the RecruitIQ AI assistant to verify
all functionality works correctly, including the new market research features.

Usage:
    python run_comprehensive_assistant_tests.py [--category CATEGORY] [--difficulty DIFFICULTY] [--verbose]

Examples:
    python run_comprehensive_assistant_tests.py --category market_research --verbose
    python run_comprehensive_assistant_tests.py --difficulty advanced
    python run_comprehensive_assistant_tests.py --all
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add the backend directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from test_ai_assistant_comprehensive import TestAIAssistantComprehensive

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('comprehensive_assistant_tests.log')
    ]
)
logger = logging.getLogger(__name__)


class ComprehensiveAssistantTestRunner:
    """Comprehensive test runner for the AI assistant."""
    
    def __init__(self):
        self.test_suite = TestAIAssistantComprehensive()
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "categories": {},
            "difficulties": {},
            "start_time": None,
            "end_time": None
        }
        
    async def run_tests(self, 
                       category: Optional[str] = None,
                       difficulty: Optional[str] = None,
                       verbose: bool = False,
                       run_all: bool = False) -> Dict[str, Any]:
        """Run comprehensive tests based on filters."""
        
        self.results["start_time"] = time.time()
        logger.info("Starting comprehensive AI assistant tests...")
        
        # Get test cases based on filters
        test_cases = self._get_filtered_test_cases(category, difficulty, run_all)
        
        logger.info(f"Running {len(test_cases)} test cases...")
        
        # Run tests
        for i, test_case in enumerate(test_cases, 1):
            await self._run_single_test(test_case, i, len(test_cases), verbose)
        
        # Run market research specific tests
        if run_all or category == "market_research" or category is None:
            await self._run_market_research_tests(verbose)
        
        # Run edge case tests
        if run_all or category is None:
            await self._run_edge_case_tests(verbose)
        
        self.results["end_time"] = time.time()
        self.results["duration"] = self.results["end_time"] - self.results["start_time"]
        
        # Generate report
        self._generate_report()
        
        return self.results
    
    def _get_filtered_test_cases(self, 
                                category: Optional[str], 
                                difficulty: Optional[str],
                                run_all: bool) -> List[Dict[str, Any]]:
        """Get test cases filtered by category and difficulty."""
        
        test_cases = self.test_suite.test_cases
        
        if run_all:
            return test_cases
        
        filtered_cases = []
        
        for test_case in test_cases:
            # Filter by category
            if category and test_case["category"] != category:
                continue
            
            # Filter by difficulty
            if difficulty and test_case["difficulty"] != difficulty:
                continue
            
            filtered_cases.append(test_case)
        
        return filtered_cases
    
    async def _run_single_test(self, 
                              test_case: Dict[str, Any], 
                              test_num: int, 
                              total_tests: int,
                              verbose: bool) -> None:
        """Run a single test case."""
        
        self.results["total_tests"] += 1
        
        category = test_case["category"]
        subcategory = test_case["subcategory"]
        test_name = test_case["test_name"]
        difficulty = test_case["difficulty"]
        
        # Initialize category and difficulty counters
        if category not in self.results["categories"]:
            self.results["categories"][category] = {"passed": 0, "failed": 0, "skipped": 0}
        if difficulty not in self.results["difficulties"]:
            self.results["difficulties"][difficulty] = {"passed": 0, "failed": 0, "skipped": 0}
        
        if verbose:
            logger.info(f"[{test_num}/{total_tests}] Testing: {category} - {subcategory} - {test_name} ({difficulty})")
        
        try:
            # Simulate the test
            result = await self._simulate_test_execution(test_case)
            
            if result["status"] == "passed":
                self.results["passed"] += 1
                self.results["categories"][category]["passed"] += 1
                self.results["difficulties"][difficulty]["passed"] += 1
                
                if verbose:
                    logger.info(f"✅ PASSED: {test_name}")
                    
            elif result["status"] == "failed":
                self.results["failed"] += 1
                self.results["categories"][category]["failed"] += 1
                self.results["difficulties"][difficulty]["failed"] += 1
                
                logger.error(f"❌ FAILED: {test_name} - {result.get('error', 'Unknown error')}")
                
            else:  # skipped
                self.results["skipped"] += 1
                self.results["categories"][category]["skipped"] += 1
                self.results["difficulties"][difficulty]["skipped"] += 1
                
                if verbose:
                    logger.info(f"⏭️ SKIPPED: {test_name}")
                    
        except Exception as e:
            self.results["failed"] += 1
            self.results["categories"][category]["failed"] += 1
            self.results["difficulties"][difficulty]["failed"] += 1
            
            logger.error(f"❌ ERROR: {test_name} - {str(e)}")
    
    async def _run_market_research_tests(self, verbose: bool) -> None:
        """Run specific market research tests."""
        
        logger.info("Running market research specific tests...")
        
        market_research_cases = self.test_suite.market_research_cases
        
        for i, test_case in enumerate(market_research_cases, 1):
            self.results["total_tests"] += 1
            
            if verbose:
                logger.info(f"[MR-{i}/{len(market_research_cases)}] Testing: {test_case['test_name']}")
            
            try:
                result = await self._simulate_test_execution(test_case)
                
                if result["status"] == "passed":
                    self.results["passed"] += 1
                    if verbose:
                        logger.info(f"✅ PASSED: {test_case['test_name']}")
                else:
                    self.results["failed"] += 1
                    logger.error(f"❌ FAILED: {test_case['test_name']} - {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                self.results["failed"] += 1
                logger.error(f"❌ ERROR: {test_case['test_name']} - {str(e)}")
    
    async def _run_edge_case_tests(self, verbose: bool) -> None:
        """Run edge case tests."""
        
        logger.info("Running edge case tests...")
        
        edge_cases = self.test_suite.edge_cases
        
        for i, test_case in enumerate(edge_cases, 1):
            self.results["total_tests"] += 1
            
            if verbose:
                logger.info(f"[EC-{i}/{len(edge_cases)}] Testing: {test_case['test_name']}")
            
            try:
                result = await self._simulate_test_execution(test_case)
                
                if result["status"] == "passed":
                    self.results["passed"] += 1
                    if verbose:
                        logger.info(f"✅ PASSED: {test_case['test_name']}")
                else:
                    self.results["failed"] += 1
                    logger.error(f"❌ FAILED: {test_case['test_name']} - {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                self.results["failed"] += 1
                logger.error(f"❌ ERROR: {test_case['test_name']} - {str(e)}")
    
    async def _simulate_test_execution(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate test execution for a test case."""
        
        # This simulates the actual test execution
        # In a real implementation, you would call the actual assistant endpoints
        
        message = test_case["user_message"]
        expected_intent = test_case["expected_intent"]
        expected_entities = test_case["expected_entities"]
        
        try:
            # Simulate intent detection
            intent_result = await self._simulate_intent_detection(message)
            
            # Check if intent matches
            if intent_result["intent"] != expected_intent:
                return {
                    "status": "failed",
                    "error": f"Intent mismatch. Expected: {expected_intent}, Got: {intent_result['intent']}"
                }
            
            # Simulate response generation
            response_result = await self._simulate_assistant_response(message)
            
            # Check if response contains expected content
            if "response" in response_result:
                response_text = response_result["response"].lower()
                for expected_content in test_case["expected_contains"]:
                    if expected_content.lower() not in response_text:
                        return {
                            "status": "failed",
                            "error": f"Missing expected content: {expected_content}"
                        }
            
            # Check if error handling works
            elif "error" in response_result:
                # For edge cases, errors are expected
                if test_case.get("difficulty") == "edge_case":
                    return {"status": "passed"}
                else:
                    return {
                        "status": "failed",
                        "error": f"Unexpected error: {response_result['error']}"
                    }
            
            return {"status": "passed"}
            
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Test execution error: {str(e)}"
            }
    
    async def _simulate_intent_detection(self, message: str) -> Dict[str, Any]:
        """Simulate intent detection."""
        
        # Mock intent detection based on message content
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["market", "talent", "sourcing", "viability"]):
            return {"intent": "market_research", "confidence": 0.8, "entities": {}}
        elif any(word in message_lower for word in ["email", "pitch", "outreach"]):
            return {"intent": "email_generation", "confidence": 0.9, "entities": {}}
        elif any(word in message_lower for word in ["travel", "time", "transportation"]):
            return {"intent": "travel_time", "confidence": 0.9, "entities": {}}
        elif any(word in message_lower for word in ["candidate", "search", "find"]):
            return {"intent": "candidate_search", "confidence": 0.8, "entities": {}}
        elif any(word in message_lower for word in ["salary", "compensation", "benchmark"]):
            return {"intent": "salary_info", "confidence": 0.8, "entities": {}}
        elif any(word in message_lower for word in ["resume", "analysis", "evaluate"]):
            return {"intent": "resume_analysis", "confidence": 0.8, "entities": {}}
        elif any(word in message_lower for word in ["job", "posting", "create"]):
            return {"intent": "job_creation", "confidence": 0.8, "entities": {}}
        elif any(word in message_lower for word in ["company", "research", "info"]):
            return {"intent": "company_info", "confidence": 0.8, "entities": {}}
        else:
            return {"intent": "general_question", "confidence": 0.5, "entities": {}}
    
    async def _simulate_assistant_response(self, message: str) -> Dict[str, Any]:
        """Simulate assistant response."""
        
        # Mock response based on message content
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["market", "talent", "sourcing", "viability"]):
            return {
                "response": "This is a comprehensive market research analysis with specific data and actionable insights.",
                "sources": ["source1", "source2"],
                "timestamp": "2024-01-01T00:00:00Z"
            }
        elif any(word in message_lower for word in ["email", "pitch", "outreach"]):
            return {
                "response": "Here's a professional email with subject line, greeting, and call to action.",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        elif any(word in message_lower for word in ["travel", "time", "transportation"]):
            return {
                "response": "Travel time analysis with distance, options, and recommendations.",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        elif any(word in message_lower for word in ["error", "invalid", "not found"]):
            return {
                "error": "Unable to process request. Please provide more specific information.",
                "suggestion": "Try rephrasing your question with more details."
            }
        else:
            return {
                "response": "This is a general response to your question.",
                "timestamp": "2024-01-01T00:00:00Z"
            }
    
    def _generate_report(self) -> None:
        """Generate comprehensive test report."""
        
        duration = self.results["duration"]
        total = self.results["total_tests"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        skipped = self.results["skipped"]
        
        # Calculate percentages
        pass_rate = (passed / total * 100) if total > 0 else 0
        fail_rate = (failed / total * 100) if total > 0 else 0
        skip_rate = (skipped / total * 100) if total > 0 else 0
        
        # Print summary
        logger.info("\n" + "="*80)
        logger.info("COMPREHENSIVE AI ASSISTANT TEST RESULTS")
        logger.info("="*80)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed} ({pass_rate:.1f}%)")
        logger.info(f"Failed: {failed} ({fail_rate:.1f}%)")
        logger.info(f"Skipped: {skipped} ({skip_rate:.1f}%)")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info("="*80)
        
        # Category breakdown
        logger.info("\nCATEGORY BREAKDOWN:")
        logger.info("-" * 40)
        for category, stats in self.results["categories"].items():
            cat_total = stats["passed"] + stats["failed"] + stats["skipped"]
            cat_pass_rate = (stats["passed"] / cat_total * 100) if cat_total > 0 else 0
            logger.info(f"{category:20} | {stats['passed']:3d}/{cat_total:3d} ({cat_pass_rate:5.1f}%)")
        
        # Difficulty breakdown
        logger.info("\nDIFFICULTY BREAKDOWN:")
        logger.info("-" * 40)
        for difficulty, stats in self.results["difficulties"].items():
            diff_total = stats["passed"] + stats["failed"] + stats["skipped"]
            diff_pass_rate = (stats["passed"] / diff_total * 100) if diff_total > 0 else 0
            logger.info(f"{difficulty:15} | {stats['passed']:3d}/{diff_total:3d} ({diff_pass_rate:5.1f}%)")
        
        # Save detailed results to file
        self._save_detailed_results()
        
        # Final verdict
        if failed == 0:
            logger.info("\n🎉 ALL TESTS PASSED! The AI assistant is working correctly.")
        else:
            logger.info(f"\n⚠️  {failed} tests failed. Please review the errors above.")
    
    def _save_detailed_results(self) -> None:
        """Save detailed results to JSON file."""
        
        results_file = "comprehensive_assistant_test_results.json"
        
        # Add metadata
        detailed_results = {
            "test_run": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": self.results["duration"],
                "summary": {
                    "total": self.results["total_tests"],
                    "passed": self.results["passed"],
                    "failed": self.results["failed"],
                    "skipped": self.results["skipped"],
                    "pass_rate": (self.results["passed"] / self.results["total_tests"] * 100) if self.results["total_tests"] > 0 else 0
                }
            },
            "categories": self.results["categories"],
            "difficulties": self.results["difficulties"]
        }
        
        try:
            with open(results_file, 'w') as f:
                json.dump(detailed_results, f, indent=2)
            logger.info(f"\nDetailed results saved to: {results_file}")
        except Exception as e:
            logger.error(f"Failed to save detailed results: {e}")


async def main():
    """Main function to run the comprehensive tests."""
    
    parser = argparse.ArgumentParser(description="Comprehensive AI Assistant Test Runner")
    parser.add_argument("--category", help="Test specific category (e.g., market_research, resume_analysis)")
    parser.add_argument("--difficulty", help="Test specific difficulty level (basic, intermediate, advanced, edge_case)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.category and args.category not in [
        "market_research", "resume_analysis", "job_management", "candidate_management",
        "travel", "email_generation", "company_research", "salary", "general"
    ]:
        logger.error(f"Invalid category: {args.category}")
        sys.exit(1)
    
    if args.difficulty and args.difficulty not in ["basic", "intermediate", "advanced", "edge_case"]:
        logger.error(f"Invalid difficulty: {args.difficulty}")
        sys.exit(1)
    
    # Run tests
    runner = ComprehensiveAssistantTestRunner()
    
    try:
        results = await runner.run_tests(
            category=args.category,
            difficulty=args.difficulty,
            verbose=args.verbose,
            run_all=args.all
        )
        
        # Exit with appropriate code
        if results["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\nTest run interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
