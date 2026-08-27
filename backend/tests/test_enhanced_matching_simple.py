#!/usr/bin/env python3
"""
Simple test script to verify enhanced matching fix
"""

import asyncio
import logging
from sqlalchemy import text
from utils.database import get_db
from services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from services.experience_analysis_service import ExperienceAnalysisService

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_enhanced_matching_simple():
    """Test the enhanced matching fix with minimal dependencies"""
    print("🧪 Testing Enhanced Matching Fix (Simple)")
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
        
        # Initialize services with minimal dependencies
        experience_service = ExperienceAnalysisService()
        
        # Create a mock RAG service for testing
        class MockRAGService:
            def __init__(self):
                pass
        
        enhanced_integrator = EnhancedMatchingIntegrator(
            rag_service=MockRAGService(),
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
            
            # Test the data retrieval directly
            print("🔍 Testing data retrieval...")
            
            # Check if analysis exists
            analysis_result = db.execute(
                text("SELECT * FROM candidate_experience_analysis WHERE candidate_id = :candidate_id"),
                {"candidate_id": candidate_id}
            ).fetchone()
            
            if analysis_result:
                print("✅ Found existing analysis in database")
                
                # Convert to dict and parse JSON fields
                analysis = dict(analysis_result._mapping)
                import json
                
                for field in ['achievements', 'technologies', 'leadership_indicators', 'semantic_themes']:
                    if analysis.get(field):
                        if isinstance(analysis[field], str):
                            analysis[field] = json.loads(analysis[field])
                
                # Display the data
                achievements = analysis.get("achievements", [])
                technologies = analysis.get("technologies", {})
                complexity_score = analysis.get("complexity_score", 0)
                impact_score = analysis.get("impact_score", 0)
                
                print(f"📊 Analysis Data:")
                print(f"   Achievements: {len(achievements)} found")
                print(f"   Technologies: {len(technologies)} found")
                print(f"   Complexity Score: {complexity_score}")
                print(f"   Impact Score: {impact_score}")
                
                if achievements:
                    print(f"   Sample achievement: {achievements[0]}")
                
                if technologies:
                    tech_list = list(technologies.keys())[:3]
                    print(f"   Sample technologies: {tech_list}")
                
                # Test the mapping function
                print("\n🔧 Testing data mapping...")
                mapped_analysis = await enhanced_integrator._get_or_create_candidate_analysis(candidate_id, db)
                
                print(f"📈 Mapped Analysis:")
                print(f"   Experience Count: {mapped_analysis.get('experience_count', 0)}")
                print(f"   Total Achievements: {mapped_analysis.get('total_achievements', 0)}")
                print(f"   Unique Technologies: {mapped_analysis.get('unique_technologies', 0)}")
                print(f"   Average Complexity: {mapped_analysis.get('average_complexity', 0)}")
                
                # Test individual scoring functions
                print("\n🎯 Testing scoring functions...")
                
                # Mock job analysis
                mock_job_analysis = {
                    "required_achievements": [],
                    "required_technologies": {},
                    "complexity_requirements": {"score": 5.0}
                }
                
                # Test experience scoring
                experience_score = await enhanced_integrator._calculate_experience_match_score(mapped_analysis, mock_job_analysis)
                print(f"   Experience Score: {experience_score:.1f}%")
                
                # Test achievement scoring
                achievement_score = await enhanced_integrator._calculate_achievement_match_score(mapped_analysis, mock_job_analysis)
                print(f"   Achievement Score: {achievement_score:.1f}%")
                
                # Test technology scoring
                technology_score = await enhanced_integrator._calculate_technology_proficiency_score(mapped_analysis, mock_job_analysis)
                print(f"   Technology Score: {technology_score:.1f}%")
                
                # Test complexity scoring
                complexity_score = await enhanced_integrator._calculate_complexity_alignment_score(mapped_analysis, mock_job_analysis)
                print(f"   Complexity Score: {complexity_score:.1f}%")
                
                print("✅ All scoring functions working correctly!")
                
            else:
                print("❌ No analysis found in database")
        
        print("\n" + "=" * 50)
        print("🎉 Enhanced matching test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_matching_simple()) 