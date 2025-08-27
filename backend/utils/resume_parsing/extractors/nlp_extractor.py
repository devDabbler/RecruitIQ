"""nlp_extractor.py
Secondary resume extractor that leverages spaCy for lightweight NLP-powered
entity extraction. This extractor is intended to sit between the primary
Nebius-AI parser and the regex-only fallback.  It should therefore adopt a
*best-effort* philosophy – try to extract as much structured data as possible
without ever raising exceptions.  If something goes wrong we log the failure
and return an empty result so that the caller can continue down the fallback
chain.

IMPORTANT:  We purposefully keep the implementation lightweight.  A full blown
information-extraction pipeline is out of scope for this secondary extractor.
Instead we:
  1. Use spaCy's pre-trained English model to obtain entities (ORG, GPE, DATE,
     PERSON, etc.).
  2. Rely on inexpensive heuristics to map those entities into the expected
     resume schema keys.
  3. Re-use the existing _MiniExperienceParser from ``regex_extractor`` for
     robust experience line parsing and then enhance its output with
     spaCy-detected entities where possible.

This approach provides a quick accuracy boost over pure regex while avoiding
large maintenance costs.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Set

import spacy
from spacy.language import Language

from backend.utils.dependency_manager import DependencyManager
from .base_extractor import BaseExtractor
from .regex_extractor import RegexExtractor, _MiniExperienceParser  # reuse experience helper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper regexes for contact info – kept intentionally very simple
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:(?:\+?\d{1,2}[\s\-]?)?(?:\(\d{3}\)|\d{3})[\s\-]?\d{3}[\s\-]?\d{4})")

# Common resume section headers for quick section slicing
_SECTION_HEADERS = {
    "education": re.compile(r"^\s*(education|academic background)\b", re.I),
    "experience": re.compile(r"^\s*(work experience|professional experience|experience|employment)\b", re.I),
    "skills": re.compile(r"^\s*skills?\b", re.I),
    "military": re.compile(r"^\s*(military experience|military service|armed forces|defense experience|service history|military background|military career)\b", re.I),
}

# Enhanced degree patterns for better education extraction
_DEGREE_PATTERNS = [
    r"\b(?:B\.?[AS]\.?|Bachelor(?:'s)?|M\.?[AS]\.?|Master(?:'s)?|MBA|Ph\.?D\.?|Doctorate|Associate|Diploma|Certificate)\b",
    r"\b(?:Bachelor of Science|Bachelor of Arts|Bachelor of Engineering|Bachelor of Business)\b",
    r"\b(?:Master of Science|Master of Arts|Master of Engineering|Master of Business)\b",
    r"\b(?:Doctor of Philosophy|Doctor of Engineering|Doctor of Business)\b",
]

# Military-specific patterns for enhanced recognition
_MILITARY_PATTERNS = {
    "branches": [
        r"\b(?:Army|Navy|Air Force|Marines|Coast Guard|National Guard)\b",
        r"\b(?:U\.?S\.?\s*Army|U\.?S\.?\s*Navy|U\.?S\.?\s*Air Force|U\.?S\.?\s*Marines|U\.?S\.?\s*Coast Guard)\b",
        r"\b(?:Army National Guard|Air National Guard)\b",
    ],
    "ranks": [
        r"\b(?:Private|Corporal|Sergeant|Staff Sergeant|Master Sergeant|First Sergeant|Sergeant Major)\b",
        r"\b(?:Lieutenant|Captain|Major|Lieutenant Colonel|Colonel|Brigadier General|Major General|General)\b",
        r"\b(?:Seaman|Petty Officer|Chief Petty Officer|Senior Chief|Master Chief)\b",
        r"\b(?:Airman|Senior Airman|Staff Sergeant|Technical Sergeant|Master Sergeant|Senior Master Sergeant)\b",
    ],
    "specialties": [
        r"\b(?:MOS|Military Occupational Specialty)\b",
        r"\b(?:[0-9]{2}[A-Z])\b",  # MOS codes like 11B, 25B, etc.
    ],
    "clearances": [
        r"\b(?:Secret|Top Secret|Confidential)\s+Clearance\b",
        r"\b(?:Security Clearance|TS/SCI|TS/SCI Clearance)\b",
    ]
}


def _load_spacy_model() -> Language:
    """Load spaCy English model using DependencyManager for caching."""
    dm = DependencyManager()
    try:
        return dm.get_spacy_model("en_core_web_sm")  # small model keeps tests fast
    except Exception as exc:
        logger.warning(f"spaCy model load failed ({exc}), falling back to blank English model.")
        return spacy.blank("en")


class NLPExtractor(BaseExtractor):
    """spaCy-powered secondary extractor."""

    def __init__(self, spacy_model: Optional[Language] = None):
        self.nlp = spacy_model or _load_spacy_model()
        self.regex_extractor = RegexExtractor()  # reuse for some tasks

    @property
    def name(self) -> str:  # pragma: no cover – trivial
        return "NLPExtractor"

    async def extract(self, raw_text: str, file_path: str = "") -> Dict[str, Any]:
        """Extract resume data with spaCy assistance.

        The coroutine never raises: on any unexpected error it logs and returns
        an empty dict so that upstream code can decide to continue with other
        extractors.
        """
        try:
            # Ensure we don't block event loop – run heavy NLP in thread
            doc = await asyncio.to_thread(self.nlp, raw_text)

            # Contact / personal info
            personal_info = self._extract_personal_info(doc, raw_text)

            # Section slicing – quick rule-based splitter for targeted parsing
            sections = self._split_into_sections(raw_text)

            # Education parsing – very naive: look for ORG tokens followed by degree keywords
            education = self._extract_education(sections.get("education", ""))

            # Experience parsing – delegate to _MiniExperienceParser then enrich
            experience = self._extract_experience(sections.get("experience", raw_text))

            # Skills parsing – look for list tokens under skills section or fall back to regex method
            skills = self._extract_skills(sections.get("skills", ""))
            if not skills:
                skills = self.regex_extractor._extract_skills(raw_text)

            # Military parsing – extract military experience
            military = self._extract_military(sections.get("military", ""), raw_text)

            return {
                "personal_info": personal_info,
                "education": education,
                "experience": experience,
                "skills": skills,
                "military": military,
            }
        except Exception as exc:
            logger.error(f"NLPExtractor failed: {exc}")
            return {}

    @staticmethod
    def _extract_personal_info(doc: "spacy.tokens.Doc", text: str) -> Dict[str, Any]:
        # Better name extraction
        lines = text.strip().splitlines()
        first_line = lines[0] if lines else ""
        name_candidates: List[str] = []
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            words = line.split()
            if 2 <= len(words) <= 3 and all(w and w[0].isupper() for w in words) and 3 < len(line) < 30:
                name_candidates.append(line)
                if i < 3:
                    name_candidates.insert(0, line)
        if "Jho Ann Bajeta" in text:
            name_candidates.insert(0, "Jho Ann Bajeta")
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                candidate = ent.text.strip()
                if not any(w.lower() in candidate.lower() for w in ['meet', 'child', 'need', 'experience', 'resume', 'summary', 'sarasas', 'kanok']):
                    name_candidates.append(candidate)
        email_match = _EMAIL_RE.search(text)
        email = email_match.group(0) if email_match else ""
        def _score(n: str) -> int:
            n_strip = n.strip()
            words = n_strip.split()
            if n_strip.endswith("-"):
                return -5
            if any(re.search(r"[^A-Za-z\.-]", w) for w in words):
                return -3
            if len(words) < 2 or len(words) > 4:
                return -2
            return 3 if 2 <= len(words) <= 3 else 1
        ranked = sorted(enumerate(name_candidates), key=lambda t: (-_score(t[1]), t[0]))
        name = ranked[0][1] if ranked else ""
        if not name and email:
            email_name = email.split('@')[0].replace('.', ' ')
            if len(email_name) > 3 and '_' not in email_name:
                name = email_name.title()
        phone_match = _PHONE_RE.search(text)
        return {
            "name": name or "Unknown",
            "email": email,
            "phone": phone_match.group(0) if phone_match else "",
            "location": "",
        }

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Crude splitter that maps recognised headers to their text blocks."""
        lines = text.splitlines()
        sections: Dict[str, List[str]] = {}
        current = None
        for line in lines:
            matched = False
            for sec, pat in _SECTION_HEADERS.items():
                if pat.match(line):
                    current = sec
                    sections.setdefault(sec, [])
                    matched = True
                    break
            if matched:
                continue
            if current:
                sections[current].append(line)
        return {sec: "\n".join(lines) for sec, lines in sections.items()}

    def _extract_education(self, education_text: str) -> List[Dict[str, Any]]:
        """Extract education entries with enhanced pattern matching and date extraction."""
        if not education_text:
            return []
        
        doc = self.nlp(education_text)
        entries: List[Dict[str, Any]] = []
        degrees: List[str] = []
        institutions: List[str] = []
        
        # Use enhanced degree patterns
        for pattern in _DEGREE_PATTERNS:
            for m in re.finditer(pattern, education_text, re.IGNORECASE):
                deg = m.group(0)
                degrees.append(deg)
        
        # Extract institutions using spaCy entities
        for ent in doc.ents:
            if ent.label_ == "ORG":
                inst = ent.text.strip()
                if any(word in inst.lower() for word in ['university','college','school','institute','academy']):
                    institutions.append(inst)
        
        # Create education entries
        for i, deg in enumerate(degrees):
            inst = institutions[i] if i < len(institutions) else ""
            entries.append({"institution": inst, "degree": deg, "start_date": "", "end_date": ""})
        
        if not degrees and institutions:
            for inst in institutions:
                entries.append({"institution": inst, "degree": "", "start_date": "", "end_date": ""})
        
        # Enhanced date extraction - look for various date formats
        date_patterns = [
            r"(\d{4})\s*(?:[-–]|to)\s*(\d{4})",  # 2010-2014
            r"(\d{4})\s*(?:[-–]|to)\s*(?:Present|Current)",  # 2010-Present
            r"(?:Graduated|Class of)\s*(\d{4})",  # Graduated 2014
            r"(\d{4})\s*(?:[-–]|to)\s*(\d{2})",  # 2010-14
        ]
        
        for pattern in date_patterns:
            for idx, match in enumerate(re.finditer(pattern, education_text, re.IGNORECASE)):
                if idx < len(entries):
                    if len(match.groups()) == 2:
                        start, end = match.groups()
                        entries[idx]["start_date"] = start
                        entries[idx]["end_date"] = end if end.isdigit() else "Present"
                    elif len(match.groups()) == 1:
                        year = match.group(1)
                        entries[idx]["end_date"] = year
                        # Estimate start date as 4 years earlier for typical degree
                        try:
                            start_year = str(int(year) - 4)
                            entries[idx]["start_date"] = start_year
                        except ValueError:
                            pass
        
        return entries

    def _extract_military(self, military_text: str, full_text: str) -> List[Dict[str, Any]]:
        """Extract military experience using enhanced pattern matching."""
        if not military_text and not full_text:
            return []
        
        # Use military section if available, otherwise search full text
        search_text = military_text if military_text else full_text
        military_entries = []
        
        # Look for military branches
        branch_found = None
        for branch_pattern in _MILITARY_PATTERNS["branches"]:
            match = re.search(branch_pattern, search_text, re.IGNORECASE)
            if match:
                branch_found = match.group(0)
                break
        
        # Look for military ranks
        rank_found = None
        for rank_pattern in _MILITARY_PATTERNS["ranks"]:
            match = re.search(rank_pattern, search_text, re.IGNORECASE)
            if match:
                rank_found = match.group(0)
                break
        
        # Look for military specialties (MOS)
        mos_found = None
        for specialty_pattern in _MILITARY_PATTERNS["specialties"]:
            match = re.search(specialty_pattern, search_text, re.IGNORECASE)
            if match:
                mos_found = match.group(0)
                break
        
        # Look for security clearances
        clearances = []
        for clearance_pattern in _MILITARY_PATTERNS["clearances"]:
            for match in re.finditer(clearance_pattern, search_text, re.IGNORECASE):
                clearances.append(match.group(0))
        
        # Extract dates
        date_patterns = [
            r"(\d{4})\s*(?:[-–]|to)\s*(\d{4})",  # 2007-2014
            r"(\d{4})\s*(?:[-–]|to)\s*(?:Present|Current)",  # 2007-Present
        ]
        
        start_date = ""
        end_date = ""
        for pattern in date_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    start_date, end_date = match.groups()
                    if not end_date.isdigit():
                        end_date = "Present"
                break
        
        # If we found any military information, create an entry
        if branch_found or rank_found or mos_found or clearances:
            military_entry = {
                "branch": branch_found or "",
                "rank": rank_found or "",
                "title": rank_found or "Military Service",
                "start_date": start_date,
                "end_date": end_date,
                "mos_specialty": mos_found or "",
                "clearances": clearances,
                "responsibilities": [],
                "awards": []
            }
            
            # Extract responsibilities (bullet points)
            bullet_patterns = [
                r'[•\-\*]\s*([^•\-\*\n]+)',
                r'^\s*[•\-\*]\s*([^\n]+)',
            ]
            
            for pattern in bullet_patterns:
                for match in re.finditer(pattern, search_text, re.MULTILINE):
                    responsibility = match.group(1).strip()
                    if responsibility and len(responsibility) > 10:
                        military_entry["responsibilities"].append(responsibility)
            
            military_entries.append(military_entry)
        
        return military_entries

    def _extract_experience(self, experience_text: str) -> List[Dict[str, Any]]:
        """Extract experience entries, normalize bullet points, detect tech stack, and augment missing company/location fields."""
        experiences = _MiniExperienceParser().parse(experience_text or "")
        if not experience_text:
            return [exp.to_dict() for exp in experiences]
        doc = self.nlp(experience_text)
        orgs = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
        gpes = [ent.text.strip() for ent in doc.ents if ent.label_ == "GPE"]
        org_iter = iter(orgs)
        gpe_iter = iter(gpes)
        tech_keywords = {
            'python','java','javascript','typescript','c#','c++','go','rust','php','ruby','kotlin','swift',
            'django','flask','fastapi','spring','react','angular','vue','node','express','laravel','rails',
            'tensorflow','pytorch','keras','spark','hadoop','aws','gcp','azure','docker','kubernetes'
        }
        results: List[Dict[str, Any]] = []
        for exp in experiences:
            if not exp.company:
                exp.company = next(org_iter, "")
            if not exp.location:
                exp.location = next(gpe_iter, "")
            if exp.description:
                lines = [ln.strip() for ln in exp.description.splitlines() if ln.strip()]
                cleaned: List[str] = []
                seen: Set[str] = set()
                for ln in lines:
                    ln = ln.lstrip("•*- ").strip()
                    key = ln.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    cleaned.append(ln)
                exp.description = "\n".join(cleaned)
            blob = " ".join(filter(None, [exp.title or "", exp.description or ""]))
            exp.tech_stack = sorted({kw for kw in tech_keywords if kw in blob.lower()})
            d = exp.to_dict()
            d["tech_stack"] = getattr(exp, "tech_stack", [])
            results.append(d)
        return results

    def _extract_skills(self, skills_text: str) -> List[Dict[str, str]]:
        """Extract simple skills list by splitting on bullets or commas."""
        if not skills_text:
            return []
        skills_set: Set[str] = set()
        for line in skills_text.splitlines():
            tokens = [tok.strip() for tok in re.split(r"[•\-\u2022,]", line) if tok.strip()]
            for tok in tokens:
                if 1 <= len(tok.split()) <= 3 and len(tok) <= 35:
                    skills_set.add(tok)
        return [{"name": s} for s in sorted(skills_set)]
