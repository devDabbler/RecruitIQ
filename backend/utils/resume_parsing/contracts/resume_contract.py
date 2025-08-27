"""
Resume contract schema for resume parsing pipeline.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import date
from pydantic import BaseModel, Field, validator
import re

class PersonalInfoContract(BaseModel):
    """Personal information contract"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    summary: Optional[str] = None
    
    @validator('name', pre=True)
    def normalize_name_casing(cls, v):
        """Normalize name casing to proper format (First Last)"""
        if not v or not isinstance(v, str):
            return v
        
        # Clean up the name
        name = v.strip()
        if not name:
            return v
        
        # Handle common cases
        # If it's already properly cased, return as is
        if name == name.title():
            return name
        
        # If it's all caps, convert to title case
        if name.isupper():
            return name.title()
        
        # If it's all lowercase, convert to title case
        if name.islower():
            return name.title()
        
        # For mixed cases, try to normalize
        # Split by spaces and handle each part
        name_parts = name.split()
        normalized_parts = []
        
        for part in name_parts:
            part = part.strip()
            if not part:
                continue
            
            # Handle special cases like "Jr.", "Sr.", "III", "IV", etc.
            if part.upper() in ['JR', 'SR', 'JR.', 'SR.', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']:
                normalized_parts.append(part.upper())
            # Handle common prefixes like "Mc", "Mac", "O'", etc.
            elif part.lower().startswith(('mc', 'mac', "o'", "d'", "l'")):
                if len(part) > 2:
                    normalized_parts.append(part[0].upper() + part[1:].lower())
                else:
                    normalized_parts.append(part.title())
            # Handle hyphens (e.g., "Jean-Pierre")
            elif '-' in part:
                hyphen_parts = part.split('-')
                normalized_hyphen_parts = []
                for hp in hyphen_parts:
                    if hp:
                        normalized_hyphen_parts.append(hp[0].upper() + hp[1:].lower())
                normalized_parts.append('-'.join(normalized_hyphen_parts))
            else:
                # Standard case: first letter uppercase, rest lowercase
                normalized_parts.append(part[0].upper() + part[1:].lower())
        
        return ' '.join(normalized_parts)

class ExperienceContract(BaseModel):
    """Work experience contract"""
    title: str
    company: str
    start_date: Optional[Union[str, date]] = None
    end_date: Optional[Union[str, date]] = None
    description: Optional[str] = None

class EducationContract(BaseModel):
    """Education contract"""
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[Union[str, date]] = None
    end_date: Optional[Union[str, date]] = None
    gpa: Optional[str] = None
    location: Optional[str] = None
    honors: Optional[List[str]] = Field(default_factory=list)
    certifications: Optional[List[str]] = Field(default_factory=list)

class SkillContract(BaseModel):
    """Skill contract"""
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
    keywords: Optional[List[str]] = Field(default_factory=list)

class LanguageContract(BaseModel):
    """Language contract"""
    name: str
    proficiency: Optional[str] = None

class MilitaryContract(BaseModel):
    """Military experience contract"""
    branch: str
    rank: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[Union[str, date]] = None
    end_date: Optional[Union[str, date]] = None
    mos_specialty: Optional[str] = None  # Military Occupational Specialty
    location: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    deployments: Optional[List[str]] = Field(default_factory=list)
    awards: Optional[List[str]] = Field(default_factory=list)
    clearances: Optional[List[str]] = Field(default_factory=list)
    training: Optional[List[str]] = Field(default_factory=list)
    
    @validator('responsibilities', pre=True)
    def ensure_responsibilities_list(cls, v):
        """Ensure responsibilities is always a list of strings"""
        if v is None:
            return []
        if isinstance(v, str):
            # Split by newlines and clean up
            lines = [line.strip() for line in v.split('\n') if line.strip()]
            # Remove bullet markers and clean up
            cleaned_lines = []
            for line in lines:
                # Remove common bullet markers
                cleaned_line = re.sub(r'^[•\-*◦]\s*', '', line)
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            return cleaned_lines
        elif isinstance(v, list):
            # Clean up each item in the list
            cleaned_items = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    cleaned_item = re.sub(r'^[•\-*◦]\s*', '', item.strip())
                    if cleaned_item:
                        cleaned_items.append(cleaned_item)
            return cleaned_items
        return []

class ResumeContract(BaseModel):
    """Complete resume contract"""
    personal_info: PersonalInfoContract
    experience: List[ExperienceContract] = Field(default_factory=list)
    education: List[EducationContract] = Field(default_factory=list)
    skills: List[SkillContract] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)
    languages: List[LanguageContract] = Field(default_factory=list)
    raw_text: Optional[str] = None

    def validate(self) -> bool:
        """Validate the resume contract"""
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()


class EnhancedExperienceContract(ExperienceContract):
    """Enhanced work experience contract with additional fields"""
    location: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Compatibility helpers for legacy code expecting 'highlights'
    # ------------------------------------------------------------------
    @property
    def highlights(self) -> List[str]:
        """Alias for `responsibilities` used by older code/tests."""
        return self.responsibilities

    def get_bullet_points(self) -> List[str]:
        """Return responsibilities for backward-compatibility with tests."""
        return self.responsibilities
    responsibilities: List[str] = Field(default_factory=list)
    duration_months: Optional[int] = None
    
    @validator('responsibilities', pre=True)
    def ensure_responsibilities_list(cls, v):
        """Ensure responsibilities is always a list of strings"""
        if v is None:
            return []
        if isinstance(v, str):
            # Split by newlines and clean up
            lines = [line.strip() for line in v.split('\n') if line.strip()]
            # Remove bullet markers and clean up
            cleaned_lines = []
            for line in lines:
                # Remove common bullet markers
                cleaned_line = re.sub(r'^[•\-*◦]\s*', '', line)
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            return cleaned_lines
        elif isinstance(v, list):
            # Clean up each item in the list
            cleaned_items = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    cleaned_item = re.sub(r'^[•\-*◦]\s*', '', item.strip())
                    if cleaned_item:
                        cleaned_items.append(cleaned_item)
            return cleaned_items
        return []


class ResumeV2(BaseModel):
    """Enhanced resume contract with more detailed fields including military experience"""
    personal_info: PersonalInfoContract
    experience: List[EnhancedExperienceContract] = Field(default_factory=list)
    education: List[EducationContract] = Field(default_factory=list)
    skills: List[SkillContract] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)
    languages: List[LanguageContract] = Field(default_factory=list)
    military: List[MilitaryContract] = Field(default_factory=list)  # Added military experience
    raw_text: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate the resume contract"""
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
