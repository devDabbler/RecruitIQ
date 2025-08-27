# military_extractor.py
"""
Purpose-built military experience extractor independent of RegexExtractor.
Exposes MilitaryExtractor.extract(text: str) -> List[MilitaryEntry].

This module focuses on:
- Section detection (headers and fallback scanning)
- Block segmentation
- Parsing entries (branch, rank/title, dates, unit, location, extras)
- Normalization and confidence scoring

Dictionaries are intentionally small seeds and can be extended safely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple


# -----------------------------
# Data model
# -----------------------------
@dataclass
class MilitaryEntry:
    branch: Optional[str] = None
    rank: Optional[str] = None
    title: Optional[str] = None
    unit: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    responsibilities: List[str] = None
    deployments: List[str] = None
    awards: List[str] = None
    clearances: List[str] = None
    training: List[str] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Ensure lists are not None
        for k in ["responsibilities", "deployments", "awards", "clearances", "training"]:
            if d.get(k) is None:
                d[k] = []
        return d


# -----------------------------
# Dictionaries and patterns
# -----------------------------
BRANCH_SYNONYMS: Dict[str, List[str]] = {
    "Army": [r"u\.?s\.?\s*army", r"us\s*army", r"\barmy\b", r"\busa\b", r"\barng\b"],
    "Navy": [r"u\.?s\.?\s*navy", r"us\s*navy", r"\bnavy\b", r"\busn\b"],
    "Air Force": [r"u\.?s\.?\s*air\s*force", r"air\s*force", r"\busaf\b", r"\bus\s*air\s*force\b"],
    "Marines": [r"u\.?s\.?\s*marines", r"marine\s+corps", r"\bmarines\b", r"\busmc\b"],
    "Coast Guard": [r"u\.?s\.?\s*coast\s*guard", r"\bcoast\s*guard\b", r"\buscg\b"],
    "Space Force": [r"space\s*force", r"\bussf\b"],
    "National Guard": [r"army\s+national\s+guard", r"\bnational\s+guard\b", r"\bguard\b"],
}

RANK_MAP: Dict[str, List[str]] = {
    "Second Lieutenant": [r"2nd\s+lieutenant", r"second\s+lieutenant", r"2LT"],
    "First Lieutenant": [r"1st\s+lieutenant", r"first\s+lieutenant", r"1LT"],
    "Captain": [r"captain", r"cpt"],
    "Major": [r"major"],
    "Lieutenant Colonel": [r"lieutenant\s+colonel", r"ltc"],
    "Colonel": [r"colonel", r"col"],
    "General": [r"brigadier\s+general|major\s+general|lieutenant\s+general|general"],
    "Sergeant": [r"sergeant", r"sgt"],
    "Staff Sergeant": [r"staff\s+sergeant", r"ssg"],
    "Master Sergeant": [r"master\s+sergeant", r"msg"],
    "First Sergeant": [r"first\s+sergeant", r"1sg"],
}

BASE_NAMES: List[str] = [
    "Fort Bragg", "Fort Liberty", "Fort Campbell", "Fort Benning", "Fort Moore",
    "Camp Pendleton", "Camp Lejeune", "Joint Base Lewis-McChord", "Norfolk", "San Diego",
    "Fort Hood", "Fort Cavazos", "Fort Bliss", "Fort Carson", "Fort Drum",
    "Fort Stewart", "Fort Riley", "Fort Sill", "Fort Eustis", "Fort Jackson",
]

CLEARANCE_KEYWORDS = [r"top\s*secret", r"secret", r"ts/sci", r"sci", r"public\s*trust"]
AWARD_KEYWORDS = [r"bronze\s+star", r"army\s+commendation\s+medal", r"purple\s+heart", r"medal", r"ribbon", r"commendation"]
TRAINING_KEYWORDS = [r"ranger\s+school", r"airborne", r"air\s*assault", r"sere", r"leadership\s+course", r"mos"]

DATE_RANGE_PATTERNS = [
    # Month Word YYYY – Month Word YYYY/Present
    r"(?P<start>\b\w{3,9}\s+\d{4}|\d{2}/\d{4}|\d{4}-\d{2}|\d{4})\s*[–—-]\s*(?P<end>\b\w{3,9}\s+\d{4}|\d{2}/\d{4}|\d{4}-\d{2}|\d{4}|present|current|now)",
    # YYYY to YYYY/Present
    r"(?P<start>\d{4})\s+to\s+(?P<end>\d{4}|present|current|now)",
    # MM/YYYY - MM/YYYY
    r"(?P<start>\d{2}/\d{4})\s*[–—-]\s*(?P<end>\d{2}/\d{4}|present|current|now)",
    # YYYY-MM - YYYY-MM
    r"(?P<start>\d{4}-\d{2})\s*[–—-]\s*(?P<end>\d{4}-\d{2}|present|current|now)",
]

SECTION_HEADERS = re.compile(
    r"(?i)\b(?:"
    r"military\s+(?:experience|service|background|career|record|assignment|training)"
    r"|armed\s+forces|armed\s+services"
    r"|national\s+guard|reserve|reserve\s+duty|guard\s+service"
    r"|active\s+duty"
    r"|mos|military\s+occupational\s+specialty"
    r"|service\s+record|service|background|career|record|assignment|training"
    r")\b:?"
)

TOC_LINE = re.compile(r"^[A-Z\s]{3,40}\s*\d{1,3}$")

SEPARATOR = re.compile(r"\n\s*\n", re.MULTILINE)


class MilitaryExtractor:
    @classmethod
    def extract(cls, text: str) -> List[MilitaryEntry]:
        sections = cls._find_sections(text)
        blocks: List[str] = []
        for start, end in sections:
            blocks.extend(cls._split_blocks(text[start:end]))

        # Fallback: scan full text if no section
        if not blocks:
            blocks = cls._split_blocks(text)

        entries: List[MilitaryEntry] = []
        for b in blocks:
            entry = cls._parse_block(b)
            if entry:
                norm = cls._normalize_entry(entry)
                norm.confidence = cls._score_entry(norm)
                if norm.confidence >= 0.4:  # acceptance threshold
                    entries.append(norm)

        # Additional robust fallback: scan lines that contain both a branch and a rank
        if not entries:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            branch_regex = re.compile("|".join([p for pats in BRANCH_SYNONYMS.values() for p in pats]), re.IGNORECASE)
            rank_regex = re.compile("|".join([p for pats in RANK_MAP.values() for p in pats]), re.IGNORECASE)
            for ln in lines:
                if branch_regex.search(ln) and rank_regex.search(ln):
                    entry = cls._parse_block(ln)
                    if entry:
                        norm = cls._normalize_entry(entry)
                        norm.confidence = cls._score_entry(norm)
                        if norm.confidence >= 0.4:
                            entries.append(norm)

        # Final fallback: try parsing the whole text as a single block
        if not entries:
            entry = cls._parse_block(text)
            if entry:
                norm = cls._normalize_entry(entry)
                norm.confidence = cls._score_entry(norm)
                if norm.confidence >= 0.4:
                    entries.append(norm)

        # Deduplicate by (branch, unit, dates)
        dedup: Dict[Tuple[str, str, str, str], MilitaryEntry] = {}
        for e in entries:
            key = (
                (e.branch or "").lower(),
                (e.unit or "").lower(),
                (e.start_date or ""),
                (e.end_date or ""),
            )
            if key not in dedup:
                dedup[key] = e
        return list(dedup.values())

    # --------------- helpers ---------------
    @classmethod
    def _find_sections(cls, text: str) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        for m in SECTION_HEADERS.finditer(text):
            # avoid TOC-like short all-caps lines with page numbers
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line_txt = text[line_start: line_end if line_end != -1 else len(text)].strip()
            if TOC_LINE.match(line_txt):
                continue
            start = m.end()
            # End at next all-caps header or double newline near a header
            next_header = re.search(r"\n\s*[A-Z][A-Z\s&]{3,}\n", text[start:])
            end = start + next_header.start() if next_header else len(text)
            spans.append((start, end))
        return spans

    @classmethod
    def _split_blocks(cls, text: str) -> List[str]:
        parts = re.split(SEPARATOR, text)
        # Allow slightly smaller blocks to catch concise entries
        return [p.strip() for p in parts if p and len(p.strip()) > 10]

    @classmethod
    def _parse_block(cls, block: str) -> Optional[MilitaryEntry]:
        b = block
        entry = MilitaryEntry(
            responsibilities=[], deployments=[], awards=[], clearances=[], training=[]
        )

        # Branch
        for canon, patterns in BRANCH_SYNONYMS.items():
            for pat in patterns:
                if re.search(pat, b, re.IGNORECASE):
                    entry.branch = canon
                    break
            if entry.branch:
                break

        # Rank/Title
        for canon, pats in RANK_MAP.items():
            for pat in pats:
                m = re.search(pat, b, re.IGNORECASE)
                if m:
                    entry.rank = canon
                    entry.title = canon
                    break
            if entry.rank:
                break

        # Dates
        for pat in DATE_RANGE_PATTERNS:
            m = re.search(pat, b, re.IGNORECASE)
            if m:
                entry.start_date = cls._norm_date(m.group("start"))
                entry.end_date = cls._norm_date(m.group("end"))
                break

        # Location (base names or City, ST heuristic)
        for base in BASE_NAMES:
            if re.search(rf"\b{re.escape(base)}\b", b, re.IGNORECASE):
                entry.location = base
                break
        if not entry.location:
            # City, ST or City ST or Base, ST
            m = re.search(r"\b([A-Z][a-z]+,\s*[A-Z]{2})\b", b)
            if m:
                entry.location = m.group(1)
            else:
                m2 = re.search(r"\b([A-Z][a-z]+\s+[A-Z]{2})\b", b)
                if m2:
                    entry.location = m2.group(1)

        # Unit
        m = re.search(r"\b(\d{1,3}(?:st|nd|rd|th)?\s+[A-Z][A-Za-z()\s]+?\b(?:Division|Brigade|Brigade\s+Combat\s+Team|Regiment|Battalion|Company|Group|Squadron|Wing|SFG\(A\)))", b)
        if m:
            entry.unit = m.group(1).strip()

        # MOS codes (e.g., 11B, 25B, 68W) captured as training/responsibility context
        mos_matches = re.findall(r"\b\d{2}[A-Z]{1,2}\b", b)
        for mos in mos_matches:
            if mos not in (entry.training or []):
                (entry.training or []).append(mos)

        # Responsibilities: capture bullet-like lines under block
        bullets = re.findall(r"(?m)^(?:[-•*]\s+|\d+\.\s+)(.+)$", b)
        for line in bullets:
            t = line.strip()
            if len(t) > 3:
                entry.responsibilities.append(t)

        # Extras
        for kw in CLEARANCE_KEYWORDS:
            mclr = re.search(kw, b, re.IGNORECASE)
            if mclr:
                # Normalize TS/SCI variants
                val = mclr.group(0)
                val = re.sub(r"ts\s*/\s*sci", "TS/SCI", val, flags=re.IGNORECASE)
                val = re.sub(r"top\s*secret", "Top Secret", val, flags=re.IGNORECASE)
                val = re.sub(r"public\s*trust", "Public Trust", val, flags=re.IGNORECASE)
                entry.clearances.append(val)
        for kw in AWARD_KEYWORDS:
            if re.search(kw, b, re.IGNORECASE):
                entry.awards.append(re.search(kw, b, re.IGNORECASE).group(0))
        for kw in TRAINING_KEYWORDS:
            if re.search(kw, b, re.IGNORECASE):
                entry.training.append(re.search(kw, b, re.IGNORECASE).group(0))

        # Deployments (simple heuristic)
        dep = re.findall(r"\b(?:deployed\s+to|deployment\s*:?|operation\s+)[^.;\n]{3,60}", b, re.IGNORECASE)
        for d in dep:
            entry.deployments.append(d.strip())

        # If nothing military-like, return None
        if not (entry.branch or entry.rank or entry.unit or entry.responsibilities):
            return None
        return entry

    @classmethod
    def _norm_date(cls, s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        s = s.strip().lower()
        if s in {"present", "current", "now"}:
            return "Present"
        # Try to extract YYYY
        m = re.search(r"(\d{4})", s)
        if m:
            return m.group(1)
        # Try Mon YYYY -> YYYY-MM
        m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{4})", s)
        if m:
            month_map = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06","jul":"07","aug":"08","sep":"09","sept":"09","oct":"10","nov":"11","dec":"12"}
            return f"{m.group(2)}-{month_map[m.group(1)]}"
        return s

    @classmethod
    def _normalize_entry(cls, e: MilitaryEntry) -> MilitaryEntry:
        # Already canonicalized branch/rank above; ensure title fallback
        if not e.title and e.rank:
            e.title = e.rank
        # Trim strings
        for field in ["branch","rank","title","unit","start_date","end_date","location"]:
            v = getattr(e, field)
            if isinstance(v, str):
                setattr(e, field, v.strip())
        # Dedup list fields
        for field in ["responsibilities","deployments","awards","clearances","training"]:
            lst = getattr(e, field) or []
            dedup = []
            seen = set()
            for item in lst:
                key = item.strip()
                if key and key.lower() not in seen:
                    seen.add(key.lower())
                    dedup.append(key)
            setattr(e, field, dedup)
        return e

    @classmethod
    def _score_entry(cls, e: MilitaryEntry) -> float:
        score = 0.0
        if e.branch:
            score += 0.4
        if e.rank or e.title:
            score += 0.2
        if e.start_date or e.end_date:
            score += 0.2
        if e.responsibilities and len(e.responsibilities) > 1:
            score += 0.1
        if e.unit:
            score += 0.1
        # Bonus for clearances/awards presence
        if e.clearances:
            score += 0.05
        if e.awards:
            score += 0.05
        return min(score, 1.0)
