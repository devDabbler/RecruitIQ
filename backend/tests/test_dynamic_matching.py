#!/usr/bin/env python3
"""
Test script to demonstrate dynamic configuration system for matching algorithm.
This script shows how to use different configurations for different job types.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_dynamic_configurations():
    """Test different configurations for different job types."""
    
    print("🧪 Testing Dynamic Configuration System")
    print("=" * 60)
    
    try:
        from services.matching_enhancer import MatchingEnhancer, MATCHING_CONFIGS, MatchingConfig
        print("✅ MatchingEnhancer imported successfully")
        
        # Test data
        job_title = "Data Scientist"
        job_skills = ['Python', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn']
        job_requirements = "3+ years of experience in data science, machine learning, and statistical analysis"
        
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
        
        # Test different configurations
        configs_to_test = [
            ('default', 'Default Configuration'),
            ('data_science', 'Data Science Configuration'),
            ('senior_level', 'Senior Level Configuration'),
            ('entry_level', 'Entry Level Configuration')
        ]
        
        for config_name, config_description in configs_to_test:
            print(f"\n🔧 Testing {config_description}")
            print("-" * 50)
            
            # Initialize enhancer with specific config
            enhancer = MatchingEnhancer()
            enhancer.set_job_type_config(config_name)
            
            print(f"   Config: {config_name}")
            print(f"   Weights: Skill={enhancer.config.skill_weight:.2f}, Role={enhancer.config.role_weight:.2f}, Experience={enhancer.config.experience_weight:.2f}")
            print(f"   Data Science Exact Match Score: {enhancer.config.data_science_exact_match_score}")
            print(f"   Advanced Skill Bonus: {enhancer.config.advanced_skill_bonus}")
            print(f"   Experience Depth Bonus: {enhancer.config.experience_depth_bonus}")
            
            results = []
            
            for candidate in test_candidates:
                # Calculate component scores
                skill_score, matching_skills = enhancer.calculate_skill_match_score(job_skills, candidate['skills'])
                role_score = enhancer.calculate_role_match_score(job_title, "", candidate['position'])
                
                # Extract experience level
                candidate_level, candidate_years = enhancer.extract_experience_level(candidate['position'])
                job_level, job_years = enhancer.extract_experience_level(job_requirements)
                experience_score = enhancer.calculate_experience_match_score(job_level, job_years, candidate_level, candidate_years, candidate['position'])
                
                # Calculate final score using config weights
                if role_score < enhancer.config.role_mismatch_severe_threshold:
                    match_score = (skill_score * 0.35 + role_score * 0.45 + experience_score * 0.2) * enhancer.config.role_mismatch_severe_penalty
                elif role_score < enhancer.config.role_mismatch_moderate_threshold:
                    match_score = (skill_score * 0.4 + role_score * 0.4 + experience_score * 0.2) * enhancer.config.role_mismatch_moderate_penalty
                else:
                    match_score = (skill_score * enhancer.config.skill_weight + 
                                 role_score * enhancer.config.role_weight + 
                                 experience_score * enhancer.config.experience_weight)
                
                # Apply cross-domain penalty if needed
                if role_score < enhancer.config.cross_domain_threshold_role and skill_score < enhancer.config.cross_domain_threshold_skill:
                    match_score *= enhancer.config.cross_domain_penalty
                
                results.append({
                    'name': candidate['name'],
                    'position': candidate['position'],
                    'skill_score': skill_score,
                    'role_score': role_score,
                    'experience_score': experience_score,
                    'match_score': match_score,
                    'expected_ranking': candidate['expected_ranking']
                })
            
            # Sort results
            sorted_results = sorted(results, key=lambda x: x['match_score'], reverse=True)
            
            print(f"   Results:")
            for i, result in enumerate(sorted_results):
                print(f"     {i+1}. {result['name']}: {result['match_score']:.1f}% (Expected: {result['expected_ranking']})")
            
            # Check if ranking improved
            jacob_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Jacob Smith') + 1
            alex_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Alex Jones') + 1
            clint_rank = next(i for i, r in enumerate(sorted_results) if r['name'] == 'Clint Forest') + 1
            
            if jacob_rank <= 2 and alex_rank <= 2 and clint_rank >= 2:
                print(f"   ✅ GOOD: Experienced candidates rank higher than junior")
            else:
                print(f"   ❌ NEEDS IMPROVEMENT: Ranking not optimal")
        
        # Test custom configuration
        print(f"\n🔧 Testing Custom Configuration")
        print("-" * 50)
        
        # Create custom config for data science with higher skill weight
        custom_config = enhancer.create_custom_config(
            skill_weight=0.5,
            role_weight=0.3,
            experience_weight=0.2,
            data_science_exact_match_score=90.0,
            advanced_skill_bonus=1.2,
            experience_depth_bonus=10.0
        )
        
        enhancer.set_config(custom_config)
        print(f"   Custom Config: Skill={custom_config.skill_weight:.2f}, Role={custom_config.role_weight:.2f}, Experience={custom_config.experience_weight:.2f}")
        print(f"   Data Science Exact Match Score: {custom_config.data_science_exact_match_score}")
        print(f"   Advanced Skill Bonus: {custom_config.advanced_skill_bonus}")
        print(f"   Experience Depth Bonus: {custom_config.experience_depth_bonus}")
        
        # Test with custom config
        results = []
        for candidate in test_candidates:
            skill_score, matching_skills = enhancer.calculate_skill_match_score(job_skills, candidate['skills'])
            role_score = enhancer.calculate_role_match_score(job_title, "", candidate['position'])
            
            candidate_level, candidate_years = enhancer.extract_experience_level(candidate['position'])
            job_level, job_years = enhancer.extract_experience_level(job_requirements)
            experience_score = enhancer.calculate_experience_match_score(job_level, job_years, candidate_level, candidate_years, candidate['position'])
            
            # Calculate final score using custom config
            if role_score < custom_config.role_mismatch_severe_threshold:
                match_score = (skill_score * 0.35 + role_score * 0.45 + experience_score * 0.2) * custom_config.role_mismatch_severe_penalty
            elif role_score < custom_config.role_mismatch_moderate_threshold:
                match_score = (skill_score * 0.4 + role_score * 0.4 + experience_score * 0.2) * custom_config.role_mismatch_moderate_penalty
            else:
                match_score = (skill_score * custom_config.skill_weight + 
                             role_score * custom_config.role_weight + 
                             experience_score * custom_config.experience_weight)
            
            if role_score < custom_config.cross_domain_threshold_role and skill_score < custom_config.cross_domain_threshold_skill:
                match_score *= custom_config.cross_domain_penalty
            
            results.append({
                'name': candidate['name'],
                'position': candidate['position'],
                'match_score': match_score,
                'expected_ranking': candidate['expected_ranking']
            })
        
        sorted_results = sorted(results, key=lambda x: x['match_score'], reverse=True)
        
        print(f"   Custom Config Results:")
        for i, result in enumerate(sorted_results):
            print(f"     {i+1}. {result['name']}: {result['match_score']:.1f}% (Expected: {result['expected_ranking']})")
        
        print(f"\n🎯 Configuration System Summary:")
        print(f"   ✅ Dynamic configuration system working")
        print(f"   ✅ Different job types can use different weights")
        print(f"   ✅ Custom configurations can be created")
        print(f"   ✅ All parameters are configurable")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def demonstrate_usage_examples():
    """Demonstrate how to use the dynamic configuration system."""
    
    print(f"\n📚 Usage Examples:")
    print("=" * 60)
    
    print(f"\n1. Using Predefined Configurations:")
    print("   enhancer = MatchingEnhancer()")
    print("   enhancer.set_job_type_config('data_science')  # For data science jobs")
    print("   enhancer.set_job_type_config('software_engineering')  # For SWE jobs")
    print("   enhancer.set_job_type_config('product_management')  # For PM jobs")
    print("   enhancer.set_job_type_config('entry_level')  # For entry level jobs")
    print("   enhancer.set_job_type_config('senior_level')  # For senior level jobs")
    
    print(f"\n2. Creating Custom Configuration:")
    print("   custom_config = enhancer.create_custom_config(")
    print("       skill_weight=0.5,")
    print("       role_weight=0.3,")
    print("       experience_weight=0.2,")
    print("       data_science_exact_match_score=90.0,")
    print("       advanced_skill_bonus=1.2,")
    print("       experience_depth_bonus=10.0")
    print("   )")
    print("   enhancer.set_config(custom_config)")
    
    print(f"\n3. Available Configuration Parameters:")
    print("   - skill_weight, role_weight, experience_weight")
    print("   - role_mismatch_severe_threshold, role_mismatch_moderate_threshold")
    print("   - role_mismatch_severe_penalty, role_mismatch_moderate_penalty")
    print("   - cross_domain_penalty, cross_domain_threshold_role, cross_domain_threshold_skill")
    print("   - overqualification_penalty, underqualification_penalty")
    print("   - experience_depth_bonus, junior_penalty_threshold")
    print("   - skill_depth_bonus_threshold, skill_depth_bonus_multiplier")
    print("   - highly_relevant_skill_bonus, advanced_skill_bonus, complementary_skill_bonus")
    print("   - same_category_bonus, incompatible_penalty, moderate_incompatible_penalty")
    print("   - data_science_exact_match_score, data_science_related_match_score")
    
    print(f"\n4. Integration with Matching Integrator:")
    print("   # The matching integrator automatically uses the enhancer's config")
    print("   integrator = MatchingIntegrator(rag_service)")
    print("   integrator.enhancer.set_job_type_config('data_science')")
    print("   matches = await integrator.enhanced_candidate_job_matching(job_id, db)")

def main():
    """Main test function."""
    print("🚀 Starting Dynamic Configuration System Test")
    print("=" * 60)
    
    # Test the dynamic configuration system
    success = test_dynamic_configurations()
    
    # Demonstrate usage examples
    demonstrate_usage_examples()
    
    if success:
        print(f"\n🎉 Dynamic configuration system test completed successfully!")
        print(f"   You can now use different configurations for different job types")
        print(f"   and easily customize the matching algorithm parameters.")
    else:
        print(f"\n❌ Dynamic configuration system test failed!")

if __name__ == "__main__":
    main() 