"""
Integration module for the enhanced matching capabilities.

`score_pair` is the one place a job and a candidate are turned into a number.
Both ranking directions (candidates for a job, jobs for a candidate) call it,
and so does the transparency view, so what the admin screen shows as "how this
score was built" is the actual computation, not a description of it that
could drift.
"""

import logging
from typing import List, Dict, Any, Optional

from .job_requirements import (
    EDUCATION_LABELS,
    NICE_TO_HAVE_MAX_BONUS,
    YEARS_OVER_PENALTY_PER_YEAR,
    YEARS_SHORT_MAX_PENALTY,
    YEARS_SHORT_PENALTY_PER_YEAR,
    YEARS_OVER_MAX_PENALTY,
    YEARS_SHORT_COUNTS_AS_MISSING,
    CandidateProfile,
    cap_for,
    education_rank,
    load_profiles,
    parse_requirements,
    profile_for,
)
from .matching_enhancer import MatchingEnhancer

logger = logging.getLogger(__name__)


# The three weighting tiers, chosen by the role score alone. A candidate whose
# current role is far from the requisition is not rescued by skill overlap: the
# weights shift toward the (poor) role score and the whole thing is scaled
# down. Expressed as data so the transparency endpoint can publish exactly
# what the ranking code applies.
WEIGHT_TIERS: List[Dict[str, Any]] = [
    {
        "name": "severe_role_mismatch",
        "label": "Severe role mismatch",
        "condition": "role score below 30",
        "max_role_score": 30.0,
        "weights": {"skill": 0.15, "role": 0.7, "experience": 0.15},
        "multiplier": 0.25,
    },
    {
        "name": "moderate_role_mismatch",
        "label": "Moderate role mismatch",
        "condition": "role score from 30 to below 50",
        "max_role_score": 50.0,
        "weights": {"skill": 0.2, "role": 0.6, "experience": 0.2},
        "multiplier": 0.45,
    },
    {
        "name": "standard",
        "label": "Standard",
        "condition": "role score 50 or above",
        "max_role_score": None,
        "weights": {"skill": 0.35, "role": 0.45, "experience": 0.2},
        "multiplier": 1.0,
    },
]

# Applied after the tier weighting when both role and skills look weak.
CROSS_DOMAIN_FINAL_PENALTY: Dict[str, Any] = {
    "condition": "role score below 50 and skill score below 60",
    "max_role_score": 50.0,
    "max_skill_score": 60.0,
    "multiplier": 0.4,
}


# What `score_pair` reads, and what it deliberately never reads. The second
# list is enforced by a test that changes every one of those fields and
# asserts the score does not move, so this is a checked contract rather than
# a statement of intent.
SCORED_CANDIDATE_FIELDS: List[Dict[str, str]] = [
    {"field": "current_position", "used_for": "role fit (title similarity and role category) and seniority"},
    {"field": "skills", "used_for": "skill overlap against the job's listed skills, and must-have and nice-to-have checks"},
    {
        "field": "experience dates",
        "used_for": "years of recorded experience, read only when the job sets a years range",
    },
    {
        "field": "education degree",
        "used_for": "highest degree level, read only when the job sets a minimum education",
    },
]
SCORED_JOB_FIELDS: List[Dict[str, str]] = [
    {"field": "title", "used_for": "role fit, role category, and seniority"},
    {"field": "skills", "used_for": "skill overlap"},
    {"field": "required_qualifications", "used_for": "seniority (years and level keywords only)"},
    {
        "field": "requirements",
        "used_for": "must-have skills (caps), nice-to-have skills (bonus), years range and minimum education",
    },
]


def requirement_explanation(nice, must_have, years, education, cap) -> List[str]:
    """Sentences appended to a match explanation when the job sets requirements."""
    parts: List[str] = []
    if must_have:
        if must_have["missing"]:
            parts.append(f"Missing must-have skills: {', '.join(must_have['missing'])}")
        else:
            parts.append(f"Has all {len(must_have['skills'])} must-have skills")
    if nice:
        matched = len(nice["exact"]) + len(nice["partial"])
        parts.append(f"Has {matched} of {len(nice['skills'])} nice-to-have skills")
    if years and years["candidate_years"] is not None:
        if years["short_by"]:
            parts.append(
                f"About {years['candidate_years']:g} years of recorded experience against a minimum of {years['min_years']}"
            )
        elif years["over_by"]:
            parts.append(
                f"About {years['candidate_years']:g} years of recorded experience, above the range of up to {years['max_years']}"
            )
    if education and education["meets"] is False:
        wanted = EDUCATION_LABELS[education["min_education"]]
        if education["candidate_education"] == "none":
            parts.append(f"No degree recorded, and the job asks for a {wanted}")
        else:
            have = EDUCATION_LABELS[education["candidate_education"]]
            parts.append(f"Highest recorded degree is a {have}, below the {wanted} asked for")
    if cap["applied"]:
        count = cap["missing_count"]
        what = "one requirement is" if count == 1 else f"{count} requirements are"
        parts.append(f"Score capped at {cap['limit']:g} because {what} missing")
    return parts
UNSCORED_CANDIDATE_FIELDS: List[Dict[str, str]] = [
    {"field": "first_name", "reason": "a name carries gender and ethnicity signal and says nothing about fit"},
    {"field": "last_name", "reason": "same as first name"},
    {"field": "email", "reason": "contact detail, not a qualification"},
    {"field": "phone", "reason": "contact detail, not a qualification"},
    {"field": "location", "reason": "never a ranking input; a place filter is an explicit WHERE clause the recruiter asks for"},
    {"field": "headline", "reason": "free text that can carry age, family or health details"},
    {"field": "notes", "reason": "recruiter notes are for people, not for scoring"},
    {"field": "current_company", "reason": "employer prestige is not fit"},
    {"field": "source", "reason": "how someone arrived must not change how they rank"},
    {"field": "status", "reason": "pipeline stage is an outcome, not an input"},
    {"field": "position_applied", "reason": "not scored; only shown as a label when the current position is blank"},
    {"field": "created_at", "reason": "recency in the database is not a qualification"},
    {"field": "resume text", "reason": "the parsed resume is read at upload time to fill skills and position, never by the ranker directly"},
]
NOT_COLLECTED_FIELDS: List[str] = [
    "age or date of birth",
    "gender",
    "ethnicity",
    "photo",
    "disability or health",
    "marital or family status",
    "nationality or visa status",
]


def select_weight_tier(role_score: float) -> Dict[str, Any]:
    for tier in WEIGHT_TIERS:
        ceiling = tier["max_role_score"]
        if ceiling is None or role_score < ceiling:
            return tier
    return WEIGHT_TIERS[-1]


def _split_skills(raw) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return list(raw)


class MatchingIntegrator:
    """Integrates advanced matching capabilities with existing services."""

    def __init__(self, embedding_model=None):
        """
        Args:
            embedding_model: optional adapter with encode/embed_query/embed_documents,
                used by MatchingEnhancer for semantic scoring. Matching works without it.
        """
        self.enhancer = MatchingEnhancer(embedding_model=embedding_model)

    def score_pair(self, job, candidate, profile: Optional[CandidateProfile] = None) -> Dict[str, Any]:
        """Score one candidate against one job and return the full trace.

        The trace carries every intermediate: the inputs each component read,
        the component scores, which weighting tier fired, and each penalty
        with its before/after. `match_score` is the number the ranking uses.

        Only these things about the candidate are read: current position,
        skills, and (for the explanation text) position_applied and name;
        and, only when the job sets a years range or a minimum education,
        the dates of their recorded experience and their degrees. Name,
        contact details, location, notes, company, source and pipeline status
        never reach a score. That is a property the tests assert, not just a
        comment.

        `profile` carries the years and degrees; ranking loops pass it in
        bulk (`load_profiles`), and when it is missing it is looked up here.
        A job with no requirements never reads it and scores exactly as it
        did before requirements existed (test_score_baseline).
        """
        job_title = job.title or ""
        job_description = job.job_overview or ""
        job_requirements = job.required_qualifications or ""
        job_skills = _split_skills(job.skills)
        requirements = parse_requirements(getattr(job, "requirements", None))
        if requirements is not None:
            # A must-have is a skill the job asks for, so it counts in the
            # overlap too even when it was not also typed into `skills`.
            listed = {s.lower().strip() for s in job_skills}
            job_skills = job_skills + [s for s in requirements.must_have_skills if s.lower() not in listed]
        if requirements is not None and requirements.needs_profile() and profile is None:
            profile = profile_for(candidate)

        job_text = f"{job_title} {job_requirements}"
        job_level, job_years = self.enhancer.extract_experience_level(job_text)

        candidate_skills = (
            [skill.skill_name for skill in candidate.skills]
            if hasattr(candidate, "skills") and candidate.skills
            else []
        )
        candidate_position = candidate.current_position or ""

        # 1. Skill overlap, plus any nice-to-have bonus, then the cross-domain
        # discount on it.
        skills = self.enhancer.skill_match_details(job_skills, candidate_skills)
        nice = self._nice_to_have(requirements, candidate_skills)
        skill_before_penalty = min(skills["score"] + nice["bonus"], 100.0) if nice else skills["score"]
        penalty = self.enhancer.cross_domain_skill_penalty_details(
            skill_before_penalty, job_title, candidate_position
        )
        skill_score = penalty["score"]
        if penalty["applied"]:
            logger.info(
                f"[MatchIntegratorDebug] Cross-domain skill penalty applied to candidate {candidate.id}: "
                f"{skills['score']:.1f}% → {skill_score:.1f}%"
            )

        # 2. Role fit.
        role = self.enhancer.role_match_details(job_title, job_description, candidate_position)
        role_score = role["score"]

        # 3. Seniority, read from the titles alone.
        candidate_level, candidate_years = self.enhancer.extract_experience_level(candidate_position)
        experience = self.enhancer.experience_match_details(
            job_level, job_years, candidate_level, candidate_years
        )
        years = self._years_rule(requirements, profile)
        experience_score = experience["score"]
        if years and years["penalty"]:
            experience_score = max(experience_score - years["penalty"], 0.0)

        logger.debug(
            f"[MatchIntegratorDebug] Candidate {candidate.id} - Position: '{candidate_position}' - "
            f"Role: {role_score:.1f}%, Skill: {skill_score:.1f}%, Experience: {experience_score:.1f}%"
        )

        # 4. Weighted blend; the tier is picked by the role score.
        tier = select_weight_tier(role_score)
        weights = tier["weights"]
        weighted_score = (
            skill_score * weights["skill"]
            + role_score * weights["role"]
            + experience_score * weights["experience"]
        ) * tier["multiplier"]

        # 5. One more discount when role and skills both look weak.
        final_penalty_applied = (
            role_score < CROSS_DOMAIN_FINAL_PENALTY["max_role_score"]
            and skill_score < CROSS_DOMAIN_FINAL_PENALTY["max_skill_score"]
        )
        match_score = weighted_score
        if final_penalty_applied:
            match_score *= CROSS_DOMAIN_FINAL_PENALTY["multiplier"]
            logger.info(
                f"[MatchIntegratorDebug] Additional cross-domain penalty for role/skill mismatch: "
                f"candidate {candidate.id}, final score = {match_score:.1f}%"
            )

        # 6. Requirements: missing must-haves cap the score. Flagged, never
        # rejected; a person still decides.
        must_have = self._must_have(requirements, candidate_skills)
        education = self._education_rule(requirements, profile)
        cap = self._requirement_cap(match_score, must_have, years, education)
        match_score = cap["score_after"]

        match_explanation = self.enhancer.generate_match_explanation(
            job, candidate, skills["matching_skills"], role_score, skill_score, experience_score
        )
        if requirements is not None:
            match_explanation = ". ".join(
                [match_explanation] + requirement_explanation(nice, must_have, years, education, cap)
            )

        return {
            "match_score": match_score,
            "match_explanation": match_explanation,
            "skill_match_score": skill_score,
            "role_match_score": role_score,
            "experience_match_score": experience_score,
            "matching_skills": skills["matching_skills"],
            "candidate_skills": candidate_skills,
            "candidate_position": candidate_position,
            "candidate_level": candidate_level,
            "candidate_years": candidate_years,
            "job_skills": job_skills,
            "job_level": job_level,
            "job_years": job_years,
            "skills": skills,
            "cross_domain_skill_penalty": penalty,
            "role": role,
            "experience": experience,
            "tier": tier,
            "weighted_score": weighted_score,
            "final_penalty_applied": final_penalty_applied,
            "final_penalty_multiplier": CROSS_DOMAIN_FINAL_PENALTY["multiplier"],
            "requirements": requirements.model_dump() if requirements is not None else None,
            "nice_to_have": nice,
            "must_have": must_have,
            "years": years,
            "education": education,
            "requirement_cap": cap,
        }

    # --- requirement rules (Track 2 Phase 1) --------------------------------

    def _nice_to_have(self, requirements, candidate_skills) -> Optional[Dict[str, Any]]:
        """Up to NICE_TO_HAVE_MAX_BONUS points on the skill score. With no
        nice-to-have list the job's skills already carry this (no bonus)."""
        if requirements is None or not requirements.nice_to_have_skills:
            return None
        wanted = requirements.nice_to_have_skills
        details = self.enhancer.skill_match_details(wanted, candidate_skills)
        credit = len(details["exact"]) + 0.5 * len(details["partial"])
        return {
            "skills": list(wanted),
            "exact": details["exact"],
            "partial": details["partial"],
            "missing": details["missing"],
            "bonus": NICE_TO_HAVE_MAX_BONUS * credit / len(wanted),
            "max_bonus": NICE_TO_HAVE_MAX_BONUS,
        }

    def _must_have(self, requirements, candidate_skills) -> Optional[Dict[str, Any]]:
        """Present or missing per must-have, using the same exact/partial
        matcher as the skill overlap. A partial match counts as present."""
        if requirements is None or not requirements.must_have_skills:
            return None
        details = self.enhancer.skill_match_details(requirements.must_have_skills, candidate_skills)
        return {
            "skills": list(requirements.must_have_skills),
            "present": details["exact"] + details["partial"],
            "partial": details["partial"],
            "missing": details["missing"],
        }

    @staticmethod
    def _years_rule(requirements, profile) -> Optional[Dict[str, Any]]:
        if requirements is None or (requirements.min_years is None and requirements.max_years is None):
            return None
        years = profile.years if profile is not None else None
        short_by = over_by = 0.0
        if years is not None and requirements.min_years is not None:
            short_by = max(requirements.min_years - years, 0.0)
        if years is not None and requirements.max_years is not None:
            over_by = max(years - requirements.max_years, 0.0)
        penalty = 0.0
        if short_by:
            penalty = min(short_by * YEARS_SHORT_PENALTY_PER_YEAR, YEARS_SHORT_MAX_PENALTY)
        elif over_by:
            penalty = min(over_by * YEARS_OVER_PENALTY_PER_YEAR, YEARS_OVER_MAX_PENALTY)
        return {
            "min_years": requirements.min_years,
            "max_years": requirements.max_years,
            "candidate_years": years,
            "short_by": round(short_by, 1),
            "over_by": round(over_by, 1),
            "penalty": round(penalty, 2),
            "counts_as_missing": short_by >= YEARS_SHORT_COUNTS_AS_MISSING,
        }

    @staticmethod
    def _education_rule(requirements, profile) -> Optional[Dict[str, Any]]:
        if requirements is None or requirements.min_education in (None, "none"):
            return None
        level = profile.education if profile is not None else None
        meets = None if level is None else education_rank(level) >= education_rank(requirements.min_education)
        return {
            "min_education": requirements.min_education,
            "candidate_education": level,
            "meets": meets,
            "counts_as_missing": meets is False,
        }

    @staticmethod
    def _requirement_cap(score, must_have, years, education) -> Dict[str, Any]:
        reasons: List[str] = []
        if must_have:
            reasons += [f"must-have skill {s}" for s in must_have["missing"]]
        if years and years["counts_as_missing"]:
            reasons.append(f"at least {years['min_years']} years of experience")
        if education and education["counts_as_missing"]:
            reasons.append(f"a {EDUCATION_LABELS[education['min_education']]}")
        cap = cap_for(len(reasons))
        limit = cap["limit"] if cap else None
        after = min(score, limit) if limit is not None else score
        return {
            "missing": reasons,
            "missing_count": len(reasons),
            "limit": limit,
            "applied": limit is not None and score > limit,
            "score_before": score,
            "score_after": after,
        }

    async def enhanced_candidate_job_matching(self, job_id: int, db, min_score: float = 20.0, limit: int = 10):
        """
        Find candidates matching a job with enhanced scoring and explanations.

        Args:
            job_id: ID of the job to match candidates against
            db: Database session
            min_score: Minimum match score threshold
            limit: Maximum number of candidates to return

        Returns:
            List of candidates with enhanced match data
        """
        from backend.models.models import Job, Candidate, Resume
        from sqlalchemy import desc

        # Get the job details
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job with ID {job_id} not found")
            return []

        # Get all candidates with skills
        candidates = db.query(Candidate).all()
        if not candidates:
            logger.warning("No candidates found in database")
            return []

        # Years and degrees in two queries for everyone, rather than two per
        # candidate, when the job's requirements read them.
        requirements = parse_requirements(getattr(job, "requirements", None))
        profiles = (
            load_profiles(db, [c.id for c in candidates])
            if requirements is not None and requirements.needs_profile()
            else {}
        )

        # Process each candidate
        matches = []
        for candidate in candidates:
            trace = self.score_pair(job, candidate, profiles.get(candidate.id))
            match_score = trace["match_score"]

            # Include candidate if score meets threshold
            if match_score >= min_score:
                # Get most recent resume
                resume = db.query(Resume).filter(
                    Resume.candidate_id == candidate.id
                ).order_by(desc(Resume.created_at)).first()

                # Create match result
                match_data = {
                    "id": candidate.id,
                    "name": f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or "Unknown",
                    "email": candidate.email or "",
                    "resume_id": resume.id if resume else None,
                    "skills": trace["candidate_skills"],
                    "position": trace["candidate_position"],
                    "experience_level": trace["candidate_level"],
                    "years_experience": trace["candidate_years"],
                    "skill_match_score": trace["skill_match_score"],
                    "role_match_score": trace["role_match_score"],
                    "experience_match_score": trace["experience_match_score"],
                    "match_score": match_score,
                    "match_explanation": trace["match_explanation"],
                    "source": "enhanced_match"
                }

                matches.append(match_data)

        # Sort by match score and limit results
        sorted_matches = sorted(matches, key=lambda x: x.get("match_score", 0), reverse=True)
        return sorted_matches[:limit]

    async def enhanced_job_candidate_matching(self, candidate_id: str, db, min_score: float = 20.0, limit: int = 10):
        """
        Find jobs matching a candidate with enhanced scoring and explanations.

        Args:
            candidate_id: ID of the candidate to match jobs against
            db: Database session
            min_score: Minimum match score threshold
            limit: Maximum number of jobs to return

        Returns:
            List of jobs with enhanced match data
        """
        from backend.models.models import Job, Candidate

        # Get the candidate details
        candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
        if not candidate:
            logger.warning(f"Candidate with ID {candidate_id} not found")
            return []

        # Only open requisitions are matchable. A draft is a job that has not
        # been decided on yet and a closed one cannot be filled, so neither
        # belongs in "roles this person could be put forward for". Without this
        # filter, saving a draft in the jobs UI immediately surfaced it in every
        # candidate's matches.
        #
        # Deliberately not applied to enhanced_candidate_job_matching: that one
        # takes an explicit job_id the caller already chose, so filtering there
        # would break viewing candidates for a role you are still drafting.
        jobs = db.query(Job).filter(Job.status == "open").all()
        if not jobs:
            logger.warning("No open jobs found in database")
            return []

        profile = load_profiles(db, [candidate.id]).get(candidate.id)

        # Process each job
        matches = []
        for job in jobs:
            trace = self.score_pair(job, candidate, profile)
            match_score = trace["match_score"]

            # Include job if score meets threshold
            if match_score >= min_score:
                match_data = {
                    "id": job.id,
                    "title": job.title,
                    "department": job.department if hasattr(job, 'department') else None,
                    "description": job.job_overview,
                    "location": job.location if hasattr(job, 'location') else None,
                    "skills": trace["job_skills"],
                    "skill_match_score": trace["skill_match_score"],
                    "role_match_score": trace["role_match_score"],
                    "experience_match_score": trace["experience_match_score"],
                    "match_score": match_score,
                    "match_explanation": trace["match_explanation"]
                }

                matches.append(match_data)

        # Sort by match score and limit results
        sorted_matches = sorted(matches, key=lambda x: x.get("match_score", 0), reverse=True)
        return sorted_matches[:limit]

    async def find_similar_jobs(self, job_id: int, db, limit: int = 5):
        """
        Find jobs similar to the specified job with enhanced similarity metrics.

        Args:
            job_id: ID of the job to find similar jobs for
            db: Database session
            limit: Maximum number of similar jobs to return

        Returns:
            List of similar jobs with similarity scores and explanations
        """
        from backend.models.models import Job

        # Get the target job
        target_job = db.query(Job).filter(Job.id == job_id).first()
        if not target_job:
            logger.warning(f"Job with ID {job_id} not found")
            return []

        # Get all other jobs
        other_jobs = db.query(Job).filter(Job.id != job_id).all()
        if not other_jobs:
            logger.warning("No other jobs found in database")
            return []

        # Calculate similarity between target job and each other job
        similarities = []
        for job in other_jobs:
            similarity_score, similarity_explanation = self.enhancer.calculate_job_similarity(
                target_job, job
            )

            similarities.append({
                "job": job,
                "score": similarity_score,
                "explanation": similarity_explanation
            })

        # Sort by similarity score and limit results
        sorted_similarities = sorted(similarities, key=lambda x: x.get("score", 0), reverse=True)
        limited_similarities = sorted_similarities[:limit]

        # Format results
        similar_jobs = [
            {
                "id": item["job"].id,
                "title": item["job"].title,
                "department": item["job"].department if hasattr(item["job"], 'department') else None,
                "location": item["job"].location if hasattr(item["job"], 'location') else None,
                "skills": _split_skills(item["job"].skills),
                "similarity_score": item["score"],
                "similarity_explanation": item["explanation"]
            }
            for item in limited_similarities
        ]

        return similar_jobs
