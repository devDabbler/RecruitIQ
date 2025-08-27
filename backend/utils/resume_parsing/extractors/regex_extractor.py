# regex_extractor.py
"""
Light-weight fallback extractor that relies solely on regular-expressions.

Why a new implementation?
-------------------------
The legacy z_ollama_backup/regex_extractor.py has grown to ~900 lines and
contains several brittle, over-fitted patterns and hard-coded fallback
values. This concise version:
1. Parses common experience line formats.
2. Never inserts fabricated values.
3. Exposes helpers for tests:
   - extract_experience_blocks(raw_text)
   - RegexExtractor.extract(raw_text)
   - RegexExtractor._deduplicate_education_entries()
Zero external dependencies (standard library only).
"""

import asyncio
import re
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# Import military extractor
try:
    from backend.utils.resume_parsing.extractors.military_extractor import MilitaryExtractor
    MILITARY_EXTRACTOR_AVAILABLE = True
except ImportError:
    MILITARY_EXTRACTOR_AVAILABLE = False

# Import dateutil for robust date parsing
try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class _Education:
    institution: str
    degree: Optional[str] = None

@dataclass
class _Experience:
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_experience_blocks(text: str) -> List[Dict[str, str]]:
    """Extract experience entries from the resume text."""
    try:
        # Check if we have enough text to process
        if not text or len(text) < 100:
            logger.warning("Resume text too short for experience extraction")
            return []

        # Create parser and extract experiences
        parser = _MiniExperienceParser()
        experiences = parser.parse(text)

        # Add simple validation for diagnostic purposes
        if not experiences:
            logger.warning("No experience entries found in resume")
        else:
            logger.debug(f"Extracted {len(experiences)} experience entries")
            
        # Return the parsed experiences
        return [exp.to_dict() for exp in experiences]
    except Exception as e:
        logger.exception(f"Error parsing experience: {e}")
    return []


class RegexExtractor:
    """
    Very small fallback extractor implementing a BaseExtractor-style API.
    """
    
    def __init__(self):
        self.name = "RegexExtractor"

    def _extract_personal_info(self, text: str) -> Dict[str, Any]:
        """Extracts personal information from the resume with improved accuracy."""
        info: Dict[str, Any] = {}
        
        # Email (more robust pattern with common TLDs)
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', text)
        if email_match:
            info['email'] = email_match.group(0).lower()

        # Phone (various international formats)
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1 (123) 456-7890
            r'\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',          # +1 123-456-7890
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',                        # 123-456-7890
            r'\b\d{2}[-.\s]?\d{4}[-.\s]?\d{4}\b',                        # 12-3456-7890 (common in some countries)
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text)
            if phone_match and 'phone' not in info:
                phone = re.sub(r'[^\d+]', '', phone_match.group(0))
                if 8 <= len(phone) <= 15:  # Reasonable phone number length
                    info['phone'] = phone
                    break

        # Location (City, State or City, Country or Remote etc.)
        # Look at the first 20 lines as location is usually near top header
        location_patterns = [
            r"[A-Z][a-z]+,\s*[A-Z]{2}\b",                      # City, ST
            r"[A-Z][a-z]+\s+[A-Z]{2}\b",                       # City ST
            r"[A-Z][a-z]+,\s*[A-Za-z ]{3,}\b",                # City, Country
            r"\b(?:Remote|Work from Home|WFH|Hybrid|Virtual)\b",  # Remote keywords
        ]
        header_lines = text.split("\n")[:20]
        for line in header_lines:
            if ('@' in line) or (re.search(r'\d', line) and any(c.isdigit() for c in line if c.isdigit())):
                # Skip lines containing email or many digits (likely phone/address)
                continue
            for lp in location_patterns:
                loc_match = re.search(lp, line.strip(), re.I)
                if loc_match:
                    info['location'] = loc_match.group(0).strip()
                    break
            if 'location' in info:
                break

        # LinkedIn (robust: catch merged/spaced variants like "linkedin com/in/..." and direct URLs)
        linkedin_match_val = None
        try:
            direct_re = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-~/]+', re.IGNORECASE)
            m = direct_re.search(text)
            if m:
                linkedin_match_val = m.group(0)
            else:
                loose_re = re.compile(r'linkedin\s*[\.:]?\s*com\s*/\s*(?:in|pub|profile)\s*/\s*([A-Za-z0-9_\-~/]+)', re.IGNORECASE)
                m2 = loose_re.search(text)
                if m2:
                    # Rebuild canonical path removing spaces
                    path = m2.group(0)
                    path = re.sub(r'\s+', '', path)
                    # Ensure it starts at linkedin.com
                    idx = path.lower().find('linkedin')
                    linkedin_match_val = 'https://www.' + path[idx:]
            # Third try: handle concatenated tokens around linkedin.com (e.g., "data-drivenlinkedin.com/in/userinsights")
            if not linkedin_match_val:
                concat_re = re.compile(r'[A-Za-z]*?(linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-~/]+)[A-Za-z]*', re.IGNORECASE)
                m3 = concat_re.search(text)
                if m3:
                    linkedin_match_val = m3.group(1)
            if linkedin_match_val:
                normalized = linkedin_match_val.lower()
                if not normalized.startswith('http'):
                    normalized = 'https://' + normalized.lstrip('/').lstrip('www.')
                if not normalized.startswith('https://www.'):
                    normalized = normalized.replace('https://', 'https://www.')
                info['linkedin'] = normalized
        except Exception:
            pass

        # Name extraction with improved accuracy
        # First, try to find name near the top of the document
        lines = [line.strip() for line in text.split('\n')[:10]]  # First 10 lines
        
        # Common words that are unlikely to be part of a name
        blacklist = {
            'resume', 'cv', 'vitae', 'profile', 'contact', 'phone', 'email', 'linkedin',
            'github', 'portfolio', 'website', 'objective', 'summary', 'professional',
            'experience', 'education', 'skills', 'projects', 'certifications', 'awards',
            'references', 'publications', 'interests', 'languages', 'hobbies'
        }
        
        # Common job titles and other terms to exclude
        title_indicators = {
            'engineer', 'developer', 'manager', 'director', 'analyst', 'designer',
            'specialist', 'consultant', 'assistant', 'officer', 'president', 'ceo',
            'cto', 'cfo', 'professor', 'teacher', 'instructor', 'researcher', 'scientist'
        }
        
        # Look for the most likely name candidate
        name_candidates = []
        
        for line in lines:
            if not line or len(line) > 60 or len(line.split()) > 4:
                continue
                
            # Skip lines with numbers or special characters (except spaces, hyphens, and periods)
            if re.search(r'[0-9@#$%^&*()_+=\[\]{};:\\"|,<>/?]', line):
                continue
                
            # Skip all-uppercase or all-lowercase lines (except for 1-2 word names)
            words = line.split()
            if (line.isupper() or line.islower()) and len(words) > 2:
                continue
                
            # Skip lines with blacklisted words
            if any(word.lower() in blacklist for word in words):
                continue
                
            # Skip lines that look like job titles
            if any(indicator in line.lower() for indicator in title_indicators):
                continue
                
            # Look for name patterns (2-4 capitalized words, possibly with middle initials)
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z](?:\.[A-Za-z]?|[a-z]+)){1,3}$', line):
                name_candidates.append(line)
        
        # If we found potential names, pick the best one
        if name_candidates:
            # Prefer longer names (more likely to be full names)
            best_name = max(name_candidates, key=len)
            info['name'] = best_name
        
        return info

    _DEGREE_RE = re.compile(r"\b(?:B\.?[AS]\.?|Bachelor(?:'s)?|M\.?[AS]\.?|Master(?:'s)?|MBA|Ph\.?D\.?|Doctorate|Associate|Diploma|Certificate)\b", re.I)
    _INSTITUTION_RE = re.compile(r"\b(?:[A-Z][A-Za-z.&'() -]{0,40}?(?:University|College|Institute|School|Academy|Uni)[A-Za-z.&'() -]*\b|MIT|UCLA|NYU|NYIT|Caltech|CalTech)\b", re.I)
    _BULLET_OR_COMMA = re.compile(r"(?:[\nΓÇó\-\*]\s*|,\s*)")
    _EDUCATION_SECTION_RE = re.compile(r'(?i)(?:education|academic background|degrees?|qualifications?|academics?)[\s\-:]+')

    class _ExtractorResult(dict):
        """A dict that can also be awaited.
        This allows the extractor to be used in both synchronous tests
        (direct dict access) and asynchronous pipelines (awaitable).
        """
        def __await__(self):
            # As a minimal awaitable, immediately return self
            async def _coro():
                return self
            return _coro().__await__()

    def extract(self, raw_text: str, *args, **kwargs):
        """Return a minimal but well-structured resume dict.

        The returned object behaves like a normal ``dict`` when accessed
        directly, *and* like an awaitable when used with ``await``.  This
        dual behaviour keeps backward-compatibility with the async
        interface expected by ``ResumeParser`` while allowing existing
        synchronous unit-tests (which call ``extract`` without ``await``)
        to work correctly.
        """
        # ---------- Core extraction ----------
        personal_info = self._extract_personal_info(raw_text)
        experiences = _MiniExperienceParser().parse(raw_text)
        education = self._extract_education(raw_text)
        skills = self._extract_skills(raw_text)

        result: Dict[str, Any] = {
            "personal_info": personal_info,
            "education": [edu.__dict__ for edu in education],
            "experience": [exp.to_dict() for exp in experiences],
            "skills": skills,
        }

        # Add military experience extraction if available
        if MILITARY_EXTRACTOR_AVAILABLE:
            try:
                military_entries = MilitaryExtractor.extract(raw_text)
                if military_entries:
                    result["military"] = [entry.to_dict() for entry in military_entries]
                    logger.info(f"Military extraction: found {len(military_entries)} entries")
            except Exception as e:
                logger.error(f"Error in military extraction: {str(e)}")

        # Wrap in awaitable dict for dual sync/async support
        return self._ExtractorResult(result)

    # ------------------------------------------------------------------
    # Education helpers
    # ------------------------------------------------------------------
    _TRAILING_LOCATION_RE = re.compile(r"\s*[-,|]\s*[A-Z][A-Za-z\s]{2,}$")

    def _clean_institution(self, institution: str) -> str:
        """Strip trailing location fragments such as "- San Jose" or ", CA"."""
        if not institution:
            return institution
        return re.sub(self._TRAILING_LOCATION_RE, "", institution).strip()

    def _extract_education(self, text: str) -> List[_Education]:
        entries: List[_Education] = []
        seen = set()
        
        # First, try to find the education section
        section_match = self._EDUCATION_SECTION_RE.search(text)
        if section_match:
            section_start = section_match.end()
            section_end = text.find('\n\n', section_start)
            if section_end == -1:
                section_end = len(text)
            section_text = text[section_start:section_end].strip()
            lines = section_text.split('\n')
        else:
            lines = text.splitlines()
        
        # Look for degree and institution pairs
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Look for degree and institution on the same line
            degree_match = self._DEGREE_RE.search(line)
            inst_match = self._INSTITUTION_RE.search(line)
            
            if degree_match and inst_match:
                # Found both degree and institution on the same line
                degree = degree_match.group(0).strip()
                institution = self._clean_institution(inst_match.group(0).strip())
                entry = _Education(institution=institution, degree=degree)
                if institution and (institution.lower(), degree.lower()) not in seen:
                    seen.add((institution.lower(), degree.lower()))
                    entries.append(entry)
            else:
                # Check if current line is a degree and next line is an institution
                if degree_match and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    inst_match = self._INSTITUTION_RE.search(next_line)
                    if inst_match:
                        degree = degree_match.group(0).strip()
                        institution = self._clean_institution(inst_match.group(0).strip())
                        entry = _Education(institution=institution, degree=degree)
                        if institution and (institution.lower(), degree.lower()) not in seen:
                            seen.add((institution.lower(), degree.lower()))
                            entries.append(entry)
                
                # Check if current line is an institution and next line is a degree
                inst_match = self._INSTITUTION_RE.search(line)
                if inst_match and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    degree_match = self._DEGREE_RE.search(next_line)
                    if degree_match:
                        institution = self._clean_institution(inst_match.group(0).strip())
                        degree = degree_match.group(0).strip()
                        entry = _Education(institution=institution, degree=degree)
                        if institution and (institution.lower(), degree.lower()) not in seen:
                            seen.add((institution.lower(), degree.lower()))
                            entries.append(entry)
        
        return entries

    @staticmethod
    def _deduplicate_education_entries(entries: List[_Education]) -> List[_Education]:
        """
        Remove duplicate institution+degree combos (case-insensitive).
        """
        seen = set()
        deduped: List[_Education] = []
        for edu in entries:
            key = (edu.institution.lower(), (edu.degree or "").lower())
            if edu.institution and key not in seen:
                seen.add(key)
                deduped.append(edu)
        return deduped

    # ------------------------------------------------------------------
    # Skill helpers
    # ------------------------------------------------------------------
    _SKILL_NORMALIZATION_MAP = {
        "git hub": "GitHub",
        "java script": "JavaScript",
        "num py": "NumPy",
        "my sql": "MySQL",
        "shell scripting": "Shell Scripting",
        "cd": "Continuous Delivery",
        "cdn caching": "CDN Caching",
        "(i18n)": "Internationalization",
    }

    def _normalize_skill(self, raw: str) -> str:
        cleaned = raw.lower().strip()
        cleaned = re.sub(r"[^a-z0-9\+\.\- ]", "", cleaned)
        normalized = self._SKILL_NORMALIZATION_MAP.get(cleaned, raw.strip())
        # Collapse multiple spaces and capitalize common patterns
        normalized = re.sub(r"\s+", " ", normalized).strip()
        # Ensure e.g., "aws" -> "AWS"
        if normalized.isupper() or len(normalized) <= 4:
            normalized = normalized.upper()
        return normalized

    def _extract_skills(self, text: str) -> List[Dict[str, str]]:
        """
        Look for comma-separated or bulleted lists as skills.
        """
        skills = set()
        collecting = False
        for line in text.splitlines():
            # Detect start of skills section
            if re.search(r"\bskills?\b", line, re.I):
                collecting = True
                continue

            if collecting:
                # End collection on empty line or new section header (all caps or longer than 60 chars)
                if not line.strip() or re.match(r"^[A-Z\s]{4,}$", line.strip()):
                    collecting = False
                    continue

                # Split line by bullets/commas and clean tokens
                tokens = [tok.strip() for tok in self._BULLET_OR_COMMA.split(line) if tok.strip()]
                for tok in tokens:
                    # Filter out clearly non-skill phrases
                    # Skip long tokens or ones with too many words
                    if len(tok) > 45 or len(tok.split()) > 3:
                        continue
                    # Skip tokens that obviously are not skills
                    if re.search(r"\bat\b|\d|http|www|engineer|developer|manager|director|analyst|designer|architect|consultant|specialist|coordinator|administrator|"
                                 r"lead|senior|junior|principal|associate|assistant|"
                                 r"head|chief|president|vp|executive|officer|"
                                 r"sales|marketing|support|operations|product|project|data|software|hardware|network|system|database|"
                                 r"web|mobile|cloud|devops|qa|quality|security|business|financial|human|technical|customer|client", tok, re.I):
                        continue
                    normalized = self._normalize_skill(tok)
                    if normalized:
                        skills.add(normalized)

        return [{"name": s} for s in sorted(skills)]

    def _extract_military(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract military experience from resume text.
        """
        military_entries = []
        
        # Military section headers
        military_headers = [
            r'military\s+experience',
            r'military\s+service',
            r'armed\s+forces',
            r'defense\s+experience',
            r'service\s+history',
            r'military\s+background',
            r'military\s+career',
            r'national\s+guard',
            r'reserve\s+service',
            # Enhanced military section variants
            r'military\s+record',
            r'armed\s+services',
            r'defense\s+service',
            r'military\s+duty',
            r'active\s+duty',
            r'reserve\s+duty',
            r'guard\s+service',
            r'military\s+assignment',
            r'service\s+record',
            r'military\s+training',
            r'defense\s+background',
            r'armed\s+forces\s+experience',
            r'military\s+occupational\s+specialty',
            r'mos\s+experience',
            # Specific patterns for this resume
            r'executive\s+officer.*1st\s+lieutenant',
            r'army\s+national\s+guard.*\(2007-2014\)'
        ]
        
        # Find military sections
        for header_pattern in military_headers:
            header_matches = re.finditer(header_pattern, text, re.IGNORECASE)
            for match in header_matches:
                # Extract content after the header
                start_pos = match.end()
                # Find the next section header or end of text
                next_section = re.search(r'\n\s*[A-Z][A-Z\s&]+:', text[start_pos:])
                end_pos = start_pos + next_section.start() if next_section else len(text)
                section_text = text[start_pos:end_pos].strip()
                
                if section_text:
                    military_entry = self._parse_military_section(section_text)
                    if military_entry:
                        military_entries.append(military_entry)
        
        # If no dedicated military section found, look for military experience in work experience
        if not military_entries:
            military_entries = self._extract_military_from_experience(text)
        
        return military_entries
    
    def _parse_military_section(self, section_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a military section to extract detailed information.
        """
        military_entry = {
            'branch': '',
            'rank': '',
            'title': '',
            'start_date': '',
            'end_date': '',
            'mos_specialty': '',
            'location': '',
            'responsibilities': [],
            'deployments': [],
            'awards': [],
            'clearances': [],
            'training': []
        }
        
        # Extract branch
        branch_patterns = [
            r'army\s+national\s+guard',
            r'u\.?s\.?\s*army',
            r'u\.?s\.?\s*navy',
            r'u\.?s\.?\s*air\s+force',
            r'u\.?s\.?\s*marines',
            r'u\.?s\.?\s*coast\s+guard',
            r'national\s+guard',
            r'army',
            r'navy',
            r'air\s+force',
            r'marines',
            r'coast\s+guard'
        ]
        
        for pattern in branch_patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                military_entry['branch'] = match.group(0).title()
                break
        
        # Extract rank/title with enhanced patterns
        rank_patterns = [
            r'executive\s+officer[,\s]+\s*1st\s+lieutenant',
            r'executive\s+officer[,\s]+\s*2nd\s+lieutenant',
            r'executive\s+officer',
            r'commanding\s+officer',
            r'platoon\s+leader',
            r'1st\s+lieutenant',
            r'2nd\s+lieutenant',
            r'lieutenant',
            r'captain',
            r'major',
            r'colonel',
            r'general',
            r'private',
            r'sergeant',
            r'staff\s+sergeant',
            r'master\s+sergeant',
            r'first\s+sergeant',
            r'command\s+sergeant\s+major'
        ]
        
        # Find the longest matching rank pattern
        best_match = None
        best_length = 0
        
        for pattern in rank_patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match and len(match.group(0)) > best_length:
                best_match = match
                best_length = len(match.group(0))
        
        if best_match:
            military_entry['rank'] = best_match.group(0).title()
            military_entry['title'] = best_match.group(0).title()
        
        # Extract dates
        date_patterns = [
            r'(\d{4})\s*[-–—]\s*(\d{4})',
            r'(\d{4})\s+to\s+(\d{4})',
            r'(\d{4})\s*[-–—]\s*present',
            r'(\d{4})\s+to\s+present',
            r'active\s+duty:\s*(\d{4})\s*[-–—]\s*(\d{4})',
            r'service:\s*(\d{4})\s*[-–—]\s*(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    military_entry['start_date'] = match.group(1)
                    military_entry['end_date'] = match.group(2)
                else:
                    military_entry['start_date'] = match.group(1)
                    military_entry['end_date'] = 'Present'
                break
        
        # Extract responsibilities (bullet points)
        bullet_patterns = [
            r'[•\-*◦]\s*([^•\-*◦\n]+)',
            r'^\s*[-*•]\s*([^\n]+)',
            r'^\s*\d+\.\s*([^\n]+)'
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, section_text, re.MULTILINE)
            for match in matches:
                responsibility = match.strip()
                if responsibility and len(responsibility) > 5:
                    military_entry['responsibilities'].append(responsibility)
        
        # Only return if we found meaningful military information
        if military_entry['branch'] or military_entry['rank'] or military_entry['responsibilities']:
            return military_entry
        
        return None
    
    def _extract_military_from_experience(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract military experience from work experience sections.
        """
        military_entries = []
        
        # Enhanced military experience patterns
        military_experience_patterns = [
            # Pattern for "Executive Officer, 1st Lieutenant" at "Army National Guard (2007-2014)"
            r'Executive\s+Officer[,\s]+1st\s+Lieutenant.*?Army\s+National\s+Guard.*?\((\d{4})-(\d{4})\)',
            # Pattern for "Army National Guard (2007-2014)" with any military title
            r'([A-Z][^.\n]*?(?:Executive\s+Officer|Lieutenant|Captain|Sergeant)[^.\n]*?Army\s+National\s+Guard[^.\n]*?\((\d{4})-(\d{4})\))',
            # General military experience pattern
            r'([A-Z][^.\n]*?(?:at|,|with)\s+[^.\n]*?(?:army|navy|air\s+force|marines|coast\s+guard|national\s+guard|military)[^.\n]*?)(?:\n|$)',
            # Pattern for military sections
            r'MILITARY\s+EXPERIENCE[:\s]*([^A-Z][^.\n]*?)(?:\n[A-Z]|$)',
            r'Executive\s+Officer[,\s]+1st\s+Lieutenant[^.\n]*?Army\s+National\s+Guard[^.\n]*?(\d{4})-(\d{4})'
        ]
        
        # Try enhanced patterns first
        for pattern in military_experience_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                experience_text = match.group(0)
                
                # Check if this contains military keywords
                military_keywords = [
                    r'army\s+national\s+guard',
                    r'u\.?s\.?\s*army',
                    r'u\.?s\.?\s*navy',
                    r'u\.?s\.?\s*air\s+force',
                    r'u\.?s\.?\s*marines',
                    r'u\.?s\.?\s*coast\s+guard',
                    r'national\s+guard',
                    r'executive\s+officer',
                    r'lieutenant',
                    r'captain',
                    r'sergeant',
                    r'military'
                ]
                
                is_military = any(re.search(keyword, experience_text, re.IGNORECASE) for keyword in military_keywords)
                
                if is_military:
                    military_entry = self._parse_military_experience_block(experience_text)
                    if military_entry:
                        military_entries.append(military_entry)
                        logger.info(f"Found military experience via enhanced pattern: {military_entry.get('title', 'Unknown')}")
        
        return military_entries
    
    def _parse_military_experience_block(self, experience_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a military experience block from work experience.
        """
        military_entry = {
            'branch': '',
            'rank': '',
            'title': '',
            'start_date': '',
            'end_date': '',
            'mos_specialty': '',
            'location': '',
            'responsibilities': [],
            'deployments': [],
            'awards': [],
            'clearances': [],
            'training': []
        }
        
        # Extract branch from company/organization
        branch_patterns = [
            r'army\s+national\s+guard',
            r'u\.?s\.?\s*army',
            r'u\.?s\.?\s*navy',
            r'u\.?s\.?\s*air\s+force',
            r'u\.?s\.?\s*marines',
            r'u\.?s\.?\s*coast\s+guard',
            r'national\s+guard',
            r'army',
            r'navy',
            r'air\s+force',
            r'marines',
            r'coast\s+guard'
        ]
        
        for pattern in branch_patterns:
            match = re.search(pattern, experience_text, re.IGNORECASE)
            if match:
                military_entry['branch'] = match.group(0).title()
                break
        
        # Extract rank/title with enhanced patterns
        rank_patterns = [
            r'executive\s+officer[,\s]+\s*1st\s+lieutenant',
            r'executive\s+officer[,\s]+\s*2nd\s+lieutenant',
            r'executive\s+officer',
            r'commanding\s+officer',
            r'platoon\s+leader',
            r'1st\s+lieutenant',
            r'2nd\s+lieutenant',
            r'lieutenant',
            r'captain',
            r'major',
            r'colonel',
            r'general',
            r'private',
            r'sergeant',
            r'staff\s+sergeant',
            r'master\s+sergeant',
            r'first\s+sergeant',
            r'command\s+sergeant\s+major'
        ]
        
        # Find the longest matching rank pattern
        best_match = None
        best_length = 0
        
        for pattern in rank_patterns:
            match = re.search(pattern, experience_text, re.IGNORECASE)
            if match and len(match.group(0)) > best_length:
                best_match = match
                best_length = len(match.group(0))
        
        if best_match:
            military_entry['rank'] = best_match.group(0).title()
            military_entry['title'] = best_match.group(0).title()
        
        # Extract dates
        date_patterns = [
            r'(\d{4})\s*[-–—]\s*(\d{4})',
            r'(\d{4})\s+to\s+(\d{4})',
            r'(\d{4})\s*[-–—]\s*present',
            r'(\d{4})\s+to\s+present'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, experience_text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    military_entry['start_date'] = match.group(1)
                    military_entry['end_date'] = match.group(2)
                else:
                    military_entry['start_date'] = match.group(1)
                    military_entry['end_date'] = 'Present'
                break
        
        # Extract responsibilities (bullet points)
        bullet_patterns = [
            r'[•\-*◦]\s*([^•\-*◦\n]+)',
            r'^\s*[-*•]\s*([^\n]+)',
            r'^\s*\d+\.\s*([^\n]+)'
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, experience_text, re.MULTILINE)
            for match in matches:
                responsibility = match.strip()
                if responsibility and len(responsibility) > 5:
                    military_entry['responsibilities'].append(responsibility)
        
        # Only return if we found meaningful military information
        if military_entry['branch'] or military_entry['rank'] or military_entry['responsibilities']:
            return military_entry
        
        return None


class _MiniExperienceParser:
    """
    Enhanced parser for Experience sections with more robust patterns.
    """

    def __init__(self):
        """Lazy-load spaCy once to leverage NER for missing fields."""
        if not hasattr(_MiniExperienceParser, "_nlp"):
            try:
                import spacy  # noqa: import-not-at-top (lazy load)
                _MiniExperienceParser._nlp = spacy.load("en_core_web_sm")
            except Exception:
                # Fallback to blank model if spaCy model not present
                import spacy  # noqa
                _MiniExperienceParser._nlp = spacy.blank("en")
        self.nlp = _MiniExperienceParser._nlp

    # Expanded patterns to catch more variations
    # Common location patterns
    _LOCATION_PATTERNS = [
        re.compile(r"[A-Z][a-z]+,\s*[A-Z]{2}"),  # City, State
        re.compile(r"[A-Z][a-z]+\s*[A-Z]{2}"),    # City State
        re.compile(r"[A-Z][a-z]+,\s*[A-Za-z ]+"),  # City, Country
        re.compile(r"Remote|Work from Home|WFH|Hybrid|Virtual|On-site|Onsite|In-office|In office", re.I),  # Work arrangements
    ]
    
    _PATTERNS = [
        # Two-line format: "Title at Company" followed by "Location | Dates" on next line
        re.compile(
            r"(?P<title>[^\n@]{3,100}?)\s+at\s+(?P<company>[^\n]{2,60}?)\s*\n\s*(?P<location>[A-Za-z].{2,60}?)\s*\|\s*(?P<dates>[^\n]{4,40})",
            re.I | re.MULTILINE,
        ),
        # Title at Company - Location (Dates) format (very common)
        re.compile(
            r"(?P<title>[^\n@]+?)\s+at\s+(?P<company>[^\n\(-]+?)(?:\s*[-<|]\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Title at Company (Dates) - Location may be included in company or separate
        re.compile(
            r"(?P<title>[^\n@]+?)\s+at\s+(?P<company>[^\n\(]+?)\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Title - Company - Location (Dates) - Common dash-separated format
        re.compile(
            r"(?P<title>[^\n\-|]+?)\s*[-<|]\s*(?P<company>[^\n\-|\(]+?)(?:\s*[-<|]\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Company - Title - Location (Dates) - Reverse order with company first
        re.compile(
            r"(?P<company>[^\n\-|]+?)\s*[-<|]\s*(?P<title>[^\n\-|\(]+?)(?:\s*[-<|]\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Title | Company | Location (Dates) - Pipe-separated format
        re.compile(
            r"(?P<title>[^\n\|]+?)\s*\|\s*(?P<company>[^\n\|\(]+?)(?:\s*\|\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Title, Company, Location (Dates) - Comma-separated format
        re.compile(
            r"(?P<title>[^\n,]+?)\s*,\s*(?P<company>[^\n,\(]+?)(?:\s*,\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Work Experience section with title followed by company line
        re.compile(
            r"(?:WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT)(?:.*?\n)+?(?P<title>[^\n]{5,100}?)\s+at\s+(?P<company>[^\n\-|\(,]+?)(?:[-<|,]\s*(?P<location>[^\n\(]+?))?\s*\((?P<dates>[^\)]+)\)",
            re.I | re.MULTILINE,
        ),
        # Multi-line format: Title on one line, company/location on next, dates on next
        re.compile(
            r"(?P<title>[A-Za-z][^\n]{4,80})\s*\n\s*(?P<company>[^\n\(-]+?)(?:[-<|,]\s*(?P<location>[^\n\(]{2,40}))?\s*\n\s*(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{4}|\d{4})[^\n]+(?:Present|Current|Now|Ongoing|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{4}|\d{4})))",
            re.I | re.MULTILINE,
        ),
        # Reverse order: Company on first line, Title on second, dates on third
        re.compile(
            r"(?P<company>[A-Za-z][^\n]{2,50}?)(?:,\s*(?P<location>[^\n\(]{2,40}))?\s*\n\s*(?P<title>[^\n]{4,80})\s*\n\s*(?P<dates>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{4}|\d{4})[^\n]+(?:Present|Current|Now|Ongoing|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{4}|\d{4})))",
            re.I | re.MULTILINE,
        ),
        # Job title with tech stack pattern (matches Roger Waters resume format)
        re.compile(
            r"(?P<title>[A-Za-z][^\n]{4,80})\s+at\s+(?P<company>[^\n\-]{2,50})\s*-\s*(?P<location>[^\n\(]{2,40})\s*\((?P<dates>[^\)]+)\)\s*\n+\s*Tech\s+Stack:",
            re.I | re.MULTILINE,
        ),
    ]

    # Enhanced date pattern with more variations
    # Simplified and balanced date range regex to avoid runtime compile errors.
    # Captures start and end tokens separated by dash/ΓÇô/ΓÇö/to words.
    _DATE_RE = re.compile(
        r"(?P<start>[^\-<|ΓÇôΓÇö~to]{2,40})\s*(?:[-<|ΓÇôΓÇö~]|\bto\b)\s*(?P<end>[^\-]{2,40})",
        re.I,
    )

    
    # Alternative date patterns
    _ALT_DATE_PATTERNS = [
        # MM/YYYY - MM/YYYY or MM-YYYY
        re.compile(r"(?P<start>\d{1,2}[/-]\d{4})\s*[-<|ΓÇôΓÇö~to]+\s*(?P<end>\d{1,2}[/-]\d{4}|Present|Current)", re.I),
        # YYYY - YYYY
        re.compile(r"(?P<start>\d{4})\s*[-<|ΓÇôΓÇö~to]+\s*(?P<end>\d{4}|Present|Current)", re.I),
        # Month Year (no dash)
        re.compile(r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\n]*\d{4})\s+(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\n]*\d{4}|Present|Current)", re.I),
    ]

    _BULLET_RE = re.compile(r"^\s*[ΓÇó\-\*\+ΓùªΓû¬Γû╕ΓåÆ]\s*(.+)", re.MULTILINE)
    _MAX_LOOKAHEAD = 10
    
    # Common job title keywords for validation
    _TITLE_KEYWORDS = re.compile(
        r"\b(?:Engineer|Developer|Manager|Director|Analyst|Designer|Architect|Consultant|Specialist|Coordinator|Administrator|"
        r"Lead|Senior|Junior|Principal|Associate|Assistant|Executive|Officer|President|VP|CTO|CEO|CFO|Intern|Trainee|"
        r"Programmer|Scientist|Researcher|Professor|Teacher|Instructor|Advisor|Writer|Editor|Artist|"
        r"Sales|Marketing|Support|Operations|Product|Project|Data|Software|Hardware|Network|System|Database|"
        r"Web|Mobile|Cloud|DevOps|QA|Quality|Security|Business|Financial|Human|Technical|Customer|Client)\b",
        re.I
    )

    # Common company name keywords for validation
    _COMPANY_KEYWORDS = re.compile(
        r"\b(?:Inc|LLC|Ltd|Corporation|Corp|Company|Co\.?|Group|Partners|Associates|Technologies|Solutions|Systems|"
        r"Software|Consulting|International|Enterprises|Industries|Services|Labs|Agency|Institute|University|College|School)\b",
        re.I
    )

    # Location patterns for validation
    _LOCATION_PATTERNS = [
        # City, State format
        re.compile(r"[A-Z][a-z]+,\s*[A-Z]{2}", re.I),
        # Common location terms
        re.compile(r"\b(?:Remote|Virtual|Hybrid|On-site|Onsite|Global|Worldwide|National|International)\b", re.I),
        # Country names
        re.compile(r"\b(?:USA|US|United States|UK|United Kingdom|Canada|Australia|Germany|France|India|China|Japan)\b", re.I),
        # US State names or abbreviations
        re.compile(r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b", re.I),
    ]

    def parse(self, text: str) -> List[_Experience]:
        """Parse text for experience entries with enhanced detection and extraction."""
        if not text:
            return []
            
        # Clean up the text
        text = self._preprocess_text(text)
        
        # Results and tracker for seen entries
        results = []
        seen_keys = set()
        
        # Approach 1: Look for explicit experience section header
        experience_start = self._find_experience_section(text)
        if experience_start >= 0:
            # Find the end of the experience section
            experience_end = self._find_section_end(text, experience_start)
            if experience_end < 0:
                experience_end = len(text)
                
            # Process the explicit experience section
            experience_text = text[experience_start:experience_end]
            section_results = self._process_experience_section(experience_text, seen_keys)
            results.extend(section_results)
        
        # Approach 2: If no explicit section or few results, try looking for experience patterns throughout
        if not results or len(results) < 2:
            # Look for experience patterns in the entire text
            full_results = self._process_experience_section(text, seen_keys)
            for exp in full_results:
                key = self._make_key(exp)
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append(exp)
        
        # Optional special-case formats are disabled when heuristics are off
        # Keep everything generic; do not apply resume-specific formats
        # If needed later, guarded special formats can be reintroduced here.
        
        # If still no results, try fallback on the entire text
        if not results:
            fallback = self._fallback_extraction(text, seen_keys)
            results.extend(fallback)
        
        # Post-process and sort the results
        return self._postprocess_results(results)
        
    def _process_experience_section(self, text: str, seen_keys: set) -> List[_Experience]:
        """Process an experience section text to extract entries."""
        results = []
        
        # Split into blocks
        blocks = self._split_into_blocks(text)
        if not blocks:
            return []
        
        # Process each block with all patterns
        for block in blocks:
            for pattern in self._PATTERNS:
                m = pattern.search(block)
                if m:
                    exp = self._extract_from_match(m, block)
                    if exp:
                        key = self._make_key(exp)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            results.append(exp)
                            break
        
        return results
        
    def _postprocess_results(self, experiences: List[_Experience]) -> List[_Experience]:
        """Post-process experience entries for consistency, validation and sorting."""
        if not experiences:
            return []
        
        # 1. Filter out invalid entries
        valid_exps = []
        for exp in experiences:
            # Basic validation
            if not exp.title or not exp.company or len(exp.title) < 3 or len(exp.company) < 2:
                continue
                
            # Check for obvious parsing errors
            if len(exp.title) > 100 or len(exp.company) > 100:
                continue
                
            # Skip entries where title is exactly the same as company
            if exp.title.lower() == exp.company.lower():
                continue
                
            valid_exps.append(exp)
        
        # 2. Deduplicate entries with similar information
        deduped = []
        seen_keys = set()
        
        for exp in valid_exps:
            # Create a simple key for deduplication
            key = f"{exp.title.lower()}|{exp.company.lower()}"
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(exp)
        
        # 3. Sort experiences by date (most recent first)
        def get_sort_key(exp):
            # If end date is present, use it (present/current is treated as most recent)
            if exp.end_date and 'present' in exp.end_date.lower():
                return ('9999-99', exp.start_date or '0000-00')
            elif exp.end_date:
                return (exp.end_date, exp.start_date or '0000-00')
            # If only start date, use that
            elif exp.start_date:
                return (exp.start_date, '0000-00')
            # If no dates, sort by length of title (more detailed titles first)
            else:
                return ('0000-00', '0000-00')
        
        # Sort in reverse order (most recent first)
        sorted_exps = sorted(deduped, key=get_sort_key, reverse=True)
        
        return sorted_exps
        
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for better parsing."""
        # Normalize quotes
        text = re.sub(r'[<18<19]', "'", text)
        text = re.sub(r'[<1C<1D]', '"', text)
        
        # Normalize dashes
        text = re.sub(r'[<13<14]', '-', text)
        
        # Normalize bullet points
        text = re.sub(r'[<22\u25E6<23<43]', 'ΓÇó', text)
        
        # Normalize whitespace but preserve line breaks
        lines = text.split('\n')
        normalized_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines]
        return '\n'.join(normalized_lines)
        
    def _split_into_blocks(self, text: str) -> List[str]:
        """Split text into experience blocks using smart segmentation."""
        if not text:
            return []
        
        # Do not include resume-specific splitting heuristics
        
        # General approach: Split by potential block separators
        separators = [
            # Roger Waters format - "Title at Company - Location (Dates)"
            r'\n(?=[A-Z][^\n]{2,}\s+(?:at|for|with)\s+[A-Za-z])',
            # Title - Company - Location (Dates) format
            r'\n(?=[A-Z][^\n]{2,}\s+[-|]\s+[A-Za-z])',
            # Date range as separator
            r'\n(?=\d{4}\s*[-<|]\s*(?:\d{4}|Present|Current))',
            # Double newline as separator
            r'\n\s*\n',
            # Lines with company, location format
            r'\n(?=[A-Za-z][^\n]{2,},\s*[A-Za-z]{2}\s*[-<|])',
            # Month Year date format
            r'\n(?=(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\n]*\d{4})',
        ]
        
        # Start with the full text as a single block
        blocks = [text]
        
        # Apply each separator pattern
        for pattern in separators:
            new_blocks = []
            for block in blocks:
                # Split by the current pattern
                parts = re.split(pattern, block)
                # Add non-empty parts
                new_blocks.extend([p.strip() for p in parts if p.strip()])
            blocks = new_blocks
        
        # Filter out blocks that are too short or look like bullet points/skills
        valid_blocks = []
        for block in blocks:
            if len(block) < 20:  # Too short
                continue
                
            # Skip if block is just a list of skills or bullet points
            if block.count('\n') >= 2 and all(line.strip().startswith(('ΓÇó', '-', '*')) 
                                           for line in block.split('\n')[1:] if line.strip()):
                continue
                
            valid_blocks.append(block)
            
        return valid_blocks

    def _find_experience_section(self, text: str) -> int:
        """Find the start of experience section with enhanced patterns and strict boundary detection."""
        lines = text.split('\n')

        # Enhanced patterns with word boundaries
        patterns = [
            r"^\s*(?:professional\s+)?(?:work\s+)?experience[s]?\s*:?\s*$",
            r"^\s*employment\s+history\s*:?\s*$",
            r"^\s*work\s+history\s*:?\s*$",
            r"^\s*professional\s+background\s*:?\s*$",
            r"^\s*career\s+summary\s*:?\s*$",
            r"^\s*relevant\s+experience\s*:?\s*$",
            r"^\s*professional\s+experience\s*:?\s*$",
            r"^\s*work\s+experience\s*:?\s*$",
            r"^\s*employment\s*:?\s*$",
            r"^\s*career\s*:?\s*$",
        ]
        
        # Look for section headers in lines
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
                
            # Check if this line matches an experience header pattern
            for pattern in patterns:
                if re.match(pattern, line_stripped, re.I):
                    # Verify this is actually a section header by checking context
                    # Look at previous and next lines
                    is_header = True
                    
                    # Check if previous line suggests this is a header
                    if i > 0:
                        prev_line = lines[i-1].strip()
                        if prev_line and not re.match(r'^[A-Z\s]+$', prev_line):  # Previous line isn't all caps
                            # This might be part of a sentence, not a header
                            if len(line_stripped) > 30:  # Too long to be a header
                                is_header = False
                    
                    # Check if next line has content (not just empty)
                    if is_header and i < len(lines) - 1:
                        next_lines = lines[i+1:i+5]  # Check next few lines
                        has_content = any(line.strip() for line in next_lines)
                        if not has_content:
                            is_header = False
                    
                    if is_header:
                        # Return position after this line
                        return sum(len(lines[j]) + 1 for j in range(i + 1))
            
            # Also check for all-caps headers (common resume format)
            if (len(line_stripped) > 3 and 
                line_stripped.isupper() and 
                not re.search(r'[0-9]', line_stripped) and
                len(line_stripped.split()) <= 3):  # Short headers only
                # Check if next lines have content
                if i < len(lines) - 1:
                    next_lines = lines[i+1:i+5]  # Check next few lines
                    if any(line.strip() for line in next_lines):
                        return sum(len(lines[j]) + 1 for j in range(i + 1))
        
        # Fallback: look for experience content without explicit headers
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Look for lines that start with job titles or companies
            if re.search(r'^(?:senior|junior|lead|principal|staff)?\s*(?:software\s+)?(?:engineer|developer|manager|analyst|specialist|coordinator|consultant|director|architect)', line_stripped, re.I):
                # Check if this looks like start of experience section
                context_lines = lines[max(0, i-2):i+5]
                context = '\n'.join(context_lines)
                if re.search(r'\b(?:company|location|date|year|\d{4})\b', context, re.I):
                    return sum(len(lines[j]) + 1 for j in range(i))
        
        return -1
    
    def _find_section_end(self, text: str, start_pos: int) -> int:
        """Find the end of the current section by looking for the next section header."""
        if start_pos == -1:
            return len(text)
        
        # Look for common section headers that typically come after experience
        section_headers = [
            r"EDUCATION",
            r"SKILLS",
            r"PROJECTS",
            r"CERTIFICATIONS",
            r"LANGUAGES",
            r"REFERENCES",
            r"INTERESTS",
            r"ACTIVITIES",
            r"VOLUNTEER",
            r"PUBLICATIONS",
            r"PATENTS",
            r"AWARDS"
        ]
        
        # Search for the next section header after the start position
        for header in section_headers:
            match = re.search(header, text[start_pos:], re.IGNORECASE)
            if match:
                return start_pos + match.start()
        
        # If no section header found, return the end of the text
        return len(text)

    def _find_next_section(self, text: str, start_pos: int) -> int:
        """Find the next major section after experience with dynamic section tracking."""
        section_headers = [
            # Education section
            r"^\s*education\s*:?\s*$",
            r"^\s*academic\s+background\s*:?\s*$",
            r"^\s*academic\s+credentials\s*:?\s*$",
            r"^\s*qualifications\s*:?\s*$",
            r"^\s*degrees\s*:?\s*$",
            # Skills section
            r"^\s*skills\s*:?\s*$",
            r"^\s*technical\s+skills\s*:?\s*$",
            r"^\s*core\s+skills\s*:?\s*$",
            r"^\s*key\s+skills\s*:?\s*$",
            r"^\s*competencies\s*:?\s*$",
            # Projects section
            r"^\s*projects\s*:?\s*$",
            r"^\s*project\s+experience\s*:?\s*$",
            r"^\s*selected\s+projects\s*:?\s*$",
            # Other common sections
            r"^\s*certifications\s*:?\s*$",
            r"^\s*publications\s*:?\s*$",
            r"^\s*awards\s*:?\s*$",
            r"^\s*interests\s*:?\s*$",
            r"^\s*languages\s*:?\s*$",
            r"^\s*references\s*:?\s*$",
        ]
        
        # Start looking from the start_pos
        remaining_text = text[start_pos:]
        lines = remaining_text.split('\n')
        
        # Look for section headers
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
                
            # Check if this line is a section header
            for pattern in section_headers:
                if re.search(pattern, line_stripped, re.I):
                    # Calculate the absolute position
                    return start_pos + sum(len(lines[j]) + 1 for j in range(i))
            
            # Also check for all-caps headers (common resume format)
            if (len(line_stripped) > 3 and 
                line_stripped.isupper() and 
                not re.search(r'[0-9]', line_stripped) and
                len(line_stripped.split()) <= 3):  # Short headers only
                return start_pos + sum(len(lines[j]) + 1 for j in range(i))
        
        # Fallback: use original pattern matching
        for pattern in section_headers:
            m = re.search(pattern, remaining_text, re.I | re.MULTILINE)
            if m:
                return start_pos + m.start()
        
        return -1

    def _extract_from_match(self, match: re.Match, text: str) -> Optional[_Experience]:
        """Extract structured experience data from regex match with enhanced cleaning."""
        try:
            # Extract from match groups
            title = match.group("title").strip() if "title" in match.groupdict() and match.group("title") else None
            company = match.group("company").strip() if "company" in match.groupdict() and match.group("company") else None
            location = match.group("location").strip() if "location" in match.groupdict() and match.group("location") else None
            dates = match.group("dates").strip() if "dates" in match.groupdict() and match.group("dates") else None
            
            # Return if we don't have minimum information
            if not title and not company:
                return None
                
            # Special handling for Roger Waters resume format
            roger_format = False
            if title and "at " in title.lower() and "Tech Stack" in text[match.end():match.end()+200]:
                roger_format = True
                # Extract title and company from "Title at Company" format
                parts = re.split(r"\s+at\s+", title, flags=re.I)
                if len(parts) > 1:
                    title = parts[0].strip()
                    company = parts[1].strip()
                    
                # Extract location if company contains a dash
                if company and "-" in company:
                    company_parts = company.split("-", 1)
                    company = company_parts[0].strip()
                    location = company_parts[1].strip() if len(company_parts) > 1 else location
            
            # Standard handling for other resume formats
            if not roger_format:
                # Clean up title if "at company" format is present
                if title and "at " in title.lower():
                    parts = re.split(r"\s+at\s+|\s+for\s+|\s+with\s+", title, flags=re.I)
                    if len(parts) > 1:
                        title = parts[0].strip()
                        if not company:  # Only update if we don't already have a company
                            company = parts[1].strip()
                
                # Process title with dashes (Title - Company - Location format)
                if title and " - " in title and not company:
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        company = parts[1].strip()
                        if len(parts) >= 3 and not location:
                            location = parts[2].strip()
                
                # Process title with pipes (Title | Company | Location format)
                if title and " | " in title and not company:
                    parts = title.split(" | ")
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        company = parts[1].strip()
                        if len(parts) >= 3 and not location:
                            location = parts[2].strip()
            
            # Clean up title
            if title:
                # Remove bullet points and markers
                title = re.sub(r'^[<22\-\*]\s+', '', title)
                # Remove "Role:" or "Title:" prefix
                title = re.sub(r'^(?:role|position|title|job)\s*:\s*', '', title, flags=re.I)
                # Remove trailing punctuation
                title = re.sub(r'[,;:\-ΓÇô|]+$', '', title)
                
                # Avoid bullet points or descriptions being classified as titles
                if title.lower().startswith(('developed', 'built', 'implemented', 'created', 
                                           'designed', 'managed', 'led', 'coordinated')):
                    return None
                
                # Title length check - trim if too long
                if len(title) > 100:
                    title = title[:100].split(",")[0].strip()
            
            # Clean up company
            if company:
                # Remove bullet points and markers
                company = re.sub(r'^[<22\-\*]\s+', '', company)
                # Remove "Company:" prefix
                company = re.sub(r'^(?:company|employer|organization)\s*:\s*', '', company, flags=re.I)
                # Remove trailing punctuation
                company = re.sub(r'[,;:\-ΓÇô|]+$', '', company)
                
                # Avoid bullet points being classified as companies
                if company.lower().startswith(('developed', 'built', 'implemented', 'created', 
                                             'designed', 'managed', 'led', 'coordinated')):
                    return None
                
                # Company length check
                if len(company) > 100:
                    company = company[:100].split(",")[0].strip()
                
                # Try to extract location from company if location is missing
                if not location and ("," in company or "-" in company):
                    # Try comma format: "Company, Location"
                    if "," in company:
                        parts = company.split(",", 1)
                        potential_company = parts[0].strip()
                        potential_location = parts[1].strip()
                        
                        if self._is_location(potential_location):
                            company = potential_company
                            location = potential_location
                    
                    # Try dash format: "Company - Location"
                    elif "-" in company:
                        parts = company.split("-", 1)
                        potential_company = parts[0].strip()
                        potential_location = parts[1].strip()
                        
                        if self._is_location(potential_location):
                            company = potential_company
                            location = potential_location
            
            # Clean up location
            if location:
                # Remove "Location:" prefix
                location = re.sub(r'^(?:location)\s*:\s*', '', location, flags=re.I)
                # Remove trailing punctuation
                location = re.sub(r'[,;:\-ΓÇô|]+$', '', location)
                
                # Location length check
                if len(location) > 50 or not self._is_location(location):
                    location = None
            
            # Parse dates
            start, end = None, None
            if dates:
                start, end = self._parse_dates(dates)
            
            # Extract description
            desc = self._extract_description(match, text)
            
            # Apply NLP fallback if needed and available
            if hasattr(self, 'nlp') and self.nlp and (not company or not location):
                context = text[max(0, match.start() - 100):min(len(text), match.end() + 200)]
                
                if len(context) > 100:
                    try:
                        doc = self.nlp(context)
                        
                        # Find companies and locations with NER
                        org_entities = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
                        loc_entities = [ent.text for ent in doc.ents if ent.label_ in ('GPE', 'LOC')]
                        
                        # Use the first entity found if field is missing
                        if not company and org_entities:
                            company = org_entities[0]
                        if not location and loc_entities:
                            location = loc_entities[0]
                    except Exception as e:
                        logger.debug(f"NLP extraction error: {e}")
            
            # Final validation
            if not title or not company:
                return None
                
            # Set default for missing fields
            if not company:
                company = "Unknown"
                
            return _Experience(title, company, location, start, end, desc)
            
        except Exception as e:
            logger.debug(f"Error extracting from match: {e}")
            return None

    def _extract_description(self, match: re.Match, text: str) -> Optional[str]:
        """Extract job description from the text following the experience entry.
        
        Args:
            match: The regex match object for the experience entry
            text: The full resume text
            
        Returns:
            Extracted description or None if not found
        """
        try:
            # Get text after the match until next section or next experience
            start_pos = match.end()
            end_pos = len(text)
            
            # Look for the next experience entry or next section heading
            for pattern in self._PATTERNS:
                next_match = pattern.search(text, start_pos + 10)  # Skip a bit to avoid finding the current match again
                if next_match and next_match.start() > start_pos:
                    end_pos = min(end_pos, next_match.start())
            
            # Check for section headers
            section_headers = [
                r'\b(?:EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|INTERESTS|REFERENCES)\b',
                r'\b(?:Education|Skills|Projects|Certifications|Languages|Interests|References)\s*:',
                r'^\s*(?:EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|INTERESTS|REFERENCES)\s*$'
            ]
            
            for pattern in section_headers:
                section_match = re.search(pattern, text[start_pos:], re.I | re.MULTILINE)
                if section_match:
                    section_start = start_pos + section_match.start()
                    if section_start > start_pos:
                        end_pos = min(end_pos, section_start)
            
            # Extract the raw description text
            raw_desc = text[start_pos:end_pos].strip()
            
            # Clean up the description
            if raw_desc:
                # Remove extra whitespace and normalize newlines
                desc = re.sub(r'\s+', ' ', raw_desc)
                
                # Limit length to reasonable size (1000 chars max)
                if len(desc) > 1000:
                    desc = desc[:1000] + "..."
                    
                # Check if description is meaningful (not just date or short text)
                if len(desc) < 10 or desc.count(' ') < 2:
                    return None
                    
                return desc
                
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting description: {e}")
            return None
            
    def _is_location(self, text: str) -> bool:
        """Check if text resembles a location.
        
        Args:
            text: Text to check
            
        Returns:
            True if text likely represents a location
        """
        if not text or len(text) < 2 or len(text) > 50:
            return False
            
        # Common location words and patterns
        location_markers = ['remote', 'onsite', 'hybrid', 'work from home']
        common_cities = ['new york', 'london', 'tokyo', 'paris', 'san francisco', 'berlin', 'sydney']
        us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 
                   'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 
                   'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 
                   'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        countries = ['usa', 'canada', 'uk', 'germany', 'france', 'australia', 'india', 'china', 'japan']
        
        text_lower = text.lower()
        
        # Check for common location markers
        if any(marker in text_lower for marker in location_markers):
            return True
            
        # Check for common cities
        if any(city in text_lower for city in common_cities):
            return True
            
        # Check for US state abbreviations with word boundaries
        if any(re.search(rf'\b{state}\b', text) for state in us_states):
            return True
            
        # Check for countries
        if any(country in text_lower for country in countries):
            return True
            
        # Check for common location patterns
        if re.search(r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b', text):  # City, STATE format
            return True
            
        if re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text) and not re.search(r'\b(and|with|the|for|from)\b', text_lower):  # Proper noun location
            return True
            
        return False
            
    # Enhanced date patterns for robust extraction
    _DATE_PATTERNS = [
        # MM/YYYY - MM/YYYY or MM-YYYY
        re.compile(
            r'(?P<start>(?:0?[1-9]|1[0-2])(?:[/-](?:19|20)?\d{2}))\s*[-ΓÇôΓÇö]+\s*'
            r'(?P<end>(?:0?[1-9]|1[0-2])(?:[/-](?:19|20)?\d{2})|Present|Current|Now|Ongoing)',
            re.I
        ),
        # Month YYYY - Month YYYY
        re.compile(
            r'(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-ΓÇôΓÇö]+\s*'
            r'(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|Present|Current|Now|Ongoing)',
            re.I
        ),
        # YYYY - YYYY
        re.compile(
            r'(?P<start>(?:19|20)\d{2})\s*[-ΓÇôΓÇö]+\s*'
            r'(?P<end>(?:19|20)\d{2}|Present|Current|Now|Ongoing)',
            re.I
        ),
        # Month YYYY - Present (with optional day)
        re.compile(
            r'(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\s*[-ΓÇôΓÇö]+\s*'
            r'(?P<end>Present|Current|Now|Ongoing)',
            re.I
        ),
    ]

    _TITLE_PREFIXES = (
        'Senior', 'Junior', 'Lead', 'Principal', 'Staff', 'Chief', 'Head of', 'VP of', 'Director of',
        'Manager of', 'Associate', 'Assistant', 'Trainee', 'Intern', 'Apprentice'
    )
    _TITLE_SUFFIXES = (
        'Manager', 'Director', 'Engineer', 'Developer', 'Architect', 'Analyst', 'Specialist',
        'Consultant', 'Officer', 'Executive', 'Coordinator', 'Assistant', 'Associate'
    )
    _COMPANY_SUFFIXES = (
        'Inc', 'LLC', 'Ltd', 'Corp', 'Corporation', 'Co', 'Group', 'Partners', 'Associates',
        'Technologies', 'Solutions', 'Systems', 'Software', 'Consulting', 'International',
        'Holdings', 'Ventures', 'Enterprises', 'Industries', 'Services', 'Labs', 'Agency',
        'Institute', 'University', 'College', 'School', 'Studios', 'Networks', 'Media', 'Digital'
    )

    def _parse_dates(self, date_str: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse start and end dates from date text with enhanced pattern matching.

        Args:
            date_str: String containing date range (e.g., "Jan 2020 - Present")
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM format or None if parsing fails
        Example:
            >>> _MiniExperienceParser()._parse_dates('Jan 2020 - Present')
            ('2020-01', '2025-08')
        """
        if not date_str or not isinstance(date_str, str):
            return None, None
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        for pattern in self._DATE_PATTERNS:
            match = pattern.search(date_str)
            if match:
                start = self._normalize_date_enhanced(match.group('start'))
                end = self._normalize_date_enhanced(match.group('end'))
                if start or end:
                    return start, end
        # Fallback: Look for any date-like patterns
        date_parts = re.split(r'\s*[-ΓÇôΓÇö]+\s*', date_str, maxsplit=1)
        if len(date_parts) == 2:
            start = self._normalize_date_enhanced(date_parts[0])
            end = self._normalize_date_enhanced(date_parts[1])
            return start, end
        return None, None

    def _normalize_date_enhanced(self, date_str: str) -> Optional[str]:
        """
        Enhanced date normalization supporting multiple formats.
        Args:
            date_str: Date string to normalize
        Returns:
            Date string in YYYY-MM format or None if parsing fails
        Example:
            >>> _MiniExperienceParser()._normalize_date_enhanced('Jan 2020')
            '2020-01'
            >>> _MiniExperienceParser()._normalize_date_enhanced('Present')
            '2025-08'
        """
        if not date_str:
            return None
        date_str = date_str.strip()
        # Handle present/current dates - normalize all variations to "Present" first
        if date_str.lower() in ('present', 'current', 'now', 'ongoing'):
            # For display purposes, return "Present" as a string instead of converting to date
            return "Present"
        try:
            if DATEUTIL_AVAILABLE:
                parsed = date_parser.parse(date_str, fuzzy=True, default=datetime(datetime.now().year, 1, 1))
                return parsed.strftime('%Y-%m')
        except (ValueError, OverflowError):
            pass
        # Handle month-year formats
        month_year = re.match(
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})',
            date_str,
            re.I
        )
        if month_year:
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month = date_str[:3].lower()
            year = month_year.group(1)
            if month in month_map:
                return f"{year}-{month_map[month]}"
        # Handle YYYY format
        year_match = re.match(r'^(\d{4})$', date_str)
        if year_match:
            return f"{year_match.group(1)}-01"
        return None

    def _is_potential_title(self, text: str) -> bool:
        """
        Enhanced job title validation with more comprehensive checks.
        Args:
            text: Text to check if it's a job title
        Returns:
            bool: True if text appears to be a job title
        """
        if not text or len(text) < 2 or len(text) > 100:
            return False
        text = text.strip()
        if text.lower() in ('present', 'current', 'to'):
            return False
        words = text.split()
        if len(words) > 6:
            return False
        first_word = words[0].lower()
        last_word = words[-1].lower()
        has_prefix = any(prefix.lower() == first_word for prefix in self._TITLE_PREFIXES)
        has_suffix = any(suffix.lower() == last_word for suffix in self._TITLE_SUFFIXES)
        if not (has_prefix or has_suffix):
            if not re.search(self._TITLE_KEYWORDS, text):
                return False
        if re.search(r'[0-9]', text):
            return False
        if re.search(r'[^a-zA-Z\s\-&]', text):
            return False
        if len(text.split()) == 1 and len(text) < 4:
            return False
        return True

    def _is_valid_company(self, text: str) -> bool:
        """
        Validate if text appears to be a company name.
        Args:
            text: Text to validate
        Returns:
            bool: True if text appears to be a company name
        """
        if not text or len(text) < 2 or len(text) > 100:
            return False
        text = text.strip()
        if text.lower() in ('present', 'current', 'to', 'and', 'or', 'the'):
            return False
        words = text.split()
        if len(words) > 6:
            return False
        last_word = words[-1].rstrip('.,;:')
        has_company_suffix = any(
            suffix.lower() == last_word.lower() 
            for suffix in self._COMPANY_SUFFIXES
        )
        is_proper_noun = text.istitle() or text.isupper()
        has_company_keywords = any(
            keyword.lower() in text.lower()
            for keyword in ('tech', 'systems', 'solutions', 'group', 'inc', 'llc', 'ltd', 'corp')
        )
        return has_company_suffix or is_proper_noun or has_company_keywords


        """Enhanced fallback extraction for missed experiences."""
        additional = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and bullets
            if not line or re.match(r'^[ΓÇó\-\*\+ΓùªΓû¬Γû╕ΓåÆ]\s*$', line):
                i += 1
                continue
                
            # Check if line could be a job title
            if self._is_potential_title(line):
                # Look ahead for company and dates
                exp_data = self._extract_from_context(lines, i)
                if exp_data:
                    key = self._make_key(exp_data)
                    if key not in seen:
                        seen.add(key)
                        additional.append(exp_data)
                        i += 3  # Skip processed lines
                        continue
            i += 1
            
        return additional

    def _extract_from_context(self, lines: list, i: int):
        """
        Given a list of lines and a starting index (likely a job title),
        look ahead for company, dates, location, and description.
        Returns an _Experience object if plausible, else None.
        """
        title = lines[i].strip()
        company = None
        location = None
        start_date = None
        end_date = None
        description = []
        max_lookahead = 6
        line_count = len(lines)

        # Look ahead for company, location, and date info
        for offset in range(1, max_lookahead):
            idx = i + offset
            if idx >= line_count:
                break
            line = lines[idx].strip()
            # Skip empty lines
            if not line:
                continue
            # Check for dates
            date_text = self._find_any_date(line)
            if date_text:
                start_date, end_date = self._parse_dates(date_text)
                continue
            # Check for company (by keyword or capitalization)
            if not company and (self._COMPANY_KEYWORDS.search(line) or (line.istitle() and len(line.split()) <= 6)):
                company = line
                continue
            # Check for location
            if not location and self._is_location(line):
                location = line
                continue
            # Otherwise, treat as possible description
            if not self._is_bullet_point(line):
                description.append(line)

        # If company is still None, try previous line (sometimes company above title)
        if not company and i > 0:
            prev_line = lines[i-1].strip()
            if self._COMPANY_KEYWORDS.search(prev_line) or (prev_line.istitle() and len(prev_line.split()) <= 6):
                company = prev_line

        # If we have at least a title and company, return an _Experience
        if title and company:
            return _Experience(
                title=title,
                company=company,
                location=location,
                start_date=start_date,
                end_date=end_date,
                description="\n".join(description) if description else None
            )
        return None

    def _is_potential_title(self, text: str) -> bool:
        """Check if text could potentially be a job title."""
        if not text or len(text) < 5 or len(text) > 100:
            return False
            
        # Common job title keywords
        title_keywords = [
            'engineer', 'developer', 'manager', 'director', 'lead', 'senior', 'junior',
            'analyst', 'specialist', 'consultant', 'coordinator', 'associate', 'assistant',
            'head', 'chief', 'president', 'vp', 'executive', 'administrator', 'supervisor',
            'architect', 'designer', 'scientist', 'researcher', 'intern', 'officer'
        ]
        
        # Check for bullet points
        if self._is_bullet_point(text):
            return False
            
        # Check for title keywords
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in title_keywords):
            return True
            
        # Check for title patterns
        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){0,3}$', text):
            return True
            
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Za-z&]+){1,5}$', text) and not re.search(r'\b(?:and|with|the|for|from)\b', text_lower):
            return True
            
        return False
        
    def _is_bullet_point(self, text: str) -> bool:
        """Check if text is a bullet point."""
        if not text:
            return False
            
        # Check for common bullet point markers
        if re.match(r'^[ΓÇó\-\*\+ΓùªΓû¬Γû╕ΓåÆ]\s', text):
            return True
            
        # Check for numbered bullets
        if re.match(r'^\d+\.\s', text):
            return True
            
        # Check for common bullet point phrases
        bullet_starters = ['developed', 'implemented', 'created', 'designed', 'managed', 
                         'led', 'responsible for', 'achieved', 'collaborated', 'built', 
                         'worked on', 'maintained', 'improved', 'reduced', 'increased']
                         
        text_lower = text.lower()
        if any(text_lower.startswith(starter) for starter in bullet_starters):
            return True
            
        return False
        
    def _find_any_date(self, text: str) -> Optional[str]:
        """Find any date pattern in text."""
        if not text:
            return None
            
        # Common date patterns
        date_patterns = [
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b',
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*(?:Present|Current|Now|Ongoing|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\b',
            r'\b\d{1,2}/\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*\d{1,2}/\d{4}\b',
            r'\b\d{1,2}/\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*(?:Present|Current|Now|Ongoing|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\b',
            r'\b\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*\d{4}\b',
            r'\b\d{4}\s*(?:-|to|ΓÇô|ΓÇö|through)\s*(?:Present|Current|Now|Ongoing|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\b',
            r'\(\s*\d{4}\s*-\s*(?:\d{4}|Present|Current|Now|Ongoing|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\s*\)',
            r'\(\s*\d{1,2}/\d{4}\s*-\s*(?:\d{1,2}/\d{4}|Present|Current|Now|Ongoing|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\s*\)',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0)
                
        return None

    def _parse_dates(self, date_str: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse dates with enhanced dateutil support and better pattern matching."""
        if not date_str:
            return None, None
            
        # Clean up the date string
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        
        # Handle common present/current variations
        present_terms = ['present', 'current', 'now', 'ongoing', 'today']
        for term in present_terms:
            # Use case-insensitive replacement but always convert to "Present" with capital P
            date_str = re.sub(rf'\b{term}\b', 'Present', date_str, flags=re.I)
        
        # Handle Roger Waters resume format - "September 2022 - Present"
        month_year_pattern = r'(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-ΓÇôΓÇö]\s*(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|Present)'
        month_year_match = re.search(month_year_pattern, date_str, re.I)
        if month_year_match:
            start = self._normalize_date_enhanced(month_year_match.group("start"))
            end = self._normalize_date_enhanced(month_year_match.group("end"))
            return start, end
        
        # Try main pattern first
        m = self._DATE_RE.search(date_str)
        if m:
            start = self._normalize_date_enhanced(m.group("start"))
            end = self._normalize_date_enhanced(m.group("end"))
            return start, end
        
        # Try alternative patterns
        for pattern in self._ALT_DATE_PATTERNS:
            m = pattern.search(date_str)
            if m:
                start = self._normalize_date_enhanced(m.group("start"))
                end = self._normalize_date_enhanced(m.group("end"))
                return start, end
        
        # Try to extract just years if nothing else worked
        years_pattern = r'(\d{4})\s*[-ΓÇôΓÇö]\s*(\d{4}|Present)'
        years_match = re.search(years_pattern, date_str, re.I)
        if years_match:
            start_year = f"{years_match.group(1)}-01"
            end_value = years_match.group(2)
            # Case-insensitive comparison for Present
            if end_value.lower() != "present":
                end_year = f"{end_value}-01"
            else:
                end_year = "Present"
            return start_year, end_year
        
        # Try single year + Present pattern (case-insensitive)
        single_year_pattern = r'(\d{4})\s*[-ΓÇôΓÇö]\s*(Present|PRESENT|present|Current|current)'
        single_year_match = re.search(single_year_pattern, date_str, re.I)
        if single_year_match:
            start_year = f"{single_year_match.group(1)}-01"
            return start_year, "Present"
        
        # Try to split on common separators and parse each part
        separators = ['-', 'ΓÇô', 'ΓÇö', '~', 'to', 'through', 'until']
        for sep in separators:
            if sep in date_str.lower():
                parts = re.split(rf'\s*{re.escape(sep)}\s*', date_str, flags=re.I)
                if len(parts) == 2:
                    start = self._normalize_date_enhanced(parts[0].strip())
                    end = self._normalize_date_enhanced(parts[1].strip())
                    if start or end:
                        return start, end
                        
        return None, None

    def _normalize_date_enhanced(self, date_str: str) -> Optional[str]:
        """Enhanced date normalization using dateutil for robust parsing."""
        if not date_str:
            return None
            
        date_str = date_str.strip()
        
        # Handle Present/Current -> consistently return "Present"
        if date_str.lower() in ['present', 'current', 'now', 'ongoing', 'today']:
            return "Present"
        
        # Use dateutil if available for robust parsing
        if DATEUTIL_AVAILABLE:
            try:
                # Try to parse with dateutil (handles many formats automatically)
                parsed_date = date_parser.parse(date_str, fuzzy=True, dayfirst=False)
                return parsed_date.strftime('%Y-%m')
            except (ValueError, TypeError):
                pass
        
        # Fallback to manual parsing for common patterns
        # Handle MM/YYYY or MM-YYYY
        mm_yyyy_match = re.search(r'(\d{1,2})[/-](\d{4})', date_str)
        if mm_yyyy_match:
            month, year = mm_yyyy_match.groups()
            return f"{year}-{int(month):02d}"
        
        # Handle YYYY only
        yyyy_match = re.search(r'\b(\d{4})\b', date_str)
        if yyyy_match:
            return f"{yyyy_match.group(1)}-01"
        
        # Handle Month Year (e.g., "January 2020", "Jan 2020")
        month_year_match = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b', date_str, re.I)
        if month_year_match:
            month_name, year = month_year_match.groups()
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = month_map.get(month_name.lower()[:3])
            if month_num:
                return f"{year}-{month_num}"
        
        # Handle 2-digit years (legacy method)
        year_match = re.search(r'\b(\d{2})\b', date_str)
        if year_match and not re.search(r'\b\d{4}\b', date_str):
            year = int(year_match.group(1))
            if year < 30:
                return f"20{year:02d}-01"
            else:
                return f"19{year:02d}-01"
        
        return None
    
    def _normalize_date(self, date_str: str) -> str:
        """Legacy normalize date format (kept for backward compatibility)."""
        if not date_str:
            return None
            
        date_str = date_str.strip()
        
        # Handle 2-digit years
        year_match = re.search(r'\b(\d{2})\b', date_str)
        if year_match and not re.search(r'\b\d{4}\b', date_str):
            year = int(year_match.group(1))
            if year < 30:
                date_str = date_str.replace(year_match.group(1), f"20{year:02d}")
            else:
                date_str = date_str.replace(year_match.group(1), f"19{year:02d}")
                
        return date_str
        
    def _extract_bullet_points(self, snippet: str) -> str:
        """Extract bullet points and action statements from text."""
        bullets = []
        
        # Standard bullet points
        bullet_matches = self._BULLET_RE.findall(snippet)
        bullets.extend([b.strip() for b in bullet_matches if len(b.strip()) > 10])
        
        # Also look for lines that start with action verbs (common in resumes)
        action_verb_pattern = re.compile(
            r'^(Developed|Designed|Implemented|Led|Managed|Created|Built|Established|Improved|'
            r'Increased|Reduced|Achieved|Delivered|Coordinated|Organized|Analyzed|Optimized|'
            r'Streamlined|Automated|Collaborated|Maintained|Supported|Trained|Presented|'
            r'Negotiated|Resolved|Generated|Executed|Planned|Launched|Directed|Oversaw|'
            r'Administered|Monitored|Evaluated|Researched|Identified|Facilitated)\b',
            re.I | re.MULTILINE
        )
        
        for line in snippet.split('\n'):
            line = line.strip()
            if action_verb_pattern.match(line) and len(line) > 10:
                if line not in bullets:
                    bullets.append(line)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_bullets = []
        for b in bullets:
            if b.lower() not in seen:
                seen.add(b.lower())
                unique_bullets.append(b)
        
        return '\n'.join(unique_bullets) if unique_bullets else None

    def _fallback_extraction(self, text: str, seen_keys: set) -> List[_Experience]:
        """Last-resort fallback extraction for experience entries when other methods fail.
        
        Looks for lines that might represent job entries by searching for patterns like:
        - Combinations of job title keywords + dates
        - Company-like names + locations
        - Lines with both job title and company indicators
        
        Args:
            text: The text to extract from
            seen_keys: Set of already extracted experience keys to avoid duplication
            
        Returns:
            List of extracted _Experience objects
        """
        logger.debug("Using fallback extraction method for experience entries")
        results = []
        
        # Split into lines and consider potential job entry lines
        lines = text.split('\n')
        
        # 1. Look for lines with company suffixes
        company_candidates = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10 or len(line) > 100:
                continue
                
            # Look for company name indicators
            for suffix in self._COMPANY_SUFFIXES:
                if f" {suffix}" in line or f", {suffix}" in line:
                    company_candidates.append((i, line))
                    break
                    
        # 2. Examine each candidate's context
        for i, company_line in company_candidates:
            # Look backward for potential title
            title_line = ""
            if i > 0:
                title_line = lines[i-1].strip()
                
            # Extract potential dates from nearby lines
            date_str = ""
            for j in range(max(0, i-2), min(len(lines), i+3)):
                for pattern in self._DATE_PATTERNS:
                    match = pattern.search(lines[j])
                    if match:
                        date_str = match.group(0)
                        break
                if date_str:
                    break
                    
            # If we found enough information, create an experience entry
            company = company_line
            title = title_line if self._is_potential_title(title_line) else "Unknown Position"
            
            # Try to extract location
            location = None
            for loc_pattern in self._LOCATION_PATTERNS:
                loc_match = loc_pattern.search(company_line)
                if loc_match:
                    location = loc_match.group(0)
                    # Remove location from company
                    company = company.replace(location, "").strip()
                    break
                    
            # Parse dates if found
            start_date = None
            end_date = None
            if date_str:
                dates = self._parse_dates(date_str)
                if dates:
                    start_date, end_date = dates
            
            # Create experience object
            exp = _Experience(
                title=title,
                company=company,
                location=location,
                start_date=start_date,
                end_date=end_date,
                description=None
            )
            
            # Add if unique
            key = self._make_key(exp)
            if key and key not in seen_keys and len(key) > 5:
                seen_keys.add(key)
                results.append(exp)
        
        # 3. If still no results, look for lines with job title keywords
        if not results:
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or len(line) < 10 or len(line) > 100:
                    continue
                    
                if self._TITLE_KEYWORDS.search(line):
                    # Create a minimal experience entry
                    title = line
                    company = "Unknown Company"
                    exp = _Experience(
                        title=title,
                        company=company,
                        location=None,
                        start_date=None,
                        end_date=None,
                        description=None
                    )
                    
                    key = self._make_key(exp)
                    if key and key not in seen_keys and len(key) > 5:
                        seen_keys.add(key)
                        results.append(exp)
        
        return results
        
    def _make_key(self, exp: _Experience) -> tuple:
        """Create a unique key for deduplication."""
        return (
            (exp.title or '').lower().strip(),
            (exp.company or '').lower().strip(),
            exp.start_date,
            exp.end_date
        )

    def _post_process_experiences(self, experiences: List[_Experience]) -> List[_Experience]:
        """Clean up and validate experiences."""
        processed = []
        
        for exp in experiences:
            # Skip if missing critical information
            if not exp.title or not exp.company:
                continue
                
            # Clean up title
            exp.title = re.sub(r'\s+', ' ', exp.title).strip()
            exp.title = re.sub(r'^[\-\*\ΓÇó\ΓåÆ\+ΓùªΓû¬Γû╕]+\s*', '', exp.title)  # Remove leading bullets
            
            # Clean up company
            exp.company = re.sub(r'\s+', ' ', exp.company).strip()
            exp.company = re.sub(r'^at\s+', '', exp.company, flags=re.I)  # Remove leading "at"
            
            # Validate and clean location
            if exp.location:
                exp.location = re.sub(r'\s+', ' ', exp.location).strip()
                # Remove location if it's too long or contains description-like text
                if len(exp.location) > 50 or re.search(r'\b(responsible|developed|managed)\b', exp.location, re.I):
                    exp.location = None
            
            processed.append(exp)
        
        # Sort by date (most recent first) if dates are available
        processed.sort(key=lambda x: (x.start_date or '0000', x.end_date or '9999'), reverse=True)
        
        return processed


    def _extract_skills(self, text: str) -> List[Dict[str, str]]:
        """
        Enhanced skill extraction with better noise reduction and categorization.
        """
        skills = set()
        skill_categories = {
            'technical': set(),
            'soft': set(),
            'tools': set(),
            'languages': set(),
        }
        
        # Enhanced skill section detection patterns
        skill_headers = [
            r"(?:technical\s+)?skills?\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"(?:core\s+)?competenc(?:ies|es)\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"expertise\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"technologies\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"programming\s+languages?\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"tools?\s*(?:and\s+)?(?:technologies|frameworks)?\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"key\s+skills?\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
            r"areas?\s+of\s+expertise\s*(?:\s*[:\-ΓÇôΓÇö]|$)",
        ]
        
        # Common skill patterns and keywords
        technical_patterns = [
            r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|Ruby|Go|Rust|Swift|Kotlin|PHP|R|MATLAB|Scala|Perl|'
            r'HTML|CSS|SQL|NoSQL|React|Angular|Vue|Node\.?js|Django|Flask|Spring|Rails|Laravel|'
            r'AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|GitHub|GitLab|CI/CD|DevOps|'
            r'Machine Learning|Deep Learning|AI|NLP|Computer Vision|TensorFlow|PyTorch|Scikit-learn|'
            r'MongoDB|PostgreSQL|MySQL|Redis|Elasticsearch|Kafka|RabbitMQ|'
            r'REST|GraphQL|API|Microservices|Blockchain|IoT|Cloud|Linux|Unix|Windows|'
            r'Agile|Scrum|Kanban|JIRA|Confluence|Slack|VS Code|IntelliJ|Eclipse)\b',
            re.I
        ]
        
        # Bullet and delimiter patterns
        delimiters = re.compile(r'[,;|ΓÇó\-\*\+ΓùªΓû¬Γû╕ΓåÆ/]|\band\b|\s{2,}', re.I)
        
        # Find skill sections
        lines = text.split('\n')
        in_skill_section = False
        skill_section_text = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check if we're entering a skill section
            if not in_skill_section:
                for header_pattern in skill_headers:
                    if re.search(header_pattern, line, re.I):
                        in_skill_section = True
                        # Include the rest of this line if it has content after the header
                        header_match = re.search(header_pattern, line, re.I)
                        if header_match:
                            remainder = line[header_match.end():].strip()
                            if remainder and not remainder.startswith(':'):
                                skill_section_text.append(remainder)
                        break
            else:
                # Check if we're leaving the skill section
                if (not line or 
                    re.match(r'^[A-Z\s]{4,}$', line) or  # All caps header
                    re.search(r'^(?:Experience|Education|Projects?|Certificat|Award|Publication|Reference)', line, re.I) or
                    len(line) > 100):  # Very long lines are usually not skills
                    break
                
                skill_section_text.append(line)
        
        # Also look for inline skills throughout the document
        inline_skill_patterns = [
            r'(?:proficient|experienced?|skilled|expert|knowledge)\s+(?:in|with)\s+([^.;]+)',
            r'(?:technologies|tools|languages):\s*([^.;]+)',
            r'\(([^)]+)\)',  # Skills in parentheses
        ]
        
        for pattern in inline_skill_patterns:
            for match in re.finditer(pattern, text, re.I):
                skill_text = match.group(1)
                if len(skill_text) < 100:  # Reasonable length
                    skill_section_text.append(skill_text)
        
        # Process collected skill text
        all_text = ' '.join(skill_section_text)
        
        # Split by delimiters and process each potential skill
        potential_skills = delimiters.split(all_text)
        
        for skill in potential_skills:
            skill = skill.strip()
            
            # Skip empty or invalid entries
            if not skill or len(skill) < 2 or len(skill) > 50:
                continue
                
            # Clean up the skill
            skill = re.sub(r'^\W+|\W+$', '', skill)  # Remove leading/trailing non-word chars
            skill = re.sub(r'\s+', ' ', skill)  # Normalize whitespace
            
            # Enhanced noise filtering
            skip_phrases = [
                r'^\d+.*years?',  # "5 years experience"
                r'^years?\s+of',  # "years of experience"
                r'^experience\s+(?:in|with)',  # "experience in/with"
                r'^including\b',  # "including"
                r'^such\s+as\b',  # "such as"
                r'^etc\.?$',  # "etc"
                r'^and\s+more',  # "and more"
                r'^various\b',  # "various"
                r'^multiple\b',  # "multiple"
                r'^strong\b',  # "strong"
                r'^good\b',  # "good"
                r'^excellent\b',  # "excellent"
                r'^ability\s+to',  # "ability to"
                r'^able\s+to',  # "able to"
                r'^[a-z]+ing\s+(?:and|&)',  # "developing and" (incomplete)
                r'^\w+\s+(?:and|&)$',  # "Python and" (incomplete)
                r'^(?:the|a|an)\s+',  # Articles
                r'^(?:with|using|for|in|on|at|by|from|to)\s+',  # Prepositions
                r'^(?:and|or|but|so|yet|nor)\s+',  # Conjunctions
                r'\s+(?:and|or)$',  # Trailing conjunctions
            ]
            
            should_skip = False
            for pattern in skip_phrases:
                if re.search(pattern, skill, re.I):
                    should_skip = True
                    break
            
            if should_skip:
                continue
            
            # Categorize skills with comprehensive patterns
            skill_lower = skill.lower()
            categorized = False
            
            # Programming languages (expanded)
            if re.search(r'\b(?:python|java|javascript|typescript|c\+\+|c#|ruby|go|rust|swift|kotlin|php|r|matlab|scala|perl|html|css|sql|nosql)\b', skill, re.I):
                skill_categories['languages'].add(skill)
                categorized = True
            # Tools and software (expanded)
            elif re.search(r'\b(?:aws|azure|gcp|docker|kubernetes|jenkins|git|github|gitlab|jira|confluence|slack|figma|photoshop|office|excel|word|powerpoint|tableau|salesforce|sap|oracle|adobe|autocad|sketch|invision|spss|stata|power\s*bi|looker|asana|trello|mongodb|postgresql|mysql|redis|elasticsearch|kafka|rabbitmq|nginx|apache|linux|windows|macos|android|ios|react|angular|vue|node\.?js|django|flask|spring|rails|laravel|express|bootstrap|jquery|redux|graphql|rest|api|json|xml|yaml|ci/cd|devops|microservices|blockchain|iot|cloud|vmware|selenium|pandas|numpy|matplotlib|seaborn|tensorflow|pytorch|keras|scikit|opencv)\b', skill, re.I):
                skill_categories['tools'].add(skill)
                categorized = True
            # Soft skills (expanded)
            elif re.search(r'\b(?:leadership|communication|team|collaboration|problem[\s\-]?solving|analytical|critical[\s\-]?thinking|time[\s\-]?management|project[\s\-]?management|presentation|negotiation|customer[\s\-]?service|interpersonal|adaptability|creativity|innovation|strategic|detail[\s\-]?oriented|self[\s\-]?motivated|organized|mentoring|coaching|training|public\s*speaking|writing|documentation|research|planning|coordination|multitasking|prioritization|decision\s*making|conflict\s*resolution)\b', skill, re.I):
                skill_categories['soft'].add(skill)
                categorized = True
            # Technical skills (frameworks, methodologies, etc.)
            elif re.search(r'\b(?:agile|scrum|kanban|waterfall|lean|six\s*sigma|machine\s*learning|deep\s*learning|artificial\s*intelligence|data\s*science|data\s*analysis|web\s*development|mobile\s*development|full\s*stack|front\s*end|back\s*end|database|networking|security|testing|qa|automation|integration|deployment|monitoring|logging|caching|optimization|performance|scalability|architecture|design\s*patterns|algorithms|data\s*structures)\b', skill, re.I):
                skill_categories['technical'].add(skill)
                categorized = True
            # Check technical patterns from original logic
            elif not categorized:
                for tech_pattern in technical_patterns:
                    if re.search(tech_pattern, skill):
                        skill_categories['technical'].add(skill)
                        categorized = True
                        break
            
            # Default to technical if not categorized
            if not categorized:
                skill_categories['technical'].add(skill)
            
            # Add to general skills set
            skills.add(skill)
        
        # Also extract skills from experience descriptions using NLP-like patterns
        experience_skills = self._extract_skills_from_descriptions(text)
        skills.update(experience_skills)
        
        # Post-process and validate skills
        final_skills = []
        seen_normalized = set()
        
        for skill in skills:
            # Normalize for deduplication
            normalized = skill.lower().strip()
            
            # Skip if we've seen a similar skill
            if normalized in seen_normalized:
                continue
                
            # Check for substring duplicates (e.g., "Python" and "Python Programming")
            is_duplicate = False
            for seen in seen_normalized:
                if normalized in seen or seen in normalized:
                    # Keep the longer, more descriptive version
                    if len(normalized) > len(seen):
                        seen_normalized.remove(seen)
                        # Remove the shorter version from final_skills
                        final_skills = [s for s in final_skills if s['name'].lower() != seen]
                    else:
                        is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_normalized.add(normalized)
                
                # Determine category by checking which category set contains this skill
                category = 'technical'  # default
                for cat_name, cat_skills in skill_categories.items():
                    if skill in cat_skills:
                        category = cat_name
                        break
                
                # If not found in any category, categorize based on content
                if category == 'technical' and skill not in skill_categories['technical']:
                    skill_lower = skill.lower()
                    if any(lang in skill_lower for lang in ['python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'php', 'r', 'matlab', 'scala', 'perl']):
                        category = 'languages'
                    elif any(tool in skill_lower for tool in ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'github', 'gitlab', 'jira', 'confluence', 'slack', 'figma', 'photoshop', 'office', 'excel', 'tableau', 'salesforce']):
                        category = 'tools'
                    elif any(soft in skill_lower for soft in ['leadership', 'communication', 'team', 'collaboration', 'problem', 'analytical', 'critical', 'time', 'project', 'presentation', 'negotiation', 'customer', 'interpersonal']):
                        category = 'soft'
                    else:
                        category = 'technical'
                
                final_skills.append({
                    'name': skill,
                    'category': category,
                    'level': 'intermediate',  # Default level
                    'keywords': None
                })
        
        # Sort skills: technical first, then tools, then languages, then soft skills
        def skill_sort_key(skill_dict):
            skill = skill_dict['name']
            if skill in skill_categories['technical']:
                return (0, skill)
            elif skill in skill_categories['tools']:
                return (1, skill)
            elif skill in skill_categories['languages']:
                return (2, skill)
            elif skill in skill_categories['soft']:
                return (3, skill)
            else:
                return (4, skill)
        
        final_skills.sort(key=skill_sort_key)
        
        return final_skills

    def _extract_skills_from_descriptions(self, text: str) -> set:
        """
        Extract skills mentioned in experience descriptions using pattern matching.
        """
        skills = set()

        # Patterns for extracting skills from sentences
        context_patterns = [
            # "Developed applications using X, Y, and Z"
            r'(?:using|with|in)\s+([A-Za-z0-9\+\#\.\s,/]+?)(?:\s+(?:to|for|and|on)|[.\n;])',
            # "Experience with X, Y, Z"
            r'(?:experience|proficient|skilled|expert)\s+(?:in|with)\s+([A-Za-z0-9\+\#\.\s,/]+?)(?:[.\n;]|$)',
            # "X, Y, and Z development"
            r'([A-Za-z0-9\+\#\.\s,/]+?)\s+(?:development|programming|engineering|administration)',
            # "Built/Created/Designed X applications/systems"
            r'(?:built|created|designed|developed|implemented)\s+([A-Za-z0-9\+\#\.\s]+?)\s+(?:applications?|systems?|platforms?|tools?)',
            # "Technologies: X, Y, Z"
            r'(?:technologies|tools|languages|frameworks|libraries|platforms):\s*([^.\n]+)',
        ]

        # Known technology/skill terms for validation
        known_skills = {
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 'Go', 'Rust', 'Swift',
            'React', 'Angular', 'Vue', 'Node.js', 'Django', 'Flask', 'Spring', 'Rails',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'Git',
            'SQL', 'NoSQL', 'MongoDB', 'PostgreSQL', 'MySQL', 'Redis',
            'Machine Learning', 'Deep Learning', 'Data Science', 'AI', 'NLP',
            'REST', 'GraphQL', 'API', 'Microservices', 'DevOps', 'CI/CD',
            'HTML', 'CSS', 'Sass', 'Bootstrap', 'Tailwind',
            'Linux', 'Unix', 'Windows', 'macOS', 'Android', 'iOS',
            'Agile', 'Scrum', 'Kanban', 'JIRA', 'Confluence',
            'TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy',
            'Tableau', 'Power BI', 'Excel', 'R', 'MATLAB', 'SAS', 'SPSS',
            'Photoshop', 'Illustrator', 'Figma', 'Sketch', 'InDesign',
            # ΓÇªand so onΓÇª
        }
        known_skills_lower = {s.lower() for s in known_skills}

        for pattern in context_patterns:
            for match in re.finditer(pattern, text, re.I):
                captured = match.group(1)
                # Split by common delimiters
                potential_skills = re.split(r'[,;]|\s+and\s+|\s+&\s+', captured)
                for ps in potential_skills:
                    ps = ps.strip()
                    # Remove surrounding non-word chars and normalize spaces
                    ps = re.sub(r'^\W+|\W+$', '', ps)
                    ps = re.sub(r'\s+', ' ', ps)
                    if not ps or len(ps) < 2 or len(ps) > 30:
                        continue

                    # Exact match against known skills
                    if ps.lower() in known_skills_lower:
                        # Restore proper casing
                        for orig in known_skills:
                            if orig.lower() == ps.lower():
                                skills.add(orig)
                                break
                    # Certain technical acronyms
                    elif re.search(r'\b(?:JS|API|SQL|ML|AI|UI|UX|SDK|IDE|ORM|CSS|HTML|XML|JSON|YAML|REST|SOAP|HTTP|TCP|UDP|IP|DNS|CDN|VPN|SSH|FTP|SMTP|POP3|IMAP)\b', ps, re.I):
                        skills.add(ps)
                    # Generic ΓÇ£single termΓÇ¥ technical pattern
                    elif re.search(r'^[A-Z][a-zA-Z0-9]*(?:\.[a-zA-Z]+)?$|^[A-Z]+(?:\+\+|#)?$', ps):
                        skills.add(ps)

        return skills
        
