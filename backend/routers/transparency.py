"""Scoring transparency, open to every signed-in user, demo included.

Three read endpoints that expose how the ranking and the semantic search
actually work, built from the same constants and the same `score_pair` the
ranking runs. The point is that nothing here is a description that could
drift from the code: the policy endpoint reads the weight tables the ranker
applies, and the trace endpoint returns the ranker's own intermediates.

Started admin-only, opened to the demo role deliberately (2026-09-28): the
demo dataset is fully synthetic (spec §6), and every candidate field a trace
shows (name, title, skills) is already on the demo-visible candidate and
matching screens. The traces deliberately carry *no* email, phone, or notes,
so they expose strictly less about a person than /api/enhanced-matching
already hands the demo role. Transparency that hides behind a login would
undercut its own point.

Still behind `get_current_user` rather than fully anonymous: every visitor
via the site holds a demo token automatically, and requiring one keeps bare
unauthenticated scraping of the trace endpoints off the table, consistent
with the rest of the app's "the UI is courtesy, the API is the gate" stance.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job
from backend.services.search_relevance import EVIDENCE_FIELDS, RELEVANCE_BANDS, SEARCH_POOL_SIZE, rank_hits
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
from backend.services.feedback_service import FEEDBACK_NEVER_USED_FOR, FEEDBACK_USED_FOR
from backend.utils.auth import get_current_user
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/transparency",
    tags=["transparency"],
    dependencies=[Depends(get_current_user)],
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


class FeedbackPolicy(BaseModel):
    used_for: List[str]
    never_used_for: List[str]


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
    feedback_policy: FeedbackPolicy


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
    matched_on: List[str] = []
    matched_in: Dict[str, List[str]] = {}
    match_kind: str = "semantic"
    embedded_text: Optional[str] = None


class SearchTraceResponse(BaseModel):
    query: str
    location_filter: Optional[str] = None
    location_patterns: List[str]
    location_ignored: bool
    relevance_floor: float
    relevance_bands: Dict[str, float]
    embedded_fields: List[str]
    evidence_fields: List[str]
    embedding_degraded: bool
    hits: List[SearchHit]
    kept_out: List[SearchHit]


class PostParseModelCall(BaseModel):
    name: str
    purpose: str
    reads: str


class UploadPrivacyPolicy(BaseModel):
    """What happens to a resume between the upload and the screen.

    Every list here is read from the constants the upload pipeline applies
    (`resume_privacy` and the resume agent), and `test_upload_privacy` drives
    the pipeline with a resume full of contact details to check that the
    claims hold: no name, email, phone or link reaches a post-parse prompt,
    and nothing is looked up on the web.
    """
    parser_reads: str
    parser_providers: List[str]
    identifying_fields_removed: List[str]
    dropped_keys: List[str]
    text_patterns_scrubbed: List[str]
    model_calls_after_parse: List[PostParseModelCall]
    web_lookups: int
    parse_writes_nothing: bool
    stored_only_when_saved: str
    # Hosted providers (outside the operator's own hardware) that the parse
    # and post-parse chains can actually reach on this deployment. Empty when
    # every chain resolves to Ollama, which is the private, self-hosted setup.
    hosted_providers: List[str]
    # Candidate fields the ranker reads once a parse is saved; the name and
    # contact details are never among them (UNSCORED_CANDIDATE_FIELDS).
    matching_reads: List[str]


def hosted_resume_providers(settings) -> List[str]:
    """Providers outside this server that can receive a resume prompt.

    Resolved through build_chain, so a provider listed in an order but missing
    its API key does not count: it is skipped at call time too. The parse uses
    the resume_parsing chain; the post-parse calls use the default chain.
    """
    from backend.services.llm.chain import build_chain

    names: List[str] = []
    for order in (getattr(settings, "llm_provider_order_resume_parsing", "") or None, None):
        for provider in build_chain(settings, order=order).providers:
            if provider.name != "ollama" and provider.name not in names:
                names.append(provider.name)
    return names


# --- endpoints --------------------------------------------------------------


@router.get("/upload-policy", response_model=UploadPrivacyPolicy)
def upload_privacy_policy() -> UploadPrivacyPolicy:
    """How an uploaded resume is de-identified before anything but the parser reads it."""
    from backend.services.agent_framework.agents.resume_processing_agent import POST_PARSE_MODEL_CALLS
    from backend.services.resume_privacy import DROPPED_KEYS, IDENTIFYING_FIELDS, TEXT_PATTERNS_SCRUBBED
    from backend.utils.config import get_settings

    settings = get_settings()
    order = settings.llm_provider_order_resume_parsing or ""
    return UploadPrivacyPolicy(
        parser_reads="the full resume text, once, to fill the contact, experience, education and skill fields",
        parser_providers=[p.strip() for p in order.split(",") if p.strip()],
        identifying_fields_removed=list(IDENTIFYING_FIELDS),
        dropped_keys=list(DROPPED_KEYS),
        text_patterns_scrubbed=list(TEXT_PATTERNS_SCRUBBED),
        model_calls_after_parse=[PostParseModelCall(**call) for call in POST_PARSE_MODEL_CALLS],
        web_lookups=0,
        parse_writes_nothing=True,
        stored_only_when_saved=(
            "the full profile, contact details included, and only when an administrator "
            "chooses Save as candidate; a recruiter has to be able to reach the person"
        ),
        hosted_providers=hosted_resume_providers(settings),
        matching_reads=[f["field"] for f in SCORED_CANDIDATE_FIELDS],
    )


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
        # ATS Phase B. test_feedback pins that no scoring module mentions feedback.
        feedback_policy=FeedbackPolicy(
            used_for=list(FEEDBACK_USED_FOR),
            never_used_for=list(FEEDBACK_NEVER_USED_FOR),
        ),
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
    """The assistant's candidate search, with what the embedding saw, what
    each hit matched on, and who was kept out.

    Runs the search the way the assistant runs it: a pool of the closest
    people by cosine similarity (without the floor, so the trace can show
    what the floor removes), banded and re-ranked by search_relevance.
    `hits` is what the assistant is given; `kept_out` is everyone else in
    the pool, each labelled with the band and the words they matched on,
    so a visitor can see why a plumber search returns nobody instead of
    the closest data engineer.
    """
    from backend.services.service_registry import get_registry
    from backend.services.vector_search_service import VectorSearchService

    registry = get_registry()
    patterns = location_filter_patterns(location) if location else []
    effective_location = location if patterns else None

    try:
        embedding_model = registry.llm_service.get_embedding_model()
        service = VectorSearchService(embedding_model)
        pool = service.search_candidates_by_text(db, q, limit=SEARCH_POOL_SIZE, location=effective_location)
    except Exception as exc:  # noqa: BLE001 - the tunnel being down is a 503, not a 500
        logger.warning("search-trace: embedding unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The embedding model is not reachable, so the search cannot be traced right now.",
        )

    hits, kept_out = rank_hits(pool, q, limit, MIN_SEARCH_RELEVANCE)
    kept_out = kept_out[:limit]

    texts = _embedded_texts(db, [hit["id"] for hit in hits + kept_out])
    return SearchTraceResponse(
        query=q,
        location_filter=location,
        location_patterns=patterns,
        location_ignored=bool(location) and not patterns,
        relevance_floor=MIN_SEARCH_RELEVANCE,
        relevance_bands=dict(RELEVANCE_BANDS),
        embedded_fields=["current_position", "current_company", "headline", "skills"],
        evidence_fields=list(EVIDENCE_FIELDS),
        embedding_degraded=_degraded(embedding_model),
        hits=[_search_hit(hit, texts) for hit in hits],
        kept_out=[_search_hit(hit, texts) for hit in kept_out],
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
        relevance=hit["relevance"],
        matched_on=list(hit.get("matched_on", [])),
        matched_in={k: list(v) for k, v in hit.get("matched_in", {}).items()},
        match_kind=hit.get("match_kind", "semantic"),
        embedded_text=texts.get(hit["id"]),
    )
