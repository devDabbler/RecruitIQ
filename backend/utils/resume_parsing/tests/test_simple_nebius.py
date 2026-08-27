"""
Simpler test script to check Nebius AI initialization without circular imports.
"""
import logging
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def test_direct_nebius():
    """Test direct Nebius AI service initialization without other dependencies."""
    try:
        print("\n=== TESTING DIRECT NEBIUS AI INITIALIZATION ===\n")
        
        # Import the NebiusAIService class directly
        from backend.services.nebius_ai_service import NebiusAIService
        
        # Create config
        nebius_api_key = os.environ.get('NEBIUS_API_KEY', '') or os.environ.get('NEBIUS_API_TOKEN', '')
        if not nebius_api_key:
            print("No Nebius API key found in environment variables")
            return
            
        nebius_config = {
            "api_key": nebius_api_key,
            "model": "microsoft/phi-4",
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        # Create the service
        print("Creating NebiusAIService directly...")
        nebius_service = NebiusAIService(nebius_config)
        print(f"NebiusAIService created successfully: {nebius_service is not None}")
        
        print("\n=== TEST COMPLETE ===\n")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_nebius()
