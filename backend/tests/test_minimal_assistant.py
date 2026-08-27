#!/usr/bin/env python3
"""
Minimal test to isolate the text variable issue.
"""

import asyncio
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_minimal_chat():
    """Test minimal chat functionality."""
    
    base_url = "http://localhost:8000"
    api_url = f"{base_url}/api/assistant/chat"
    
    # Test with a simple message that shouldn't trigger any database queries
    test_message = "Hello, how are you?"
    
    print(f"\n🔍 Testing minimal message: '{test_message}'")
    print("=" * 60)
    
    try:
        print("Sending request...")
        response = requests.post(
            api_url,
            json={
                "message": test_message,
                "conversation_history": [],
                "conversation_context": {}
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            actual_response = data.get("response", "")
            
            print(f"Response: {actual_response}")
            
            # Check for error indicators
            error_indicators = ["encountered an error", "try again", "contact support", "trouble connecting"]
            has_error = any(indicator in actual_response.lower() for indicator in error_indicators)
            
            if has_error:
                print("❌ ERROR DETECTED: Response contains error message")
            else:
                print("✅ SUCCESS: Response does not contain error message")
                
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_minimal_chat()) 