#!/usr/bin/env python3
"""
Production test for enhanced matching - tests the actual API endpoint
"""

import asyncio
import logging
import requests
import json
from sqlalchemy import text
from utils.database import get_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_matching_production():
    """Test the enhanced matching through the actual API endpoint"""
    print("🚀 Testing Enhanced Matching in Production")
    print("=" * 50)
    
    # Get database connection
    db = next(get_db())
    
    try:
        # Get a job to test with
        job_result = db.execute(text("SELECT id, title FROM jobs LIMIT 1")).fetchone()
        if not job_result:
            print("❌ No jobs found in database")
            return
        
        job_id = job_result[0]
        job_title = job_result[1]
        print(f"🎯 Testing with job: {job_title} (ID: {job_id})")
        
        # Get all candidates
        candidates_result = db.execute(text("SELECT id, first_name, last_name FROM candidates")).fetchall()
        candidates = candidates_result
        
        print(f"📋 Testing {len(candidates)} candidates")
        
        # Test the enhanced matching API endpoint
        api_url = "http://localhost:8000/api/enhanced-matching/match-candidates"
        
        # Prepare the request payload
        payload = {
            "job_ids": [job_id],
            "min_score": 25.0,
            "limit": 10
        }
        
        print(f"\n🌐 Calling API endpoint: {api_url}")
        print(f"📤 Request payload: {json.dumps(payload, indent=2)}")
        
        # Make the API call
        try:
            response = requests.post(api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API call successful!")
                print(f"📊 Response: {json.dumps(result, indent=2)}")
                
                # Analyze the results
                candidates_data = result.get("candidates", [])
                print(f"\n📈 Enhanced Matching Results:")
                print(f"   Total candidates returned: {len(candidates_data)}")
                
                for i, candidate in enumerate(candidates_data, 1):
                    candidate_name = candidate.get("name", "Unknown")
                    match_score = candidate.get("match_score", 0)
                    skill_match = candidate.get("skill_match_score", 0)
                    role_match = candidate.get("role_match_score", 0)
                    experience_match = candidate.get("experience_match_score", 0)
                    reasoning = candidate.get("reasoning", "")
                    
                    print(f"\n   {i}. {candidate_name}")
                    print(f"      📊 Overall Score: {match_score:.1f}%")
                    print(f"      🎯 Skill Match: {skill_match:.1f}%")
                    print(f"      👔 Role Match: {role_match:.1f}%")
                    print(f"      📈 Experience Match: {experience_match:.1f}%")
                    
                    # Check if reasoning contains experience data
                    if "Experience Profile" in reasoning:
                        print(f"      ✅ Experience data found in reasoning")
                    else:
                        print(f"      ⚠️  No experience data in reasoning")
                    
                    # Extract experience profile info from reasoning
                    if "Experience Profile" in reasoning:
                        # Look for experience count
                        if "0 positions" in reasoning:
                            print(f"      ❌ Experience count showing 0")
                        else:
                            print(f"      ✅ Experience count > 0")
                        
                        # Look for achievements
                        if "0 quantifiable achievements" in reasoning:
                            print(f"      ❌ Achievements showing 0")
                        else:
                            print(f"      ✅ Achievements > 0")
                
                # Check if scores are reasonable
                if candidates_data:
                    max_score = max(c.get("match_score", 0) for c in candidates_data)
                    min_score = min(c.get("match_score", 0) for c in candidates_data)
                    avg_score = sum(c.get("match_score", 0) for c in candidates_data) / len(candidates_data)
                    
                    print(f"\n📊 Score Analysis:")
                    print(f"   Highest Score: {max_score:.1f}%")
                    print(f"   Lowest Score: {min_score:.1f}%")
                    print(f"   Average Score: {avg_score:.1f}%")
                    
                    if avg_score > 40:
                        print(f"   ✅ Scores are reasonable (average > 40%)")
                    else:
                        print(f"   ⚠️  Scores seem low (average < 40%)")
                
            else:
                print(f"❌ API call failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ API call failed: {e}")
            print("Make sure the backend server is running on http://localhost:8000")
        
        # Also test individual candidate analysis
        print(f"\n🔍 Testing Individual Candidate Analysis")
        print("-" * 40)
        
        for candidate in candidates:
            candidate_id = candidate[0]
            candidate_name = f"{candidate[1]} {candidate[2]}"
            
            print(f"\n👤 Testing candidate: {candidate_name}")
            
            # Check database directly
            analysis_result = db.execute(
                text("SELECT * FROM candidate_experience_analysis WHERE candidate_id = :candidate_id"),
                {"candidate_id": candidate_id}
            ).fetchone()
            
            if analysis_result:
                print(f"   ✅ Found analysis in database")
                
                # Parse the data
                analysis = dict(analysis_result._mapping)
                
                for field in ['achievements', 'technologies', 'leadership_indicators', 'semantic_themes']:
                    if analysis.get(field):
                        if isinstance(analysis[field], str):
                            analysis[field] = json.loads(analysis[field])
                
                achievements = analysis.get("achievements", [])
                technologies = analysis.get("technologies", {})
                complexity_score = analysis.get("complexity_score", 0)
                impact_score = analysis.get("impact_score", 0)
                
                print(f"   📊 Database Analysis:")
                print(f"      Achievements: {len(achievements)}")
                print(f"      Technologies: {len(technologies)}")
                print(f"      Complexity: {complexity_score}")
                print(f"      Impact: {impact_score}")
                
                if len(achievements) > 0:
                    print(f"      ✅ Achievements found")
                else:
                    print(f"      ❌ No achievements")
                
                if len(technologies) > 0:
                    print(f"      ✅ Technologies found")
                else:
                    print(f"      ❌ No technologies")
                
            else:
                print(f"   ❌ No analysis found in database")
        
        print("\n" + "=" * 50)
        print("🎉 Production test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_enhanced_matching_production() 