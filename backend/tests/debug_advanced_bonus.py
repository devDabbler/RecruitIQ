#!/usr/bin/env python3
"""
Debug script to test the advanced skill bonus specifically.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def debug_advanced_bonus():
    """Debug the advanced skill bonus specifically."""
    
    print("🔍 Debugging Advanced Skill Bonus")
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
        
        # Debug advanced skill detection
        print(f"\n🔍 Advanced Skill Detection:")
        
        # Normalize skills
        alex_skills_norm = [s.lower().strip() for s in alex_skills]
        matching_skills_norm = [s.lower().strip() for s in matching_skills]
        
        # Advanced skill indicators
        advanced_skill_indicators = [
            'applied machine learning', 'deep learning', 'neural networks', 'cnn', 'convolutional neural networks',
            'bayesian regression', 'causal inference', 'apache spark', 'distributed computing',
            'model fine-tuning', 'llm tuning', 'ensemble methods', 'unsupervised learning',
            'anomaly detection', 'fraud detection', 'model selection', 'performance metrics'
        ]
        
        print(f"   Advanced skill indicators: {advanced_skill_indicators}")
        print(f"   Alex's normalized skills: {alex_skills_norm}")
        print(f"   Matching skills (normalized): {matching_skills_norm}")
        
        # Check which advanced skills Alex has
        alex_advanced_skills = []
        for skill in alex_skills_norm:
            if skill in advanced_skill_indicators:
                alex_advanced_skills.append(skill)
                print(f"   ✅ Advanced skill found: '{skill}'")
            else:
                print(f"   ❌ Not advanced: '{skill}'")
                
        print(f"\n   Alex's advanced skills: {alex_advanced_skills}")
        print(f"   Count: {len(alex_advanced_skills)}")
        
        # Check which advanced skills are in matching skills
        matching_advanced_skills = []
        for skill in matching_skills_norm:
            if skill in advanced_skill_indicators:
                matching_advanced_skills.append(skill)
                print(f"   ✅ Advanced skill in matches: '{skill}'")
                
        print(f"\n   Advanced skills in matches: {matching_advanced_skills}")
        print(f"   Count: {len(matching_advanced_skills)}")
        
        # Test the bonus calculation
        if len(matching_advanced_skills) >= 2:
            bonus = 1.25
            print(f"   🎉 25% bonus would be applied (2+ advanced skills)")
        elif len(matching_advanced_skills) >= 1:
            bonus = 1.15
            print(f"   🎉 15% bonus would be applied (1 advanced skill)")
        else:
            bonus = 1.0
            print(f"   ❌ No bonus (0 advanced skills)")
            
        return True
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main debug function."""
    print("🚀 Starting Advanced Skill Bonus Debug")
    print("=" * 60)
    
    success = debug_advanced_bonus()
    
    if success:
        print(f"\n🎉 Advanced skill bonus debugging completed!")
    else:
        print(f"\n❌ Advanced skill bonus debugging failed!")

if __name__ == "__main__":
    main() 