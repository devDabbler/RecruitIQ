"""
ResumeParser class moved here to decouple from parser.py and resolve circular imports.
"""
from typing import Any, Optional, TYPE_CHECKING, Dict, List
import logging
from .models.resume_schema import (
    ResumeData, PersonalInfo, Education, Experience,
    Skill, Project, Certification, Language
)
from .processors.base_processor import BaseProcessor
from .processors.ocr_processor import OCRProcessor
from .processors.markdown_processor import MarkdownProcessor
from .processors.section_classifier_processor import SectionClassifierProcessor
from .extractors.base_extractor import BaseExtractor
from .extractors.nlp_extractor import NLPExtractor
from .extractors.model_extractor import ModelExtractor
from .extractors.regex_extractor import RegexExtractor, extract_education_blocks, extract_experience_blocks
from .experience_utils import normalize_experience_entry, merge_and_deduplicate_experience, normalize_education_entry, merge_and_deduplicate_education
if TYPE_CHECKING:
    from backend.services.nebius_ai_service import NebiusAIService
from pydantic import ValidationError
import re
import os
from backend.utils.resume_parsing.exceptions import ParsingError

# --- Utility: Centralized text cleaning ---
def clean_resume_text(text: str) -> str:
    """Clean and normalize resume text for LLM and extractors, preserving newlines and bullet structure."""
    if not text:
        return ""
    
    # Step 1: First process bullet points at beginning of lines
    # Remove bullet point characters from beginning of lines but remember their positions
    bullet_line_indices = []
    lines = text.splitlines()
    processed_lines = []
    
    for i, line in enumerate(lines):
        # Check for bullet points at start of line (with optional whitespace)
        if re.match(r'^\s*[-*•·▪◦‣❖]\s+', line):
            # Remove the bullet character and leading whitespace, preserving content
            processed_line = re.sub(r'^\s*[-*•·▪◦‣❖]\s+', '', line)
            processed_lines.append(processed_line)
            bullet_line_indices.append(i)
        else:
            processed_lines.append(line)
    
    # Step 2: Handle inline bullet separators
    result_lines = []
    for i, line in enumerate(processed_lines):
        # Split line on bullet point separators surrounded by whitespace
        # This handles patterns like "Item 1 - Item 2 * Item 3"
        parts = re.split(r'\s+[-*•·▪◦‣❖]\s+', line)
        
        if len(parts) > 1:
            # Line contains inline bullet separators
            # Add each part as a separate line to result_lines instead of joining them
            for p in parts:
                if p.strip():
                    result_lines.append(p.strip())
        else:
            # No inline separators, keep the line as is
            result_lines.append(line)
    
    # Step 3: Clean up each line
    cleaned_lines = []
    for line in result_lines:
        # Remove JSON brackets and other noise characters
        line = re.sub(r'[\{\}\[\]]', '', line)
        
        # Normalize unicode characters
        line = line.replace('\u2013', '-').replace('\u2014', '--').replace("\u2019", "'")
        
        # Remove non-ASCII characters (but preserve newlines)
        line = re.sub(r'[^\x00-\x7F\n]+', ' ', line)
        
        # Normalize whitespace within the line (but don't strip empty lines)
        if line.strip():
            line = re.sub(r'\s+', ' ', line).strip()
        
        # Add all lines, including empty ones to preserve spacing
        cleaned_lines.append(line)
    
    # Join the lines with newlines
    return '\n'.join(cleaned_lines)


# --- Utility: Token counting ---
def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken if available, else fallback to word count."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text))
    except Exception:
        # Fallback: count words as a rough proxy
        return len(text.split())

logger = logging.getLogger(__name__)

class ResumeParser:
    """
    Main resume parser orchestrator that coordinates between different parsing strategies.
    """
    def __init__(self, storage_service: Any, llm_service: Any, nebius_ai_service: "NebiusAIService", config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.storage_service = storage_service
        self.llm_service = llm_service
        self.nebius_ai_service = nebius_ai_service
        self.processors = [
            OCRProcessor(),
            MarkdownProcessor(),
            SectionClassifierProcessor()
        ]
        self.extractors = [
            NLPExtractor(llm_service),
            ModelExtractor(llm_service),
            RegexExtractor()
        ]
        # Initialize cache
        from backend.utils.cache.local_cache import LocalCache
        self.cache = LocalCache()

    def _extract_personal_info_bulletproof(self, text: str) -> PersonalInfo:
        """
        Bulletproof personal info extraction from the first 10 lines of resume text.
        Always runs and always returns valid personal info.
        """
        self.logger.info("[PERSONAL_INFO] Starting bulletproof personal info extraction")
        
        # Get first 10 lines for header analysis
        lines = text.split('\n')[:10]
        header_text = '\n'.join(lines)
        self.logger.info(f"[PERSONAL_INFO] Analyzing header text (first 10 lines): {repr(header_text[:200])}")
        
        # Initialize personal info
        personal_info = PersonalInfo()
        
        # 1. Extract email (most reliable)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, header_text)
        if email_match:
            personal_info.email = email_match.group(0)
            self.logger.info(f"[PERSONAL_INFO] Found email: {personal_info.email}")
        
        # 2. Extract phone number
        phone_patterns = [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 123-456-7890
            r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b',  # (123) 456-7890
            r'\b\d{10}\b',  # 1234567890
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, header_text)
            if phone_match:
                personal_info.phone = phone_match.group(0)
                self.logger.info(f"[PERSONAL_INFO] Found phone: {personal_info.phone}")
                break
        
        # 3. Extract LinkedIn URL
        linkedin_patterns = [
            r'linkedin\.com/in/[A-Za-z0-9_-]+',
            r'linkedin\.com/profile/[A-Za-z0-9_-]+',
            r'www\.linkedin\.com/in/[A-Za-z0-9_-]+',
            r'www\.linkedin\.com/profile/[A-Za-z0-9_-]+',
        ]
        for pattern in linkedin_patterns:
            linkedin_match = re.search(pattern, header_text)
            if linkedin_match:
                linkedin_url = linkedin_match.group(0)
                if not linkedin_url.startswith('http'):
                    linkedin_url = 'https://' + linkedin_url
                personal_info.linkedin = linkedin_url
                self.logger.info(f"[PERSONAL_INFO] Found LinkedIn: {personal_info.linkedin}")
                break
        
        # 4. Extract name (most challenging - use multiple strategies)
        name = None
        
        # Strategy 1: Look for the first line that doesn't contain email/phone/URL and has 2-3 words
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove markdown headers first
            clean_line = re.sub(r'^#+\s*', '', line).strip()
            
            # Skip lines with email, phone, or URLs
            if re.search(email_pattern, clean_line) or re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', clean_line) or re.search(r'http|www|linkedin|github', clean_line, re.I):
                continue
            
            # Skip lines that are too short or too long
            if len(clean_line) < 3 or len(clean_line) > 50:
                continue
            
            # Skip lines that are all caps (likely section headers) unless they look like names
            if clean_line.isupper() and len(clean_line) > 15:
                continue
            
            # Look for 2-3 word patterns that could be names
            words = clean_line.split()
            if 2 <= len(words) <= 3:
                # Check if words look like names (not all caps, reasonable length)
                if all(1 < len(word) < 20 for word in words) and not all(word.isupper() for word in words):
                    # Additional check: ensure it's not a common section header
                    if clean_line.lower() not in ['profile summary', 'work experience', 'professional experience', 'contact information']:
                        name = clean_line
                        self.logger.info(f"[PERSONAL_INFO] Found name via line analysis: {name}")
                        break
        
        # Strategy 2: If no name found, try to extract from email
        if not name and personal_info.email:
            email_name = personal_info.email.split('@')[0]
            # Convert email name to proper name format
            name_parts = email_name.replace('.', ' ').replace('_', ' ').replace('-', ' ').split()
            if len(name_parts) >= 2:
                name = ' '.join(name_parts[:2]).title()
                self.logger.info(f"[PERSONAL_INFO] Extracted name from email: {name}")
        
        # Strategy 3: Look for common name patterns in the first few lines
        if not name:
            for line in lines[:3]:
                # Remove markdown headers
                clean_line = re.sub(r'^#+\s*', '', line).strip()
                # Look for "FirstName LastName" pattern
                name_match = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', clean_line)
                if name_match:
                    name = f"{name_match.group(1)} {name_match.group(2)}"
                    self.logger.info(f"[PERSONAL_INFO] Found name via pattern matching: {name}")
                    break
        
        if name:
            personal_info.name = name
        
        # 5. Extract location/address
        # Look for city, state pattern
        location_patterns = [
            r'\b([A-Za-z\s]+),\s*([A-Z]{2})\b',  # City, State
            r'\b([A-Za-z\s]+),\s*([A-Za-z\s]+),\s*([A-Z]{2})\b',  # City, State, Country
        ]
        for pattern in location_patterns:
            location_match = re.search(pattern, header_text)
            if location_match:
                location = location_match.group(0)
                personal_info.location = location
                self.logger.info(f"[PERSONAL_INFO] Found location: {personal_info.location}")
                break
        
        # 6. Extract full address if available
        address_pattern = r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Place|Pl|Court|Ct|Way|Terrace|Ter)'
        address_match = re.search(address_pattern, header_text, re.I)
        if address_match:
            personal_info.address = address_match.group(0)
            self.logger.info(f"[PERSONAL_INFO] Found address: {personal_info.address}")
        
        # 7. Extract website
        website_patterns = [
            r'https?://[^\s]+',
            r'www\.[^\s]+',
        ]
        for pattern in website_patterns:
            website_match = re.search(pattern, header_text)
            if website_match:
                website = website_match.group(0)
                # Don't include LinkedIn as website
                if 'linkedin' not in website.lower():
                    if not website.startswith('http'):
                        website = 'https://' + website
                    personal_info.website = website
                    self.logger.info(f"[PERSONAL_INFO] Found website: {personal_info.website}")
                    break
        
        # Ensure we have at least a name
        if not personal_info.name:
            personal_info.name = "Unknown"
            self.logger.warning("[PERSONAL_INFO] Could not extract name, using 'Unknown'")
        
        self.logger.info(f"[PERSONAL_INFO] Final personal info: name='{personal_info.name}', email='{personal_info.email}', phone='{personal_info.phone}', location='{personal_info.location}'")
        return personal_info

    def _validate_experience_entry(self, exp: dict) -> bool:
        """
        Validate if an experience entry is actually a real job.
        Returns True if it's a valid job entry, False otherwise.
        """
        # Must have both title and company
        if not exp.get('title') or not exp.get('company'):
            return False
        
        title = str(exp.get('title', '')).strip()
        company = str(exp.get('company', '')).strip()
        
        # Skip if title or company is too short
        if len(title) < 2 or len(company) < 2:
            return False
        
        # Skip if title or company is too long (likely contains description)
        if len(title) > 100 or len(company) > 100:
            return False
        
        # Skip common non-job patterns
        skip_patterns = [
            'unknown', 'position', 'company', 'title', 'name', 'email', 'phone',
            'address', 'location', 'linkedin', 'github', 'website', 'summary',
            'objective', 'skills', 'education', 'experience', 'projects',
            'certifications', 'languages', 'references', 'contact'
        ]
        
        title_lower = title.lower()
        company_lower = company.lower()
        
        for pattern in skip_patterns:
            if pattern in title_lower or pattern in company_lower:
                return False
        
        # Skip if it looks like contact info
        if re.search(r'@|http|www|linkedin|github', title + ' ' + company, re.I):
            return False
        
        # Skip if it looks like a section header
        if title.isupper() and len(title) > 10:
            return False
        
        # Must have at least one date or some description content
        has_date = bool(exp.get('start_date') or exp.get('end_date'))
        has_description = bool(exp.get('description') and len(str(exp.get('description', ''))) > 10)
        
        if not has_date and not has_description:
            return False
        
        return True

    def _validate_education_entry(self, edu: dict) -> bool:
        """
        Validate if an education entry is actually a real education entry.
        Returns True if it's valid, False otherwise.
        """
        # Must have institution
        if not edu.get('institution'):
            return False
        
        institution = str(edu.get('institution', '')).strip()
        
        # Skip if institution is too short or too long
        if len(institution) < 3 or len(institution) > 100:
            return False
        
        # Skip common non-education patterns
        skip_patterns = [
            'unknown', 'institution', 'school', 'university', 'college',
            'education', 'degree', 'field', 'study', 'gpa', 'location',
            'date', 'year', 'graduation', 'academic'
        ]
        
        institution_lower = institution.lower()
        for pattern in skip_patterns:
            if pattern in institution_lower and len(institution) < 20:
                return False
        
        # Must have at least degree or some description
        has_degree = bool(edu.get('degree') and len(str(edu.get('degree', ''))) > 2)
        has_description = bool(edu.get('description') and len(str(edu.get('description', ''))) > 10)
        
        if not has_degree and not has_description:
            return False
        
        return True
    
    def _apply_final_cleanup(self, resume_data: 'ResumeData') -> 'ResumeData':
        """Apply final cleanup to resume data before returning"""
        if not resume_data:
            self.logger.warning("No resume data to clean up")
            return resume_data
            
        try:
            self.logger.info("[CLEANUP] Applying final cleanup to resume data")
            
            # --- Clean up personal info ---
            if resume_data.personal_info:
                # Normalize name to title case if it exists
                if resume_data.personal_info.name:
                    # Special handling for names with McX or O'X patterns
                    name = resume_data.personal_info.name.strip()
                    # First convert to title case
                    name = name.title()
                    # Then handle special cases like "McDowell" -> "McDowell" not "Mcdowell"
                    name = re.sub(r'\bMc([a-z])', lambda x: f"Mc{x.group(1).upper()}", name)
                    # Handle O'Name -> O'Name not O'name
                    name = re.sub(r"\bO'([a-z])", lambda x: f"O'{x.group(1).upper()}", name)
                    resume_data.personal_info.name = name
                
                # Normalize email to lowercase
                if resume_data.personal_info.email:
                    resume_data.personal_info.email = resume_data.personal_info.email.lower().strip()
                
                # Format phone numbers consistently
                if resume_data.personal_info.phone:
                    # Remove all non-digit characters
                    phone = re.sub(r'\D', '', resume_data.personal_info.phone)
                    # Format as XXX-XXX-XXXX if it's a 10-digit number
                    if len(phone) == 10:
                        phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
                    resume_data.personal_info.phone = phone
            
            # --- Clean up education ---
            if resume_data.education:
                # Filter out invalid education entries
                valid_education = []
                for edu in resume_data.education:
                    # Check for institution which is required
                    if not edu.institution or len(edu.institution.strip()) < 3:
                        continue
                        
                    # Clean up degree field
                    if edu.degree:
                        edu.degree = edu.degree.strip()
                        # Normalize common degree abbreviations
                        degree_mapping = {
                            "bachelors": "Bachelor's", "bachelor of": "Bachelor of",
                            "masters": "Master's", "master of": "Master of",
                            "phd": "Ph.D.", "doctorate": "Doctorate", 
                            "associates": "Associate's", "associate of": "Associate of"
                        }
                        for key, value in degree_mapping.items():
                            if key in edu.degree.lower():
                                # Replace while preserving the rest of the string
                                edu.degree = re.sub(re.escape(key), value, edu.degree, flags=re.IGNORECASE)
                    
                    # Clean up dates
                    for date_field in ['start_date', 'end_date']:
                        date_value = getattr(edu, date_field, None)
                        if date_value:
                            # Try to convert month names to numbers
                            month_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
                            month_mapping = {
                                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                            }
                            for month_name, month_num in month_mapping.items():
                                if re.search(month_name, date_value.lower()):
                                    # Replace month name with number
                                    date_value = re.sub(
                                        r'\b' + month_name + r'\w*\b', 
                                        month_num, 
                                        date_value, 
                                        flags=re.IGNORECASE
                                    )
                            # Set the cleaned date
                            setattr(edu, date_field, date_value)
                    
                    valid_education.append(edu)
                
                # Update education list
                resume_data.education = valid_education
            
            # --- Clean up experience ---
            if resume_data.experience:
                # Sort experience by start_date (descending/most recent first)
                # Extract years from dates for sorting
                def extract_year(date_str):
                    if not date_str:
                        return 0
                    # Extract 4-digit year
                    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                    if year_match:
                        return int(year_match.group(0))
                    return 0
                
                # Sort by start_date (most recent first)
                resume_data.experience.sort(
                    key=lambda exp: extract_year(exp.start_date) if exp.start_date else 0,
                    reverse=True
                )
                
                # Clean up company and title fields
                for exp in resume_data.experience:
                    # Normalize company field
                    if exp.company:
                        # Remove common suffixes
                        for suffix in [' Inc', ' LLC', ' Ltd', ' Corporation', ' Corp', ' Co', ' Company']:
                            exp.company = re.sub(re.escape(suffix + '$'), '', exp.company, flags=re.IGNORECASE)
                        exp.company = exp.company.strip()
                    
                    # Normalize title field
                    if exp.title:
                        exp.title = exp.title.strip()
                        
                    # Clean up description - remove excessive whitespace
                    if exp.description:
                        # Preserve newlines but normalize spaces
                        lines = exp.description.splitlines()
                        cleaned_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines]
                        exp.description = '\n'.join(line for line in cleaned_lines if line)
            
            # --- Clean up skills ---
            if resume_data.skills:
                # Normalize skill names and remove duplicates
                unique_skills = {}
                for skill in resume_data.skills:
                    if not skill.name:
                        continue
                    # Convert to lowercase for deduplication
                    skill_name = skill.name.strip().lower()
                    # Skip skills that are too short or too long
                    if len(skill_name) < 2 or len(skill_name) > 50:
                        continue
                    # Keep only the first occurrence
                    if skill_name not in unique_skills:
                        unique_skills[skill_name] = skill.name.strip()  # Keep original capitalization
                
                # Rebuild skills list with normalized names
                from backend.utils.resume_parsing.models.resume_schema import Skill
                cleaned_skills = [Skill(name=name) for name in unique_skills.values()]
                resume_data.skills = cleaned_skills
                
                # Sort skills alphabetically
                resume_data.skills.sort(key=lambda x: x.name.lower())
            
            self.logger.info("[CLEANUP] Final cleanup completed successfully")
            return resume_data
        except Exception as e:
            self.logger.error(f"[CLEANUP] Error during final cleanup: {e}")
            # Return original data if cleanup fails
            return resume_data
    
    def _clean_section_for_llm(self, text: str) -> str:
        """Clean section text before sending to LLM"""
        if not text:
            return ""
        
        # Import re at the method level to ensure availability
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove any markdown or formatting artifacts
        text = re.sub(r'##+\s*', '', text)  # Remove markdown headers
        text = re.sub(r'\*\*|__', '', text)  # Remove bold markers
        text = re.sub(r'\*|_', '', text)     # Remove italic markers
        
        # Clean up bullet points for consistency
        text = re.sub(r'^\s*[-*•·▪◦‣❖]\s+', '- ', text, flags=re.MULTILINE)
        
        # Remove URLs and email addresses (often not relevant for parsing)
        text = re.sub(r'https?://\S+|www\.\S+', '[URL]', text)
        text = re.sub(r'\S+@\S+\.\S+', '[EMAIL]', text)
        
        # Normalize newlines
        text = re.sub(r'\n{3,}', '\n\n', text)  # Replace 3+ newlines with just 2
        
        return text.strip()
    
    def _truncate_by_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text by token count, not character count"""
        if not text:
            return ""
            
        # Simple word-based approximation of tokens
        words = text.split()
        if len(words) <= max_tokens:
            return text
            
        # Take approximately max_tokens words
        truncated_text = ' '.join(words[:max_tokens])
        return truncated_text + "..."
    
    def _calculate_confidence_score(self, resume_data: ResumeData) -> dict:
        """
        Calculate confidence scores for different sections of the parsed resume.
        Returns a dictionary with confidence scores and warnings.
        """
        confidence = {
            'overall': 0.0,
            'sections': {},
            'warnings': [],
            'missing_fields': [],
            'parsing_errors': False,
            'fallback_used': False
        }
        
        # Check if fallback extraction was used
        if hasattr(resume_data, 'fallback_used') and resume_data.fallback_used:
            confidence['fallback_used'] = True
            confidence['warnings'].append("Fallback extraction methods were used due to LLM parsing issues")
        
        # Check if there were parsing errors
        if hasattr(resume_data, 'parsing_errors') and resume_data.parsing_errors:
            confidence['parsing_errors'] = True
            confidence['warnings'].append("Errors occurred during parsing that may affect quality")
        
        # Calculate section-specific confidence scores
        section_scores = {}
        
        # Personal info confidence
        personal_info_score = 0.0
        if resume_data.personal_info:
            pi = resume_data.personal_info
            if pi.name and pi.name.strip():
                personal_info_score += 0.3
            if pi.email and pi.email.strip():
                personal_info_score += 0.3
            if pi.phone and pi.phone.strip():
                personal_info_score += 0.2
            if pi.location and pi.location.strip():
                personal_info_score += 0.2
        else:
            confidence['warnings'].append("No personal information extracted")
            confidence['missing_fields'].append('personal_info')
        
        section_scores['personal_info'] = personal_info_score
        
        # Experience confidence
        experience_score = 0.0
        if resume_data.experience and len(resume_data.experience) > 0:
            valid_experience = [exp for exp in resume_data.experience if self._validate_experience_entry(exp.model_dump())]
            if len(valid_experience) > 0:
                experience_score = min(1.0, len(valid_experience) * 0.4)  # Cap at 1.0
                if len(valid_experience) < len(resume_data.experience):
                    confidence['warnings'].append(f"Some experience entries may be incomplete ({len(valid_experience)}/{len(resume_data.experience)} valid)")
            else:
                confidence['warnings'].append("No valid experience entries found")
                confidence['missing_fields'].append('experience')
        else:
            confidence['warnings'].append("No experience information extracted")
            confidence['missing_fields'].append('experience')
        
        section_scores['experience'] = experience_score
        
        # Education confidence
        education_score = 0.0
        if resume_data.education and len(resume_data.education) > 0:
            valid_education = [edu for edu in resume_data.education if self._validate_education_entry(edu.model_dump())]
            if len(valid_education) > 0:
                education_score = min(1.0, len(valid_education) * 0.5)  # Cap at 1.0
                if len(valid_education) < len(resume_data.education):
                    confidence['warnings'].append(f"Some education entries may be incomplete ({len(valid_education)}/{len(resume_data.education)} valid)")
            else:
                confidence['warnings'].append("No valid education entries found")
                confidence['missing_fields'].append('education')
        else:
            confidence['warnings'].append("No education information extracted")
            confidence['missing_fields'].append('education')
        
        section_scores['education'] = education_score
        
        # Skills confidence
        skills_score = 0.0
        if resume_data.skills and len(resume_data.skills) > 0:
            skills_score = min(1.0, len(resume_data.skills) * 0.1)  # Cap at 1.0
            if len(resume_data.skills) < 5:
                confidence['warnings'].append("Few skills detected - consider adding more skills to your resume")
        else:
            confidence['warnings'].append("No skills information extracted")
            confidence['missing_fields'].append('skills')
        
        section_scores['skills'] = skills_score
        
        # Calculate overall confidence
        confidence['sections'] = section_scores
        if section_scores:
            overall_score = sum(section_scores.values()) / len(section_scores)
            
            # Apply penalties for parsing errors and fallback usage
            if confidence['parsing_errors']:
                overall_score = max(0.0, overall_score - 0.3)  # 30% penalty for parsing errors
            if confidence['fallback_used']:
                overall_score = max(0.0, overall_score - 0.2)  # 20% penalty for fallback extraction
            
            # Apply penalty for missing required fields
            missing_critical = any(field in confidence['missing_fields'] 
                                   for field in ['personal_info', 'experience', 'education'])
            if missing_critical:
                overall_score = max(0.0, overall_score - 0.25)  # 25% penalty for missing critical fields
                
            confidence['overall'] = overall_score
        
        # Add specific warnings based on confidence levels
        if confidence['overall'] < 0.5:
            confidence['warnings'].append("Low overall confidence - some sections may be incomplete or missing")
        elif confidence['overall'] < 0.7:
            confidence['warnings'].append("Moderate confidence - review extracted information for accuracy")
        
        return confidence

    async def parse_resume(self, file_path: str, strategy: str = 'fast') -> ResumeData:
        self.logger.info(f"[TRACE] Entered parse_resume for {file_path} with strategy '{strategy}'")
        
        # Generate cache key based on file content
        file_hash = self._get_file_hash(file_path)
        cache_key = f"resume_{file_hash}_{strategy}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            self.logger.info(f"[CACHE] Using cached result for {file_path}")
            return cached_result
        
        try:
            self.logger.info(f"Starting resume parsing for {file_path} with strategy '{strategy}'")
            
            # Process the document through each processor in sequence
            processed_text = file_path
            for processor in self.processors:
                self.logger.info(f"[TRACE] Running processor: {processor.__class__.__name__}")
                processed_text = await processor.process(processed_text)
            
            # Extract text for parsing
            if isinstance(processed_text, dict):
                if 'text' in processed_text:
                    text_for_parsing = processed_text['text']
                elif 'content' in processed_text:
                    text_for_parsing = processed_text['content']
                else:
                    text_parts = []
                    for key, value in processed_text.items():
                        if isinstance(value, str):
                            text_parts.append(value)
                    text_for_parsing = '\n'.join(text_parts)
            else:
                text_for_parsing = str(processed_text)
            
            # Centralized cleaning
            text_for_parsing = clean_resume_text(text_for_parsing)
            
            # ALWAYS extract personal info first using bulletproof method
            self.logger.info("[PERSONAL_INFO] Running bulletproof personal info extraction")
            personal_info = self._extract_personal_info_bulletproof(text_for_parsing)
            
            # Use SectionClassifierProcessor to extract sections
            self.logger.info("[SECTION] Running SectionClassifierProcessor to extract sections")
            section_classifier = SectionClassifierProcessor()
            sections = await section_classifier.process(text_for_parsing)
            
            # Clean each section
            for k in sections:
                if isinstance(sections[k], str):
                    sections[k] = clean_resume_text(sections[k])
            
            # Choose parsing method based on strategy
            if strategy == 'fast':
                try:
                    self.logger.info("Using fast parsing strategy with sectioned LLM calls")
                    
                    # Pre-validate sections before sending to LLM
                    llm_sections = {}
                    for field in ['experience', 'education', 'skills']:
                        if field in sections and sections[field]:
                            # Clean the section
                            cleaned_section = self._clean_section_for_llm(sections[field])
                            # Count tokens BEFORE truncation
                            token_count = count_tokens(cleaned_section)
                            
                            if token_count > 2048:
                                self.logger.warning(f"Section '{field}' has {token_count} tokens, truncating")
                                # Truncate by tokens, not characters
                                cleaned_section = self._truncate_by_tokens(cleaned_section, 2000)
                            
                            llm_sections[field] = cleaned_section
                    
                    # If no sections found, fallback to full text
                    if not llm_sections:
                        self.logger.warning("[SECTION] No relevant sections found, falling back to full resume text for LLM.")
                        llm_sections = {'full_text': self._clean_section_for_llm(text_for_parsing[:3000])}
                        self.logger.info(f"[TOKENS] Full text token count: {count_tokens(llm_sections['full_text'])}")
                    
                    # Call LLM for each section with structured output format
                    schema_prompt = """
                    Extract resume information and return ONLY valid JSON in this exact format:
                    {
                        "personal_info": {"name": "", "email": "", "phone": "", "location": ""},
                        "education": [{"institution": "", "degree": "", "field_of_study": "", "start_date": "", "end_date": ""}],
                        "experience": [{"title": "", "company": "", "start_date": "", "end_date": "", "description": ""}],
                        "skills": [{"name": ""}]
                    }
                    Do not include any text outside the JSON structure.
                    """
                    
                    # Call LLM for each section
                    parsed_fields = {}
                    for field, content in llm_sections.items():
                        self.logger.info(f"[LLM] Calling LLM for section: {field}")
                        
                        try:
                            response = await self.nebius_ai_service.parse_resume(content, schema_prompt)
                            self.logger.debug(f"[LLM] Raw response for {field}: type={type(response)}")
                            
                            # Validate and repair response structure
                            if self._validate_llm_response(response, field):
                                # Ensure response is properly formatted
                                repaired_response = self._repair_llm_response(response, field)
                                parsed_fields[field] = repaired_response
                                self.logger.info(f"[LLM] Successfully processed {field} response")
                            else:
                                self.logger.error(f"[LLM] Invalid response structure for {field}")
                                # No need to track validation errors here - will be handled in exception block
                                raise ValueError(f"Invalid LLM response structure for {field}")
                                
                        except Exception as e:
                            self.logger.error(f"[LLM] Failed to parse {field}: {str(e)}")
                            # Don't continue with other fields if one fails
                            # We'll handle the error in the outer exception block
                            raise

                    # Initialize result dictionary
                    pdict = {'parsing_errors': False}  # Initialize parsing_errors flag
                    
                    # Merge LLM results into a single dict with improved handling
                    for field, result in parsed_fields.items():
                        try:
                            if isinstance(result, dict):
                                # Extract the specific field data
                                if field in result:
                                    pdict[field] = result[field]
                                else:
                                    # If field not in result, look for it in the top level
                                    field_candidates = [k for k in result.keys() if field in k.lower()]
                                    if field_candidates:
                                        pdict[field] = result[field_candidates[0]]
                                    else:
                                        pdict[field] = result  # Use entire result as fallback
                            else:
                                pdict[field] = result
                                
                            self.logger.info(f"[LLM] Merged {field} with {len(pdict[field]) if isinstance(pdict[field], list) else 'N/A'} items")
                            
                        except Exception as e:
                            self.logger.error(f"[LLM] Failed to merge {field} results: {e}")
                            pdict[field] = []  # Provide empty list as fallback
                    
                    # ALWAYS use our bulletproof personal info extraction
                    self.logger.info("[PERSONAL_INFO] Overwriting LLM personal info with bulletproof extraction")
                    pdict['personal_info'] = personal_info.model_dump() if hasattr(personal_info, 'model_dump') else dict(personal_info)
                    
                    # Fallback for missing fields using regex/NLP
                    missing_fields = [f for f in ['skills', 'education', 'experience'] if f not in pdict or not pdict[f]]
                    if missing_fields:
                        self.logger.warning(f"[FALLBACK] LLM output missing fields: {missing_fields}. Running targeted fallback extraction.")
                        regex_extractor = RegexExtractor()
                        nlp_extractor = NLPExtractor(self.llm_service)
                        fallback_sections = {'full_text': text_for_parsing}
                        for field in missing_fields:
                            regex_results = await regex_extractor.extract(fallback_sections)
                            nlp_results = await nlp_extractor.extract(fallback_sections)
                            fallback_value = regex_results.get(field) or nlp_results.get(field)
                            if fallback_value:
                                pdict[field] = fallback_value
                                self.logger.info(f"[FALLBACK] Filled missing '{field}' from fallback extractor.")
                    
                    # Rebuild ResumeData object with improved data
                    from backend.utils.resume_parsing.models.resume_schema import ResumeData
                    parsed_data = ResumeData(**pdict)
                    
                    # Apply final cleanup and validation if method exists
                    if hasattr(self, '_apply_final_cleanup'):
                        parsed_data = self._apply_final_cleanup(parsed_data)
                    
                    # Track if fallback extraction was used
                    if missing_fields:
                        parsed_data.fallback_used = True
                        self.logger.info(f"[CONFIDENCE] Setting fallback_used flag due to missing fields: {missing_fields}")
                    
                    # Calculate confidence score
                    confidence = self._calculate_confidence_score(parsed_data)
                    parsed_data.confidence = confidence
                    
                    # Only enrich with regex extractor if we're missing fields or have low confidence
                    missing_required_fields = (
                        not getattr(parsed_data, 'experience', None) or 
                        not getattr(parsed_data, 'education', None) or 
                        not getattr(parsed_data, 'skills', None) or
                        len(getattr(parsed_data, 'experience', [])) == 0 or
                        len(getattr(parsed_data, 'education', [])) == 0
                    )
                    
                    if missing_required_fields:
                        try:
                            self.logger.info("[TRACE] Enriching with RegexExtractor due to missing required fields")
                            regex_extractor = RegexExtractor()
                            
                            # Extract additional data using regex - only do this once
                            regex_sections = {'full_text': text_for_parsing}
                            regex_results = await regex_extractor.extract(regex_sections)
                            
                            # Merge experience entries only if missing or empty
                            if regex_results.get('experience') and (not hasattr(parsed_data, 'experience') or not parsed_data.experience):
                                regex_experience_blocks = regex_results['experience']
                                # Convert existing experience to dict format if any
                                llm_experience = [e.dict() if hasattr(e, 'dict') else dict(e) for e in getattr(parsed_data, 'experience', []) or []]
                                regex_experience = [e for e in regex_experience_blocks]
                                merged_experience = merge_and_deduplicate_experience(llm_experience, regex_experience)
                                self.logger.info(f"[MERGE] Total experience entries before validation: {len(merged_experience)}")
                                
                                # Validate and sanitize experience entries before creating objects
                                valid_experience = []
                                for exp in merged_experience:
                                    # Use our validation function
                                    if self._validate_experience_entry(exp):
                                        try:
                                            from backend.utils.resume_parsing.models.resume_schema import Experience
                                            exp_obj = Experience(**exp)
                                            valid_experience.append(exp_obj)
                                        except Exception as exp_err:
                                            self.logger.warning(f"Failed to create Experience object: {exp_err}")
                                
                                parsed_data.experience = valid_experience
                                self.logger.info(f"[VALIDATION] Valid experience entries after filtering: {len(valid_experience)}")
                            
                            # Merge education entries only if missing or empty
                            if regex_results.get('education') and (not hasattr(parsed_data, 'education') or not parsed_data.education):
                                regex_education_blocks = regex_results['education']
                                # Convert existing education to dict format if any
                                llm_education = [e.dict() if hasattr(e, 'dict') else dict(e) for e in getattr(parsed_data, 'education', []) or []]
                                regex_education = [e for e in regex_education_blocks]
                                merged_education = merge_and_deduplicate_education(llm_education, regex_education)
                                self.logger.info(f"[MERGE] Total education entries before validation: {len(merged_education)}")
                                
                                # Validate and sanitize education entries before creating objects
                                valid_education = []
                                for edu in merged_education:
                                    # Use our validation function
                                    if self._validate_education_entry(edu):
                                        try:
                                            from backend.utils.resume_parsing.models.resume_schema import Education
                                            edu_obj = Education(**edu)
                                            valid_education.append(edu_obj)
                                        except Exception as edu_err:
                                            self.logger.warning(f"Failed to create Education object: {edu_err}")
                                
                                parsed_data.education = valid_education
                                self.logger.info(f"[VALIDATION] Valid education entries after filtering: {len(valid_education)}")
                            
                            # Merge skills only if missing or empty
                            if regex_results.get('skills') and (not hasattr(parsed_data, 'skills') or not parsed_data.skills):
                                regex_skills = regex_results['skills']
                                llm_skills = getattr(parsed_data, 'skills', []) or []
                                # Combine and deduplicate skills
                                all_skills = []
                                skill_names = set()
                                
                                for skill_list in [llm_skills, regex_skills]:
                                    for skill in skill_list:
                                        if hasattr(skill, 'name'):
                                            skill_name = skill.name.lower().strip()
                                        elif isinstance(skill, dict):
                                            skill_name = skill.get('name', '').lower().strip()
                                        else:
                                            skill_name = str(skill).lower().strip()
                                        
                                        if skill_name and skill_name not in skill_names:
                                            skill_names.add(skill_name)
                                            if hasattr(skill, 'model_dump'):
                                                all_skills.append(skill)
                                            elif isinstance(skill, dict):
                                                from backend.utils.resume_parsing.models.resume_schema import Skill
                                                all_skills.append(Skill(**skill))
                                            else:
                                                from backend.utils.resume_parsing.models.resume_schema import Skill
                                                all_skills.append(Skill(name=str(skill)))
                                parsed_data.skills = all_skills
                                                
                        except Exception as enrich_err:
                            self.logger.error(f"Regex enrichment/merging after fast parse failed: {enrich_err}", exc_info=True)
                            # Continue with parsed data only - don't fail the entire process
                    self.logger.info("Successfully parsed resume with fast approach (enriched and merged)")
                    self.logger.info(f"[FINAL] Personal info: {parsed_data.personal_info.name if parsed_data.personal_info else 'None'}")
                    self.logger.info(f"[FINAL] Experience entries: {len(getattr(parsed_data, 'experience', []))}")
                    self.logger.info(f"[FINAL] Education entries: {len(getattr(parsed_data, 'education', []))}")
                    self.logger.info(f"[FINAL] Skills: {len(getattr(parsed_data, 'skills', []))}")
                    
                    # Log first few entries for debugging
                    if hasattr(parsed_data, 'experience') and parsed_data.experience:
                        for i, exp in enumerate(parsed_data.experience[:3]):
                            self.logger.info(f"[FINAL] Experience {i+1}: {exp.title} at {exp.company}")
                    if hasattr(parsed_data, 'education') and parsed_data.education:
                        for i, edu in enumerate(parsed_data.education[:2]):
                            self.logger.info(f"[FINAL] Education {i+1}: {edu.institution} - {edu.degree}")
                    
                    # Cache successful result
                    # TEMPORARILY DISABLED: await self.cache.set(cache_key, parsed_data, ex=3600)  # Cache for 1 hour
                    self.logger.info(f"[CACHE] Caching temporarily disabled for testing - would cache key: {cache_key}")
                    return parsed_data
                except Exception as e:
                    self.logger.error(f"Fast parsing failed: {str(e)}")
                    # Track that we encountered parsing errors
                    if 'parsed_data' in locals():
                        parsed_data.parsing_errors = True
                        self.logger.info("[CONFIDENCE] Setting parsing_errors flag due to exception in fast parsing")
                    # Only fall back if we have a genuine parsing error
                    if "rate limit" in str(e).lower():
                        raise  # Don't retry on rate limits
                    # Only fall back to fallback strategy if we have a genuine parsing failure
                    # and don't have any usable data
                    if 'parsed_data' not in locals() or not parsed_data or (
                       not getattr(parsed_data, 'experience', None) and 
                       not getattr(parsed_data, 'education', None)):
                        strategy = 'fallback'
                        self.logger.info("Falling back to fallback strategy due to fast parsing failure and no usable data")
                    else:
                        # We have some data from fast parsing, so use it but mark as having errors
                        if 'parsed_data' in locals() and parsed_data:
                            parsed_data.parsing_errors = True
                            self.logger.info("Using partial data from fast parsing despite errors")
                            
                            # Calculate confidence score
                            confidence = self._calculate_confidence_score(parsed_data)
                            parsed_data.confidence = confidence
                            
                            # Cache partial result
                            self.logger.info(f"[CACHE] Caching temporarily disabled for testing - would cache key: {cache_key}")
                            return parsed_data
                else:
                    raise ValueError("Fast parsing returned None")
                    
            elif strategy == 'fallback':
                self.logger.info("Using fallback parsing strategy")
                # Fallback strategy: use regex and NLP extractors only
                fallback_sections = {}
                for field in ['experience', 'education', 'skills']:
                    if field in sections and sections[field]:
                        fallback_sections[field] = sections[field][:3000]
                        self.logger.info(f"[TOKENS][FALLBACK] Section '{field}' token count: {count_tokens(fallback_sections[field])}")
                
                if not fallback_sections:
                    self.logger.warning("[FALLBACK] No relevant sections found, using full text.")
                    fallback_sections = {'full_text': text_for_parsing[:3000]}
                    self.logger.info(f"[TOKENS][FALLBACK] Full text token count: {count_tokens(fallback_sections['full_text'])}")
                # Use regex and NLP extractors on these sections
                regex_extractor = RegexExtractor()
                nlp_extractor = NLPExtractor(self.llm_service)
                extracted_data = {}
                for field, content in fallback_sections.items():
                    regex_results = await regex_extractor.extract({field: content})
                    nlp_results = await nlp_extractor.extract({field: content})
                    # Prefer regex, then NLP
                    extracted_data[field] = regex_results.get(field) or nlp_results.get(field)
                # Create minimal ResumeData with bulletproof personal info
                resume_data = ResumeData(
                    personal_info=personal_info,
                    education=extracted_data.get('education', []),
                    experience=extracted_data.get('experience', []),
                    skills=extracted_data.get('skills', []),
                    projects=extracted_data.get('projects', []),
                    certifications=extracted_data.get('certifications', []),
                    languages=extracted_data.get('languages', []),
                    fallback_used=True,  # Always set this in fallback strategy
                    parsing_errors=True   # Indicate parsing errors since we're in fallback mode
                )
                # Always merge and deduplicate experience from all sources
                llm_experience = [e.dict() if hasattr(e, 'dict') else dict(e) for e in extracted_data.get('experience', []) or []]
                regex_experience = [e for e in extracted_data.get('experience', []) or []]
                merged_experience = merge_and_deduplicate_experience(llm_experience, regex_experience)
                self.logger.info(f"[MERGE] Total jobs before deduplication: {len(merged_experience)} (LLM: {len(llm_experience)}, Regex: {len(regex_experience)})")
                
                # Validate and sanitize experience entries
                valid_experience = []
                for exp in merged_experience:
                    if self._validate_experience_entry(exp):
                        try:
                            from backend.utils.resume_parsing.models.resume_schema import Experience
                            exp_obj = Experience(**exp)
                            valid_experience.append(exp_obj)
                        except Exception as exp_err:
                            self.logger.warning(f"Failed to create Experience object: {exp_err}")
                
                resume_data.experience = valid_experience
                self.logger.info(f"[VALIDATION] Valid experience entries after filtering: {len(valid_experience)}")
                
                # Apply final cleanup
                resume_data = self._apply_final_cleanup(resume_data)
                
                # Calculate confidence score
                confidence = self._calculate_confidence_score(resume_data)
                resume_data.confidence = confidence
                
                # Cache successful result
                # TEMPORARILY DISABLED: await self.cache.set(cache_key, resume_data, ex=3600)  # Cache for 1 hour
                self.logger.info(f"[CACHE] Caching temporarily disabled for testing - would cache key: {cache_key}")
                return resume_data
                
            else:
                self.logger.info("[TRACE] Using comprehensive extractor strategy")
                # Extract information using each extractor
                extracted_data = {}
                for extractor in self.extractors:
                    try:
                        extracted_info = await extractor.extract(processed_text)
                        extracted_data.update(extracted_info)
                    except Exception as extractor_error:
                        self.logger.error(f"Extractor {extractor.__class__.__name__} failed: {extractor_error}", exc_info=True)
                        # Set flag that we encountered parsing errors
                        if 'resume_data' in locals():
                            resume_data.parsing_errors = True
                        # Continue with other extractors
                
                # 5.5. Deduplicate education entries from multiple extractors
                if 'education' in extracted_data:
                    education_entries = extracted_data['education']
                    # Deduplicate based on institution and degree
                    seen_education = set()
                    unique_education = []
                    for edu in education_entries:
                        if hasattr(edu, 'institution'):
                            key = (edu.institution.lower().strip(), edu.degree.lower().strip() if edu.degree else '')
                        elif isinstance(edu, dict):
                            key = (edu.get('institution', '').lower().strip(), edu.get('degree', '').lower().strip())
                        else:
                            continue
                        
                        if key not in seen_education:
                            seen_education.add(key)
                            unique_education.append(edu)
                    
                    # Clean up education entries
                    cleaned_education = []
                    for edu in unique_education:
                        if hasattr(edu, 'model_dump'):
                            merged_edu = edu
                        elif isinstance(edu, dict):
                            from backend.utils.resume_parsing.models.resume_schema import Education
                            try:
                                merged_edu = Education(**edu)
                            except Exception as e:
                                self.logger.warning(f"Failed to create Education object: {e}")
                                continue
                        else:
                            continue
                        
                        # Only keep if at least institution and one other meaningful field
                        has_meaningful = any(getattr(merged_edu, f, None) for f in ['degree', 'field_of_study', 'start_date', 'end_date'])
                        if merged_edu.institution and has_meaningful:
                            cleaned_education.append(merged_edu)
                    extracted_data['education'] = cleaned_education
                
                # Create ResumeData object from extracted information
                try:
                    resume_data = ResumeData(
                        personal_info=personal_info,  # Use our bulletproof extraction
                        education=extracted_data.get('education', []),
                        experience=extracted_data.get('experience', []),
                        skills=extracted_data.get('skills', []),
                        projects=extracted_data.get('projects', []),
                        certifications=extracted_data.get('certifications', []),
                        languages=extracted_data.get('languages', []),
                        raw_text=processed_text,
                        file_name=os.path.basename(file_path),
                        parser_version="1.0.0"  # Hardcoded for now
                    )
                    
                    # Apply final cleanup and sanity checks
                    resume_data = self._apply_final_cleanup(resume_data)
                    
                    # Calculate confidence score before returning
                    confidence = self._calculate_confidence_score(resume_data)
                    resume_data.confidence = confidence
                    
                    # Cache successful result
                    # TEMPORARILY DISABLED: await self.cache.set(cache_key, resume_data, ex=3600)  # Cache for 1 hour
                    self.logger.info(f"[CACHE] Caching temporarily disabled for testing - would cache key: {cache_key}")
                    return resume_data
                except Exception as creation_error:
                    self.logger.error(f"Failed to create ResumeData object: {creation_error}", exc_info=True)
                    raise
                    
        except Exception as e:
            self.logger.error(f"Resume parsing failed: {e}", exc_info=True)
            # Return minimal ResumeData with error information
            from backend.utils.resume_parsing.models.resume_schema import ResumeData
            return ResumeData(
                personal_info=personal_info,
                confidence=0.0,
                raw_text=text_for_parsing if 'text_for_parsing' in locals() else "",
                file_name=os.path.basename(file_path) if 'file_path' in locals() else "",
                parser_version="1.0.0"
            )

    def _repair_llm_response(self, response: Any, field: str) -> dict:
        """
        Attempt to repair malformed LLM response structures.
        Returns a fixed response if possible, or the original if not repairable.
        """
        self.logger.debug(f"[REPAIR] Repairing {field} response of type: {type(response)}")
        
        # Handle ResumeData objects (common with Phi-4/structured responses)
        if hasattr(response, 'model_dump'):
            try:
                response_dict = response.model_dump()
                self.logger.info(f"[REPAIR] Successfully converted {type(response)} to dict for {field}")
                
                # If the field exists in the response dict, return it properly structured
                if field in response_dict:
                    return {field: response_dict[field]}
                
                # For structured objects, try to extract relevant data based on field type
                if field == 'experience' and hasattr(response, 'experience'):
                    exp_data = response.experience if response.experience else []
                    # Convert Experience objects to dicts if needed
                    if exp_data and hasattr(exp_data[0], 'model_dump'):
                        exp_data = [exp.model_dump() for exp in exp_data]
                    return {'experience': exp_data}
                
                elif field == 'education' and hasattr(response, 'education'):
                    edu_data = response.education if response.education else []
                    # Convert Education objects to dicts if needed
                    if edu_data and hasattr(edu_data[0], 'model_dump'):
                        edu_data = [edu.model_dump() for edu in edu_data]
                    return {'education': edu_data}
                
                elif field == 'skills' and hasattr(response, 'skills'):
                    skills_data = response.skills if response.skills else []
                    # Convert Skill objects to dicts if needed
                    if skills_data and hasattr(skills_data[0], 'model_dump'):
                        skills_data = [skill.model_dump() for skill in skills_data]
                    return {'skills': skills_data}
                
                # If no specific field match, return the entire dict
                return response_dict
                
            except Exception as e:
                self.logger.error(f"[REPAIR] Failed to convert structured object to dict: {e}")
                # Fall through to other repair strategies
        
        # Handle dictionary responses
        if isinstance(response, dict):
            # Handle case where the field isn't in the dictionary but should be
            if field not in response:
                self.logger.warning(f"[REPAIR] {field} field missing from response, adding empty list")
                fixed_response = response.copy()
                fixed_response[field] = []
                return fixed_response
                
            # Field exists but isn't a list when it should be
            if field in response and not isinstance(response[field], list):
                self.logger.warning(f"[REPAIR] {field} field exists but isn't a list, fixing")
                fixed_response = response.copy()
                
                # If it's a dict, try to convert it to a list with one item
                if isinstance(response[field], dict):
                    fixed_response[field] = [response[field]]
                else:
                    # Otherwise just create an empty list
                    fixed_response[field] = []
                
                return fixed_response
            
            # Dictionary is properly structured
            return response
        
        # Handle list responses (sometimes Phi-4 returns direct lists)
        if isinstance(response, list):
            self.logger.info(f"[REPAIR] Converting direct list to proper {field} structure")
            return {field: response}
        
        # Handle string responses (JSON strings)
        if isinstance(response, str):
            try:
                import json
                parsed = json.loads(response)
                self.logger.info(f"[REPAIR] Successfully parsed string response as JSON for {field}")
                
                if isinstance(parsed, dict):
                    return self._repair_llm_response(parsed, field)  # Recursive call with parsed dict
                elif isinstance(parsed, list):
                    return {field: parsed}
            except Exception as e:
                self.logger.warning(f"[REPAIR] Failed to parse string as JSON: {e}")
        
        # Handle None or empty responses
        if not response:
            self.logger.warning(f"[REPAIR] Empty response for {field}, creating default structure")
            return {field: []}
        
        # Last resort: create empty structure
        self.logger.error(f"[REPAIR] Could not repair response of type {type(response)} for {field}")
        return {field: []}

    def _validate_llm_response(self, response: Any, field: str) -> bool:
        """Validate LLM response has expected structure and required fields"""
        self.logger.debug(f"[VALIDATE] Validating {field} response of type: {type(response)}")
        
        # First, try to repair the response to ensure it's in the right format
        try:
            response = self._repair_llm_response(response, field)
            self.logger.debug(f"[VALIDATE] After repair, response type: {type(response)}")
        except Exception as e:
            self.logger.error(f"[VALIDATE] Failed to repair response during validation: {e}")
            return False
        
        # Now response should be a dictionary
        if not isinstance(response, dict):
            self.logger.error(f"[VALIDATE] Response is not a dictionary after repair: {type(response)}")
            return False
        
        # Validate based on field type
        if field == 'experience':
            return self._validate_experience_response(response)
        elif field == 'education':
            return self._validate_education_response(response)
        elif field == 'skills':
            return self._validate_skills_response(response)
        else:
            # Generic validation for other fields
            return field in response

    def _validate_experience_response(self, response: dict) -> bool:
        """Validate experience-specific response structure"""
        if 'experience' not in response:
            self.logger.error("[VALIDATE] Experience field missing from response")
            return False
        
        if not isinstance(response['experience'], list):
            self.logger.error("[VALIDATE] Experience field is not a list")
            return False
        
        # Empty list is valid
        if len(response['experience']) == 0:
            self.logger.info("[VALIDATE] Experience list is empty but valid")
            return True
        
        # Validate each experience entry
        valid_entries = 0
        for i, entry in enumerate(response['experience']):
            if not isinstance(entry, dict):
                self.logger.warning(f"[VALIDATE] Experience entry {i} is not a dictionary")
                continue
            
            # Check for at least one of the critical fields
            has_title = bool(entry.get('title', '').strip())
            has_company = bool(entry.get('company', '').strip())
            
            if has_title or has_company:
                valid_entries += 1
            else:
                self.logger.warning(f"[VALIDATE] Experience entry {i} missing both title and company")
        
        if valid_entries > 0:
            self.logger.info(f"[VALIDATE] Found {valid_entries} valid experience entries")
            return True
        else:
            self.logger.warning("[VALIDATE] No valid experience entries found")
            return True  # Still return True to allow processing, just with empty data

    def _validate_education_response(self, response: dict) -> bool:
        """Validate education-specific response structure"""
        if 'education' not in response:
            self.logger.error("[VALIDATE] Education field missing from response")
            return False
        
        if not isinstance(response['education'], list):
            self.logger.error("[VALIDATE] Education field is not a list")
            return False
        
        # Empty list is valid
        if len(response['education']) == 0:
            self.logger.info("[VALIDATE] Education list is empty but valid")
            return True
        
        # Validate each education entry
        valid_entries = 0
        for i, entry in enumerate(response['education']):
            if not isinstance(entry, dict):
                self.logger.warning(f"[VALIDATE] Education entry {i} is not a dictionary")
                continue
            
            # Check for institution (most critical field)
            has_institution = bool(entry.get('institution', '').strip())
            
            if has_institution:
                valid_entries += 1
            else:
                self.logger.warning(f"[VALIDATE] Education entry {i} missing institution")
        
        if valid_entries > 0:
            self.logger.info(f"[VALIDATE] Found {valid_entries} valid education entries")
            return True
        else:
            self.logger.warning("[VALIDATE] No valid education entries found")
            return True  # Still return True to allow processing

    def _validate_skills_response(self, response: dict) -> bool:
        """Validate skills-specific response structure"""
        if 'skills' not in response:
            self.logger.error("[VALIDATE] Skills field missing from response")
            return False
        
        if not isinstance(response['skills'], list):
            self.logger.error("[VALIDATE] Skills field is not a list")
            return False
        
        # Empty list is valid
        if len(response['skills']) == 0:
            self.logger.info("[VALIDATE] Skills list is empty but valid")
            return True
        
        # Validate each skill entry
        valid_skills = 0
        for i, entry in enumerate(response['skills']):
            if isinstance(entry, str) and entry.strip():
                valid_skills += 1
            elif isinstance(entry, dict) and entry.get('name', '').strip():
                valid_skills += 1
            else:
                self.logger.warning(f"[VALIDATE] Skill entry {i} is invalid: {entry}")
        
        if valid_skills > 0:
            self.logger.info(f"[VALIDATE] Found {valid_skills} valid skills")
            return True
        else:
            self.logger.warning("[VALIDATE] No valid skills found")
            return True  # Still return True to allow processing

    def _clean_section_for_llm(self, text: str) -> str:
        """Clean section text before sending to LLM"""
        # First, detect if this is a bullet list based on • - * characters at line starts
        has_bullets = bool(re.search(r'(?:^|\n)\s*[•\-*]\s+', text))
        
        # Remove any JSON-like structures that might confuse the LLM
        text = re.sub(r'[{}\[\]]', '', text)
        
        if has_bullets:
            # Process as bullet list - preserve newlines between items
            lines = text.splitlines()
            cleaned_lines = []
            
            for line in lines:
                # Remove bullet points at start of lines
                line = re.sub(r'^\s*[•\-*]\s*', '', line)
                
                # Split on inline bullet separators
                if re.search(r'\s+[•\-*]\s+', line):
                    parts = re.split(r'\s+[•\-*]\s+', line)
                    for part in parts:
                        if part.strip():
                            # Clean each part individually
                            clean_part = re.sub(r'\s+', ' ', part)  # Normalize spaces
                            cleaned_lines.append(clean_part.strip())
                else:
                    # Process normal lines
                    clean_line = re.sub(r'\s+', ' ', line)  # Normalize spaces
                    if clean_line.strip():
                        cleaned_lines.append(clean_line.strip())
            
            # Join with newlines to preserve structure
            return '\n'.join(cleaned_lines)
        else:
            # For regular text (non-bullet lists), normalize all whitespace
            # Remove excessive whitespace, including newlines
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

    def _truncate_by_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text by token count, not character count"""
        try:
            import tiktoken
            enc = tiktoken.get_encoding('cl100k_base')
            tokens = enc.encode(text)
            if len(tokens) > max_tokens:
                truncated_tokens = tokens[:max_tokens]
                return enc.decode(truncated_tokens)
        except Exception:
            # Fallback to character truncation
            return text[:max_tokens * 4]  # Rough estimate: 4 chars per token
        
        return text

    def _apply_final_cleanup(self, resume_data: 'ResumeData') -> 'ResumeData':
        """Apply final cleanup to resume data before returning"""
        if not resume_data:
            self.logger.warning("No resume data to clean up")
            return resume_data
            
        try:
            self.logger.info("[CLEANUP] Applying final cleanup to resume data")
            
            # --- Clean up personal info ---
            if resume_data.personal_info:
                # Normalize name to title case if it exists
                if resume_data.personal_info.name:
                    # Special handling for names with McX or O'X patterns
                    name = resume_data.personal_info.name.strip()
                    # First convert to title case
                    name = name.title()
                    # Then handle special cases like "McDowell" -> "McDowell" not "Mcdowell"
                    name = re.sub(r'\bMc([a-z])', lambda x: f"Mc{x.group(1).upper()}", name)
                    # Handle O'Name -> O'Name not O'name
                    name = re.sub(r"\bO'([a-z])", lambda x: f"O'{x.group(1).upper()}", name)
                    resume_data.personal_info.name = name
                
                # Normalize email to lowercase
                if resume_data.personal_info.email:
                    resume_data.personal_info.email = resume_data.personal_info.email.lower().strip()
                
                # Format phone numbers consistently
                if resume_data.personal_info.phone:
                    # Remove all non-digit characters
                    phone = re.sub(r'\D', '', resume_data.personal_info.phone)
                    # Format as XXX-XXX-XXXX if it's a 10-digit number
                    if len(phone) == 10:
                        phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
                    resume_data.personal_info.phone = phone
            
            # --- Clean up education ---
            if resume_data.education:
                # Filter out invalid education entries
                valid_education = []
                for edu in resume_data.education:
                    # Check for institution which is required
                    if not edu.institution or len(edu.institution.strip()) < 3:
                        continue
                        
                    # Clean up degree field
                    if edu.degree:
                        edu.degree = edu.degree.strip()
                        # Normalize common degree abbreviations
                        degree_mapping = {
                            "bachelors": "Bachelor's", "bachelor of": "Bachelor of",
                            "masters": "Master's", "master of": "Master of",
                            "phd": "Ph.D.", "doctorate": "Doctorate", 
                            "associates": "Associate's", "associate of": "Associate of"
                        }
                        for key, value in degree_mapping.items():
                            if key in edu.degree.lower():
                                # Replace while preserving the rest of the string
                                edu.degree = re.sub(re.escape(key), value, edu.degree, flags=re.IGNORECASE)
                    
                    # Clean up dates
                    for date_field in ['start_date', 'end_date']:
                        date_value = getattr(edu, date_field, None)
                        if date_value:
                            # Try to convert month names to numbers
                            month_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
                            month_mapping = {
                                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                            }
                            for month_name, month_num in month_mapping.items():
                                if re.search(month_name, date_value.lower()):
                                    # Replace month name with number
                                    date_value = re.sub(
                                        r'\b' + month_name + r'\w*\b', 
                                        month_num, 
                                        date_value, 
                                        flags=re.IGNORECASE
                                    )
                            # Set the cleaned date
                            setattr(edu, date_field, date_value)
                    
                    valid_education.append(edu)
                
                # Update education list
                resume_data.education = valid_education
            
            # --- Clean up experience ---
            if resume_data.experience:
                # Sort experience by start_date (descending/most recent first)
                # Extract years from dates for sorting
                def extract_year(date_str):
                    if not date_str:
                        return 0
                    # Extract 4-digit year
                    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                    if year_match:
                        return int(year_match.group(0))
                    return 0
                
                # Sort by start_date (most recent first)
                resume_data.experience.sort(
                    key=lambda exp: extract_year(exp.start_date) if exp.start_date else 0,
                    reverse=True
                )
                
                # Clean up company and title fields
                for exp in resume_data.experience:
                    # Normalize company field
                    if exp.company:
                        # Remove common suffixes
                        for suffix in [' Inc', ' LLC', ' Ltd', ' Corporation', ' Corp', ' Co', ' Company']:
                            exp.company = re.sub(re.escape(suffix + '$'), '', exp.company, flags=re.IGNORECASE)
                        exp.company = exp.company.strip()
                    
                    # Normalize title field
                    if exp.title:
                        exp.title = exp.title.strip()
                        
                    # Clean up description - remove excessive whitespace
                    if exp.description:
                        # Preserve newlines but normalize spaces
                        lines = exp.description.splitlines()
                        cleaned_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines]
                        exp.description = '\n'.join(line for line in cleaned_lines if line)
            
            # --- Clean up skills ---
            if resume_data.skills:
                # Normalize skill names and remove duplicates
                unique_skills = {}
                for skill in resume_data.skills:
                    if not skill.name:
                        continue
                    # Convert to lowercase for deduplication
                    skill_name = skill.name.strip().lower()
                    # Skip skills that are too short or too long
                    if len(skill_name) < 2 or len(skill_name) > 50:
                        continue
                    # Keep only the first occurrence
                    if skill_name not in unique_skills:
                        unique_skills[skill_name] = skill.name.strip()  # Keep original capitalization
                
                # Rebuild skills list with normalized names
                from backend.utils.resume_parsing.models.resume_schema import Skill
                cleaned_skills = [Skill(name=name) for name in unique_skills.values()]
                resume_data.skills = cleaned_skills
                
                # Sort skills alphabetically
                resume_data.skills.sort(key=lambda x: x.name.lower())
            
            self.logger.info("[CLEANUP] Final cleanup completed successfully")
            return resume_data
        except Exception as e:
            self.logger.error(f"[CLEANUP] Error during final cleanup: {e}")
            # Return original data if cleanup fails
            return resume_data
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash of file content for caching"""
        import hashlib
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.logger.warning(f"Failed to generate file hash: {e}")
            # Fallback to file path hash
            return hashlib.md5(file_path.encode()).hexdigest()
