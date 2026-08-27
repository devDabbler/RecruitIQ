"""
Resume Data Schema
Defines Pydantic models for structured resume data
"""
from typing import List, Optional, Dict, Any, Union
from datetime import date as datetime_date
from pydantic import BaseModel, Field, validator
import re


class PersonalInfo(BaseModel):
    """Personal information from resume"""
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


class Education(BaseModel):
    """Education information"""
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[Union[str, datetime_date]] = None
    end_date: Optional[Union[str, datetime_date]] = None
    gpa: Optional[float] = None
    location: Optional[str] = None
    description: Optional[str] = None

    @validator('gpa', pre=True)
    def gpa_empty_str_to_none(cls, v):
        if v == '':
            return None
        return v
    
    @property
    def major(self) -> Optional[str]:
        """Alias for field_of_study to maintain compatibility with tests"""
        return self.field_of_study
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary with proper date formatting"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime_date):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result


class Experience(BaseModel):
    """Work experience information"""
    company: str
    title: str
    start_date: Optional[Union[str, datetime_date]] = None
    end_date: Optional[Union[str, datetime_date]] = None
    location: Optional[str] = None
    description: Optional[Union[str, List[str]]] = None
    highlights: Optional[List[str]] = None
    
    @validator('description')
    def validate_description(cls, v):
        """Convert description to properly formatted string with enhanced readability"""
        if isinstance(v, list):
            # Preserve bullet points with enhanced formatting for better readability
            formatted_items = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    cleaned_item = item.strip()
                    # Remove existing bullet markers to standardize
                    cleaned_item = re.sub(r'^[•\-*◦]\s*', '', cleaned_item)
                    # Ensure sentence ends with period for consistency
                    if not cleaned_item.endswith(('.', '!', '?')):
                        cleaned_item += '.'
                    # Add standardized bullet marker
                    formatted_items.append(f"• {cleaned_item}")
            
            # Join with double newlines for better visual separation
            return '\n\n'.join(formatted_items)
        elif isinstance(v, str) and v.strip():
            # If it's already a string, ensure it has proper formatting
            lines = v.split('\n')
            formatted_lines = []
            
            for line in lines:
                line = line.strip()
                if line:
                    # Remove existing bullet markers to standardize
                    cleaned_line = re.sub(r'^[•\-*◦]\s*', '', line)
                    # Ensure sentence ends with period for consistency
                    if not cleaned_line.endswith(('.', '!', '?')):
                        cleaned_line += '.'
                    # Add standardized bullet marker
                    formatted_lines.append(f"• {cleaned_line}")
            
            # Join with double newlines for better visual separation
            return '\n\n'.join(formatted_lines) if formatted_lines else v
        return v
    
    def get_bullet_points(self) -> List[str]:
        """Get description as a list of bullet points"""
        if not self.description:
            return []
        
        if isinstance(self.description, list):
            return [item.strip() for item in self.description if item.strip()]
        
        # Parse string description back into bullet points
        if '\n' in self.description:
            # Multi-line description - split by lines
            lines = [line.strip() for line in self.description.split('\n') if line.strip()]
            return lines
        elif any(marker in self.description for marker in ['•', '-', '*', '◦']):
            # Has bullet markers - split by them
            import re
            bullets = re.split(r'[•\-*◦]\s*', self.description)
            return [bullet.strip() for bullet in bullets if bullet.strip()]
        else:
            # Single paragraph - try to split by common action words that indicate new bullet points
            import re
            # Look for patterns like "Led" or "Developed" that often start new bullet points
            action_words = r'\b(Led|Developed|Implemented|Built|Created|Managed|Optimized|Reduced|Delivered|Collaborated|Designed|Architected|Mentored|Conducted|Established|Streamlined|Automated|Enhanced|Scaled|Deployed)\b'
            parts = re.split(action_words, self.description)
            
            if len(parts) > 1:
                # Reconstruct sentences starting with action words
                bullets = []
                for i in range(1, len(parts), 2):  # Skip even indices (action words)
                    if i + 1 < len(parts):
                        bullet = parts[i] + parts[i + 1]
                        if bullet.strip():
                            bullets.append(bullet.strip())
                if bullets:
                    return bullets
            
            # Fallback to sentence splitting
            sentences = [s.strip() for s in self.description.split('. ') if s.strip() and len(s.strip()) > 10]
            return sentences
    
    def get_bullet_count(self) -> int:
        """Get the number of bullet points in the description"""
        return len(self.get_bullet_points())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary with proper date formatting and bullet point info"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime_date):
                result[key] = value.isoformat()
            elif key == 'highlights' and value is not None:
                result[key] = value
            else:
                result[key] = value
        
        # Add bullet point metadata for easier analysis
        result['bullet_points'] = self.get_bullet_points()
        result['bullet_count'] = self.get_bullet_count()
        return result


class Skill(BaseModel):
    """Skill information with automatic categorization"""
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
    keywords: Optional[List[str]] = None
    
    @validator('category', pre=True, always=True)
    def categorize_skill(cls, v, values):
        """Automatically categorize skills if not provided"""
        if v is not None:
            return v
        
        skill_name = values.get('name', '').lower() if values else ''
        if not skill_name:
            return "Other Technical Skills"
        
        # Programming Languages
        programming_languages = [
            "python", "java", "javascript", "typescript", "c++", "c#", "csharp",
            "ruby", "php", "swift", "kotlin", "go", "golang", "rust", 
            "scala", "perl", "r", "matlab", "cobol", "fortran", "assembly",
            "vb.net", "visual basic", "delphi", "objective-c", "haskell",
            "erlang", "elixir", "clojure", "f#", "lua", "bash", "powershell"
        ]
        
        # Web Technologies & Frameworks
        web_technologies = [
            "react", "angular", "vue", "node.js", "nodejs", "django", "flask", 
            "spring", "rails", "laravel", "express", "bootstrap", "jquery", 
            "redux", "graphql", "rest", "api", "html", "css", "sass", "less", "scss"
        ]
        
        # Databases & Data Storage
        databases = [
            "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "kafka", 
            "rabbitmq", "oracle", "sql server", "sqlite", "dynamodb", "cassandra"
        ]
        
        # Cloud & Infrastructure
        cloud_infrastructure = [
            "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "terraform",
            "ansible", "chef", "puppet", "vmware", "openstack", "heroku"
        ]
        
        # Data Science & Analytics
        data_science = [
            "pandas", "numpy", "matplotlib", "seaborn", "tensorflow", "pytorch", 
            "keras", "scikit", "opencv", "machine learning", "ml", "deep learning",
            "neural", "data science", "analytics", "statistics", "predictive"
        ]
        
        # Development Tools & IDEs
        dev_tools = [
            "git", "github", "gitlab", "bitbucket", "svn", "subversion",
            "visual studio", "vscode", "visual studio code", "intellij", 
            "eclipse", "xcode", "android studio", "sublime text", "atom", 
            "vim", "emacs", "postman", "insomnia", "jira", "confluence"
        ]
        
        # Check categories in order (most specific first)
        if skill_name in programming_languages:
            return "Programming Languages"
        elif skill_name in web_technologies:
            return "Web Technologies & Frameworks"
        elif skill_name in databases:
            return "Databases & Data Storage"
        elif skill_name in cloud_infrastructure:
            return "Cloud & Infrastructure"
        elif skill_name in data_science:
            return "Data Science & Analytics"
        elif skill_name in dev_tools:
            return "Development Tools & IDEs"
        
        # Enhanced fallback logic for skills not explicitly categorized
        # AI/ML/Data Science patterns
        if any(pattern in skill_name for pattern in [
            "machine learning", "ml", "deep learning", "neural", "data science",
            "analytics", "statistics", "predictive", "modeling", "algorithm",
            "regression", "classification", "clustering", "nlp", "computer vision"
        ]):
            return "Data Science & Analytics"
        
        # Programming language patterns
        if any(pattern in skill_name for pattern in [
            "script", "lang", "programming", "coding", ".js", ".py", ".java", 
            "compiler", "interpreter", "syntax"
        ]):
            return "Programming Languages"
        
        # Framework/Library patterns
        if any(pattern in skill_name for pattern in [
            "framework", "library", "lib", "api", "sdk", "platform", "stack"
        ]):
            return "Web Technologies & Frameworks"
        
        # DevOps patterns
        if any(pattern in skill_name for pattern in [
            "devops", "ci/cd", "deployment", "infrastructure", "automation",
            "monitoring", "logging", "testing", "quality"
        ]):
            return "DevOps & CI/CD"
        
        # Security patterns
        if any(pattern in skill_name for pattern in [
            "security", "authentication", "authorization", "encryption", "ssl",
            "oauth", "jwt", "oidc", "penetration", "vulnerability"
        ]):
            return "Security & Compliance"
        
        return "Other Technical Skills"


class Project(BaseModel):
    """Project information"""
    name: str
    description: Optional[str] = None
    start_date: Optional[Union[str, datetime_date]] = None
    end_date: Optional[Union[str, datetime_date]] = None
    highlights: Optional[List[str]] = None
    url: Optional[str] = None
    technologies: Optional[List[str]] = None


class Certification(BaseModel):
    """Certification information"""
    name: str
    issuer: Optional[str] = None
    date: Optional[Union[str, datetime_date]] = None
    url: Optional[str] = None
    expires: Optional[Union[str, datetime_date]] = None


class Language(BaseModel):
    """Language proficiency"""
    name: str
    proficiency: Optional[str] = None


class Military(BaseModel):
    """Military service information"""
    branch: Optional[str] = Field(default="", description="Military branch or organization")
    organization: Optional[str] = Field(default="", description="Military organization (alias for branch)")
    rank: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[Union[str, datetime_date]] = None
    end_date: Optional[Union[str, datetime_date]] = None
    description: Optional[str] = None
    responsibilities: Optional[List[str]] = Field(default_factory=list)
    location: Optional[str] = None
    unit: Optional[str] = None
    clearances: Optional[List[str]] = Field(default_factory=list)
    awards: Optional[List[str]] = Field(default_factory=list)
    training: Optional[List[str]] = Field(default_factory=list)
    deployments: Optional[List[str]] = Field(default_factory=list)
    
    def model_post_init(self, __context) -> None:
        """Ensure branch and organization are synchronized"""
        if self.branch and not self.organization:
            self.organization = self.branch
        elif self.organization and not self.branch:
            self.branch = self.organization


class ResumeData(BaseModel):
    """Complete structured resume data"""
    personal_info: Optional[PersonalInfo] = Field(default_factory=PersonalInfo)
    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    military: List[Military] = Field(default_factory=list)
    
    # Metadata
    raw_text: Optional[Union[str, Dict[str, str]]] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    parser_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire model to dictionary with proper handling of nested objects"""
        result = {}
        for key, value in self.__dict__.items():
            if key == 'personal_info' and value is not None:
                result[key] = value.dict()
            elif isinstance(value, list):
                result[key] = [
                    item.to_dict() if hasattr(item, 'to_dict') else item.dict() 
                    for item in value
                ]
            else:
                result[key] = value
        return result