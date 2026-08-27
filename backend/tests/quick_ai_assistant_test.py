"""
Quick AI Assistant Test
Tests basic functionality to verify Groq integration is working.
"""
import asyncio
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_assistant():
    """Quick test of AI assistant functionality."""
    base_url = "http://localhost:8000"
    chat_endpoint = f"{base_url}/api/assistant/chat"
    
    test_cases = [
        {
            "name": "Basic Greeting",
            "message": "Hello, how are you?",
            "expected_contains": ["hello", "hi", "greeting"]
        },
        {
            "name": "Skill Information",
            "message": "What skills do data scientists need?",
            "expected_contains": ["python", "machine learning", "data"]
        },
        {
            "name": "Database Query",
            "message": "How many candidates are in the database?",
            "expected_contains": ["candidates", "database"]
        },
        {
            "name": "Web Search",
            "message": "What are the latest trends in AI?",
            "expected_contains": ["ai", "trends", "artificial intelligence"]
        },
        {
            "name": "Salary Information",
            "message": "What's the salary for a software engineer in San Francisco?",
            "expected_contains": ["salary", "software engineer", "san francisco"]
        }
    ]
    
    print("🤖 Testing AI Assistant with Groq...")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['name']}")
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
                    
                    # Check if response contains expected content
                    response_ok = True
                    missing_content = []
                    for expected in test_case["expected_contains"]:
                        if expected.lower() not in response_text.lower():
                            response_ok = False
                            missing_content.append(expected)
                    
                    # Check intent detection
                    detected_intent = context.get("last_intent", "unknown")
                    db_available = context.get("db_available", True)
                    
                    print(f"   ✅ Status: SUCCESS")
                    print(f"   📝 Intent: {detected_intent}")
                    print(f"   🗄️  DB Available: {db_available}")
                    print(f"   📊 Response Length: {len(response_text)} chars")
                    
                    if response_ok:
                        print(f"   ✅ Content: All expected content found")
                    else:
                        print(f"   ⚠️  Content: Missing {missing_content}")
                    
                    # Show response preview
                    preview = response_text[:150] + "..." if len(response_text) > 150 else response_text
                    print(f"   💬 Response: {preview}")
                    
                else:
                    print(f"   ❌ Status: FAILED (HTTP {response.status_code})")
                    print(f"   📄 Response: {response.text}")
                    
            except Exception as e:
                print(f"   ❌ Status: ERROR - {str(e)}")
            
            print("-" * 50)
    
    print("\n🎯 Test Summary:")
    print("If you see successful responses above, your AI assistant is working with Groq!")
    print("Check the intent detection and response quality to ensure proper functionality.")

if __name__ == "__main__":
    asyncio.run(test_ai_assistant()) 