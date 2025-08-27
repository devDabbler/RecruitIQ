"""
Candidate Analyzer for RecruitIQ
Provides AI-powered analysis for candidate-job matching, separate from resume parsing
Uses local models for resume data access and API calls for advanced AI matching
"""

import logging
import os
import json
import requests
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

# Import the new resume parser components
from backend.utils.resume_parsing import ResumeData, create_resume_parser

# Import database connection utilities (PostgreSQL and Neo4j)
from backend.database.db_connection import get_postgres_connection, get_neo4j_connection

logger = logging.getLogger(__name__)

# API Configuration
API_ENDPOINT = os.environ.get('AI_MATCHING_API_ENDPOINT', 'https://api.recruitiq.ai/v1/matching')
API_KEY = os.environ.get('AI_MATCHING_API_KEY', '')
API_TIMEOUT = 30  # seconds

class CandidateAnalyzer:
    """
    Provides AI-powered analysis for candidate-job matching.
    Uses local models for resume data access but API calls for advanced matching and predictions.
    """
    
    def __init__(self, model_path: Optional[str] = None, use_api: bool = True):
        """
        Initialize the candidate analyzer
        
        Args:
            model_path: Optional path to the directory containing prediction models
            use_api: Whether to use API calls for advanced matching (vs. local-only)
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = model_path or "training_data/parsing/models"
        self.predictor = None
        self.use_api = use_api
        
        # Initialize the resume parser with default config
        self.resume_parser = create_resume_parser()
        
        # Initialize the local model for direct resume data access
        self._initialize_local_model()
        
        # Check API configuration
        if self.use_api and not API_KEY:
            self.logger.warning("API key not configured. Will use local models only.")
            self.use_api = False
    
    def _initialize_local_model(self) -> bool:
        """Initialize the local resume predictor for direct data access"""
        try:
            # Dynamic import to avoid circular dependencies
            from training_data.parsing.updates.resume_predictor import ResumePredictor
            self.predictor = ResumePredictor(self.model_path)
            
            if self.predictor.decision_model is not None:
                self.logger.info("Local resume model initialized successfully")
                return True
            else:
                self.logger.warning("Local resume model initialized but no model loaded")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to initialize local resume model: {e}")
            return False
    
    async def parse_resume(self, file_path: str) -> ResumeData:
        """
        Parse a resume file using the new resume parser
        
        Args:
            file_path: Path to the resume file
            
        Returns:
            ResumeData object with parsed resume information
        """
        try:
            # Use the new resume parser to parse the file
            resume_data = await self.resume_parser.parse_resume(file_path)
            self.logger.info(f"Successfully parsed resume from {file_path}")
            return resume_data
        except Exception as e:
            self.logger.error(f"Error parsing resume from {file_path}: {e}")
            raise
    
    def analyze_candidate(self, resume_data: ResumeData) -> Dict[str, Any]:
        """
        Generate AI-powered analysis for a candidate's resume
        Uses local model for resume access but can use API for advanced analysis
        
        Args:
            resume_data: Parsed resume data
            
        Returns:
            Dictionary with AI analysis results
        """
        # First generate basic analysis using local model
        local_analysis = self._generate_local_analysis(resume_data)
        
        # If API is enabled, enhance with API-based analysis
        if self.use_api:
            try:
                api_analysis = self._call_analysis_api(resume_data)
                
                # Merge local and API analysis results, with API taking precedence
                merged_analysis = {**local_analysis, **api_analysis}
                self.logger.info(f"Enhanced analysis with API data")
                return merged_analysis
            except Exception as e:
                self.logger.error(f"API analysis failed, using local analysis only: {e}")
        
        return local_analysis
    
    def _convert_to_dict(self, resume_data: ResumeData) -> Dict[str, Any]:
        """Convert ResumeData Pydantic model to a plain dictionary for ResumePredictor"""
        if not hasattr(resume_data, 'model_dump'):
            # If it's already a dict or similar, return as is
            return resume_data
        
        # Convert the main ResumeData object to dict
        resume_dict = resume_data.model_dump() if hasattr(resume_data, 'model_dump') else resume_data.__dict__.copy()
        
        # Ensure education is in the right format (list of dicts)
        if 'education' in resume_dict and resume_dict['education']:
            education_list = []
            for edu in resume_dict['education']:
                if isinstance(edu, dict):
                    education_list.append(edu)
                else:
                    # Convert to dict with get() method
                    education_list.append({
                        'degree': getattr(edu, 'degree', ''),
                        'institution': getattr(edu, 'institution', ''),
                        'location': getattr(edu, 'location', ''),
                        'start_date': getattr(edu, 'start_date', ''),
                        'end_date': getattr(edu, 'end_date', ''),
                        'description': getattr(edu, 'description', '')
                    })
            resume_dict['education'] = education_list
        
        # Ensure experience is in the right format (list of dicts)
        if 'experience' in resume_dict and resume_dict['experience']:
            experience_list = []
            for exp in resume_dict['experience']:
                if isinstance(exp, dict):
                    experience_list.append(exp)
                else:
                    # Convert to dict with get() method
                    experience_list.append({
                        'title': getattr(exp, 'title', ''),
                        'company': getattr(exp, 'company', ''),
                        'location': getattr(exp, 'location', ''),
                        'start_date': getattr(exp, 'start_date', ''),
                        'end_date': getattr(exp, 'end_date', ''),
                        'description': getattr(exp, 'description', '')
                    })
            resume_dict['experience'] = experience_list
        
        return resume_dict

    def _generate_local_analysis(self, resume_data: ResumeData) -> Dict[str, Any]:
        """Generate analysis using local model only"""
        if not self.predictor or not self.predictor.decision_model:
            self.logger.warning("Cannot analyze candidate: local model not initialized")
            return {}
        
        try:
            # Convert resume_data to a dictionary format compatible with ResumePredictor
            resume_dict = self._convert_to_dict(resume_data)
            
            # Generate predictions using the local predictor
            predictions = self.predictor.predict(resume_dict)
            
            # Return analysis results
            analysis = {
                'ai_score': predictions.get('ai_score'),
                'recommendation': predictions.get('recommendation'),
                'salary_range': predictions.get('salary_range'),
                'skill_gaps': predictions.get('skill_gaps'),
                'source': 'local_model'
            }
            
            self.logger.info(f"Generated local AI score: {analysis.get('ai_score')}")
            return analysis
        except Exception as e:
            self.logger.error(f"Error generating local analysis: {e}")
            return {'source': 'local_model_error'}
    
    def _call_analysis_api(self, resume_data: ResumeData) -> Dict[str, Any]:
        """Call external API for enhanced analysis"""
        try:
            # Convert resume data to API format
            resume_json = self._resume_to_api_format(resume_data)
            
            # Prepare API request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
                'X-API-Version': '2025-05'
            }
            
            # Make API call
            response = requests.post(
                f"{API_ENDPOINT}/analyze",
                headers=headers,
                json={
                    'resume_data': resume_json,
                    'include_trained_data': True  # This tells the API to use your newly trained data
                },
                timeout=API_TIMEOUT
            )
            
            # Check response
            if response.status_code == 200:
                api_analysis = response.json()
                api_analysis['source'] = 'api'
                return api_analysis
            else:
                self.logger.error(f"API analysis failed: {response.status_code} - {response.text}")
                return {'source': 'api_error'}
                
        except Exception as e:
            self.logger.error(f"Error calling analysis API: {e}")
            return {'source': 'api_error'}
    
    def match_to_job(self, resume_data: ResumeData, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match a candidate to a specific job
        Uses API for matching if enabled, falls back to local matching
        
        Args:
            resume_data: Parsed resume data
            job_data: Job posting data
            
        Returns:
            Dictionary with match results
        """
        # Try API matching if enabled
        if self.use_api:
            try:
                api_match_results = self._call_matching_api(resume_data, job_data)
                if api_match_results and 'match_score' in api_match_results:
                    return api_match_results
            except Exception as e:
                self.logger.error(f"API matching failed, falling back to local: {e}")
        
        # Fall back to local matching
        return self._generate_local_match(resume_data, job_data)
    
    def _call_matching_api(self, resume_data: ResumeData, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call external API for enhanced job matching"""
        try:
            # Convert data to API format
            resume_json = self._resume_to_api_format(resume_data)
            
            # Prepare API request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
                'X-API-Version': '2025-05'
            }
            
            # Make API call
            response = requests.post(
                f"{API_ENDPOINT}/match",
                headers=headers,
                json={
                    'resume_data': resume_json,
                    'job_data': job_data,
                    'include_trained_data': True,  # Use your newly trained data
                    'explanation': True  # Request explanation of match
                },
                timeout=API_TIMEOUT
            )
            
            # Check response
            if response.status_code == 200:
                api_results = response.json()
                api_results['source'] = 'api'
                return api_results
            else:
                self.logger.error(f"API matching failed: {response.status_code} - {response.text}")
                return {'source': 'api_error'}
                
        except Exception as e:
            self.logger.error(f"Error calling matching API: {e}")
            return {'source': 'api_error'}
    
    def _generate_local_match(self, resume_data: ResumeData, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate match results using local model only"""
        if not self.predictor or not self.predictor.decision_model:
            self.logger.warning("Cannot match candidate to job: local model not initialized")
            return {}
        
        try:
            # Basic analysis using local model
            analysis = self._generate_local_analysis(resume_data)
            
            # Extract job requirements
            required_skills = job_data.get('required_skills', [])
            preferred_skills = job_data.get('preferred_skills', [])
            
            # Get candidate skills
            candidate_skills = []
            if hasattr(resume_data, 'skills') and resume_data.skills:
                candidate_skills = [skill.name if hasattr(skill, 'name') else skill 
                                   for skill in resume_data.skills]
            
            # Calculate match score
            match_score = self._calculate_match_score(
                candidate_skills, 
                required_skills, 
                preferred_skills
            )
            
            # Calculate experience match
            experience_match = self._calculate_experience_match(
                resume_data, 
                job_data.get('min_years_experience', 0)
            )
            
            # Combine scores
            combined_score = (match_score * 0.7) + (experience_match * 0.3)
            
            # Return match results
            return {
                'match_score': round(combined_score, 2),
                'skill_match': round(match_score, 2),
                'experience_match': round(experience_match, 2),
                'missing_required_skills': [s for s in required_skills if s.lower() not in [sk.lower() for sk in candidate_skills]],
                'missing_preferred_skills': [s for s in preferred_skills if s.lower() not in [sk.lower() for sk in candidate_skills]],
                'analysis': analysis,
                'source': 'local_model'
            }
        except Exception as e:
            self.logger.error(f"Error generating local match: {e}")
            return {'source': 'local_model_error'}
    
    def _resume_to_api_format(self, resume_data: ResumeData) -> Dict[str, Any]:
        """Convert ResumeData object to API-compatible format"""
        # Convert ResumeData to dictionary if it's not already
        if hasattr(resume_data, '__dict__'):
            resume_dict = resume_data.__dict__
        else:
            resume_dict = resume_data
            
        # Clean up the dictionary for API transmission
        # Remove any non-serializable objects or large text fields
        cleaned_dict = {}
        for key, value in resume_dict.items():
            if key in ['file_id', 'file_name', 'content_type', 'personal_info', 'skills', 
                      'education', 'experience', 'certifications', 'projects', 'languages']:
                cleaned_dict[key] = value
        
        # Include trained model data markers to ensure the API uses your local model's data
        cleaned_dict['_trained_model_data'] = {
            'model_version': self._get_local_model_version(),
            'training_date': time.strftime('%Y-%m-%d')
        }
            
        return cleaned_dict
    
    def _get_local_model_version(self) -> str:
        """Get version information from local model"""
        if self.predictor and hasattr(self.predictor, 'decision_model'):
            # Try to extract version from model metadata
            model = self.predictor.decision_model
            if hasattr(model, 'metadata') and isinstance(model.metadata, dict):
                return model.metadata.get('version', 'unknown')
        return 'local-model'
    
    def _calculate_match_score(self, 
                              candidate_skills: List[str], 
                              required_skills: List[str], 
                              preferred_skills: List[str]) -> float:
        """Calculate skill match score"""
        if not required_skills and not preferred_skills:
            return 0.5  # Neutral score if no skills specified
        
        # Convert to lowercase for case-insensitive matching
        candidate_skills_lower = [s.lower() for s in candidate_skills]
        required_skills_lower = [s.lower() for s in required_skills]
        preferred_skills_lower = [s.lower() for s in preferred_skills]
        
        # Calculate required skills match
        required_match = 0.0
        if required_skills_lower:
            matched_required = sum(1 for skill in required_skills_lower if skill in candidate_skills_lower)
            required_match = matched_required / len(required_skills_lower)
        
        # Calculate preferred skills match
        preferred_match = 0.0
        if preferred_skills_lower:
            matched_preferred = sum(1 for skill in preferred_skills_lower if skill in candidate_skills_lower)
            preferred_match = matched_preferred / len(preferred_skills_lower)
        
        # Combined score (required skills have higher weight)
        if required_skills_lower and preferred_skills_lower:
            return (required_match * 0.7) + (preferred_match * 0.3)
        elif required_skills_lower:
            return required_match
        else:
            return preferred_match * 0.7  # Reduce score if only preferred skills provided
    
    def _calculate_experience_match(self, resume_data: ResumeData, min_years: int) -> float:
        """Calculate experience match score"""
        if min_years <= 0:
            return 1.0  # Perfect match if no minimum experience required
        
        # Calculate total years of experience
        total_years = 0
        if hasattr(resume_data, 'experience') and resume_data.experience:
            for exp in resume_data.experience:
                # Skip if missing start or end date
                if not hasattr(exp, 'start_date') or not hasattr(exp, 'end_date'):
                    continue
                
                # Extract years from dates
                start_year = self._extract_year(exp.start_date) if exp.start_date else None
                end_year = self._extract_year(exp.end_date) if exp.end_date else None
                
                # Skip if can't parse dates
                if not start_year or not end_year:
                    continue
                
                # Handle 'Present' in end date
                if isinstance(end_year, str) and (end_year.lower() == 'present' or end_year.lower() == 'current'):
                    import datetime
                    end_year = datetime.datetime.now().year
                
                # Calculate years
                try:
                    years = int(end_year) - int(start_year)
                    if years > 0:
                        total_years += years
                except (ValueError, TypeError):
                    continue
        
        # Calculate match score
        if total_years >= min_years:
            return 1.0
        elif total_years <= 0:
            return 0.0
        else:
            return total_years / min_years
    
    def _extract_year(self, date_value: Any) -> Optional[int]:
        """Extract year from various date formats"""
        if not date_value:
            return None
        
        # If it's already a year (int)
        if isinstance(date_value, int):
            return date_value
        
        # If it's a string
        if isinstance(date_value, str):
            # Try to extract year from string
            import re
            year_match = re.search(r'\b(19|20)\d{2}\b', date_value)
            if year_match:
                return int(year_match.group(0))
            
            # Check for 'Present' or 'Current'
            if 'present' in date_value.lower() or 'current' in date_value.lower():
                return 'Present'
        
        # If it's a datetime object
        if hasattr(date_value, 'year'):
            return date_value.year
        
        return None


# Example usage
if __name__ == "__main__":
    analyzer = CandidateAnalyzer()
    
    # This would normally be loaded from a database
    from backend.utils.enhanced_resume_parser import EnhancedResumeParser
    parser = EnhancedResumeParser()
    
    # Example usage
    resume_data = parser.parse_resume("path/to/resume.pdf")
    
    # Generate analysis
    analysis = analyzer.analyze_candidate(resume_data)
    print(f"AI Score: {analysis.get('ai_score')}")
    
    # Match to job
    job_data = {
        'title': 'Senior Python Developer',
        'required_skills': ['Python', 'Django', 'SQL'],
        'preferred_skills': ['AWS', 'Docker', 'Kubernetes'],
        'min_years_experience': 5
    }
    
    match_results = analyzer.match_to_job(resume_data, job_data)
    print(f"Match Score: {match_results.get('match_score')}")
    print(f"Missing Required Skills: {match_results.get('missing_required_skills')}")
