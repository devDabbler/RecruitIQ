"""
Intelligent text processor for resume parsing pipeline.
Provides text cleaning, normalization, and section splitting utilities.
"""

from typing import Any, Dict, Optional, NamedTuple

class TextProcessingConfig(NamedTuple):
    preserve_formatting: bool = True
    remove_headers: bool = False
    normalize_bullets: bool = True
    deep_clean: bool = True
    fix_merged_words: bool = True
    normalize_dates: bool = True

class TextProcessingResult(NamedTuple):
    cleaned_text: str
    sections: Optional[Dict[str, str]] = None

class IntelligentTextProcessor:
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        self.config = config or TextProcessingConfig()

    def clean_text(self, text: str) -> str:
        """Enhanced text cleaning with better bullet point detection and normalization"""
        import re
        
        # Preserve original text for processing
        original_text = text
        
        # Fix merged words (common PDF extraction issue)
        if self.config.fix_merged_words:
            # Fix common merged words
            text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
            # Fix specific common cases
            text = re.sub(r'\b([A-Z])\s+([a-z]+)\b', r'\1\2', text)  # "A WS" -> "AWS"
            text = re.sub(r'\b([a-z]+)\s+([A-Z][a-z]+)\b', r'\1\2', text)  # "Java Script" -> "JavaScript"
        
        # Enhanced bullet point normalization
        if self.config.normalize_bullets:
            # Normalize various bullet characters to standard bullet
            text = re.sub(r'[\u2022\u2023\u25e6\u2043\u2219\u2022\u25aa\u25ab\u25cf\u25cb\u25a0\u25a1]', '•', text)
            # Also handle dash bullets
            text = re.sub(r'^\s*[-*+]\s+', '• ', text, flags=re.MULTILINE)
            
            # Enhanced bullet point detection for lines without explicit bullets
            # Look for lines that appear to be bullet points based on content patterns
            lines = text.split('\n')
            processed_lines = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    processed_lines.append(line)
                    continue
                
                # Check if this line looks like a bullet point
                is_bullet_point = False
                
                # Pattern 1: Line starts with bullet marker
                if re.match(r'^\s*[•\-*+]\s+', line):
                    is_bullet_point = True
                
                # Pattern 2: Line contains technology lists (common in resume bullet points)
                tech_patterns = [
                    r'\b(C#|JavaScript|TypeScript|PHP|Python|Java|C\+\+|Ruby|Swift|Go|Rust)\b',
                    r'\b(React|Angular|Vue|Node\.js|ASP\.NET|Django|Laravel|Express)\b',
                    r'\b(AWS|Azure|GCP|SQL Server|MySQL|PostgreSQL|MongoDB|Redis)\b',
                    r'\b(Visual Studio|VS Code|IntelliJ|Eclipse|Xcode|Android Studio)\b',
                    r'\b(Git|Docker|Kubernetes|Jenkins|CI/CD|Agile|Scrum)\b'
                ]
                
                for pattern in tech_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Check if this line is likely a continuation of a bullet point
                        # Look at previous line to see if it's part of the same job description
                        if i > 0 and processed_lines:
                            prev_line = processed_lines[-1].strip()
                            # If previous line ends with a bullet point or is a job title, this might be a bullet
                            if (prev_line.endswith('.') or 
                                re.search(r'\b(Engineer|Developer|Manager|Analyst|Designer|Specialist)\b', prev_line, re.IGNORECASE) or
                                re.search(r'\b(at|,)\s+[A-Z][a-zA-Z\s&]+', prev_line)):
                                is_bullet_point = True
                                break
                
                # Pattern 3: Short lines that look like technology lists
                if len(line.split(',')) >= 2 and len(line) < 100:
                    # Check if it's mostly technology terms
                    tech_terms = line.split(',')
                    tech_count = sum(1 for term in tech_terms if re.search(r'\b[A-Z][a-zA-Z0-9\s\.]+\b', term.strip()))
                    if tech_count >= 2:
                        is_bullet_point = True
                
                # Add bullet marker if detected
                if is_bullet_point and not line.startswith('•'):
                    line = f"• {line}"
                
                processed_lines.append(line)
            
            text = '\n'.join(processed_lines)
        
        # Normalize dates
        if self.config.normalize_dates:
            text = text.replace('Present', 'Current')
            text = re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', 
                         lambda m: m.group(1).title(), text)
        
        # Deep clean (remove excessive whitespace)
        if self.config.deep_clean:
            # Remove excessive newlines but preserve structure
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text)
        
        return text

    def split_into_sections(self, text: str) -> Dict[str, str]:
        # Minimal stub: pretend to split into sections
        return {"main": text}

    async def process(self, text: str) -> dict:
        cleaned = self.clean_text(text)
        sections = self.split_into_sections(cleaned) if self.config.preserve_formatting else None
        stats = {
            "length": len(cleaned),
            "num_sections": len(sections) if sections else 0
        }
        return {
            "processed_text": cleaned,
            "sections": sections,
            "stats": stats
        }
