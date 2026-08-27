#!/usr/bin/env python3
"""
Test script to verify enhanced matching fix
"""

import asyncio
import logging
from sqlalchemy import text
from utils.database import get_db
from services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from services.experience_analysis_service import ExperienceAnalysisService
from services.rag_service import RAGService

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_enhanced_matching_fix():
    """Test the enhanced matching fix"""
    print("🧪 Testing Enhanced Matching Fix")
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
        
        # Initialize services using dependency injection
        from services.service_registry import provide_rag_service, provide_matching_service
        from services.matching_service import MatchingService
        
        # Get services from registry
        rag_service = provide_rag_service()
        matching_service = provide_matching_service()
        experience_service = ExperienceAnalysisService()
        
        enhanced_integrator = EnhancedMatchingIntegrator(
            rag_service=rag_service,
            experience_analysis_service=experience_service
        )
        
        # Get all candidates
        candidates_result = db.execute(text("SELECT id, first_name, last_name FROM candidates")).fetchall()
        candidates = candidates_result
        
        print(f"📋 Testing {len(candidates)} candidates")
        
        for candidate in candidates:
            candidate_id = candidate[0]
            candidate_name = f"{candidate[1]} {candidate[2]}"
            
            print(f"\n👤 Testing candidate: {candidate_name}")
            print("-" * 40)
            
            # Test enhanced match
            enhanced_match = await enhanced_integrator.get_enhanced_match(candidate_id, job_id, db)
            
            if "error" in enhanced_match:
                print(f"❌ Error: {enhanced_match['error']}")
                continue
            
            # Display results
            overall_score = enhanced_match.get("overall_score", 0)
            base_score = enhanced_match.get("base_match_score", 0)
            experience_bonus = enhanced_match.get("experience_bonus", 0)
            achievement_bonus = enhanced_match.get("achievement_bonus", 0)
            technology_bonus = enhanced_match.get("technology_bonus", 0)
            leadership_bonus = enhanced_match.get("leadership_bonus", 0)
            
            print(f"📊 Overall Score: {overall_score:.1f}%")
            print(f"   Base Match: {base_score:.1f}%")
            print(f"   Experience Bonus: {experience_bonus:.1f}%")
            print(f"   Achievement Bonus: {achievement_bonus:.1f}%")
            print(f"   Technology Bonus: {technology_bonus:.1f}%")
            print(f"   Leadership Bonus: {leadership_bonus:.1f}%")
            
            # Check if experience data is being used
            candidate_analysis = enhanced_match.get("candidate_analysis", {})
            if candidate_analysis:
                experience_count = candidate_analysis.get("experience_count", 0)
                total_achievements = candidate_analysis.get("total_achievements", 0)
                unique_technologies = candidate_analysis.get("unique_technologies", 0)
                average_complexity = candidate_analysis.get("average_complexity", 0)
                
                print(f"📈 Experience Data:")
                print(f"   Experience Count: {experience_count}")
                print(f"   Total Achievements: {total_achievements}")
                print(f"   Unique Technologies: {unique_technologies}")
                print(f"   Average Complexity: {average_complexity:.1f}")
                
                if experience_count > 0 and total_achievements > 0:
                    print("✅ Experience data is being used correctly!")
                else:
                    print("⚠️  Experience data may not be properly loaded")
            else:
                print("❌ No candidate analysis data found")
        
        print("\n" + "=" * 50)
        print("🎉 Enhanced matching test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_matching_fix()) 