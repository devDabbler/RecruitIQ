"""
Advanced matching functionality for the Recruiter Dashboard application.
This module enhances the existing matching capabilities with more sophisticated algorithms.
"""

import re
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class MatchingEnhancer:
    """Enhances matching between candidates and jobs with advanced algorithms."""
    
    def __init__(self, embedding_model=None):
        """
        Initialize the matching enhancer.
        
        Args:
            embedding_model: Optional embedding model for semantic matching
        """
        self.embedding_model = embedding_model
    
    def extract_experience_level(self, text: str) -> Tuple[str, int]:
        """
        Extract experience level from text and return a normalized value.
        
        Args:
            text: Text to extract experience level from (job title, description, etc.)
            
        Returns:
            Tuple of (experience_level, years) where experience_level is one of:
            'entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive'
        """
        text = text.lower()
        
        # First, look for explicit years of experience mentioned
        year_patterns = [
            r'(\d+)\+?\s*years?\s*(of\s*)?experience',
            r'experience\s*(of|:)?\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*yrs?\s*(of\s*)?experience',
            r'experience\s*(of|:)?\s*(\d+)\+?\s*yrs?',
            r'(\d+)\+?\s*y\.?o\.?e\.?',  # Abbreviation: y.o.e. (years of experience)
        ]
        
        years = 0
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                for group in groups:
                    if group and group.isdigit():
                        years = int(group)
                        break
                if years > 0:
                    break
                    
        # Map specific experience levels mentioned in the text
        level_keywords = {
            'entry': ['entry', 'entry level', 'entry-level', 'junior', 'intern', 'internship', 'graduate', 'trainee', 'apprentice', 'beginner'],
            'junior': ['junior', 'jr', 'jr.', 'associate', 'early career'],
            'mid': ['mid', 'mid level', 'mid-level', 'intermediate', 'regular', 'experienced'],
            'senior': ['senior', 'sr', 'sr.', 'experienced', 'expert', 'advanced'],
            'lead': ['lead', 'team lead', 'technical lead', 'manager', 'head of', 'director'],
            'principal': ['principal', 'staff', 'distinguished', 'architect'],
            'executive': ['chief', 'cto', 'cio', 'vp', 'vice president', 'executive']
        }
        
        # Find the highest level mentioned
        found_level = 'mid'  # Default to mid-level if nothing is found
        level_hierarchy = ['entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive']
        
        for level, keywords in level_keywords.items():
            if any(keyword in text for keyword in keywords):
                idx = level_hierarchy.index(level)
                current_idx = level_hierarchy.index(found_level)
                if idx > current_idx:
                    found_level = level
        
        # If we found years but no specific level, infer level from years
        if years > 0 and found_level == 'mid':
            if years < 2:
                found_level = 'entry'
            elif years < 5:
                found_level = 'mid'
            elif years < 8:
                found_level = 'senior'
            elif years < 12:
                found_level = 'lead'
            else:
                found_level = 'principal'
                
        # Map level to approximate years if we didn't find explicit years
        if years == 0:
            level_to_years = {
                'entry': 1,
                'junior': 2,
                'mid': 4,
                'senior': 7,
                'lead': 10,
                'principal': 12,
                'executive': 15
            }
            years = level_to_years.get(found_level, 4)
            
        return found_level, years
    
    def calculate_experience_match_score(self, job_level: str, job_years: int, 
                                        candidate_level: str, candidate_years: int) -> float:
        """
        Calculate an experience match score between job requirements and candidate experience.
        
        Args:
            job_level: Job experience level (entry, junior, mid, senior, etc.)
            job_years: Job required years of experience
            candidate_level: Candidate experience level
            candidate_years: Candidate years of experience
            
        Returns:
            Match score between 0-100
        """
        # Define level hierarchy for comparison
        level_hierarchy = ['entry', 'junior', 'mid', 'senior', 'lead', 'principal', 'executive']
        
        # Get indices for levels
        try:
            job_idx = level_hierarchy.index(job_level)
            candidate_idx = level_hierarchy.index(candidate_level)
        except ValueError:
            # Default to mid if level not found
            job_idx = level_hierarchy.index('mid')
            candidate_idx = level_hierarchy.index('mid')
            
        # Calculate level match component (0-100)
        level_diff = candidate_idx - job_idx
        
        if level_diff < -2:  # Significantly underqualified
            level_match = 20
        elif level_diff == -2:  # Somewhat underqualified
            level_match = 40
        elif level_diff == -1:  # Slightly underqualified
            level_match = 70
        elif level_diff == 0:  # Perfect level match
            level_match = 100
        elif level_diff == 1:  # Slightly overqualified
            level_match = 90
        elif level_diff == 2:  # Somewhat overqualified
            level_match = 80
        else:  # Significantly overqualified
            level_match = 60
            
        # Calculate years match component (0-100)
        years_diff = candidate_years - job_years
        
        if years_diff < -3:  # Significantly less experience
            years_match = 30
        elif years_diff < -1:  # Somewhat less experience
            years_match = 60
        elif years_diff <= 1:  # Almost exact experience match
            years_match = 100
        elif years_diff <= 3:  # Slightly more experience
            years_match = 90
        elif years_diff <= 5:  # Somewhat more experience
            years_match = 80
        else:  # Significantly more experience
            years_match = 70
            
        # Blend level and years match scores (level is more important)
        final_score = (level_match * 0.7) + (years_match * 0.3)
        
        # Add context to score
        if job_level in ['entry', 'junior'] and candidate_level in ['senior', 'lead', 'principal']:
            # Significant overqualification penalty for entry roles
            final_score -= 20
            
        if job_level in ['principal', 'executive'] and candidate_level in ['entry', 'junior']:
            # Significant underqualification penalty for senior roles
            final_score -= 25
            
        return max(min(final_score, 100), 0)  # Ensure score is between 0-100
    
    def calculate_skill_match_score(self, job_skills: List[str], candidate_skills: List[str]) -> Tuple[float, List[str]]:
        """
        Calculate a skill match score between job requirements and candidate skills.
        
        Args:
            job_skills: List of skills required for the job
            candidate_skills: List of skills the candidate possesses
            
        Returns:
            Tuple of (score, matching_skills)
        """
        if not job_skills or not candidate_skills:
            return 30.0, []
            
        # Normalize skills for comparison
        job_skills_norm = [s.lower().strip() for s in job_skills]
        candidate_skills_norm = [s.lower().strip() for s in candidate_skills]
        
        # Find exact matches
        exact_matches = []
        partial_matches = []
        
        for job_skill in job_skills_norm:
            if not job_skill:  # Skip empty skills
                continue
                
            # Check for exact match
            if job_skill in candidate_skills_norm:
                exact_matches.append(job_skill)
            else:
                # Check for partial matches (fuzzy matching)
                for candidate_skill in candidate_skills_norm:
                    # Check if one skill contains the other
                    if (job_skill in candidate_skill or candidate_skill in job_skill) and abs(len(job_skill) - len(candidate_skill)) <= 3:
                        partial_matches.append(job_skill)
                        break
        
        # Calculate score based on matches
        total_required = len(job_skills_norm)
        exact_score = (len(exact_matches) / total_required) * 100 if total_required > 0 else 0
        partial_score = (len(partial_matches) / total_required) * 50 if total_required > 0 else 0  # Partial matches worth 50%
        
        # Combine scores with appropriate weighting
        combined_score = exact_score + partial_score
        
        # Add bonus for having more skills than required
        if len(exact_matches) + len(partial_matches) >= total_required * 0.8:
            combined_score *= 1.1  # 10% bonus for high skill coverage
            
        # Ensure score doesn't exceed 100
        final_score = min(combined_score, 100.0)
        
        # Return original skill names (not normalized) for the matches
        original_matches = []
        for match in exact_matches + partial_matches:
            for orig_skill in job_skills:
                if match == orig_skill.lower().strip():
                    original_matches.append(orig_skill)
                    break
        
        logger.debug(f"Skill match: {len(exact_matches)} exact + {len(partial_matches)} partial out of {total_required} required = {final_score:.1f}%")
        return final_score, original_matches
    
    def apply_cross_domain_skill_penalty(self, skill_score: float, job_title: str, candidate_position: str) -> float:
        """
        Apply penalty to skill scores when roles are from different domains.
        Cross-domain technical skills should be heavily discounted.
        
        Args:
            skill_score: Original skill match score
            job_title: Job title
            candidate_position: Candidate position
            
        Returns:
            Adjusted skill score with cross-domain penalty applied
        """
        job_title = job_title.lower() if job_title else ""
        candidate_position = candidate_position.lower() if candidate_position else ""
        
        # Define role categories (same as in role matching)
        role_categories = {
            'data_science': ['data scientist', 'data analyst', 'machine learning', 'ai researcher', 'statistician', 'analytics', 'data engineer', 'ml engineer'],
            'software_engineering': ['software engineer', 'software developer', 'backend developer', 'frontend developer', 'full stack', 'devops', 'sre', 'platform engineer'],
            'product_management': ['product manager', 'product owner', 'business analyst'],
            'design': ['ux designer', 'ui designer', 'graphic designer', 'design'],
            'sales_marketing': ['sales', 'marketing', 'account manager', 'business development'],
            'finance': ['financial analyst', 'accountant', 'finance', 'controller'],
            'operations': ['operations', 'project manager', 'program manager'],
            'executive': ['ceo', 'cto', 'cio', 'vp', 'director', 'chief']
        }
        
        # Moderately incompatible pairs that should have skill penalties
        incompatible_skill_domains = [
            ('data_science', 'software_engineering'),
            ('product_management', 'software_engineering'),
            ('data_science', 'operations'),
            ('software_engineering', 'operations')
        ]
        
        # Enhanced role detection - normalize titles to handle prefixes
        def normalize_title(title):
            """Remove common prefixes and suffixes to improve matching"""
            # Remove common prefixes
            prefixes = ['senior', 'sr', 'lead', 'principal', 'staff', 'junior', 'jr', 'entry', 'associate', 'chief', 'director', 'head of', 'vp', 'vice president']
            # Remove common suffixes
            suffixes = ['i', 'ii', 'iii', 'iv', 'v', '1', '2', '3', '4', '5']
            
            normalized = title.lower().strip()
            
            # Remove prefixes
            for prefix in prefixes:
                if normalized.startswith(prefix + ' '):
                    normalized = normalized[len(prefix + ' '):].strip()
                    logger.debug(f"[CrossDomainDebug] Removed prefix '{prefix}' from '{title}' → '{normalized}'")
                    break
            
            # Remove suffixes
            for suffix in suffixes:
                if normalized.endswith(' ' + suffix):
                    normalized = normalized[:-len(' ' + suffix)].strip()
                    logger.debug(f"[CrossDomainDebug] Removed suffix '{suffix}' from title → '{normalized}'")
                    break
            
            return normalized
        
        # Normalize titles for better matching
        job_title_norm = normalize_title(job_title)
        candidate_position_norm = normalize_title(candidate_position)
        
        logger.debug(f"[CrossDomainDebug] Original titles - Job: '{job_title}' | Candidate: '{candidate_position}'")
        logger.debug(f"[CrossDomainDebug] Normalized titles - Job: '{job_title_norm}' | Candidate: '{candidate_position_norm}'")
        
        # Determine role categories
        job_category = None
        candidate_category = None
        
        for category, keywords in role_categories.items():
            if any(keyword in job_title_norm for keyword in keywords):
                job_category = category
                logger.debug(f"[CrossDomainDebug] Job category detected: {category} (matched: {[kw for kw in keywords if kw in job_title_norm]})")
                break
                
        for category, keywords in role_categories.items():
            if any(keyword in candidate_position_norm for keyword in keywords):
                candidate_category = category
                logger.debug(f"[CrossDomainDebug] Candidate category detected: {category} (matched: {[kw for kw in keywords if kw in candidate_position_norm]})")
                break
        
        # Apply skill penalty for cross-domain roles
        if (job_category and candidate_category and 
            ((job_category, candidate_category) in incompatible_skill_domains or 
             (candidate_category, job_category) in incompatible_skill_domains)):
            
            # Heavy penalty for cross-domain skill matches
            penalty_factor = 0.3  # Reduce skill relevance by 70% (more aggressive)
            adjusted_score = skill_score * penalty_factor
            logger.info(f"[CrossDomainDebug] Cross-domain skill penalty applied: {skill_score:.1f}% → {adjusted_score:.1f}% for {job_category} vs {candidate_category}")
            return adjusted_score
        
        logger.debug(f"[CrossDomainDebug] No cross-domain penalty applied - Job: {job_category}, Candidate: {candidate_category}")
        return skill_score
    
    def calculate_role_match_score(self, job_title: str, job_description: str, candidate_position: str) -> float:
        """
        Calculate a role match score between job and candidate position using semantic similarity.
        Enhanced with role category penalties for fundamentally different roles.
        
        Args:
            job_title: Job title
            job_description: Job description (unused, kept for signature consistency)
            candidate_position: Candidate's current position
            
        Returns:
            Match score between 0-100
        """
        job_title = job_title.lower() if job_title else ""
        candidate_position = candidate_position.lower() if candidate_position else ""
        
        logger.debug(f"[RoleMatchDebug] Calculating role match - Job: '{job_title}' vs Candidate: '{candidate_position}'")
        
        if not job_title or not candidate_position:
            logger.debug("[RoleMatchDebug] Role match score defaulting due to missing title.")
            return 30.0  # Default score if missing data

        # Enhanced role detection - normalize titles to handle prefixes
        def normalize_title(title):
            """Remove common prefixes and suffixes to improve matching"""
            # Remove common prefixes
            prefixes = ['senior', 'sr', 'lead', 'principal', 'staff', 'junior', 'jr', 'entry', 'associate', 'chief', 'director', 'head of', 'vp', 'vice president']
            # Remove common suffixes
            suffixes = ['i', 'ii', 'iii', 'iv', 'v', '1', '2', '3', '4', '5']
            
            normalized = title.lower().strip()
            
            # Remove prefixes
            for prefix in prefixes:
                if normalized.startswith(prefix + ' '):
                    normalized = normalized[len(prefix + ' '):].strip()
                    logger.debug(f"[RoleMatchDebug] Removed prefix '{prefix}' from '{title}' → '{normalized}'")
                    break
            
            # Remove suffixes
            for suffix in suffixes:
                if normalized.endswith(' ' + suffix):
                    normalized = normalized[:-len(' ' + suffix)].strip()
                    logger.debug(f"[RoleMatchDebug] Removed suffix '{suffix}' from title → '{normalized}'")
                    break
            
            return normalized

        # Define role categories and incompatible role pairs
        role_categories = {
            'data_science': ['data scientist', 'data analyst', 'machine learning', 'ai researcher', 'statistician', 'analytics', 'data engineer', 'ml engineer', 'research scientist'],
            'software_engineering': ['software engineer', 'software developer', 'backend developer', 'frontend developer', 'full stack', 'devops', 'sre', 'platform engineer', 'systems engineer'],
            'product_management': ['product manager', 'product owner', 'business analyst'],
            'design': ['ux designer', 'ui designer', 'graphic designer', 'design'],
            'sales_marketing': ['sales', 'marketing', 'account manager', 'business development'],
            'finance': ['financial analyst', 'accountant', 'finance', 'controller'],
            'operations': ['operations', 'project manager', 'program manager'],
            'executive': ['ceo', 'cto', 'cio', 'vp', 'director', 'chief']
        }
        
        # Highly incompatible role pairs (apply significant penalty)
        incompatible_pairs = [
            ('data_science', 'sales_marketing'),
            ('data_science', 'design'), 
            ('software_engineering', 'sales_marketing'),
            ('software_engineering', 'finance'),
            ('design', 'finance'),
            ('design', 'software_engineering')
        ]
        
        # Moderately incompatible pairs (apply moderate penalty) - KEY FIX HERE
        moderate_incompatible_pairs = [
            ('data_science', 'software_engineering'),  # This is the key one for the issue!
            ('product_management', 'software_engineering'),
            ('data_science', 'operations'),
            ('software_engineering', 'operations')
        ]
        
        # Normalize titles for better matching
        job_title_norm = normalize_title(job_title)
        candidate_position_norm = normalize_title(candidate_position)
        
        logger.debug(f"[RoleMatchDebug] Normalized - Job: '{job_title_norm}' | Candidate: '{candidate_position_norm}'")
        
        # Determine role categories
        job_category = None
        candidate_category = None
        
        for category, keywords in role_categories.items():
            if any(keyword in job_title_norm for keyword in keywords):
                job_category = category
                matched_keywords = [kw for kw in keywords if kw in job_title_norm]
                logger.debug(f"[RoleMatchDebug] Job category: {category} (matched: {matched_keywords})")
                break
                
        for category, keywords in role_categories.items():
            if any(keyword in candidate_position_norm for keyword in keywords):
                candidate_category = category
                matched_keywords = [kw for kw in keywords if kw in candidate_position_norm]
                logger.debug(f"[RoleMatchDebug] Candidate category: {category} (matched: {matched_keywords})")
                break
        
        # Calculate base semantic similarity
        base_score = 30.0  # Default fallback
        
        if self.embedding_model:
            try:
                vec1 = self.embedding_model.embed_query(job_title)
                vec2 = self.embedding_model.embed_query(candidate_position)

                # Reshape for cosine_similarity function
                vec1 = np.array(vec1).reshape(1, -1)
                vec2 = np.array(vec2).reshape(1, -1)

                # Calculate cosine similarity and scale to 0-100
                similarity = cosine_similarity(vec1, vec2)[0][0]
                base_score = float(similarity * 100)
                logger.debug(f"[RoleMatchDebug] Semantic similarity: {similarity:.3f} → {base_score:.2f}%")
            except Exception as e:
                logger.warning(f"[RoleMatchDebug] Could not calculate semantic role similarity: {e}")
        
        # Apply category-based penalties
        final_score = base_score
        
        if job_category and candidate_category:
            logger.debug(f"[RoleMatchDebug] Comparing categories: {job_category} vs {candidate_category}")
            
            # Check for highly incompatible roles
            if ((job_category, candidate_category) in incompatible_pairs or 
                (candidate_category, job_category) in incompatible_pairs):
                final_score = min(final_score * 0.15, 12.0)  # Cap at 12% for highly incompatible (more aggressive)
                logger.info(f"[RoleMatchDebug] HIGH INCOMPATIBILITY penalty: {base_score:.2f}% → {final_score:.2f}% ({job_category} vs {candidate_category})")
                
            # Check for moderately incompatible roles - CRITICAL FIX
            elif ((job_category, candidate_category) in moderate_incompatible_pairs or 
                  (candidate_category, job_category) in moderate_incompatible_pairs):
                final_score = min(final_score * 0.2, 20.0)  # Much more aggressive: Cap at 20% for moderately incompatible  
                logger.info(f"[RoleMatchDebug] MODERATE INCOMPATIBILITY penalty: {base_score:.2f}% → {final_score:.2f}% ({job_category} vs {candidate_category})")
                
            # Same category bonus
            elif job_category == candidate_category:
                final_score = min(final_score * 1.3, 100.0)  # Increased boost for same category
                logger.debug(f"[RoleMatchDebug] SAME CATEGORY bonus: {base_score:.2f}% → {final_score:.2f}% ({job_category})")
        else:
            logger.debug(f"[RoleMatchDebug] No category detected - Job: {job_category}, Candidate: {candidate_category}")
        
        logger.info(f"[RoleMatchDebug] FINAL role match score: {final_score:.2f}% (Job: '{job_title}' vs Candidate: '{candidate_position}')")
        return max(min(final_score, 100.0), 0.0)
    
    def generate_match_explanation(self, job, candidate, matching_skills, 
                             role_score, skill_score, experience_score) -> str:
        logger.debug(f"[MatchDebug] Candidate: {getattr(candidate, 'first_name', '')} {getattr(candidate, 'last_name', '')} | Position: {getattr(candidate, 'current_position', None) or getattr(candidate, 'position_applied', None) or 'Unknown'} | Role Score: {role_score} | Skill Score: {skill_score} | Experience Score: {experience_score}")
        """
        Generate a human-readable explanation of the match.
        
        Args:
            job: Job object
            candidate: Candidate object
            matching_skills: List of matching skills
            role_score: Role match score
            skill_score: Skill match score
            experience_score: Experience match score
            
        Returns:
            Explanation string
        """
        explanation_parts = []
        
        # Role match part
        if role_score >= 90:
            explanation_parts.append(f"Excellent role alignment between {getattr(candidate, 'current_position') or getattr(candidate, 'position_applied') or 'Unknown'} and {job.title}")
        elif role_score >= 70:
            explanation_parts.append(f"Good role alignment: {getattr(candidate, 'current_position') or getattr(candidate, 'position_applied') or 'Unknown'} relates well to {job.title}")
        elif role_score >= 50:
            explanation_parts.append(f"Moderate role fit between {getattr(candidate, 'current_position') or getattr(candidate, 'position_applied') or 'Unknown'} and {job.title}")
        else:
            explanation_parts.append(f"Limited role alignment: {getattr(candidate, 'current_position') or getattr(candidate, 'position_applied') or 'Unknown'} is different from {job.title}")
            
        # Skill match part
        if matching_skills:
            if len(matching_skills) > 5:
                skills_text = f"Matches {len(matching_skills)} required skills including {', '.join(matching_skills[:5])}..."
            else:
                skills_text = f"Matches {len(matching_skills)} required skills: {', '.join(matching_skills)}"
            explanation_parts.append(skills_text)
        else:
            explanation_parts.append("No direct skill matches identified")
            
        # Experience match part
        candidate_position = getattr(candidate, 'current_position', None) or getattr(candidate, 'position_applied', None) or ''
        candidate_level, candidate_years = self.extract_experience_level(candidate_position)
        job_level, job_years = self.extract_experience_level(job.title + " " + (job.required_qualifications or ""))
        
        if experience_score >= 90:
            explanation_parts.append(f"Ideal experience level: {candidate_level.title()} level ({candidate_years} years)")
        elif experience_score >= 70:
            explanation_parts.append(f"Good experience match at {candidate_level.title()} level")
        elif experience_score >= 50:
            if candidate_years > job_years:
                explanation_parts.append(f"May be overqualified with {candidate_years} years experience")
            else:
                explanation_parts.append(f"Acceptable experience match at {candidate_level.title()} level")
        else:
            if candidate_years < job_years:
                explanation_parts.append(f"Experience gap: {candidate_years} years vs {job_years} years required")
            else:
                explanation_parts.append(f"Experience level mismatch for this role")
                
        return ". ".join(explanation_parts)
    
    def calculate_job_similarity(self, job1, job2) -> Tuple[float, str]:
        """
        Calculate similarity between two jobs with a detailed explanation.
        
        Args:
            job1: First job object
            job2: Second job object
            
        Returns:
            Tuple of (similarity_score, explanation)
        """
        similarity_components = {}
        explanation_parts = []
        
        # 1. Title similarity
        title1 = job1.title.lower() if hasattr(job1, 'title') and job1.title else ""
        title2 = job2.title.lower() if hasattr(job2, 'title') and job2.title else ""
        
        title_score = 0.0
        if title1 and title2:
            # Extract "core role" from titles
            role_terms = ["engineer", "developer", "manager", "designer", "analyst", 
                         "scientist", "specialist", "director", "consultant"]
            
            role1 = next((term for term in role_terms if term in title1), None)
            role2 = next((term for term in role_terms if term in title2), None)
            
            if role1 and role2 and role1 == role2:
                title_score = 1.0
                explanation_parts.append(f"Same core role: {role1}")
            elif role1 and role2:
                # Compare role similarity
                related_roles = {
                    "engineer": ["developer"],
                    "developer": ["engineer"],
                    "manager": ["director", "lead"],
                    "director": ["manager", "lead"],
                    "designer": ["specialist"],
                    "analyst": ["scientist", "specialist"],
                    "scientist": ["analyst", "engineer"]
                }
                
                if role2 in related_roles.get(role1, []):
                    title_score = 0.7
                    explanation_parts.append(f"Related roles: {role1} and {role2}")
                else:
                    title_score = 0.3
                    explanation_parts.append(f"Different roles: {role1} and {role2}")
            else:
                # Fallback to text similarity
                title_words1 = set(title1.split())
                title_words2 = set(title2.split())
                common_words = title_words1.intersection(title_words2)
                
                if common_words:
                    title_score = len(common_words) / max(len(title_words1), len(title_words2))
                    if title_score > 0.5:
                        explanation_parts.append("Similar job titles")
                
        similarity_components["title"] = title_score
        
        # 2. Skill overlap
        job1_skills = job1.skills if hasattr(job1, 'skills') and job1.skills else []
        job2_skills = job2.skills if hasattr(job2, 'skills') and job2.skills else []
        
        skill_score = 0.0
        if job1_skills and job2_skills:
            # Normalize skills
            if isinstance(job1_skills, str):
                job1_skills = [s.strip() for s in job1_skills.split(",")]
            if isinstance(job2_skills, str):
                job2_skills = [s.strip() for s in job2_skills.split(",")]
                
            job1_skills = [s.lower() for s in job1_skills]
            job2_skills = [s.lower() for s in job2_skills]
            
            common_skills = set(job1_skills).intersection(set(job2_skills))
            total_skills = set(job1_skills).union(set(job2_skills))
            
            if total_skills:
                skill_score = len(common_skills) / len(total_skills)
                
                if common_skills:
                    if len(common_skills) > 3:
                        explanation_parts.append(f"Share {len(common_skills)} skills including {', '.join(list(common_skills)[:3])}...")
                    else:
                        explanation_parts.append(f"Share skills: {', '.join(common_skills)}")
                else:
                    explanation_parts.append("No overlapping skills detected")
        
        similarity_components["skills"] = skill_score
        
        # 3. Department match
        dept_score = 0.0
        dept1 = job1.department.lower() if hasattr(job1, 'department') and job1.department else ""
        dept2 = job2.department.lower() if hasattr(job2, 'department') and job2.department else ""
        
        if dept1 and dept2:
            if dept1 == dept2:
                dept_score = 1.0
                explanation_parts.append(f"Same department: {dept1}")
            else:
                # Check for related departments
                related_depts = {
                    "engineering": ["product", "development", "technology", "it"],
                    "product": ["engineering", "design", "marketing"],
                    "marketing": ["sales", "product", "design"],
                    "sales": ["marketing", "business"],
                    "design": ["product", "marketing", "ux", "ui"],
                    "finance": ["accounting", "operations"],
                    "hr": ["operations", "people"]
                }
                
                if dept2 in related_depts.get(dept1, []) or dept1 in related_depts.get(dept2, []):
                    dept_score = 0.6
                    explanation_parts.append(f"Related departments: {dept1} and {dept2}")
                else:
                    dept_score = 0.3
        
        similarity_components["department"] = dept_score
        
        # 4. Location match if available
        loc_score = 0.0
        loc1 = job1.location.lower() if hasattr(job1, 'location') and job1.location else ""
        loc2 = job2.location.lower() if hasattr(job2, 'location') and job2.location else ""
        
        if loc1 and loc2:
            if loc1 == loc2:
                loc_score = 1.0
                explanation_parts.append(f"Same location: {loc1}")
            else:
                # Check if the locations are in the same region/country
                loc1_parts = [p.strip() for p in loc1.split(",")]
                loc2_parts = [p.strip() for p in loc2.split(",")]
                
                # Check for any common location parts (city, state, country)
                common_loc_parts = set(loc1_parts).intersection(set(loc2_parts))
                if common_loc_parts:
                    loc_score = 0.7
                    explanation_parts.append(f"Related locations (same {'/'.join(common_loc_parts)})")
                else:
                    loc_score = 0.3
        
        similarity_components["location"] = loc_score
        
        # Final weighted score calculation
        weights = {
            "title": 0.35,
            "skills": 0.40,
            "department": 0.15,
            "location": 0.10
        }
        
        total_score = sum(score * weights[component] for component, score in similarity_components.items())
        
        # If no significant explanation was generated, add a generic one
        if not explanation_parts:
            if total_score > 0.7:
                explanation_parts.append("Strong overall job profile match")
            elif total_score > 0.5:
                explanation_parts.append("Moderate job similarity")
            else:
                explanation_parts.append("Limited similarity between job profiles")
                
        # Join all explanation parts
        explanation = ". ".join(explanation_parts)
        
        return total_score * 100, explanation  # Convert to 0-100 scale
