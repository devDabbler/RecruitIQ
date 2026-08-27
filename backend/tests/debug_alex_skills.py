#!/usr/bin/env python3
"""
Debug script to test Alex Jones's skill matching specifically.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def debug_alex_skills():
    """Debug Alex Jones's skill matching specifically."""
    
    print("🔍 Debugging Alex Jones's Skill Matching")
    print("=" * 60)
    
    try:
        from services.matching_enhancer import MatchingEnhancer
        print("✅ MatchingEnhancer imported successfully")
        
        # Alex's actual skills
        alex_skills = [
            'Apache Spark', 
            'Applied Machine Learning & AI', 
            'AWS', 
            'Azure', 
            'Bayesian Regression', 
            'Data Analytics', 
            'Causal Inference', 
            'CNN'
        ]
        
        # Job requirements
        job_skills = ['Python', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn']
        
        print(f"\n📋 Alex's Skills: {alex_skills}")
        print(f"📋 Job Requirements: {job_skills}")
        
        # Initialize enhancer
        enhancer = MatchingEnhancer()
        
        # Test skill matching
        skill_score, matching_skills = enhancer.calculate_skill_match_score(job_skills, alex_skills)
        
        print(f"\n🎯 Skill Match Results:")
        print(f"   Score: {skill_score:.1f}%")
        print(f"   Matching Skills: {matching_skills}")
        
        # Debug each skill individually
        print(f"\n🔍 Individual Skill Analysis:")
        
        job_skills_norm = [s.lower().strip() for s in job_skills]
        alex_skills_norm = [s.lower().strip() for s in alex_skills]
        
        # Get skill synonyms from the enhancer's calculate_skill_match_score method
        # We'll need to extract them manually since they're not exposed as an attribute
        
        # Define the skill synonyms manually for debugging
        skill_synonyms = {
            'python': ['python', 'python3', 'python 3'],
            'machine learning': ['machine learning', 'ml', 'ai', 'artificial intelligence', 'deep learning', 'applied machine learning', 'applied machine learning & ai', 'applied ml', 'ml algorithms', 'predictive modeling'],
            'sql': ['sql', 'mysql', 'postgresql', 'pl/sql', 'tsql'],
            'statistics': ['statistics', 'statistical analysis', 'statistical modeling', 'bayesian regression', 'causal inference', 'regression analysis', 'statistical methods'],
            'pandas': ['pandas', 'pd'],
            'numpy': ['numpy', 'np'],
            'scikit-learn': ['scikit-learn', 'sklearn', 'scikit learn'],
            'neural networks': ['neural networks', 'neural net', 'deep learning', 'cnn', 'convolutional neural networks'],
            'data science': ['data science', 'data scientist', 'data analytics', 'data analysis'],
            'spark': ['spark', 'apache spark', 'pyspark'],
        }
        
        for job_skill in job_skills_norm:
            print(f"\n   Job Skill: '{job_skill}'")
            
            # Check exact matches
            if job_skill in alex_skills_norm:
                print(f"     ✅ EXACT MATCH: '{job_skill}'")
                continue
                
            # Check synonym matches
            found_synonym = False
            for alex_skill in alex_skills_norm:
                # Check if alex_skill is a synonym for job_skill
                for synonym_key, synonyms in skill_synonyms.items():
                    if job_skill in synonyms and alex_skill in synonyms:
                        print(f"     ✅ SYNONYM MATCH: '{alex_skill}' matches '{job_skill}' via '{synonym_key}'")
                        found_synonym = True
                        break
                if found_synonym:
                    break
                    
            if not found_synonym:
                print(f"     ❌ NO MATCH found for '{job_skill}'")
                
        # Test specific mappings
        print(f"\n🔍 Testing Specific Mappings:")
        
        # Test Alex's skills against job requirements
        test_mappings = [
            ('Applied Machine Learning & AI', 'Machine Learning'),
            ('Bayesian Regression', 'Statistics'),
            ('Data Analytics', 'Data Science'),
            ('CNN', 'Neural Networks'),
            ('Causal Inference', 'Statistics'),
            ('Apache Spark', 'Spark'),
        ]
        
        for alex_skill, expected_match in test_mappings:
            alex_skill_lower = alex_skill.lower()
            expected_match_lower = expected_match.lower()
            
            # Check if this mapping exists in synonyms
            found = False
            for synonym_key, synonyms in skill_synonyms.items():
                if expected_match_lower in synonyms and alex_skill_lower in synonyms:
                    print(f"   ✅ '{alex_skill}' → '{expected_match}' via '{synonym_key}'")
                    found = True
                    break
                    
            if not found:
                print(f"   ❌ '{alex_skill}' → '{expected_match}' NOT FOUND")
                
        # Check what synonyms exist for each job skill
        print(f"\n🔍 Available Synonyms for Job Skills:")
        for job_skill in job_skills_norm:
            print(f"\n   '{job_skill}' synonyms:")
            for synonym_key, synonyms in skill_synonyms.items():
                if job_skill in synonyms:
                    print(f"     via '{synonym_key}': {synonyms}")
                    
        return True
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main debug function."""
    print("🚀 Starting Alex Jones Skill Debug")
    print("=" * 60)
    
    success = debug_alex_skills()
    
    if success:
        print(f"\n🎉 Alex Jones skill debugging completed!")
    else:
        print(f"\n❌ Alex Jones skill debugging failed!")

if __name__ == "__main__":
    main() 