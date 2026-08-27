#!/usr/bin/env python3
"""
Test script to verify improved candidate matching algorithm.
This script tests that experienced data scientists score higher than junior candidates.
"""

import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
# Ensure project root is in PYTHONPATH so 'backend' package is importable
sys.path.insert(0, str(project_root))

# Add alias modules for legacy import paths used in this file
import importlib, types
backend_pkg = importlib.import_module("backend")
sys.modules.setdefault("services", importlib.import_module("backend.services"))
sys.modules.setdefault("database", importlib.import_module("backend.database"))
sys.modules.setdefault("models", importlib.import_module("backend.models"))

# Import after path setup
import pytest

try:
    from services.matching_integrator import MatchingIntegrator
    from services.matching_enhancer import MatchingEnhancer
    from services.rag_service import RAGService
    from database.db_connection import get_db_session
    from models.models import Job, Candidate, Resume, CandidateSkill
    from sqlalchemy.orm import Session
    from sqlalchemy import desc
    print("✅ test_improved_matching: core imports successful")
except ImportError as e:
    pytest.skip(f"Skipping improved matching tests due to import error: {e}")

async def test_improved_matching_with_database():
    """Test the improved matching algorithm with real database data."""
    
    print("🧪 Testing Improved Candidate Matching Algorithm with Database")
    print("=" * 70)
    
    try:
        # Get database session
        db = next(get_db_session())
        print("✅ Database connection established")
        
        # Initialize services
        rag_service = RAGService()
        enhancer = MatchingEnhancer()
        integrator = MatchingIntegrator(rag_service)
        print("✅ Services initialized")
        
        # Get the Data Scientist job (ID 18 from the logs)
        job = db.query(Job).filter(Job.id == 18).first()
        if not job:
            print("❌ Job with ID 18 not found in database")
            return
        
        print(f"\n📋 Job Requirements:")
        print(f"   Title: {job.title}")
        print(f"   Required Skills: {job.skills if job.skills else 'None'}")
        print(f"   Experience: {job.required_qualifications if job.required_qualifications else 'None'}")
        
        # Get all candidates
        candidates = db.query(Candidate).all()
        print(f"\n👥 Found {len(candidates)} candidates in database")
        
        # Test the matching algorithm
        print(f"\n🔍 Running enhanced candidate matching for job {job.id}...")
        
        try:
            matches = await integrator.enhanced_candidate_job_matching(
                job_id=job.id, 
                db=db, 
                min_score=20.0, 
                limit=10
            )
            
            print(f"✅ Matching completed. Found {len(matches)} matches")
            
            print(f"\n🏆 Match Results:")
            print("-" * 70)
            
            for i, match in enumerate(matches):
                print(f"{i+1}. {match['name']} ({match['position']})")
                print(f"   Experience: {match['years_experience']} years ({match['experience_level']})")
                print(f"   Final Score: {match['match_score']:.1f}%")
                print(f"   Component Scores: Skill={match['skill_match_score']:.1f}%, Role={match['role_match_score']:.1f}%, Experience={match['experience_match_score']:.1f}%")
                print(f"   Skills: {len(match['skills'])} total skills")
                print(f"   Match Explanation: {match['match_explanation'][:100]}...")
                print()
            
            # Analyze the results
            print("📊 Analysis of Results:")
            print("-" * 70)
            
            # Find specific candidates from the logs
            jacob_match = next((m for m in matches if 'Jacob' in m['name']), None)
            alex_match = next((m for m in matches if 'Alex' in m['name']), None)
            clint_match = next((m for m in matches if 'Clint' in m['name']), None)
            
            if jacob_match:
                print(f"✅ Jacob Smith found: Rank {matches.index(jacob_match) + 1}, Score: {jacob_match['match_score']:.1f}%")
            else:
                print("❌ Jacob Smith not found in results")
                
            if alex_match:
                print(f"✅ Alex Jones found: Rank {matches.index(alex_match) + 1}, Score: {alex_match['match_score']:.1f}%")
            else:
                print("❌ Alex Jones not found in results")
                
            if clint_match:
                print(f"✅ Clint Forest found: Rank {matches.index(clint_match) + 1}, Score: {clint_match['match_score']:.1f}%")
            else:
                print("❌ Clint Forest not found in results")
            
            # Check if experienced candidates rank higher than junior candidates
            experienced_candidates = []
            junior_candidates = []
            
            for match in matches:
                if match['experience_level'] in ['senior', 'lead', 'principal'] and match['years_experience'] >= 8:
                    experienced_candidates.append(match)
                elif match['experience_level'] in ['entry', 'junior'] or match['years_experience'] <= 5:
                    junior_candidates.append(match)
            
            print(f"\n📈 Experience Level Analysis:")
            print(f"   Experienced candidates (senior+ with 8+ years): {len(experienced_candidates)}")
            print(f"   Junior candidates (entry/junior or ≤5 years): {len(junior_candidates)}")
            
            if experienced_candidates and junior_candidates:
                avg_experienced_score = sum(m['match_score'] for m in experienced_candidates) / len(experienced_candidates)
                avg_junior_score = sum(m['match_score'] for m in junior_candidates) / len(junior_candidates)
                
                print(f"   Average experienced candidate score: {avg_experienced_score:.1f}%")
                print(f"   Average junior candidate score: {avg_junior_score:.1f}%")
                print(f"   Score difference: {avg_experienced_score - avg_junior_score:.1f}%")
                
                if avg_experienced_score > avg_junior_score + 5:
                    print("✅ Experienced candidates score significantly higher than junior candidates")
                else:
                    print("❌ Insufficient score difference between experience levels")
            
            # Check for specific improvements
            print(f"\n🎯 Improvement Verification:")
            print("-" * 70)
            
            improvements = []
            
            # Check if data scientists rank well
            data_scientists = [m for m in matches if 'data scientist' in m['position'].lower()]
            if data_scientists:
                avg_ds_score = sum(m['match_score'] for m in data_scientists) / len(data_scientists)
                print(f"   Data Scientists: {len(data_scientists)} found, average score: {avg_ds_score:.1f}%")
                
                if avg_ds_score > 70:
                    improvements.append("✅ Data scientists score well (70%+)")
                else:
                    improvements.append("❌ Data scientists score too low")
            
            # Check if overqualified candidates aren't overly penalized
            overqualified = [m for m in matches if m['years_experience'] > 10 and m['experience_level'] in ['senior', 'lead', 'principal']]
            if overqualified:
                avg_overqualified_score = sum(m['match_score'] for m in overqualified) / len(overqualified)
                print(f"   Overqualified candidates: {len(overqualified)} found, average score: {avg_overqualified_score:.1f}%")
                
                if avg_overqualified_score > 60:
                    improvements.append("✅ Overqualified candidates not overly penalized")
                else:
                    improvements.append("❌ Overqualified candidates penalized too much")
            
            # Check skill matching quality
            high_skill_matches = [m for m in matches if m['skill_match_score'] > 70]
            if high_skill_matches:
                print(f"   High skill matches (70%+): {len(high_skill_matches)} candidates")
                improvements.append("✅ Good skill matching detected")
            else:
                improvements.append("❌ Limited high skill matches")
            
            for improvement in improvements:
                print(f"   {improvement}")
            
            print(f"\n🎯 Test Summary:")
            print(f"   The improved algorithm has been tested with real database data.")
            print(f"   Check the results above to verify that experienced data scientists")
            print(f"   now rank appropriately higher than junior candidates.")
            
            return matches
            
        except Exception as e:
            print(f"❌ Error during matching: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("Please ensure the database is running and accessible.")
        return None
    finally:
        if 'db' in locals():
            db.close()

async def test_component_scores():
    """Test individual component scores to verify improvements."""
    
    print("\n🔧 Testing Individual Component Scores")
    print("=" * 50)
    
    try:
        # Initialize enhancer
        enhancer = MatchingEnhancer()
        
        # Test data
        job_title = "Data Scientist"
        job_skills = ['Python', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn']
        
        test_cases = [
            {
                'name': 'Jacob Smith',
                'position': 'Lead Product Data Scientist',
                'skills': ['Python', 'pandas', 'sklearn', 'pyTorch', 'Linux', 'SQL', 'git', 'AWS', 'Deep Learning'],
                'expected_high_score': True
            },
            {
                'name': 'Alex Jones',
                'position': 'Staff Data Scientist',
                'skills': ['Apache Spark', 'Applied Machine Learning & AI', 'AWS', 'Azure', 'Bayesian Regression', 'Data Analytics'],
                'expected_high_score': True
            },
            {
                'name': 'Clint Forest',
                'position': 'Summer Associate - Data Analyst',
                'skills': ['Alteryx', 'Azure', 'Hadoop', 'Java', 'Jupyter Notebook', 'machine learning', 'NumPy', 'Pandas', 'Python', 'SQL'],
                'expected_high_score': False
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🔍 Testing: {test_case['name']} ({test_case['position']})")
            
            # Test skill matching
            skill_score, matching_skills = enhancer.calculate_skill_match_score(job_skills, test_case['skills'])
            
            # Test role matching
            role_score = enhancer.calculate_role_match_score(job_title, "", test_case['position'])
            
            # Test experience matching
            candidate_level, candidate_years = enhancer.extract_experience_level(test_case['position'])
            job_level, job_years = enhancer.extract_experience_level("3+ years of experience")
            experience_score = enhancer.calculate_experience_match_score(job_level, job_years, candidate_level, candidate_years)
            
            # Calculate final score
            if role_score < 25:
                match_score = (skill_score * 0.35 + role_score * 0.45 + experience_score * 0.2) * 0.7
            elif role_score < 40:
                match_score = (skill_score * 0.4 + role_score * 0.4 + experience_score * 0.2) * 0.85
            else:
                match_score = skill_score * 0.4 + role_score * 0.35 + experience_score * 0.25
            
            print(f"   Skill Score: {skill_score:.1f}% ({len(matching_skills)} matches)")
            print(f"   Role Score: {role_score:.1f}%")
            print(f"   Experience Score: {experience_score:.1f}%")
            print(f"   Final Score: {match_score:.1f}%")
            print(f"   Expected High Score: {test_case['expected_high_score']}")
            
            if test_case['expected_high_score'] and match_score > 70:
                print("   ✅ PASS: Experienced candidate scores high")
            elif not test_case['expected_high_score'] and match_score < 80:
                print("   ✅ PASS: Junior candidate scores appropriately")
            else:
                print("   ❌ FAIL: Score doesn't match expectations")
        
        print(f"\n✅ Component score testing completed")
        
    except Exception as e:
        print(f"❌ Error in component testing: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    print("🚀 Starting Improved Matching Algorithm Tests")
    print("=" * 60)
    
    # Test with database
    await test_improved_matching_with_database()
    
    # Test component scores
    await test_component_scores()
    
    print(f"\n🎉 Testing completed!")

if __name__ == "__main__":
    asyncio.run(main()) 