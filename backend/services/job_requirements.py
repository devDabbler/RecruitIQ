"""Structured job requirements (Track 2 Phase 1) and what they read about a
candidate.

A job may list must-have skills, nice-to-have skills, a years-of-experience
range and a minimum education. `score_pair` applies them; this module holds
the vocabulary, the validation, and the two candidate facts the rules need
that the ranker did not read before: years of recorded work experience and
the highest recognised degree.

The rules flag, they never reject. A candidate missing a must-have is capped,
not removed, and the decision stays with a person (Slate auto-rejects; we
deliberately do not).

Unknown is never held against anyone: a candidate with no dated experience has
unknown years, and a degree the normalizer does not recognise is unknown, and
neither moves a score or counts toward a cap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_SKILLS_PER_LIST = 20
MAX_SKILL_LENGTH = 60

EDUCATION_LEVELS: Tuple[str, ...] = ("none", "bachelor", "master", "phd")
EDUCATION_LABELS: Dict[str, str] = {
    "none": "no degree",
    "bachelor": "bachelor's degree",
    "master": "master's degree",
    "phd": "PhD",
}

# Missing must-haves cap the final score. Rows are checked in order, so the
# harsher cap must come first. Published by the transparency policy.
REQUIREMENT_CAPS: List[Dict[str, Any]] = [
    {"min_missing": 2, "limit": 50.0, "condition": "two or more must-haves missing"},
    {"min_missing": 1, "limit": 70.0, "condition": "one must-have missing"},
]

# Nice-to-have skills add up to this many points to the skill score.
NICE_TO_HAVE_MAX_BONUS = 10.0

# Recorded years outside the job's range lower the seniority score.
YEARS_SHORT_PENALTY_PER_YEAR = 10.0
YEARS_SHORT_MAX_PENALTY = 40.0
YEARS_OVER_PENALTY_PER_YEAR = 5.0
YEARS_OVER_MAX_PENALTY = 20.0
# Short of min_years by at least this much counts as one missing must-have.
YEARS_SHORT_COUNTS_AS_MISSING = 2.0


class JobRequirements(BaseModel):
    """What `jobs.requirements` holds. Every field is optional."""

    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    min_years: Optional[int] = Field(default=None, ge=0, le=50)
    max_years: Optional[int] = Field(default=None, ge=0, le=50)
    min_education: Optional[Literal["none", "bachelor", "master", "phd"]] = None

    @field_validator("must_have_skills", "nice_to_have_skills", mode="before")
    @classmethod
    def _clean_skills(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = value.split(",")
        cleaned: List[str] = []
        seen = set()
        for item in value:
            skill = " ".join(str(item).split())
            if not skill:
                continue
            if len(skill) > MAX_SKILL_LENGTH:
                raise ValueError(f"Skills are limited to {MAX_SKILL_LENGTH} characters: {skill[:20]}...")
            if skill.lower() in seen:
                continue
            seen.add(skill.lower())
            cleaned.append(skill)
        if len(cleaned) > MAX_SKILLS_PER_LIST:
            raise ValueError(f"At most {MAX_SKILLS_PER_LIST} skills per list.")
        return cleaned

    @model_validator(mode="after")
    def _check(self):
        if self.min_years is not None and self.max_years is not None and self.min_years > self.max_years:
            raise ValueError("The minimum years cannot be above the maximum.")
        must = {s.lower() for s in self.must_have_skills}
        overlap = [s for s in self.nice_to_have_skills if s.lower() in must]
        if overlap:
            raise ValueError(f"A skill cannot be both a must-have and a nice-to-have: {', '.join(overlap)}")
        return self

    def is_empty(self) -> bool:
        return not (
            self.must_have_skills
            or self.nice_to_have_skills
            or self.min_years is not None
            or self.max_years is not None
            or self.min_education not in (None, "none")
        )

    def needs_profile(self) -> bool:
        """True when scoring needs the candidate's years or degrees."""
        return (
            self.min_years is not None
            or self.max_years is not None
            or self.min_education not in (None, "none")
        )


def parse_requirements(raw: Any) -> Optional[JobRequirements]:
    """`jobs.requirements` as a model, or None when it sets nothing.

    Rows are only written through the validated API, but a hand-edited row
    that no longer validates is treated as no requirements rather than
    breaking every ranking that touches the job.
    """
    if not raw:
        return None
    if isinstance(raw, JobRequirements):
        parsed = raw
    else:
        try:
            parsed = JobRequirements.model_validate(raw)
        except Exception:  # noqa: BLE001 - a bad row must not take ranking down
            return None
    return None if parsed.is_empty() else parsed


def requirements_for_storage(value: Optional[JobRequirements]) -> Optional[Dict[str, Any]]:
    """What goes in the column: None when the requirements set nothing."""
    if value is None or value.is_empty():
        return None
    return value.model_dump()


# --- education ----------------------------------------------------------------

# Tokens after lowercasing and removing dots, so "Ph.D." is "phd" and "B.Tech"
# is "btech". Checked highest level first, so "MS/PhD" reads as a PhD.
_DEGREE_TOKENS: List[Tuple[str, Tuple[str, ...]]] = [
    ("phd", ("phd", "dphil", "doctorate")),
    ("master", ("msc", "ms", "ma", "mba", "meng", "mtech", "mphil", "mres", "mfa", "mpa", "mph", "llm",
                "mcs", "master", "masters")),
    ("bachelor", ("bsc", "bs", "ba", "btech", "beng", "be", "bba", "bcom", "bfa", "llb", "bachelor",
                  "bachelors")),
    ("none", ("associate", "associates", "ged", "highschool")),
]


def normalize_degree(degree: Optional[str]) -> Optional[str]:
    """One of EDUCATION_LEVELS, or None when the degree is not recognised."""
    if not degree:
        return None
    text = " ".join(degree.lower().replace(".", "").replace("'", "").split())
    if "doctor of philosophy" in text:
        return "phd"
    tokens = set(re.findall(r"[a-z]+", text.replace("high school", "highschool")))
    for level, words in _DEGREE_TOKENS:
        if tokens & set(words):
            return level
    return None


def highest_education(degrees: Iterable[Optional[str]]) -> Optional[str]:
    """The highest recognised level across a candidate's degrees, or None."""
    levels = [normalize_degree(d) for d in degrees]
    known = [lvl for lvl in levels if lvl is not None]
    if not known:
        return None
    return max(known, key=EDUCATION_LEVELS.index)


def education_rank(level: Optional[str]) -> int:
    return EDUCATION_LEVELS.index(level) if level in EDUCATION_LEVELS else -1


# --- years --------------------------------------------------------------------


def years_of_experience(
    spans: Iterable[Tuple[Optional[date], Optional[date]]], today: Optional[date] = None
) -> Optional[float]:
    """Total years covered by dated experience, overlaps counted once.

    A row with no start date is skipped. No end date means the role is
    current (that is how the resume save path stores "Present"). Returns None
    when nothing is dated, so an undated history reads as unknown, not zero.
    """
    today = today or date.today()
    intervals = []
    for start, end in spans:
        if start is None:
            continue
        start = _as_date(start)
        end = _as_date(end) if end is not None else today
        if end < start:
            continue
        intervals.append((start, min(end, today)))
    if not intervals:
        return None
    intervals.sort()
    total_days = 0
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total_days += (current_end - current_start).days
            current_start, current_end = start, end
    total_days += (current_end - current_start).days
    return round(total_days / 365.25, 1)


def _as_date(value) -> date:
    return value.date() if hasattr(value, "date") and callable(value.date) else value


# --- the candidate facts the rules read ------------------------------------------


@dataclass
class CandidateProfile:
    """Years and degrees from candidate_experience / candidate_education."""

    years: Optional[float] = None
    degrees: List[str] = field(default_factory=list)

    @property
    def education(self) -> Optional[str]:
        return highest_education(self.degrees)


def load_profiles(db, candidate_ids: Sequence[str]) -> Dict[str, CandidateProfile]:
    """Profiles for many candidates in two queries. Anyone with no rows gets
    an empty profile (unknown years, unknown education)."""
    from sqlalchemy import bindparam, text

    ids = [str(cid) for cid in candidate_ids if cid]
    profiles: Dict[str, CandidateProfile] = {cid: CandidateProfile() for cid in ids}
    if not ids:
        return profiles

    spans: Dict[str, List[Tuple[Optional[date], Optional[date]]]] = {}
    rows = db.execute(
        text(
            "SELECT candidate_id, start_date, end_date FROM candidate_experience "
            "WHERE candidate_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).all()
    for cid, start, end in rows:
        spans.setdefault(cid, []).append((start, end))
    for cid, rows_for in spans.items():
        profiles[cid].years = years_of_experience(rows_for)

    degrees = db.execute(
        text(
            "SELECT candidate_id, degree FROM candidate_education "
            "WHERE candidate_id IN :ids AND degree IS NOT NULL"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).all()
    for cid, degree in degrees:
        profiles[cid].degrees.append(degree)
    return profiles


def profile_for(candidate) -> CandidateProfile:
    """One candidate's profile through the session that loaded them; empty for
    a candidate not attached to a session (unit tests build those)."""
    from sqlalchemy.orm import object_session

    session = object_session(candidate)
    if session is None or not getattr(candidate, "id", None):
        return CandidateProfile()
    return load_profiles(session, [candidate.id]).get(str(candidate.id), CandidateProfile())


def cap_for(missing_count: int) -> Optional[Dict[str, Any]]:
    for cap in REQUIREMENT_CAPS:
        if missing_count >= cap["min_missing"]:
            return cap
    return None
