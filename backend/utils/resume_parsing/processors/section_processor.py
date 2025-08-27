"""
Section Processor
Identifies and extracts sections from resume markdown
"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class SectionProcessor(BaseProcessor):
    """
    Section processor identifies and extracts sections from markdown
    Uses pattern matching and heuristics to identify standard and custom sections
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize section processor with configuration
        
        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        
        # Load section patterns from config or use defaults
        self.section_patterns = self._load_section_patterns()
    
    def _load_section_patterns(self) -> Dict[str, List[str]]:
        """Load section header patterns from config or use defaults"""
        # More comprehensive patterns with better matching
        patterns = {
            'summary': [
                r'(?i)(?:^|\n)\s*##\s*(?:PROFESSIONAL\s+)?(?:CAREER\s+)?SUMMARY(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*(?:PROFESSIONAL\s+)?PROFILE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*OBJECTIVE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*ABOUT(?:\s+ME)?(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*OVERVIEW(?:\s*:|\s*$|\n)',
            ],
            'experience': [
                r'(?i)(?:^|\n)\s*##\s*(?:WORK\s+)?EXPERIENCE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*PROFESSIONAL\s+EXPERIENCE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*EMPLOYMENT(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*WORK\s+HISTORY(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*CAREER\s+HISTORY(?:\s*:|\s*$|\n)',
            ],
            'education': [
                r'(?i)(?:^|\n)\s*##\s*EDUCATION(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*EDUCATIONAL\s+BACKGROUND(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*ACADEMIC\s+BACKGROUND(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*DEGREES?(?:\s*:|\s*$|\n)',
            ],
            'skills': [
                r'(?i)(?:^|\n)\s*##\s*(?:TECHNICAL\s+)?SKILLS(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*CORE\s+(?:COMPETENCIES|SKILLS)(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*EXPERTISE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*QUALIFICATIONS(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*KEY\s+SKILLS(?:\s*:|\s*$|\n)',
            ],
            'projects': [
                r'(?i)(?:^|\n)\s*##\s*PROJECTS(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*PROJECT\s+EXPERIENCE(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*PERSONAL\s+PROJECTS(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*KEY\s+PROJECTS(?:\s*:|\s*$|\n)',
            ],
            'certifications': [
                r'(?i)(?:^|\n)\s*##\s*CERTIFICATIONS(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*CERTIFICATES(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*LICENSES(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*CREDENTIALS(?:\s*:|\s*$|\n)',
            ],
            'languages': [
                r'(?i)(?:^|\n)\s*##\s*LANGUAGES(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*LANGUAGE\s+PROFICIENCY(?:\s*:|\s*$|\n)',
            ],
            'military': [
                r'(?i)(?:^|\n)\s*##\s*MILITARY(?:\s+EXPERIENCE)?(?:\s*:|\s*$|\n)',
                r'(?i)(?:^|\n)\s*##\s*MILITARY\s+SERVICE(?:\s*:|\s*$|\n)',
            ]
        }
        
        # Merge with patterns from config if provided
        if self.config and 'section_patterns' in self.config:
            for section, section_patterns in self.config['section_patterns'].items():
                if section in patterns:
                    patterns[section].extend(section_patterns)
                else:
                    patterns[section] = section_patterns
        
        return patterns
    
    def _find_section_positions(self, markdown: str) -> List[Tuple[int, str, str]]:
        """
        Extremely robust: Find all section headers and their positions in the text, tolerant to non-standard formatting.
        Returns: List of tuples (position, section_type, section_header)
        """
        section_positions = []
        # 1. Flexible regex for section headers (allow missing ##, extra whitespace, punctuation, etc)
        fuzzy_section_words = [
            'experience', 'work experience', 'professional experience', 'employment', 'career history',
            'education', 'academic background', 'degrees',
            'skills', 'core competencies', 'expertise', 'qualifications',
            'projects', 'project experience', 'personal projects',
            'certifications', 'certificates', 'licenses', 'credentials',
            'languages', 'language proficiency',
            'military', 'military experience', 'military service',
            'summary', 'profile', 'objective', 'about', 'overview',
            'contact', 'contact information'
        ]
        # Build a single regex that matches any of these words, with or without ##, and tolerant to extra chars
        fuzzy_pattern = re.compile(
            r'(?i)(^|\n)\s{0,4}(#{{0,2}})?\s*(' + '|'.join([re.escape(w) for w in fuzzy_section_words]) + r')\s*[:\-–—]*\s*(\n|$)',
            re.MULTILINE
        )
        matches = list(re.finditer(fuzzy_pattern, markdown))
        for match in matches:
            pos = match.start()
            header = match.group(0)
            header_word = match.group(3).lower()
            # Classify header type
            section_type = self._classify_header(header_word)
            section_positions.append((pos, section_type, header))
        # 2. Add any additional matches from strict patterns (for custom/user config)
        for section_type, patterns in self.section_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, markdown, re.MULTILINE):
                    pos = match.start()
                    header = match.group(0)
                    # Only add if not already covered by fuzzy
                    if not any(abs(pos - p[0]) < 5 for p in section_positions):
                        section_positions.append((pos, section_type, header))
        # 3. Sort and merge overlapping/duplicate headers
        section_positions.sort(key=lambda x: x[0])
        merged = []
        last_end = -1
        last_type = None
        for pos, section_type, header in section_positions:
            if pos > last_end:
                merged.append((pos, section_type, header))
                last_end = pos + len(header)
                last_type = section_type
            elif section_type == last_type:
                # Merge split/fragmented section headers
                continue
        # 4. Remove duplicates (keep first occurrence)
        seen_types = set()
        filtered = []
        for pos, section_type, header in merged:
            if section_type not in seen_types:
                filtered.append((pos, section_type, header))
                seen_types.add(section_type)
        return filtered
    
    async def process(self, markdown: str) -> Dict[str, str]:
        """
        Process markdown to identify and extract sections
        
        Args:
            markdown: Markdown formatted text
            
        Returns:
            Dictionary mapping section names to section content
        """
        if not markdown:
            return {"general": ""}
        
        # First, clean the markdown and handle header/contact info
        cleaned_markdown = self._preprocess_markdown(markdown)
        
        # Find all section headers and their positions
        section_positions = self._find_section_positions(cleaned_markdown)
        
        # Sort sections by position
        section_positions.sort(key=lambda x: x[0])
        
        # Extract content between section headers
        sections = {}
        for i, (pos, section_type, section_header) in enumerate(section_positions):
            # Get start position (after the header)
            start = pos + len(section_header)
            
            # Get end position (next section or end of text)
            end = len(cleaned_markdown)
            if i < len(section_positions) - 1:
                end = section_positions[i + 1][0]
            
            # Extract content and clean it
            content = cleaned_markdown[start:end].strip()
            
            # Skip empty sections
            if content:
                sections[section_type] = content
        
        # If no sections found, try to extract basic structure
        if not sections:
            sections = self._extract_basic_structure(cleaned_markdown)
        
        # Always include the original text for reference
        sections["full_text"] = markdown
        
        # Handle special case where contact info gets misclassified
        if 'summary' in sections and self._is_contact_section(sections['summary']):
            # Move contact content to a separate area and look for actual summary
            contact_content = sections['summary']
            sections['contact'] = contact_content
            
            # Try to find actual summary/profile content
            actual_summary = self._extract_summary_from_full_text(markdown)
            if actual_summary:
                sections['summary'] = actual_summary
            else:
                del sections['summary']
        
        return sections
    
    def _preprocess_markdown(self, markdown: str) -> str:
        """Preprocess markdown to handle common formatting issues"""
        # Remove null bytes and other problematic characters
        markdown = markdown.replace('\x00', ' ')
        
        # Normalize line endings
        markdown = re.sub(r'\r\n|\r', '\n', markdown)
        
        # Fix spacing issues from OCR
        markdown = re.sub(r' {2,}', ' ', markdown)
        
        # Fix common header formatting issues - make more specific
        # Only convert likely section headers to markdown format
        section_words = r'(?:CONTACT|PROFILE|EXPERIENCE|EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|MILITARY|SUMMARY|OBJECTIVE)'
        markdown = re.sub(rf'^({section_words})\s*$', r'## \1', markdown, flags=re.MULTILINE)
        
        return markdown
    
    def _is_contact_section(self, text: str) -> bool:
        """Check if text appears to be contact information rather than summary"""
        contact_indicators = [
            r'\d{3}[-.]?\d{3}[-.]?\d{4}',  # Phone numbers
            r'@\w+\.\w+',  # Email
            r'linkedin\.com',  # LinkedIn
            r'github\.com',  # GitHub
            r'\b[A-Z]{2}\s+\d{5}',  # State + ZIP
        ]
        
        contact_matches = sum(1 for pattern in contact_indicators if re.search(pattern, text))
        
        # If more than 2 contact patterns match, likely a contact section
        return contact_matches >= 2
    
    def _extract_summary_from_full_text(self, markdown: str) -> Optional[str]:
        """Try to extract actual summary/profile content from full text"""
        # Look for profile-like content after contact info
        profile_patterns = [
            r'(?i)(?:^|\n)\s*##\s*PROFILE\s*(.*?)(?=\n\s*##|\n\s*[A-Z\s]{3,}\s*$|$)',
            r'(?i)(?:^|\n)(Strategic\s+\w+.*?(?:years?|experience).*?)(?=\n\s*##|\n\s*[A-Z\s]{3,}\s*$)',
            r'(?i)(?:^|\n)(Experienced\s+\w+.*?(?:years?|experience).*?)(?=\n\s*##|\n\s*[A-Z\s]{3,}\s*$)',
        ]
        
        for pattern in profile_patterns:
            match = re.search(pattern, markdown, re.DOTALL)
            if match:
                content = match.group(1).strip()
                if len(content) > 50:  # Ensure it's substantial content
                    return content
        
        return None
    
    def _extract_basic_structure(self, markdown: str) -> Dict[str, str]:
        """Extract basic structure when no clear sections are found"""
        sections = {}
        lines = markdown.split('\n')
        
        current_section = 'general'
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line looks like a section header
            if self._looks_like_header(line):
                # Save previous section if it has content
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                current_section = self._classify_header(line)
                current_content = []
            else:
                current_content.append(line)
        
        # Save final section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _looks_like_header(self, line: str) -> bool:
        """Check if a line looks like a section header"""
        # All caps, reasonable length
        if line.isupper() and 3 <= len(line) <= 50:
            return True
        
        # Title case with common section words
        header_words = [
            'experience', 'education', 'skills', 'summary', 'profile', 
            'objective', 'projects', 'certifications', 'languages'
        ]
        
        for word in header_words:
            if word in line.lower() and len(line) <= 50:
                return True
        
        return False
    
    def _classify_header(self, header: str) -> str:
        """Classify what type of section a header represents"""
        header_lower = header.lower()
        
        # Map header text to section types
        if any(word in header_lower for word in ['experience', 'work', 'employment', 'career']):
            return 'experience'
        elif any(word in header_lower for word in ['education', 'academic', 'degree']):
            return 'education'
        elif any(word in header_lower for word in ['skill', 'competenc', 'expertise', 'qualification']):
            return 'skills'
        elif any(word in header_lower for word in ['summary', 'profile', 'objective', 'about', 'overview']):
            return 'summary'
        elif any(word in header_lower for word in ['project']):
            return 'projects'
        elif any(word in header_lower for word in ['certification', 'certificate', 'license', 'credential']):
            return 'certifications'
        elif any(word in header_lower for word in ['language']):
            return 'languages'
        elif any(word in header_lower for word in ['military', 'service']):
            return 'military'
        else:
            return 'general'