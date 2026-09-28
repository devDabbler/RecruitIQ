"""Admin-only scoring transparency.

Three read endpoints behind `require_admin` that expose how the ranking and
the semantic search actually work, built from the same constants and the
same `score_pair` the ranking runs. The point is that nothing here is a
description that could drift from the code: the policy endpoint reads the
weight tables the ranker applies, and the trace endpoint returns the ranker's
own intermediates.

Admin-only because the traces carry every candidate's raw component scores
in one response, which is more than the read-only demo should hand out.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job
from backend.services.assistant_tools import RELEVANCE_BANDS, relevance_band
from backend.services.matching_integrator import (
    CROSS_DOMAIN_FINAL_PENALTY,
    NOT_COLLECTED_FIELDS,
    SCORED_CANDIDATE_FIELDS,
    SCORED_JOB_FIELDS,
    UNSCORED_CANDIDATE_FIELDS,
    WEIGHT_TIERS,
)
from backend.services.vector_search_service import (
    MIN_SEARCH_RELEVANCE,
    _candidate_text,
    location_filter_patterns,
)
from backend.utils.auth import require_admin
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/transparency",
    tags=["transparency"],
    dependencies=[Depends(require_admin)],
)

# The threshold the Matching screen and the assistant use when they ask for a
# ranking. Published so the trace can show who fell below it and by how much.
DEFAULT_MATCH_THRESHOLD = 20.0


# --- response models --------------------------------------------------------


class WeightTier(BaseModel):
    name: str
    label: str
    condition: str
    weights: Dict[str, float]
    multiplier: float


class FinalPenalty(BaseModel):
    condition: str
    multiplier: float


class ScoredField(BaseModel):
    field: str
    used_for: str


class UnscoredField(BaseModel):
    field: str
    reason: str


class ScoringPolicy(BaseModel):
    candidate_fields_scored: List[ScoredField]
    job_fields_scored: List[ScoredField]
    candidate_fields_never_scored: List[UnscoredField]
    fields_not_collected: List[str]
    weight_tiers: List[WeightTier]
    final_penalty: FinalPenalty
    cross_domain_skill_penalty_factor: float
    role_score_caps: Dict[str, float]
    default_match_threshold: float
    search_relevance_floor: float
    search_relevance_bands: Dict[str, float]
    search_embedded_fields: List[str]


class SkillStep(BaseModel):
    job_skills: List[str]
    candidate_skills: List[str]
    exact: List[str]
    partial: List[str]
    missing: List[str]
    coverage_bonus: bool
    no_data: bool
    raw_score: float
    penalty_applied: bool
    penalty_factor: float
    job_category: Optional[str] = None
    candidate_category: Optional[str] = None
    score: float


class RoleStep(BaseModel):
    job_title: str
    candidate_position: str
    semantic_similarity: Optional[float] = None
    base_score: float
    job_category: Optional[str] = None
    candidate_category: Optional[str] = None
    relationship: str
    score: float


class ExperienceStep(BaseModel):
    job_level: str
    job_years: int
    candidate_level: str
    candidate_years: int
    level_diff: int
    level_match: float
    years_diff: int
    years_match: float
    adjustment: float
    score: float


class PairTrace(BaseModel):
    rank: int
    candidate_id: str
    candidate_name: str
    above_threshold: bool
    match_score: float
    weighted_score: float
    skills: SkillStep
    role: RoleStep
    experience: ExperienceStep
    tier: WeightTier
    final_penalty_applied: bool
    final_penalty_multiplier: float
    explanation: str


class JobRef(BaseModel):
    id: int
    title: str
    department: Optional[str] = None
    skills: List[str]
    level: str
    years: int


class MatchTraceResponse(BaseModel):
    job: JobRef
    threshold: float
    candidates_scored: int
    candidates_above_threshold: int
    # True when the embedding endpoint was unreachable and title similarity
    # came from deterministic placeholder vectors. The ranking still runs
    # (the category rules and skills carry it), but the similarity numbers
    # are not semantic and the page says so.
    embedding_degraded: bool
    traces: List[PairTrace]


class SearchHit(BaseModel):
    id: str
    name: str
    position: Optional[str] = None
    company: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    similarity: float
    relevance: str
    embedded_text: Optional[str] = None


class SearchTraceResponse(BaseModel):
    query: str
    location_filter: Optional[str] = None
    location_patterns: List[str]
    location_ignored: bool
    relevance_floor: float
    relevance_bands: Dict[str, float]
    embedded_fields: List[str]
    embedding_degraded: bool
    hits: List[SearchHit]
    dropped_by_floor: List[SearchHit]


# --- endpoints --------------------------------------------------------------


@router.get("/policy", response_model=ScoringPolicy)
def scoring_policy() -> ScoringPolicy:
    """The scoring rules, read from the constants the ranker applies."""
    return ScoringPolicy(
        candidate_fields_scored=[ScoredField(**f) for f in SCORED_CANDIDATE_FIELDS],
        job_fields_scored=[ScoredField(**f) for f in SCORED_JOB_FIELDS],
        candidate_fields_never_scored=[UnscoredField(**f) for f in UNSCORED_CANDIDATE_FIELDS],
        fields_not_collected=list(NOT_COLLECTED_FIELDS),
        weight_tiers=[_tier_model(t) for t in WEIGHT_TIERS],
        final_penalty=FinalPenalty(
            condition=CROSS_DOMAIN_FINAL_PENALTY["condition"],
            multiplier=CROSS_DOMAIN_FINAL_PENALTY["multiplier"],
        ),
        # These three live inline in matching_enhancer; they are restated here
        # and pinned by test_transparency so a change there fails a test here.
        cross_domain_skill_penalty_factor=0.3,
        role_score_caps={"highly_incompatible": 12.0, "moderately_incompatible": 20.0},
        default_match_threshold=DEFAULT_MATCH_THRESHOLD,
        search_relevance_floor=MIN_SEARCH_RELEVANCE,
        search_relevance_bands=dict(RELEVANCE_BANDS),
        search_embedded_fields=["current_position", "current_company", "headline", "skills"],
    )


@router.get("/match-trace", response_model=MatchTraceResponse)
def match_trace(
    job_id: int,
    candidate_id: Optional[str] = None,
    limit: int = Query(30, ge=1, le=500),
    threshold: float = Query(DEFAULT_MATCH_THRESHOLD, ge=0, le=100),
    db: Session = Depends(get_db),
) -> MatchTraceResponse:
    """Every candidate scored against one job, with each step of the score.

    Unlike the ranking endpoints this does not stop at the threshold: the
    people who fell below it are the more interesting half of an audit.
    With `candidate_id`, only that person's trace is returned, still ranked
    against everyone else.
    """
    from backend.services.service_registry import get_registry

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

    integrator = get_registry().matching_integrator
    candidates = db.query(Candidate).all()

    scored = []
    for candidate in candidates:
        trace = integrator.score_pair(job, candidate)
        scored.append((candidate, trace))
    scored.sort(key=lambda item: item[1]["match_score"], reverse=True)

    traces: List[PairTrace] = []
    for rank, (candidate, trace) in enumerate(scored, start=1):
        if candidate_id and candidate.id != candidate_id:
            continue
        traces.append(_pair_trace(rank, candidate, job, trace, threshold))
        if len(traces) >= limit:
            break

    if candidate_id and not traces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate {candidate_id} not found"
        )

    job_level, job_years = integrator.enhancer.extract_experience_level(
        f"{job.title or ''} {job.required_qualifications or ''}"
    )
    return MatchTraceResponse(
        job=JobRef(
            id=job.id,
            title=job.title or "",
            department=job.department,
            skills=scored[0][1]["job_skills"] if scored else [],
            level=job_level,
            years=job_years,
        ),
        threshold=threshold,
        candidates_scored=len(scored),
        candidates_above_threshold=sum(1 for _, t in scored if t["match_score"] >= threshold),
        embedding_degraded=_degraded(integrator.enhancer.embedding_model),
        traces=traces,
    )


@router.get("/search-trace", response_model=SearchTraceResponse)
def search_trace(
    q: str = Query(..., min_length=1),
    location: Optional[str] = None,
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SearchTraceResponse:
    """The assistant's candidate search, with what the embedding saw and what
    the relevance floor removed.

    Runs the same query twice: once as the assistant runs it (with the floor)
    and once without, so the second list is exactly the set of "closest
    available people" the floor keeps the model from presenting as matches.
    """
    from backend.services.service_registry import get_registry
    from backend.services.vector_search_service import VectorSearchService

    registry = get_registry()
    patterns = location_filter_patterns(location) if location else []
    effective_location = location if patterns else None

    try:
        embedding_model = registry.llm_service.get_embedding_model()
        service = VectorSearchService(embedding_model)
        floored = service.search_candidates_by_text(
            db, q, limit=limit, location=effective_location, min_similarity=MIN_SEARCH_RELEVANCE
        )
        unfloored = service.search_candidates_by_text(
            db, q, limit=limit, location=effective_location
        )
    except Exception as exc:  # noqa: BLE001 - the tunnel being down is a 503, not a 500
        logger.warning("search-trace: embedding unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The embedding model is not reachable, so the search cannot be traced right now.",
        )

    shown = {hit["id"] for hit in floored}
    dropped = [hit for hit in unfloored if hit["id"] not in shown]

    texts = _embedded_texts(db, [hit["id"] for hit in floored + dropped])
    return SearchTraceResponse(
        query=q,
        location_filter=location,
        location_patterns=patterns,
        location_ignored=bool(location) and not patterns,
        relevance_floor=MIN_SEARCH_RELEVANCE,
        relevance_bands=dict(RELEVANCE_BANDS),
        embedded_fields=["current_position", "current_company", "headline", "skills"],
        embedding_degraded=_degraded(embedding_model),
        hits=[_search_hit(hit, texts) for hit in floored],
        dropped_by_floor=[_search_hit(hit, texts) for hit in dropped],
    )


# --- helpers ----------------------------------------------------------------


def _degraded(embedding_model) -> bool:
    return bool(getattr(embedding_model, "is_degraded", False))


def _tier_model(tier: Dict[str, Any]) -> WeightTier:
    return WeightTier(
        name=tier["name"],
        label=tier["label"],
        condition=tier["condition"],
        weights=dict(tier["weights"]),
        multiplier=tier["multiplier"],
    )


def _pair_trace(rank: int, candidate, job, trace: Dict[str, Any], threshold: float) -> PairTrace:
    skills = trace["skills"]
    penalty = trace["cross_domain_skill_penalty"]
    role = trace["role"]
    experience = trace["experience"]
    return PairTrace(
        rank=rank,
        candidate_id=candidate.id,
        candidate_name=f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or "Unknown",
        above_threshold=trace["match_score"] >= threshold,
        match_score=trace["match_score"],
        weighted_score=trace["weighted_score"],
        skills=SkillStep(
            job_skills=trace["job_skills"],
            candidate_skills=trace["candidate_skills"],
            exact=skills["exact"],
            partial=skills["partial"],
            missing=skills["missing"],
            coverage_bonus=skills["coverage_bonus"],
            no_data=skills["no_data"],
            raw_score=skills["score"],
            penalty_applied=penalty["applied"],
            penalty_factor=penalty["factor"],
            job_category=penalty["job_category"],
            candidate_category=penalty["candidate_category"],
            score=trace["skill_match_score"],
        ),
        role=RoleStep(
            job_title=job.title or "",
            candidate_position=trace["candidate_position"],
            semantic_similarity=role["semantic_similarity"],
            base_score=role["base_score"],
            job_category=role["job_category"],
            candidate_category=role["candidate_category"],
            relationship=role["relationship"],
            score=trace["role_match_score"],
        ),
        experience=ExperienceStep(
            job_level=experience["job_level"],
            job_years=experience["job_years"],
            candidate_level=experience["candidate_level"],
            candidate_years=experience["candidate_years"],
            level_diff=experience["level_diff"],
            level_match=experience["level_match"],
            years_diff=experience["years_diff"],
            years_match=experience["years_match"],
            adjustment=experience["adjustment"],
            score=trace["experience_match_score"],
        ),
        tier=_tier_model(trace["tier"]),
        final_penalty_applied=trace["final_penalty_applied"],
        final_penalty_multiplier=trace["final_penalty_multiplier"],
        explanation=trace["match_explanation"],
    )


def _embedded_texts(db: Session, ids: List[str]) -> Dict[str, str]:
    if not ids:
        return {}
    rows = db.query(Candidate).filter(Candidate.id.in_(ids)).all()
    return {row.id: _candidate_text(row) for row in rows}


def _search_hit(hit: Dict[str, Any], texts: Dict[str, str]) -> SearchHit:
    return SearchHit(
        id=hit["id"],
        name=hit["name"],
        position=hit.get("position"),
        company=hit.get("company"),
        headline=hit.get("headline"),
        location=hit.get("location"),
        similarity=hit["similarity"],
        relevance=relevance_band(hit["similarity"]),
        embedded_text=texts.get(hit["id"]),
    )
