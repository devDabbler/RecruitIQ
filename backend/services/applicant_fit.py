"""A job's applicants scored against that job (Track 2 Phase 2).

The pipeline board, the job-filtered candidate list and the bulk-upload
result all show the same number: `score_pair`, the one scoring function the
matching page and the transparency trace use, so requirement caps show here
too. Only applicants are scored, never the whole pool.

Computed live, not stored. Measured on dev: 50 applicants take 0.06s once
the title embeddings are cached, and 7.6s when they are not, because each
distinct title was one tunnel round trip. `prime_titles` makes the cold case
one batched call, so there is no stored score to go stale when a job's
requirements or a candidate's profile change.

The score visibility rule applies: an interviewer sees no score (and no cap
detail) for a candidate until they have submitted feedback on them.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session, selectinload

from backend.models.models import Candidate, Job, User
from backend.models.pipeline import ApplicantFit
from backend.services.access_service import score_visible_ids
from backend.services.job_requirements import load_profiles, parse_requirements

HIDDEN = ApplicantFit(hidden=True)


def _integrator():
    from backend.services.service_registry import get_registry

    return get_registry().matching_integrator


def score_applicants(
    db: Session, job: Job, candidate_ids: Iterable[str], user: Optional[User]
) -> Dict[str, ApplicantFit]:
    """Fit for each candidate id, keyed by id. Unknown ids are left out."""
    ids = sorted({str(cid) for cid in candidate_ids if cid})
    if not ids:
        return {}
    visible = score_visible_ids(db, user, ids)
    to_score = ids if visible is None else [cid for cid in ids if cid in visible]
    fits: Dict[str, ApplicantFit] = {cid: HIDDEN for cid in ids if cid not in set(to_score)}
    if not to_score:
        return fits

    candidates = (
        db.query(Candidate)
        .options(selectinload(Candidate.skills))
        .filter(Candidate.id.in_(to_score))
        .all()
    )
    requirements = parse_requirements(job.requirements)
    profiles = (
        load_profiles(db, [c.id for c in candidates])
        if requirements is not None and requirements.needs_profile()
        else {}
    )
    integrator = _integrator()
    integrator.enhancer.prime_titles([job.title or ""] + [c.current_position or "" for c in candidates])
    for candidate in candidates:
        trace = integrator.score_pair(job, candidate, profiles.get(candidate.id))
        cap = trace["requirement_cap"]
        fits[candidate.id] = ApplicantFit(
            score=round(float(trace["match_score"]), 1),
            capped=bool(cap["applied"]),
            missing=list(cap["missing"]),
        )
    return fits


def order_key(fit: Optional[ApplicantFit], descending: bool = True) -> tuple:
    """Sort key for a list ordered by fit (best first when `descending`).

    Hidden and unscored go last either way, so an interviewer's list order
    never hints at a score they cannot see.
    """
    if fit is None or fit.score is None:
        return (1, 0.0)
    return (0, -fit.score if descending else fit.score)
