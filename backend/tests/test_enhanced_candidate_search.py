#!/usr/bin/env python3
"""
Test script for enhanced candidate search functionality.
This script tests the backend assistant's ability to return candidate search results
with match explanations and enhanced formatting.
"""

import requests
import json
import sys

def test_candidate_search():
    """Test the enhanced candidate search functionality."""
    
    # Test data
    test_queries = [
        "Can you show me all candidates with AI development experience?",
        "Find candidates with Python experience",
        "Search for software engineers",
        "Show me candidates with machine learning skills"
    ]
    
    print("🧪 Testing Enhanced Candidate Search Functionality")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test {i}: {query}")
        print("-" * 40)
        
        try:
            # Call the backend assistant API
            response = requests.post(
                "http://localhost:8000/api/assistant/chat",
                json={
                    "message": query,
                    "conversation_history": [],
                    "conversation_context": {"db_available": True}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got a structured response with candidate details
                if "candidate_details" in data:
                    print("✅ Enhanced response received!")
                    print(f"📊 Found {len(data['candidate_details'])} candidates")
                    
                    # Display candidate details
                    for j, candidate in enumerate(data['candidate_details'][:3], 1):  # Show first 3
                        print(f"\n👤 Candidate {j}: {candidate.get('name', 'Unknown')}")
                        print(f"   Match Score: {candidate.get('match_score', 'N/A')}%")
                        print(f"   Skills: {', '.join(candidate.get('skills', [])[:5])}")
                        if candidate.get('match_explanation'):
                            print(f"   Match Reason: {candidate['match_explanation'][:100]}...")
                        if candidate.get('current_position'):
                            print(f"   Current Role: {candidate['current_position']}")
                else:
                    print("⚠️  Regular response (no candidate details)")
                    print(f"Response: {data.get('response', 'No response')[:200]}...")
                    
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Backend server not running")
            break
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🏁 Test completed!")

if __name__ == "__main__":
    test_candidate_search() 