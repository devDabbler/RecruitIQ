"""
Test AI Assistant Fixes
Comprehensive test to verify that the candidate search and intent detection fixes are working.
"""
import asyncio
import httpx
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_assistant_fixes():
    """Test the AI assistant fixes for candidate search and intent detection."""
    base_url = "http://localhost:8000"
    chat_endpoint = f"{base_url}/api/assistant/chat"
    
    test_cases = [
        # Test 1: Basic greeting (should detect as general_question)
        {
            "name": "Basic Greeting Fix",
            "message": "Hello, how are you?",
            "expected_intent": "general_question",
            "expected_contains": ["hello", "hi", "greeting", "doing well"],
            "description": "Should properly detect greeting as general_question intent"
        },
        
        # Test 2: Software engineer skills (should detect as skill_info)
        {
            "name": "Software Engineer Skills Fix",
            "message": "What skills do software engineers need?",
            "expected_intent": "skill_info",
            "expected_contains": ["software", "engineer", "skills", "programming"],
            "description": "Should detect software engineer skills query as skill_info intent"
        },
        
        # Test 3: Company information (should detect as company_info)
        {
            "name": "Company Information Fix",
            "message": "Tell me about Google as a company",
            "expected_intent": "company_info",
            "expected_contains": ["google", "company", "information"],
            "description": "Should detect company query as company_info intent"
        },
        
        # Test 4: Candidate search by role (should work without database errors)
        {
            "name": "Candidate Search by Role Fix",
            "message": "Find me all data scientist candidates",
            "expected_intent": "search_candidates",
            "expected_contains": ["candidates", "data scientist", "found"],
            "description": "Should search for candidates without database errors"
        },
        
        # Test 5: Candidate search by skills (should work without database errors)
        {
            "name": "Candidate Search by Skills Fix",
            "message": "Find candidates with Python skills",
            "expected_intent": "search_candidates",
            "expected_contains": ["candidates", "python", "skills"],
            "description": "Should search for candidates by skills without database errors"
        },
        
        # Test 6: Database count queries (should work)
        {
            "name": "Database Count Queries",
            "message": "How many candidates are in the database?",
            "expected_intent": "candidate_count",
            "expected_contains": ["candidates", "database"],
            "description": "Should return candidate count from database"
        },
        
        # Test 7: Salary information (should work)
        {
            "name": "Salary Information",
            "message": "What's the salary for a software engineer in New York?",
            "expected_intent": "salary_info",
            "expected_contains": ["salary", "software engineer", "new york"],
            "description": "Should provide salary information"
        },
        
        # Test 8: Web search (should work)
        {
            "name": "Web Search",
            "message": "What are the latest trends in AI?",
            "expected_intent": "web_search",
            "expected_contains": ["ai", "trends", "artificial intelligence"],
            "description": "Should perform web search for AI trends"
        }
    ]
    
    print("🔧 Testing AI Assistant Fixes...")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = {
        "total_tests": len(test_cases),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "intent_accuracy": 0,
        "response_accuracy": 0,
        "detailed_results": []
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            print(f"🧪 Test {i}/{len(test_cases)}: {test_case['name']}")
            print(f"   📝 Description: {test_case['description']}")
            print(f"   💬 Message: {test_case['message']}")
            print(f"   🎯 Expected Intent: {test_case['expected_intent']}")
            
            try:
                payload = {
                    "message": test_case["message"],
                    "conversation_history": [],
                    "conversation_context": {}
                }
                
                response = await client.post(chat_endpoint, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("response", "")
                    context = result.get("conversation_context", {})
                    detected_intent = context.get("last_intent", "unknown")
                    
                    # Check intent detection
                    intent_correct = detected_intent == test_case["expected_intent"]
                    
                    # Check response content
                    content_ok = True
                    missing_content = []
                    for expected in test_case["expected_contains"]:
                        if expected.lower() not in response_text.lower():
                            content_ok = False
                            missing_content.append(expected)
                    
                    # Determine test result
                    if intent_correct and content_ok:
                        status = "PASS"
                        results["passed"] += 1
                        print(f"   ✅ Status: PASS")
                    else:
                        status = "FAIL"
                        results["failed"] += 1
                        print(f"   ❌ Status: FAIL")
                    
                    # Log details
                    print(f"   🎯 Detected Intent: {detected_intent}")
                    print(f"   📊 Response Length: {len(response_text)} chars")
                    
                    if intent_correct:
                        print(f"   ✅ Intent: Correct")
                    else:
                        print(f"   ❌ Intent: Expected '{test_case['expected_intent']}', got '{detected_intent}'")
                    
                    if content_ok:
                        print(f"   ✅ Content: All expected content found")
                    else:
                        print(f"   ⚠️  Content: Missing {missing_content}")
                    
                    # Show response preview
                    preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
                    print(f"   💬 Response: {preview}")
                    
                    # Store detailed result
                    results["detailed_results"].append({
                        "test_name": test_case["name"],
                        "message": test_case["message"],
                        "status": status,
                        "expected_intent": test_case["expected_intent"],
                        "detected_intent": detected_intent,
                        "intent_correct": intent_correct,
                        "content_ok": content_ok,
                        "missing_content": missing_content,
                        "response_length": len(response_text),
                        "response_preview": preview
                    })
                    
                else:
                    print(f"   ❌ Status: HTTP ERROR ({response.status_code})")
                    print(f"   📄 Response: {response.text}")
                    results["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Status: EXCEPTION - {str(e)}")
                results["errors"] += 1
            
            print("-" * 60)
    
    # Calculate accuracy metrics
    if results["total_tests"] > 0:
        intent_correct_count = sum(1 for r in results["detailed_results"] if r.get("intent_correct", False))
        content_correct_count = sum(1 for r in results["detailed_results"] if r.get("content_ok", False))
        
        results["intent_accuracy"] = intent_correct_count / results["total_tests"]
        results["response_accuracy"] = content_correct_count / results["total_tests"]
    
    # Print summary
    print("\n📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Errors: {results['errors']} 💥")
    print(f"Intent Detection Accuracy: {results['intent_accuracy']:.1%}")
    print(f"Response Content Accuracy: {results['response_accuracy']:.1%}")
    
    # Print detailed results
    print("\n📋 DETAILED RESULTS")
    print("=" * 60)
    for result in results["detailed_results"]:
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"{status_icon} {result['test_name']}")
        print(f"   Intent: {result['detected_intent']} (Expected: {result['expected_intent']})")
        if not result["intent_correct"]:
            print(f"   ❌ Intent mismatch!")
        if not result["content_ok"]:
            print(f"   ⚠️  Missing content: {result['missing_content']}")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_assistant_fixes_test_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {filename}")
    
    # Final assessment
    print("\n🎯 FINAL ASSESSMENT")
    print("=" * 60)
    if results["passed"] == results["total_tests"]:
        print("🎉 ALL TESTS PASSED! The AI assistant fixes are working perfectly!")
    elif results["intent_accuracy"] >= 0.8 and results["response_accuracy"] >= 0.8:
        print("✅ MOSTLY WORKING! The fixes have significantly improved the AI assistant.")
        print("   Minor improvements may still be needed for edge cases.")
    elif results["intent_accuracy"] >= 0.6 and results["response_accuracy"] >= 0.6:
        print("⚠️  IMPROVED! The fixes have helped, but further work is needed.")
        print("   Focus on the failed test cases for additional improvements.")
    else:
        print("❌ NEEDS MORE WORK! The fixes haven't fully resolved the issues.")
        print("   Review the detailed results and implement additional fixes.")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_ai_assistant_fixes()) 