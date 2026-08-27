#!/usr/bin/env python3
"""
Debug script to test experience analysis service
"""

import asyncio
import logging
from sqlalchemy import text
from utils.database import get_db
from services.experience_analysis_service import ExperienceAnalysisService

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_experience_analysis():
    """Debug the experience analysis service"""
    print("🔍 Debugging Experience Analysis Service")
    print("=" * 50)
    
    # Get database connection
    db = next(get_db())
    
    try:
        # Get all candidates
        result = db.execute(text("SELECT id, first_name, last_name FROM candidates")).fetchall()
        candidates = result
        
        print(f"📋 Found {len(candidates)} candidates")
        
        # Initialize experience analysis service
        experience_service = ExperienceAnalysisService()
        
        for candidate in candidates:
            candidate_id = candidate[0]
            candidate_name = f"{candidate[1]} {candidate[2]}"
            
            print(f"\n🎯 Testing candidate: {candidate_name} ({candidate_id})")
            print("-" * 40)
            
            # Check experience records
            exp_result = db.execute(
                text("SELECT COUNT(*) FROM candidate_experience WHERE candidate_id = :candidate_id"),
                {"candidate_id": candidate_id}
            ).fetchone()
            
            exp_count = exp_result[0]
            print(f"📊 Experience records: {exp_count}")
            
            if exp_count > 0:
                # Get sample experience data
                exp_data = db.execute(
                    text("SELECT position, company, description FROM candidate_experience WHERE candidate_id = :candidate_id LIMIT 1"),
                    {"candidate_id": candidate_id}
                ).fetchone()
                
                if exp_data:
                    print(f"📝 Sample position: {exp_data[0]}")
                    print(f"🏢 Sample company: {exp_data[1]}")
                    print(f"📄 Description length: {len(exp_data[2]) if exp_data[2] else 0}")
                    
                    if exp_data[2]:
                        print(f"📄 Description preview: {exp_data[2][:100]}...")
                
                # Test experience analysis
                print("\n🔬 Running experience analysis...")
                analysis_result = await experience_service.analyze_candidate_experience(candidate_id, db)
                
                if "error" in analysis_result:
                    print(f"❌ Analysis error: {analysis_result['error']}")
                else:
                    print(f"✅ Analysis successful!")
                    print(f"   Experience count: {analysis_result.get('experience_count', 0)}")
                    print(f"   Total achievements: {analysis_result.get('total_achievements', 0)}")
                    print(f"   Unique technologies: {analysis_result.get('unique_technologies', 0)}")
                    print(f"   Average complexity: {analysis_result.get('average_complexity', 0)}")
                    
                    # Check if achievements were extracted
                    achievements = analysis_result.get('aggregated_achievements', [])
                    print(f"   Achievements found: {len(achievements)}")
                    if achievements:
                        print(f"   Sample achievement: {achievements[0]}")
                    
                    # Check if technologies were extracted
                    technologies = analysis_result.get('aggregated_technologies', {})
                    print(f"   Technologies found: {len(technologies)}")
                    if technologies:
                        tech_list = list(technologies.keys())[:3]
                        print(f"   Sample technologies: {tech_list}")
            else:
                print("⚠️  No experience records found")
        
        print("\n" + "=" * 50)
        print("🎉 Experience analysis debugging completed!")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_experience_analysis()) 