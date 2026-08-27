#!/usr/bin/env python3
"""
Test script to verify enhanced candidate matching is working properly.
"""

import asyncio
import logging
from backend.utils.database import SessionLocal
from backend.services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from backend.services.rag_service import RAGService
from backend.services.experience_analysis_service import ExperienceAnalysisService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_matching():
    """Test the enhanced candidate matching functionality."""
    try:
        logger.info("🧪 Testing enhanced candidate matching...")
        
        # Initialize services
        db = SessionLocal()
        rag_service = RAGService()
        experience_service = ExperienceAnalysisService()
        integrator = EnhancedMatchingIntegrator(rag_service, experience_service)
        
        # Test with job ID 1 (assuming it exists)
        job_id = 1
        
        logger.info(f"Testing enhanced matching for job ID: {job_id}")
        
        # Get enhanced matching results
        results = await integrator.experience_enhanced_candidate_matching(
            job_id, db, min_score=20.0, limit=10
        )
        
        logger.info(f"📊 Enhanced matching results: {len(results)} candidates found")
        
        if results:
            logger.info("🏆 Top 5 candidates:")
            for i, result in enumerate(results[:5], 1):
                name = result.get("name", "Unknown")
                score = result.get("enhanced_match_score", 0)
                position = result.get("position", "Unknown")
                
                logger.info(f"  {i}. {name} ({position}): {score:.1f}%")
                
                # Show experience analysis if available
                experience_analysis = result.get("experience_analysis", {})
                if experience_analysis:
                    experience_count = experience_analysis.get("experience_count", 0)
                    total_achievements = experience_analysis.get("total_achievements", 0)
                    avg_complexity = experience_analysis.get("average_complexity", 0)
                    
                    logger.info(f"     Experience: {experience_count} positions, {total_achievements} achievements, complexity {avg_complexity:.1f}/10")
                
                # Show match details if available
                match_details = result.get("match_details", {})
                if match_details:
                    base_score = match_details.get("base_score", 0)
                    experience_score = match_details.get("experience_score", 0)
                    achievement_score = match_details.get("achievement_score", 0)
                    
                    logger.info(f"     Scores: Base={base_score:.1f}%, Experience={experience_score:.1f}%, Achievement={achievement_score:.1f}%")
                
                logger.info("")
        else:
            logger.warning("⚠️  No candidates found with enhanced matching")
        
        # Test individual candidate matching
        if results:
            first_candidate = results[0]
            candidate_id = first_candidate.get("id")
            
            logger.info(f"🔍 Testing individual enhanced match for candidate: {first_candidate.get('name')}")
            
            individual_result = await integrator.get_enhanced_match(candidate_id, job_id, db)
            
            if individual_result:
                overall_score = individual_result.get("overall_score", 0)
                base_score = individual_result.get("base_match_score", 0)
                experience_bonus = individual_result.get("experience_bonus", 0)
                achievement_bonus = individual_result.get("achievement_bonus", 0)
                reasoning = individual_result.get("reasoning", "")
                
                logger.info(f"📈 Individual match results:")
                logger.info(f"   Overall score: {overall_score:.1f}%")
                logger.info(f"   Base score: {base_score:.1f}%")
                logger.info(f"   Experience bonus: {experience_bonus:.1f}%")
                logger.info(f"   Achievement bonus: {achievement_bonus:.1f}%")
                
                # Show first part of reasoning
                if reasoning:
                    reasoning_preview = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning
                    logger.info(f"   Reasoning preview: {reasoning_preview}")
            else:
                logger.warning("⚠️  Failed to get individual enhanced match")
        
        # Check experience data coverage
        logger.info("📊 Experience data coverage check:")
        result = db.execute("""
            SELECT 
                COUNT(*) as total_candidates,
                COUNT(CASE WHEN ce.candidate_id IS NOT NULL THEN 1 END) as candidates_with_experience,
                COUNT(CASE WHEN ce.description LIKE '%Experience details not available%' THEN 1 END) as candidates_with_fallback
            FROM candidates c
            LEFT JOIN candidate_experience ce ON c.id = ce.candidate_id
        """)
        
        stats = result.fetchone()
        total_candidates = stats[0]
        candidates_with_experience = stats[1]
        candidates_with_fallback = stats[2]
        
        coverage = (candidates_with_experience / total_candidates * 100) if total_candidates > 0 else 0
        
        logger.info(f"   Total candidates: {total_candidates}")
        logger.info(f"   Candidates with experience data: {candidates_with_experience}")
        logger.info(f"   Candidates with fallback records: {candidates_with_fallback}")
        logger.info(f"   Coverage: {coverage:.1f}%")
        
        if coverage >= 90:
            logger.info("✅ Excellent! Experience data coverage is very high.")
        elif coverage >= 75:
            logger.info("✅ Good! Experience data coverage is good.")
        else:
            logger.warning("⚠️  Experience data coverage could be improved.")
        
        logger.info("🎉 Enhanced matching test completed!")
        
    except Exception as e:
        logger.error(f"❌ Error testing enhanced matching: {e}")
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_matching()) 