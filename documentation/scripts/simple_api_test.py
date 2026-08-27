#!/usr/bin/env python3
"""
Simple API test to check both parsing endpoints and see detailed responses
"""

import requests
import json

def test_original_api_detailed():
    """Test original API with detailed logging"""
    print("🔍 TESTING ORIGINAL API (DETAILED)")
    print("=" * 40)
    
    url = "http://localhost:8000/api/resume/parse"
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    try:
        with open(resume_file, 'rb') as f:
            files = {'file': (resume_file, f, 'application/pdf')}
            data = {'parse_type': 'detailed'}
            
            response = requests.post(url, files=files, data=data, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Print the full response structure
            print("\n📋 FULL RESPONSE STRUCTURE:")
            print(json.dumps(result, indent=2, default=str)[:2000])  # First 2000 chars
            
            # Focus on experience data
            parsed_data = result.get('parsed_data', {})
            experience = parsed_data.get('experience', [])
            
            print(f"\n💼 EXPERIENCE DATA:")
            print(f"   Type: {type(experience)}")
            print(f"   Length: {len(experience) if isinstance(experience, list) else 'Not a list'}")
            
            if isinstance(experience, list) and experience:
                print("   First few entries:")
                for i, exp in enumerate(experience[:3]):
                    print(f"     {i+1}. {exp}")
            elif isinstance(experience, list):
                print("   Experience list is empty!")
            else:
                print(f"   Experience data: {experience}")
            
            return result
        else:
            print(f"❌ Error response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def test_enhanced_api_detailed():
    """Test enhanced API with detailed logging"""
    print("\n🚀 TESTING ENHANCED API (DETAILED)")
    print("=" * 40)
    
    url = "http://localhost:8000/api/api/v1/enhanced-parsing/parse"
    resume_file = "Sean B. Collins Resume - Recruiting Leader.pdf"
    
    try:
        with open(resume_file, 'rb') as f:
            files = {'file': (resume_file, f, 'application/pdf')}
            data = {'use_llm_enhancement': 'false'}
            
            response = requests.post(url, files=files, data=data, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Print sections found
            sections_info = result.get('sections_detected', {})
            print(f"\n📁 SECTIONS DETECTED:")
            for section, info in sections_info.items():
                print(f"   {section}: {info}")
            
            # Print the full response structure
            print(f"\n📋 PARSED DATA STRUCTURE:")
            parsed_data = result.get('parsed_data', {})
            for key, value in parsed_data.items():
                if isinstance(value, list):
                    print(f"   {key}: {len(value)} items")
                elif isinstance(value, dict):
                    print(f"   {key}: dict with {len(value)} keys")
                else:
                    print(f"   {key}: {type(value).__name__}")
            
            # Focus on experience data
            experience = parsed_data.get('experience', [])
            print(f"\n💼 EXPERIENCE DATA:")
            print(f"   Type: {type(experience)}")
            print(f"   Length: {len(experience) if isinstance(experience, list) else 'Not a list'}")
            
            if isinstance(experience, list) and experience:
                print("   Experience entries:")
                for i, exp in enumerate(experience[:3]):
                    print(f"     {i+1}. {json.dumps(exp, indent=6, default=str)}")
            elif isinstance(experience, list):
                print("   Experience list is empty!")
            else:
                print(f"   Experience data: {experience}")
            
            # Check extraction stats
            extraction_stats = result.get('extraction_stats', {})
            print(f"\n📊 EXTRACTION STATS:")
            for key, value in extraction_stats.items():
                print(f"   {key}: {value}")
            
            return result
        else:
            print(f"❌ Error response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def main():
    """Run detailed API tests"""
    print("🧪 DETAILED API TESTING")
    print("=" * 50)
    
    # Test both APIs with detailed output
    original_result = test_original_api_detailed()
    enhanced_result = test_enhanced_api_detailed()
    
    # Summary
    print(f"\n🎯 SUMMARY:")
    print("=" * 20)
    
    if original_result:
        orig_exp_count = len(original_result.get('parsed_data', {}).get('experience', []))
        print(f"Original API: {orig_exp_count} experience entries")
    else:
        print("Original API: Failed")
    
    if enhanced_result:
        enh_exp_count = len(enhanced_result.get('parsed_data', {}).get('experience', []))
        print(f"Enhanced API: {enh_exp_count} experience entries")
    else:
        print("Enhanced API: Failed")

if __name__ == "__main__":
    main()