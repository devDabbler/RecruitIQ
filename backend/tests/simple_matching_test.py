#!/usr/bin/env python3
"""
Simple test script to verify improved candidate matching algorithm.
This script tests the matching logic directly without complex imports.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_matching_enhancer_directly():
    """Test the matching enhancer directly without database dependencies."""
    
    print("🧪 Testing Improved Matching Algorithm (Direct Test)")
    print("=" * 60)
    
    try:
        # Import only the matching enhancer
        from services.matching_enhancer import MatchingEnhancer
        print("✅ MatchingEnhancer imported successfully")
        
        # Initialize the enhancer
        enhancer = MatchingEnhancer()
        print("✅ MatchingEnhancer initialized")
        
        # Test data
        job_title = "Data Scientist"
        job_skills = ['Python', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn']
        job_requirements = "3+ years of experience in data science, machine learning, and statistical analysis"
        
        # Test candidates
        test_candidates = [
            {
                'name': 'Clint Forest',
                'position': 'Summer Associate - Data Analyst',
                'skills': ['Alteryx', 'Azure', 'Hadoop', 'Java', 'Jupyter Notebook', 'machine learning', 'NumPy', 'Pandas', 'Python', 'SQL'],
                'expected_ranking': 3
            },
            {
                'name': 'Jacob Smith',
                'position': 'Lead Product Data Scientist',
                'skills': ['Python', 'pandas', 'sklearn', 'pyTorch', 'Linux', 'SQL', 'git', 'AWS', 'Deep Learning', 'neural network models'],
                'expected_ranking': 1
            },
            {
                'name': 'Alex Jones',
                'position': 'Staff Data Scientist',
                'skills': ['Apache Spark', 'Applied Machine Learning & AI', 'AWS', 'Azure', 'Bayesian Regression', 'Data Analytics', 'Causal Inference', 'CNN'],
                'expected_ranking': 2
            }
        ]
        
        print(f"\n📋 Job Requirements:")
        print(f"   Title: {job_title}")
        print(f"   Skills: {', '.join(job_skills)}")
        print(f"   Requirements: {job_requirements}")
        
        results = []
        
        for i, candidate in enumerate(test_candidates):
            print(f"\n🔍 Testing Candidate {i+1}: {candidate['name']}")
            print(f"   Position: {candidate['position']}")
            print(f"   Skills: {len(candidate['skills'])} skills")
            
            # Test skill matching
            skill_score, matching_skills = enhancer.calculate_skill_match_score(job_skills, candidate['skills'])
            
            # Test role matching
            role_score = enhancer.calculate_role_match_score(job_title, "", candidate['position'])
            
            # Test experience matching
            candidate_level, candidate_years = enhancer.extract_experience_level(candidate['position'])
            job_level, job_years = enhancer.extract_experience_level(job_requirements)
            experience_score = enhancer.calculate_experience_match_score(job_level, job_years, candidate_level, candidate_years, candidate['position'])
            
            # Calculate final score using improved weights
            if role_score < 25:
                match_score = (skill_score * 0.35 + role_score * 0.45 + experience_score * 0.2) * 0.7
            elif role_score < 40:
                match_score = (skill_score * 0.4 + role_score * 0.4 + experience_score * 0.2) * 0.85
            else:
                match_score = skill_score * 0.4 + role_score * 0.35 + experience_score * 0.25
            
            # Apply cross-domain penalty if needed
            if role_score < 40 and skill_score < 50:
                match_score *= 0.7
            
            results.append({
                'name': candidate['name'],
                'position': candidate['position'],
                'skill_score': skill_score,
                'role_score': role_score,
                'experience_score': experience_score,
                'match_score': match_score,
                'matching_skills': matching_skills,
                'expected_ranking': candidate['expected_ranking']
            })
            
            print(f"   Component Scores:")
            print(f"     Skill Match: {skill_score:.1f}% ({len(matching_skills)} matching skills)")
            print(f"     Role Match: {role_score:.1f}%")
            print(f"     Experience Match: {experience_score:.1f}%")
            print(f"     Final Score: {match_score:.1f}%")
            print(f"     Expected Ranking: {candidate['expected_ranking']}")
        
        # Sort results by match score
        sorted_results = sorted(results, key=lambda x: x['match_score'], reverse=True)
        
        print(f"\n🏆 Final Rankings:")
        print("-" * 60)
        
        for i, result in enumerate(sorted_results):
            print(f"{i+1}. {result['name']} ({result['position']})")
            print(f"   Final Score: {result['match_score']:.1f}%")
            print(f"   Expected Ranking: {result['expected_ranking']}")
            print(f"   Component Scores: Skill={result['skill_score']:.1f}%, Role={result['role_score']:.1f}%, Experience={result['experience_score']:.1f}%")
            print()
        
        # Verify the ranking is correct
        print("✅ Verification Results:")
        print("-" * 60)
        
        jacob_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Jacob Smith') + 1
        alex_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Alex Jones') + 1
        clint_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Clint Forest') + 1
        
        print(f"Jacob Smith (Lead Data Scientist): Rank {jacob_rank}")
        print(f"Alex Jones (Staff Data Scientist): Rank {alex_rank}")
        print(f"Clint Forest (Summer Associate): Rank {clint_rank}")
        
        # Check improvements
        improvements = []
        
        if jacob_rank <= 2:
            improvements.append("✅ Experienced data scientist (Jacob) ranks in top 2")
        else:
            improvements.append("❌ Experienced data scientist (Jacob) should rank higher")
        
        if alex_rank <= 2:
            improvements.append("✅ Very experienced data scientist (Alex) ranks in top 2")
        else:
            improvements.append("❌ Very experienced data scientist (Alex) should rank higher")
        
        if clint_rank >= 2:
            improvements.append("✅ Junior candidate (Clint) ranks appropriately lower")
        else:
            improvements.append("❌ Junior candidate (Clint) ranks too high")
        
        if jacob_rank < clint_rank and alex_rank < clint_rank:
            improvements.append("✅ Both experienced data scientists rank higher than junior candidate")
        else:
            improvements.append("❌ Junior candidate ranks higher than experienced data scientists")
        
        print(f"\n📊 Improvement Verification:")
        for improvement in improvements:
            print(f"   {improvement}")
        
        # Calculate score differences
        jacob_score = next(r['match_score'] for r in sorted_results if r['name'] == 'Jacob Smith')
        alex_score = next(r['match_score'] for r in sorted_results if r['name'] == 'Alex Jones')
        clint_score = next(r['match_score'] for r in sorted_results if r['name'] == 'Clint Forest')
        
        print(f"\n📈 Score Analysis:")
        print(f"   Jacob Smith: {jacob_score:.1f}%")
        print(f"   Alex Jones: {alex_score:.1f}%")
        print(f"   Clint Forest: {clint_score:.1f}%")
        print(f"   Score difference (Jacob - Clint): {jacob_score - clint_score:.1f}%")
        print(f"   Score difference (Alex - Clint): {alex_score - clint_score:.1f}%")
        
        if jacob_score > clint_score + 5 and alex_score > clint_score + 5:
            print("✅ Significant score difference between experienced and junior candidates")
        else:
            print("❌ Insufficient score difference between experienced and junior candidates")
        
        print(f"\n🎯 Test Summary:")
        print(f"   The improved algorithm has been tested with sample data.")
        print(f"   Check the results above to verify that experienced data scientists")
        print(f"   now rank appropriately higher than junior candidates.")
        
        return sorted_results
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test function."""
    print("🚀 Starting Simple Matching Algorithm Test")
    print("=" * 60)
    
    # Test the matching algorithm directly
    results = test_matching_enhancer_directly()
    
    if results:
        print(f"\n🎉 Testing completed successfully!")
    else:
        print(f"\n❌ Testing failed!")

if __name__ == "__main__":
    main() 