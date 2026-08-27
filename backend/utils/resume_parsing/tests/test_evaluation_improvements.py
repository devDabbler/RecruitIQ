#!/usr/bin/env python3
"""
Test script to validate improvements to the resume evaluation system.
This script tests the enhanced skill matching and scoring for Gen AI Engineer roles.
"""

import re
import logging
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _norm(s: str) -> str:
    """Normalize skill strings for comparison."""
    s = (s or "").strip().lower()
    s = re.sub(r"[\./,+_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    replacements = {
        "machine learning": "ml",
        "deep learning": "dl",
        "artificial intelligence": "ai",
        "rest apis": "rest api",
        "rest-api": "rest api",
        "rest": "rest api",
        "restful api": "rest api",
        "restful apis": "rest api",
        "ci cd": "ci/cd",
        "springboot": "spring boot",
        "js": "javascript",
        "node js": "node.js",
        "vue js": "vue js",
        "react js": "react",
        "typescript": "typescript",
        "postgresql": "sql",
        "postgres": "sql",
        "my sql": "mysql",
        "mysql": "sql",
        "tensorflow": "tensorflow",
        "pytorch": "pytorch",
        "scikit-learn": "scikit learn",
        "scikit learn": "scikit learn",
        "pandas": "pandas",
        "numpy": "numpy",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "jupyter": "jupyter",
        "git": "git",
        "github": "git",
        "gitlab": "git",
        "docker": "docker",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",
        "aws": "aws",
        "amazon web services": "aws",
        "azure": "azure",
        "google cloud": "gcp",
        "gcp": "gcp",
        "google cloud platform": "gcp",
    }
    return replacements.get(s, s)

def get_enhanced_fallback_skills(job_title: str) -> List[str]:
    """Enhanced fallback skill sets for specialized roles."""
    job_title_lower = job_title.lower()
    
    # Core AI/ML Engineer skills
    if 'gen ai' in job_title_lower or 'ai engineer' in job_title_lower or 'machine learning engineer' in job_title_lower:
        return [
            'python', 'machine learning', 'deep learning', 'neural networks', 'tensorflow', 'pytorch',
            'scikit-learn', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter', 'git', 'github',
            'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'sql', 'rest api', 'ci/cd', 'agile',
            'data analysis', 'data cleaning', 'data visualization', 'nlp', 'computer vision',
            'mlops', 'model deployment', 'api development', 'cloud computing', 'statistics',
            'linear algebra', 'calculus', 'probability', 'optimization', 'algorithms'
        ]
    
    # Software Engineer skills
    elif 'software engineer' in job_title_lower or 'developer' in job_title_lower:
        return [
            'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue', 'node.js',
            'git', 'github', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'sql', 'rest api',
            'ci/cd', 'agile', 'microservices', 'api development', 'cloud computing', 'linux',
            'html', 'css', 'bootstrap', 'tailwind', 'express', 'spring', 'django', 'flask',
            'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'kafka', 'rabbitmq'
        ]
    
    # Data Scientist skills
    elif 'data scientist' in job_title_lower or 'data analyst' in job_title_lower:
        return [
            'python', 'r', 'sql', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter',
            'scikit-learn', 'tensorflow', 'pytorch', 'statistics', 'machine learning',
            'data analysis', 'data cleaning', 'data visualization', 'git', 'github',
            'aws', 'azure', 'gcp', 'tableau', 'power bi', 'excel', 'spark', 'hadoop',
            'probability', 'linear algebra', 'calculus', 'optimization', 'ab testing'
        ]
    
    # Default fallback
    else:
        return [
            'python', 'java', 'javascript', 'git', 'sql', 'aws', 'azure', 'gcp', 'docker',
            'kubernetes', 'rest api', 'ci/cd', 'agile', 'cloud computing', 'linux',
            'html', 'css', 'react', 'node.js', 'postgresql', 'mysql', 'mongodb'
        ]

def test_gen_ai_evaluation():
    """Test the Gen AI Engineer evaluation improvements."""
    
    # Sample candidate data (based on the parsed resume)
    candidate_data = {
        "skills": [
            {"name": "C++", "category": "Programming Language"},
            {"name": "C#", "category": "Programming Language"},
            {"name": "JAVA", "category": "Programming Language"},
            {"name": "Swift", "category": "Programming Language"},
            {"name": "Python", "category": "Programming Language"},
            {"name": "RUBY", "category": "Programming Language"},
            {"name": "PHP", "category": "Programming Language"},
            {"name": "AI", "category": "Technology"},
            {"name": "HTML", "category": "Markup Language"},
            {"name": "CSS", "category": "Style Sheet Language"},
            {"name": "JavaScript", "category": "Programming Language"},
            {"name": "Type Script", "category": "Programming Language"},
            {"name": "React.js", "category": "Framework"},
            {"name": "Angular.js", "category": "Framework"},
            {"name": "Node.js", "category": "Runtime Environment"},
            {"name": ".NET Core", "category": "Framework"},
            {"name": "Django", "category": "Framework"},
            {"name": "Laravel", "category": "Framework"},
            {"name": "Azure", "category": "Cloud Platform"},
            {"name": "AWS", "category": "Cloud Platform"},
            {"name": "SQL Server", "category": "Database"},
            {"name": "Oracle", "category": "Database"},
            {"name": "Dynamo DB", "category": "Database"},
            {"name": "MySQL", "category": "Database"},
            {"name": "SQLite", "category": "Database"}
        ],
        "experience": [
            {
                "company": "Microsoft",
                "title": "Technical Lead Software Engineer",
                "description": "Spearheaded the development of new and existing use cases using the C3 AI Suite for Con Edison, enhancing the capabilities for engineering applications. Delivered a critical web app for Azure Arc Jumpstart within an aggressive six-week timeline for Microsoft's Ignite conference, showcasing dynamic markdown rendering. Advanced Microsoft's AI capabilities by developing web apps for AI computer vision visualization and editing, as well as collision detection libraries. Led the refactor of the Kinect SDK to support a range of depth cameras."
            },
            {
                "company": "Google",
                "title": "Senior Software Engineer",
                "description": "Development of Podium, a suite of tools for performing photorealistic renderings of Sketchup scenes. Development of Podium Browser, an app for downloading 3d content into Sketchup. C++, Ruby, Java Script, Angular, React, Web GL, GLSL, Three.js, Visual Studio Code, QT, Xcode, Sketchup, AWS."
            }
        ],
        "raw_text": "John Doe\n\n456-098-8776 | john.doe@email.com | www.linkedin.com/profile1 | 123 44th Ave SE Seattle, WA\n\nProfile\n\nAn adept Technical Lead Software Engineer with a proven track record of developing and leading sophisticated software solutions, particularly with C3.ai's suite for Con Edison. Skilled in delivering complex projects under tight deadlines, evidenced by the rapid development of a React-based web app for Microsoft Azure Arc Jumpstart. Brings a wealth of experience in both web and mobile app development, AI computer vision scenarios, and cross-platform integrations. Recognized for driving innovation in visual rendering tools and financial software engineering, coupled with direct client engagement and technical leadership."
    }
    
    # Test Gen AI Engineer skills
    gen_ai_skills = get_enhanced_fallback_skills("Gen AI Engineer")
    logger.info(f"Gen AI Engineer skills ({len(gen_ai_skills)}): {', '.join(gen_ai_skills[:10])}...")
    
    # Normalize candidate skills
    candidate_skills_raw = []
    for skill in candidate_data.get('skills', []):
        if isinstance(skill, dict) and skill.get('name'):
            candidate_skills_raw.append(skill.get('name', ''))
    
    candidate_skills = {_norm(x) for x in candidate_skills_raw if x}
    logger.info(f"Candidate skills ({len(candidate_skills)}): {', '.join(sorted(list(candidate_skills)))}")
    
    # Calculate matches
    market_skills = set(gen_ai_skills)
    matching_skills = candidate_skills.intersection(market_skills)
    missing_skills = market_skills.difference(candidate_skills)
    
    logger.info(f"Matching skills ({len(matching_skills)}): {', '.join(sorted(list(matching_skills)))}")
    logger.info(f"Missing skills ({len(missing_skills)}): {', '.join(sorted(list(missing_skills))[:10])}...")
    
    # Calculate overlap ratio
    union = market_skills.union(candidate_skills)
    basic_overlap = len(candidate_skills.intersection(market_skills)) / max(len(union), 1)
    
    # Apply AI-specific weighting
    core_ai_skills = {'ai', 'ml', 'python', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'git', 'aws', 'azure', 'gcp'}
    core_matches = len(candidate_skills.intersection(market_skills).intersection(core_ai_skills))
    core_weight = min(0.3, core_matches * 0.1)
    weighted_overlap = basic_overlap + core_weight
    
    logger.info(f"Basic overlap ratio: {basic_overlap:.4f}")
    logger.info(f"Core AI skills matches: {core_matches}")
    logger.info(f"Core weight bonus: {core_weight:.4f}")
    logger.info(f"Weighted overlap ratio: {weighted_overlap:.4f}")
    
    # Calculate job fit score
    skills_score = min(10.0, round(weighted_overlap * 10.0, 2))
    clarity = 7  # Assume good clarity
    impact = 8   # Assume good impact
    skills_relevance = 6  # Assume moderate relevance
    
    base_score = (skills_score * 0.6) + (clarity * 0.1) + (impact * 0.2) + (skills_relevance * 0.1)
    
    # Apply AI-specific adjustments
    if core_matches >= 5:
        base_score += 1.0
    elif core_matches >= 3:
        base_score += 0.5
    elif core_matches >= 1:
        base_score += 0.2
    
    # Check for AI experience
    ai_experience_bonus = 0
    for exp in candidate_data.get('experience', []):
        if isinstance(exp, dict) and exp.get('description'):
            desc = exp['description'].lower()
            if any(term in desc for term in ['ai', 'machine learning', 'deep learning', 'neural', 'tensorflow', 'pytorch']):
                ai_experience_bonus += 0.3
                break
    base_score += min(ai_experience_bonus, 0.6)
    
    job_fit_score = round(min(10.0, max(0.0, base_score)), 1)
    
    logger.info(f"Skills score: {skills_score}")
    logger.info(f"AI experience bonus: {ai_experience_bonus}")
    logger.info(f"Final job fit score: {job_fit_score}/10")
    
    # Generate recommendation
    if job_fit_score >= 8.0:
        recommendation = "Strong Candidate"
        decision = "yes"
    elif job_fit_score >= 6.5:
        recommendation = "Good Candidate"
        decision = "yes"
    elif job_fit_score >= 5.0:
        recommendation = "Potential Candidate"
        decision = "maybe"
    elif job_fit_score >= 3.5:
        recommendation = "Weak Candidate"
        decision = "no"
    else:
        recommendation = "Poor Candidate"
        decision = "no"
    
    logger.info(f"Recommendation: {recommendation} ({decision})")
    
    # Summary
    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print(f"Target Role: Gen AI Engineer")
    print(f"Job Fit Score: {job_fit_score}/10")
    print(f"Recommendation: {recommendation}")
    print(f"Decision: {decision}")
    print(f"Matching Skills: {len(matching_skills)}")
    print(f"Skills Gap: {len(missing_skills)}")
    print(f"Core AI Skills Matched: {core_matches}")
    print(f"AI Experience Detected: {'Yes' if ai_experience_bonus > 0 else 'No'}")
    print("="*50)
    
    # Compare with original evaluation
    print("\n" + "="*50)
    print("COMPARISON WITH ORIGINAL EVALUATION")
    print("="*50)
    print(f"Original Score: 3.3/10")
    print(f"Improved Score: {job_fit_score}/10")
    print(f"Improvement: {job_fit_score - 3.3:.1f} points")
    print(f"Original Recommendation: Weak Candidate")
    print(f"Improved Recommendation: {recommendation}")
    print("="*50)

if __name__ == "__main__":
    test_gen_ai_evaluation()
