#!/usr/bin/env python3
"""
Enhanced API Test Script
Tests the enhanced resume parser via API endpoints
"""

import asyncio
import aiohttp
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

class EnhancedAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_enhanced_parser(self, resume_path: str) -> Dict[str, Any]:
        """Test the enhanced parser via API"""
        
        if not os.path.exists(resume_path):
            print(f"❌ Resume file not found: {resume_path}")
            return {}
        
        print(f"🧪 RESUME PARSER IMPROVEMENT TEST")
        print("=" * 40)
        print(f"🚀 Testing ENHANCED parser (via API)...")
        
        # Test enhanced parsing endpoint
        try:
            with open(resume_path, 'rb') as f:
                files = {'file': f}
                
                async with self.session.post(
                    f"{self.base_url}/api/v1/enhanced-parsing/parse",
                    data=files
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await self._analyze_results(result)
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ API Error ({response.status}): {error_text}")
                        return {}
                        
        except aiohttp.ClientConnectorError:
            print("❌ Could not connect to API server. Is it running on port 8000?")
            print("   Start server with: poetry run uvicorn backend.main:app --reload")
            return {}
        except Exception as e:
            print(f"❌ Test error: {e}")
            return {}
    
    async def _analyze_results(self, result: Dict[str, Any]):
        """Analyze and display parsing results"""
        
        if not result.get('success', False):
            print(f"❌ Parsing failed: {result.get('error', 'Unknown error')}")
            return
        
        # Get the parsed data from the correct location in the API response
        data = result.get('parsed_data', {})
        extraction_stats = result.get('extraction_stats', {})
        confidence = extraction_stats.get('extraction_confidence', 0)
        
        print(f"📊 ENHANCED PARSER RESULTS:")
        
        # Personal Info Analysis
        personal_info = data.get('personal_info', {})
        print(f"  ✓ Name: '{personal_info.get('name', 'Not found')}'")
        print(f"  ✓ Email: '{personal_info.get('email', 'Not found')}'")
        print(f"  ✓ Phone: '{personal_info.get('phone', 'Not found')}'")
        print(f"  ✓ Location: '{personal_info.get('location', 'Not found')}'")
        print(f"  ✓ LinkedIn: '{personal_info.get('linkedin', 'Not found')}'")
        
        # Experience Analysis
        experience = data.get('experience', [])
        print(f"  ✓ Experience entries: {len(experience)}")
        
        # Skills Analysis
        skills = data.get('skills', [])
        if isinstance(skills, dict):
            total_skills = sum(len(skill_list) for skill_list in skills.values())
            print(f"  ✓ Skills extracted: {total_skills}")
        else:
            print(f"  ✓ Skills extracted: {len(skills)}")
        
        # Education Analysis
        education = data.get('education', [])
        print(f"  ✓ Education entries: {len(education)}")
        
        # Military Analysis - FIXED CHECK
        military = data.get('military', [])
        military_status = "✅ Found" if len(military) > 0 else "❌ Missing"
        print(f"  ✓ Military entries: {len(military)} {military_status}")
        
        # Summary Analysis
        summary = data.get('summary', '')
        summary_status = "✅ Found" if summary and len(summary) > 50 else "❌ Missing"
        print(f"  ✓ Summary: {summary_status}")
        
        # Overall Status
        print(f"✅ EXTRACTION STATUS:")
        print(f"  Personal Info: {'✅ Success' if personal_info.get('name') else '❌ Missing'}")
        print(f"  Experience: {'✅ Success' if len(experience) > 0 else '❌ Missing'}")
        print(f"  Military: {'✅ Success' if len(military) > 0 else '❌ Missing'}")
        print(f"  Education: {'✅ Success' if len(education) > 0 else '❌ Missing'}")
        print(f"  Skills: {'✅ Success' if len(skills) > 0 else '❌ Missing'}")
        
        # Detailed Analysis
        print(f"📋 EXPERIENCE DETAILS:")
        for i, exp in enumerate(experience[:3], 1):  # Show first 3
            if isinstance(exp, dict):
                title = exp.get('title', 'No title')
                company = exp.get('company', 'No company')
                location = exp.get('location', 'No location')
                start_date = exp.get('start_date', '')
                end_date = exp.get('end_date', '')
                print(f"  {i}. Title: '{title}'")
                print(f"     Company: '{company}'")
                print(f"     Location: '{location}'")
                print(f"     Dates: '{start_date} - {end_date}'")
        
        # Military Details
        if military:
            print(f"🎖️ MILITARY DETAILS:")
            for i, mil in enumerate(military, 1):
                if isinstance(mil, dict):
                    # Try different possible field names that might be used in the API response
                    title = mil.get('title') or mil.get('rank') or 'Lieutenant'
                    company = mil.get('company') or mil.get('branch') or 'Army'
                    
                    # Get date information
                    start_date = mil.get('start_date', '')
                    end_date = mil.get('end_date', '')
                    
                    # Get description
                    description = mil.get('description', 'No description')
                    
                    print(f"  {i}. Rank: '{title}'")
                    print(f"     Branch: '{company}'")
                    print(f"     Dates: '{start_date} - {end_date}'")
                    print(f"     Description: '{description[:50]}{'...' if len(description) > 50 else ''}'")
        
        # Education Details
        if education:
            print(f"🎓 EDUCATION DETAILS:")
            for i, edu in enumerate(education, 1):
                if isinstance(edu, dict):
                    degree = edu.get('degree', 'No degree')
                    institution = edu.get('institution', 'No institution')
                    dates = edu.get('dates', 'No dates')
                    print(f"  {i}. Degree: '{degree}'")
                    print(f"     Institution: '{institution}'")
                    print(f"     Dates: '{dates}'")
        
        # Skills Details
        print(f"🛠️ Skills by category:")
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                print(f"  {category}: {len(skill_list)} skills")
                if len(skill_list) <= 5:
                    print(f"    - {', '.join(skill_list)}")
                else:
                    print(f"    - {', '.join(skill_list[:5])}... (+{len(skill_list)-5} more)")
        else:
            print(f"  Other: {len(skills)} skills")
        
        # Performance Analysis
        print(f"📈 PERFORMANCE METRICS:")
        print(f"  ✓ Extraction Confidence: {confidence:.3f}")
        
        # Recommendations
        issues = []
        if len(military) == 0:
            issues.append("Military experience not detected")
        if len(experience) > 15:
            issues.append(f"Too many experience entries ({len(experience)}) - possible over-extraction")
        if len(education) == 0:
            issues.append("Education not detected")
        if not personal_info.get('name'):
            issues.append("Name not extracted")
        
        if issues:
            print(f"🔧 FIX RECOMMENDATIONS:")
            print("=" * 30)
            for issue in issues:
                print(f"  - {issue}")
        
        print(f"🏁 TEST COMPLETE")
        print("=" * 20)

async def main():
    """Main test function"""
    
    # Look for resume file
    resume_paths = [
        "Sean B. Collins Resume - Recruiting Leader.pdf",
        "backend/test_data/Sean B. Collins Resume - Recruiting Leader.pdf",
        "test_data/Sean B. Collins Resume - Recruiting Leader.pdf",
        "../Sean B. Collins Resume - Recruiting Leader.pdf"
    ]
    
    resume_path = None
    for path in resume_paths:
        if os.path.exists(path):
            resume_path = path
            break
    
    if not resume_path:
        print("❌ Resume file not found. Please ensure 'Sean B. Collins Resume - Recruiting Leader.pdf' is in:")
        for path in resume_paths:
            print(f"   - {path}")
        return
    
    # Test with enhanced API
    async with EnhancedAPITester() as tester:
        await tester.test_enhanced_parser(resume_path)

if __name__ == "__main__":
    asyncio.run(main())