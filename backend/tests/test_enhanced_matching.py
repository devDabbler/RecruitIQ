#!/usr/bin/env python3
"""
Test script to demonstrate enhanced matching capabilities with experience analysis.
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Any

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.services.experience_analysis_service import ExperienceAnalysisService
from backend.services.enhanced_matching_integrator import EnhancedMatchingIntegrator
from backend.services.rag_service import RAGService
from backend.models.models import Candidate, Job

async def test_experience_analysis():
    """Test experience analysis for candidates."""
    print("=== Testing Experience Analysis ===")
    
    db = next(get_db())
    experience_service = ExperienceAnalysisService()
    
    try:
        # Get all candidates
        candidates = db.query(Candidate).all()
        print(f"Found {len(candidates)} candidates to analyze")
        
        for candidate in candidates:
            print(f"\n--- Analyzing {candidate.first_name} {candidate.last_name} ---")
            
            # Analyze candidate experience
            analysis = await experience_service.analyze_candidate_experience(candidate.id, db)
            
            if "error" in analysis:
                print(f"  Error: {analysis['error']}")
                continue
            
            # Display key insights
            print(f"  Experience Count: {analysis.get('experience_count', 0)}")
            print(f"  Total Achievements: {analysis.get('total_achievements', 0)}")
            print(f"  Unique Technologies: {analysis.get('unique_technologies', 0)}")
            print(f"  Average Complexity: {analysis.get('average_complexity', 0):.1f}/10")
            
            # Show some achievements
            achievements = analysis.get('aggregated_achievements', [])
            if achievements:
                print(f"  Sample Achievements:")
                for i, achievement in enumerate(achievements[:3]):  # Show first 3
                    if isinstance(achievement, dict):
                        print(f"    {i+1}. {achievement.get('text', 'N/A')}")
                    else:
                        print(f"    {i+1}. {achievement}")
            
            # Show some technologies
            technologies = analysis.get('aggregated_technologies', {})
            if technologies:
                print(f"  Technologies Found: {', '.join(list(technologies.keys())[:5])}...")
            
            # Show complexity breakdown
            complexity_breakdown = analysis.get('complexity_breakdown', {})
            if complexity_breakdown:
                print(f"  Complexity Breakdown:")
                for category, score in complexity_breakdown.items():
                    print(f"    {category}: {score:.2f}")
    
    except Exception as e:
        print(f"Error in experience analysis test: {e}")
    finally:
        db.close()

async def test_job_analysis():
    """Test job requirements analysis."""
    print("\n=== Testing Job Requirements Analysis ===")
    
    db = next(get_db())
    experience_service = ExperienceAnalysisService()
    
    try:
        # Get all jobs
        jobs = db.query(Job).all()
        print(f"Found {len(jobs)} jobs to analyze")
        
        for job in jobs:
            print(f"\n--- Analyzing Job: {job.title} ---")
            
            # Analyze job requirements
            analysis = await experience_service.analyze_job_requirements(job.id, db)
            
            if "error" in analysis:
                print(f"  Error: {analysis['error']}")
                continue
            
            # Display key insights
            print(f"  Required Achievements: {len(analysis.get('required_achievements', []))}")
            print(f"  Required Technologies: {len(analysis.get('required_technologies', {}))}")
            print(f"  Complexity Requirements: {analysis.get('complexity_requirements', 0):.1f}/10")
            
            # Show industry context
            industry_context = analysis.get('industry_context', [])
            if industry_context:
                print(f"  Industry Context: {', '.join(industry_context)}")
            
            # Show some required technologies
            technologies = analysis.get('required_technologies', {})
            if technologies:
                print(f"  Required Technologies: {', '.join(list(technologies.keys())[:5])}...")
    
    except Exception as e:
        print(f"Error in job analysis test: {e}")
    finally:
        db.close()

async def test_enhanced_matching():
    """Test enhanced matching with experience analysis."""
    print("\n=== Testing Enhanced Matching ===")
    
    db = next(get_db())
    rag_service = RAGService()
    experience_service = ExperienceAnalysisService()
    enhanced_integrator = EnhancedMatchingIntegrator(rag_service, experience_service)
    
    try:
        # Get first job for testing
        job = db.query(Job).first()
        if not job:
            print("No jobs found for testing")
            return
        
        print(f"Testing enhanced matching for job: {job.title}")
        
        # Get enhanced matches
        matches = await enhanced_integrator.experience_enhanced_candidate_matching(
            job_id=job.id,
            db=db,
            min_score=20.0,
            limit=5
        )
        
        print(f"Found {len(matches)} enhanced matches")
        
        for i, match in enumerate(matches):
            print(f"\n--- Match {i+1}: {match['name']} ---")
            print(f"  Enhanced Score: {match.get('enhanced_match_score', 0):.1f}%")
            print(f"  Position: {match.get('position', 'N/A')}")
            
            # Show match details
            match_details = match.get('match_details', {})
            if match_details:
                score_breakdown = match_details.get('score_breakdown', {})
                print(f"  Score Breakdown:")
                for category, score in score_breakdown.items():
                    print(f"    {category}: {score}")
                
                # Show explanation
                explanation = match_details.get('explanation', '')
                if explanation:
                    print(f"  Explanation: {explanation[:200]}...")
    
    except Exception as e:
        print(f"Error in enhanced matching test: {e}")
    finally:
        db.close()

async def main():
    """Run all tests."""
    print("🚀 Enhanced Matching Demo")
    print("=" * 50)
    
    # Test experience analysis
    await test_experience_analysis()
    
    # Test job analysis
    await test_job_analysis()
    
    # Test enhanced matching
    await test_enhanced_matching()
    
    print("\n✅ Enhanced matching demo completed!")

if __name__ == "__main__":
    asyncio.run(main()) 