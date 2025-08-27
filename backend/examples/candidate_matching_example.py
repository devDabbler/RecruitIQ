"""
Example of integrating the new CandidateAnalyzer for job matching
Demonstrates using local models for parsing and API calls for matching
"""

import logging
import os
from pathlib import Path
import json
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import the necessary components
from backend.utils.enhanced_resume_parser import EnhancedResumeParser
from backend.utils.candidate_analyzer import CandidateAnalyzer

def main():
    """Example workflow with separated parsing and matching"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='RecruitIQ Resume Processing Example')
    parser.add_argument('--api', action='store_true', help='Use API for matching (if omitted, uses local model only)')
    parser.add_argument('--resume-dir', type=str, default="data/resumes", help='Directory containing resume files')
    args = parser.parse_args()
    
    # Set API key from environment (for demonstration purposes)
    if args.api and not os.environ.get('AI_MATCHING_API_KEY'):
        print("Warning: No API key set. Set AI_MATCHING_API_KEY environment variable for API usage.")
        print("Will use local matching only.")
    
    # Initialize the components
    parser = EnhancedResumeParser()  # Local parsing only
    analyzer = CandidateAnalyzer(use_api=args.api)  # Can use API for matching if enabled
    
    # Path to resume files
    resume_dir = Path(args.resume_dir)
    if not resume_dir.exists():
        print(f"Resume directory {resume_dir} does not exist. Creating it...")
        resume_dir.mkdir(parents=True, exist_ok=True)
        print(f"Please add resume files to {resume_dir} and run again.")
        return
    
    # Example job data
    job_data = {
        'id': 'job-123',
        'title': 'Senior Software Engineer',
        'required_skills': ['Python', 'PostgreSQL', 'API Development'],
        'preferred_skills': ['Neo4j', 'Docker', 'AWS'],
        'min_years_experience': 5,
        'description': 'We are looking for a Senior Software Engineer with strong Python skills...'
    }
    
    # Process all resumes in the directory
    results = []
    resume_files = list(resume_dir.glob("*.txt"))  # Look for text files instead of PDFs
    
    if not resume_files:
        print(f"No resume files found in {resume_dir}. Please add resume files and try again.")
        return
    
    print(f"\nProcessing {len(resume_files)} resumes with {'API+local' if args.api else 'local-only'} matching...\n")
    
    for resume_file in resume_files:
        try:
            # PHASE 1: LOCAL PARSING (always uses your local model)
            logging.info(f"Parsing resume using local model: {resume_file}")
            resume_data = parser.parse_resume(str(resume_file))
            
            # Here we would store the parsed resume in your database
            # db.store_resume(resume_data)  # This would be your actual database call
            logging.info(f"Extracted {len(resume_data.skills) if hasattr(resume_data, 'skills') else 0} skills, "
                        f"{len(resume_data.experience) if hasattr(resume_data, 'experience') else 0} experiences")
            
            # PHASE 2: MATCHING (either API or local, depending on configuration)
            # This is where your newly trained data gets utilized
            match_source = "API" if args.api else "local model"
            logging.info(f"Matching candidate to job using {match_source}")
            
            # Get match results
            match_results = analyzer.match_to_job(resume_data, job_data)
            
            # Store results
            candidate_name = resume_data.personal_info.name if hasattr(resume_data, 'personal_info') else "Unknown"
            results.append({
                'resume_id': resume_data.file_id if hasattr(resume_data, 'file_id') else str(resume_file),
                'candidate_name': candidate_name,
                'job_id': job_data['id'],
                'match_score': match_results.get('match_score', 0),
                'source': match_results.get('source', 'unknown'),
                'missing_skills': match_results.get('missing_required_skills', []),
                'recommendation': match_results.get('analysis', {}).get('recommendation'),
                'skill_match': match_results.get('skill_match'),
                'experience_match': match_results.get('experience_match')
            })
            
        except Exception as e:
            logging.error(f"Error processing {resume_file}: {e}")
    
    # Print results
    print("\n===== MATCHING RESULTS =====\n")
    if not results:
        print("No results to display.")
        return
    
    for result in sorted(results, key=lambda x: x.get('match_score', 0), reverse=True):
        print(f"{result['candidate_name']}: Match Score {result.get('match_score', 'N/A')} "
              f"(Source: {result.get('source', 'unknown')})")
        print(f"  Skills: {result.get('skill_match', 'N/A')}, Experience: {result.get('experience_match', 'N/A')}")
        print(f"  Missing Skills: {', '.join(result.get('missing_skills', []))}")
        if result.get('recommendation'):
            print(f"  Recommendation: {result.get('recommendation')}")
        print()

if __name__ == "__main__":
    main()
