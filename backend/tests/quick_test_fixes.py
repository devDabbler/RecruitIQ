"""
Quick Test for AI Assistant Fixes
Tests the most critical fixes to verify they're working.
"""
import asyncio
import httpx
import json

async def quick_test_fixes():
    """Quick test of the most critical fixes."""
    base_url = "http://localhost:8000"
    chat_endpoint = f"{base_url}/api/assistant/chat"
    
    # Test the most critical fixes
    test_cases = [
        {
            "name": "Greeting Intent Fix",
            "message": "Hello, how are you?",
            "expected_intent": "general_question",
            "expected_keywords": ["hello", "hi", "greeting"]
        },
        {
            "name": "Software Engineer Skills Intent Fix", 
            "message": "What skills do software engineers need?",
            "expected_intent": "skill_info",
            "expected_keywords": ["software", "engineer", "skills"]
        },
        {
            "name": "Company Info Intent Fix",
            "message": "Tell me about Google as a company",
            "expected_intent": "company_info", 
            "expected_keywords": ["google", "company"]
        },
        {
            "name": "Candidate Search Intent Fix",
            "message": "Find me all data scientist candidates",
            "expected_intent": "search_candidates",
            "expected_keywords": ["candidates", "data scientist"]
        }
    ]
    
    print("🔧 Quick Test of Critical Fixes...")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"\n🧪 Testing: {test_case['name']}")
            print(f"   Message: {test_case['message']}")
            
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
                    
                    # Check intent
                    intent_correct = detected_intent == test_case["expected_intent"]
                    
                    # Check keywords
                    keywords_found = all(keyword.lower() in response_text.lower() for keyword in test_case["expected_keywords"])
                    
                    if intent_correct and keywords_found:
                        print(f"   ✅ PASS - Intent: {detected_intent}, Keywords: Found")
                    elif intent_correct:
                        print(f"   ⚠️  PARTIAL - Intent: {detected_intent} (correct), Keywords: Missing")
                    else:
                        print(f"   ❌ FAIL - Intent: {detected_intent} (expected: {test_case['expected_intent']})")
                    
                    print(f"   📝 Response: {response_text[:100]}...")
                    
                else:
                    print(f"   ❌ HTTP ERROR: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ EXCEPTION: {str(e)}")
    
    print("\n🎯 Quick Test Complete!")
    print("If you see mostly ✅ PASS results, the critical fixes are working!")

if __name__ == "__main__":
    asyncio.run(quick_test_fixes()) 