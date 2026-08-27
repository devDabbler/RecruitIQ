#!/usr/bin/env python3
"""
Test script to verify that the enhanced matching fix works correctly.
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from backend.services.experience_analysis_service import ExperienceAnalysisService
from backend.services.rag_service import RAGService
from backend.services.llm_service import get_llm_service
from backend.services.graph_service import GraphService
from backend.utils.config import Settings

async def test_enhanced_matching():
    """Test the enhanced matching functionality."""
    try:
        print("Testing enhanced matching fix...")
        
        # Get database session
        db = next(get_db())
        
        # Initialize services properly using factory functions
        llm_service = get_llm_service()
        graph_service = GraphService()
        settings = Settings()
        rag_service = RAGService(llm_service, graph_service, settings)
        experience_service = ExperienceAnalysisService()
        enhanced_integrator = EnhancedMatchingIntegrator(rag_service, experience_service)
        
        print("✓ Services initialized successfully")
        
        # Test with a sample candidate and job
        # Get first candidate and job from database
        from backend.models.models import Candidate, Job
        
        candidate = db.query(Candidate).first()
        job = db.query(Job).first()
        
        if not candidate or not job:
            print("⚠ No candidates or jobs found in database")
            return
        
        print(f"✓ Testing with candidate: {candidate.first_name} {candidate.last_name}")
        print(f"✓ Testing with job: {job.title}")
        
        # Test the enhanced match
        try:
            result = await enhanced_integrator.get_enhanced_match(candidate.id, job.id, db)
            print("✓ Enhanced match calculation successful!")
            print(f"  Overall score: {result.get('overall_score', 0):.1f}%")
            print(f"  Base match score: {result.get('base_match_score', 0):.1f}%")
            print(f"  Experience bonus: {result.get('experience_bonus', 0):.1f}%")
            print(f"  Achievement bonus: {result.get('achievement_bonus', 0):.1f}%")
            print(f"  Technology bonus: {result.get('technology_bonus', 0):.1f}%")
            print(f"  Leadership bonus: {result.get('leadership_bonus', 0):.1f}%")
            
            # Check if reasoning is present
            reasoning = result.get('reasoning', '')
            if reasoning:
                print(f"  Reasoning: {reasoning[:100]}...")
            
        except Exception as e:
            print(f"✗ Error in enhanced match calculation: {e}")
            return
        
        # Test candidate matching for job
        try:
            matches = await enhanced_integrator.experience_enhanced_candidate_matching(job.id, db, min_score=10.0, limit=5)
            print(f"✓ Found {len(matches)} candidates matching job {job.title}")
            
            for i, match in enumerate(matches[:3]):  # Show first 3 matches
                print(f"  {i+1}. {match.get('name', 'Unknown')} - Score: {match.get('enhanced_match_score', 0):.1f}%")
                
        except Exception as e:
            print(f"✗ Error in candidate matching: {e}")
            return
        
        print("\n🎉 All tests passed! The enhanced matching fix is working correctly.")
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_matching()) 