"""
Markdown Processor
Converts extracted text to structured markdown format
"""
import re
import logging
from typing import Optional, Dict, Any, List

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class MarkdownProcessor(BaseProcessor):
    ALL_CAPS_HEADER_REGEX = r'^([A-Z][A-Z\s]{2,49})$'
    TITLE_CASE_HEADER_REGEX = r'^[A-Z][a-z]+(?:(?:\s(?:and|of|the|in|for|to|with|&))?\s[A-Z][a-z]+){0,3}$'
    COLON_HEADER_REGEX = r'^([\w\s]{3,50}):$'

    COMMON_HEADERS_LIST = [
        'EDUCATION', 'EXPERIENCE', 'WORK EXPERIENCE', 'SKILLS', 'TECHNICAL SKILLS',
        'SUMMARY', 'OBJECTIVE', 'CERTIFICATIONS', 'PROJECTS', 'PERSONAL PROJECTS',
        'PUBLICATIONS', 'LANGUAGES', 'INTERESTS', 'ACTIVITIES',
        'REFERENCES', 'VOLUNTEER', 'MILITARY', 'AWARDS', 'HONORS',
        'CONTACT', 'CONTACT INFORMATION', 'PERSONAL DETAILS', 'ABOUT ME'
    ]
    HEADER_KEYWORDS_LIST = [
        'EXPERIENCE', 'SKILL', 'TECHNOLOGY', 'TOOL', 'PROFICIENCY', 'EXPERTISE', 'KNOWLEDGE',
        'EDUCATION', 'ACADEMIC', 'COURSE',
        'PROJECT', 'PORTFOLIO',
        'SUMMARY', 'PROFILE', 'OBJECTIVE', 'GOAL',
        'AWARD', 'HONOR', 'ACHIEVEMENT',
        'CERTIFICATION', 'LICENSE',
        'PUBLICATION', 'PRESENTATION',
        'LANGUAGE', 'FLUENCY',
        'CONTACT', 'INFORMATION', 'DETAIL',
        'REFERENCE',
        'WORK', 'EMPLOYMENT', 'HISTORY', 'CAREER',
        'QUALIFICATION',
        'VOLUNTEER', 'SERVICE',
        'ACTIVITY', 'INVOLVEMENT', 'LEADERSHIP'
    ]
    """
    Markdown processor converts plain text to structured markdown
    to facilitate better section detection and parsing
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize markdown processor with configuration
        
        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        self.COMMON_HEADERS_UPPER = [h.upper() for h in self.COMMON_HEADERS_LIST]
        self.HEADER_KEYWORDS_UPPER = [k.upper() for k in self.HEADER_KEYWORDS_LIST]
        
        # Keep subheader patterns if _is_subheader uses them, old header patterns are now managed by _is_section_header logic
        self.section_patterns = {
            'subheader': [
                # Existing patterns (match lines ending with a colon, allow trailing spaces)
                r'^\s*(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,3}):\s*$',  # Title Case:
                r'^\s*(?:[A-Z][A-Z\s]{2,}):\s*$',                   # ALL CAPS:
                
                # New patterns:
                # Pattern A: Entity with a parenthesized date (e.g., "Job Title at Company (Date)", "Degree (Date)")
                # Requires a year (\d{4}) in the parentheses. Allows for apostrophes and initials.
                r'^(?:[A-Z][\w\s.,''&()-]+?)(?:\s(?:at|in|of|-|,)\s(?:[A-Z][\w\s.,''&()-]+?))?\s*\(.*\d{4}.*\)\s*$',
                
                # Pattern B: Title, Subtitle with a comma (e.g., "Degree, Major", "Topic, Subtopic")
                # Does not require a date. Allows for apostrophes and initials.
                r'^[A-Z][\w\s.,''&()-]+?,\s*[A-Z][\w\s.,''&()-]+?\s*$',
                
                # Pattern C: General Title Case phrase (2-6 "word units"), for titles/degrees without colons/dates/commas.
                # A "word unit" can be a full word (e.g., Master's) or initials (e.g., B.S.).
                # Avoids ending with a colon (handled by above) or a period (likely a sentence on its own).
                r'^(?:(?:[A-Z][a-z]+(?:[‘’](?:s|t|d|ve|ll|re))?)|[A-Z]\.(?:[A-Z]\.)?)(?:\s+(?:(?:[A-Z][a-z]+(?:[‘’](?:s|t|d|ve|ll|re))?)|[A-Z]\.(?:[A-Z]\.)?)){1,5}(?:\s+-\s+[A-Za-z\s]+)?(?<![:\.])$'
            ]
        }
    
    async def process(self, text: str) -> str:
        """
        Convert plain text to structured markdown
        
        Args:
            text: Plain text input
            
        Returns:
            Markdown formatted text
        """
        if not text:
            return ""
        
        # Normalize line endings and spacing
        text = self._normalize_text(text)
        
        # Split into lines for processing
        lines = text.split('\n')
        markdown_lines = []
        
        # Process line by line
        for line in lines:
            # Skip empty lines
            if not line.strip():
                markdown_lines.append('')
                continue
            
            # Check if this looks like a section header
            if self._is_section_header(line):
                # Add empty line before headers for better separation
                if markdown_lines and markdown_lines[-1]:
                    markdown_lines.append('')
                markdown_lines.append(f"## {line.strip()}")
                continue
                
            # Check if this looks like a subheader/subsection
            if self._is_subheader(line):
                # Add empty line before subheaders
                if markdown_lines and markdown_lines[-1]:
                    markdown_lines.append('')
                markdown_lines.append(f"### {line.strip()}")
                continue
            
            # Check if this looks like a bullet point
            if self._is_bullet_point(line):
                # Make sure it's properly formatted
                formatted_bullet = self._format_bullet_point(line)
                # DEBUGGING:
                # print(f"MD_PROCESSOR_DEBUG: Original line: '{line}'")
                # print(f"MD_PROCESSOR_DEBUG: Is bullet? True. Formatted: '{formatted_bullet}'")
                markdown_lines.append(formatted_bullet)
                continue
            # else: # DEBUGGING:
                # print(f"MD_PROCESSOR_DEBUG: Original line: '{line}'")
                # print(f"MD_PROCESSOR_DEBUG: Is bullet? False.")

            # Regular text content
            markdown_lines.append(line)
        
        return '\n'.join(markdown_lines)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text: consistent line endings, spacing, etc."""
        # Diagnostic print for lines with • before any processing
        # for i, l_orig in enumerate(text.split('\n')):
        #     if '•' in l_orig:
        #         print(f"NORMALIZE_TEXT_PRE_SPLIT[{i}]: RAW='{l_orig}'")

        # Replace various line endings with standard \n
        text = re.sub(r'\r\n|\r', '\n', text)
        
        # Replace multiple consecutive whitespace characters (including tabs, etc.) with a single space
        # text = re.sub(r'\s{2,}', ' ', text) # This might be too aggressive if \s includes \n

        # Let's try a multi-step normalization for spaces carefully
        lines = text.split('\n')
        normalized_lines = []
        for i, l_proc in enumerate(lines):
            original_line_for_debug = l_proc
            is_bullet_line_for_debug = '•' in original_line_for_debug

            if is_bullet_line_for_debug:
                print(f"NORMALIZE_TEXT_BEFORE_RESUB[{i}]: '{original_line_for_debug}' (len {len(original_line_for_debug)})")
                # Print char codes for the first few chars
                char_codes = [ord(c) for c in original_line_for_debug[:10]] # First 10 chars
                print(f"NORMALIZE_TEXT_BEFORE_RESUB_CHAR_CODES[{i}]: {char_codes}")


            # Replace multiple consecutive spaces (ASCII 32) on this line with a single space
            l_proc = re.sub(r' {2,}', ' ', l_proc)
            
            if is_bullet_line_for_debug:
                print(f"NORMALIZE_TEXT_AFTER_RESUB[{i}]: '{l_proc}' (len {len(l_proc)})")
                char_codes_after = [ord(c) for c in l_proc[:10]] # First 10 chars
                print(f"NORMALIZE_TEXT_AFTER_RESUB_CHAR_CODES[{i}]: {char_codes_after}")

            normalized_lines.append(l_proc)
        text = '\n'.join(normalized_lines)
        
        # Replace form feeds and other special characters
        text = re.sub(r'\f', '\n\n', text)
        
        # Remove excessive newlines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _is_section_header(self, line: str) -> bool:
        """Check if a line looks like a section header based on refined logic."""
        stripped_line = line.strip()
        line_len = len(stripped_line)

        if not (3 <= line_len <= 50):
            return False

        line_upper = stripped_line.upper()

        # 1. Check for exact match with common_headers (case-insensitive)
        if line_upper in self.COMMON_HEADERS_UPPER:
            return True

        # 2. Check for lines ending with a colon (strong indicator)
        if re.match(self.COLON_HEADER_REGEX, stripped_line):
            # Ensure the part before colon is not just noise
            if 3 <= len(stripped_line.rsplit(':', 1)[0].strip()) <= 50:
                 return True

        # 3. Check for ALL CAPS or Title Case lines that also contain section keywords
        is_all_caps = re.match(self.ALL_CAPS_HEADER_REGEX, stripped_line)
        is_title_case = re.match(self.TITLE_CASE_HEADER_REGEX, stripped_line)

        if is_all_caps or is_title_case:
            # Check for keywords only if it's ALL CAPS or Title Case
            for keyword in self.HEADER_KEYWORDS_UPPER:
                if keyword in line_upper:
                    # Check for word boundaries to avoid partial matches like 'CAT' in 'CERTIFICATION'
                    # This regex ensures the keyword is a whole word
                    if re.search(r'\b' + re.escape(keyword) + r'\b', line_upper):
                        return True
            
            # Heuristic: if a line is ALL CAPS or Title Case, very short (2-3 words),
            # and does NOT contain any major keywords, it might be a name or a short title
            # not intended as a section header. This path makes it NOT a header.
            # Example: "JANE SMITH" or "Interim Report"
            # However, if it's longer, it's more likely a header even without specific keywords.
            # E.g., "A Brief Overview Of My Accomplishments"
            num_words = len(stripped_line.split())
            if num_words >= 4: # If 4 or more words and ALL_CAPS/Title_Case, consider it a header
                return True
            # If 1-3 words and no keywords, it's not a header by this rule.

        return False
    
    def _is_subheader(self, line: str) -> bool:
        """Check if a line looks like a subheader"""
        line = line.strip()
        # Skip very long lines or very short ones
        if len(line) > 70 or len(line) < 3:
            return False
        
        for pattern in self.section_patterns['subheader']:
            if re.match(pattern, line):
                return True
            
        return False
    
    def _is_bullet_point(self, line: str) -> bool:
        """Check if line appears to be a bullet point"""
        stripped_line = line.strip()
        
        # Diagnostic print - UNCOMMENTED FOR THIS RUN
        print(f"MD_IS_BULLET_CHECK: Line: '{line}', Stripped: '{stripped_line}'")
        if stripped_line:
            print(f"MD_IS_BULLET_CHECK: Stripped[0] Unicode: {ord(stripped_line[0]) if stripped_line else 'N/A'}, Expected • (U+2022): {ord('•')}")

        # Simplified check for now
        if stripped_line.startswith('•') or stripped_line.startswith('*') or stripped_line.startswith('-'):
            print("MD_IS_BULLET_CHECK: Simplified check TRUE")
            return True

        # Common bullet point markers, allow optional space after bullet
        bullet_markers = [r'^\s*[\•\-\*\✓\✔\■\○\◉\◆]\s*', r'^\s*\d+\.\s']
        
        for marker_regex in bullet_markers:
            # Check if the line starts with a bullet marker followed by some text,
            # or is just a bullet marker (less likely but good to be robust)
            if re.match(marker_regex + r'(\S+.*)?$', stripped_line):
                print(f"MD_IS_BULLET_CHECK: Regex '{marker_regex}' TRUE")
                return True
        
        print("MD_IS_BULLET_CHECK: All checks FALSE")
        return False
    
    def _format_bullet_point(self, line: str) -> str:
        """Format bullet point consistently, preserving original bullet if standard."""
        stripped_line = line.strip()
        
        # Try to match and capture the original bullet and the text after it
        # This regex captures the bullet character and the rest of the line.
        # It allows for optional space after the bullet.
        bullet_match = re.match(r'^\s*([\•\-\*\✓\✔\■\○\◉\◆])\s*(.*)', stripped_line)
        if bullet_match:
            original_bullet = bullet_match.group(1)
            text_after_bullet = bullet_match.group(2).strip()
            # Return with the original bullet, ensuring one space after it
            return f"{original_bullet} {text_after_bullet}"
            
        # Format numbered bullets (e.g., "1. Item")
        numbered_match = re.match(r'^\s*(\d+)\.\s*(.*)', stripped_line)
        if numbered_match:
            number = numbered_match.group(1)
            text_after_number = numbered_match.group(2).strip()
            return f"{number}. {text_after_number}"
            
        # Fallback if no specific bullet pattern matched but _is_bullet_point was true
        # This case should ideally not be hit if _is_bullet_point is accurate.
        # Default to using '*' if it's an unrecognized bullet format.
        # However, if the stripped_line *still* starts with a bullet, preserve it.
        if stripped_line and stripped_line[0] in '•*-+✓✔■○◉◆':
            return f"{stripped_line[0]} {stripped_line[1:].strip()}"
        return f"* {stripped_line.lstrip('•*-+✓✔■○◉◆').strip()}"
