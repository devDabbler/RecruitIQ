"""What a signed-in person may see (ATS Phase B, spec 2026-10-03 section 8).

Two rules from the spec:

- An interviewer sees only the candidates they interview
  (`visible_candidate_ids`). Every other role sees everyone.
- An interviewer does not see a candidate's AI score, or colleagues'
  feedback on them, until they have submitted their own feedback on that
  candidate (`can_see_score`).

`enforce_interviewer_scope` (added below the rules) is installed app-wide
next to the write gate. Later phases that list or export candidates must
filter through `visible_candidate_ids` and must not expose a score where
`can_see_score` is False.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.models.models import ApplicationStage, Feedback, Interview, JobApplication, Resume, User
from backend.utils.auth import ROLE_INTERVIEWER, request_identity
from backend.utils.database import get_db
from backend.utils.permissions import SCORE_BEFORE_FEEDBACK, can

SCORE_HIDDEN_DETAIL = "Submit your feedback on this candidate to see their match scores."


def visible_candidate_ids(db: Session, user: Optional[User]) -> Optional[set[str]]:
    """None means no restriction. An interviewer gets the candidates they interview."""
    if user is None or user.role != ROLE_INTERVIEWER:
        return None
    rows = (
        db.query(JobApplication.candidate_id)
        .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
        .join(Interview, Interview.application_stage_id == ApplicationStage.id)
        .filter(Interview.interviewer_id == user.id)
        .distinct()
        .all()
    )
    return {candidate_id for (candidate_id,) in rows}


def can_see_score(db: Session, user: Optional[User], candidate_id: str) -> bool:
    """False only for a role without `score.before_feedback` that has not yet
    submitted feedback on any of this candidate's interviews."""
    if user is None or can(user.role, SCORE_BEFORE_FEEDBACK):
        return True
    submitted = (
        db.query(Feedback.id)
        .join(Interview, Feedback.interview_id == Interview.id)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .join(JobApplication, ApplicationStage.application_id == JobApplication.id)
        .filter(Interview.interviewer_id == user.id, JobApplication.candidate_id == candidate_id)
        .first()
    )
    return submitted is not None


def score_visible_ids(db: Session, user: Optional[User], candidate_ids) -> Optional[set[str]]:
    """`can_see_score` for many candidates in one query. None means all of them."""
    if user is None or can(user.role, SCORE_BEFORE_FEEDBACK):
        return None
    ids = sorted({str(cid) for cid in candidate_ids})
    if not ids:
        return set()
    rows = (
        db.query(JobApplication.candidate_id)
        .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
        .join(Interview, Interview.application_stage_id == ApplicationStage.id)
        .join(Feedback, Feedback.interview_id == Interview.id)
        .filter(Interview.interviewer_id == user.id, JobApplication.candidate_id.in_(ids))
        .distinct()
        .all()
    )
    return {candidate_id for (candidate_id,) in rows}


def request_user(request: Request) -> Optional[User]:
    """The staff User behind this request, as resolved by the app-wide gates.

    None for anonymous callers and for the demo role (which has no per-user
    restrictions). Handlers use this instead of a second token lookup.
    """
    identity = getattr(request.state, "identity", None)
    return identity[1] if identity else None


INTERVIEWER_SCOPE_DETAIL = (
    "Interviewers can open their own interviews and the candidates they interview."
)

# For the interviewer role, the only reachable paths. `kind` says what the
# `id` group names, so the gate can check it against visible_candidate_ids;
# None means the path is safe as is (or its handler filters). Matched with
# `fullmatch` after the trailing slash is stripped. Writes are still gated by
# enforce_read_only, which runs first.
INTERVIEWER_PATHS: list[tuple[re.Pattern[str], Optional[str]]] = [
    (re.compile(pattern), kind)
    for pattern, kind in [
        (r"/", None),
        (r"/health", None),
        (r"/auth/(me|login|demo)", None),
        (r"/api/team/me(/password)?", None),
        (r"/api/interviews", None),  # the handler limits interviewers to scope=mine
        (r"/api/interviews/\d+/feedback", None),  # the handler checks the assignee
        (r"/api/jobs", None),
        (r"/api/jobs/\d+", None),
        (r"/api/jobs/\d+/pipeline", None),  # the handler filters the cards
        (r"/api/candidates", None),  # the handler filters the list
        (r"/api/candidates/export\.csv", None),  # the handler filters by visible_candidate_ids
        (r"/api/candidates/(?P<id>[^/]+)(/resumes|/notes|/tags)?", "candidate"),
        (r"/api/tags", None),  # the handler counts only visible candidates
        (r"/api/reports/dashboard", None),  # the handler narrows to visible_candidate_ids
        (r"/api/jobs/(applications|saved)/(?P<id>[^/]+)", "candidate"),
        (r"/api/applications/(?P<id>\d+)(/interviews)?", "application"),
        (r"/api/resume/(?P<id>\d+)(/preview|/view)?", "resume"),
        (r"/api/enhanced-matching/match-jobs", None),  # the handler checks can_see_score
        (r"/api/transparency/(policy|upload-policy)", None),
    ]
]


def _candidate_for(db: Session, kind: str, raw_id: str) -> Optional[str]:
    if kind == "candidate":
        return raw_id
    if not raw_id.isdigit():
        return None
    if kind == "application":
        application = db.get(JobApplication, int(raw_id))
        return application.candidate_id if application else None
    if kind == "resume":
        resume = db.get(Resume, int(raw_id))
        return resume.candidate_id if resume else None
    return None


def enforce_interviewer_scope(request: Request, db: Session = Depends(get_db)) -> None:
    """Installed app-wide after enforce_read_only. A no-op for every role but
    interviewer; for interviewers, default-deny outside INTERVIEWER_PATHS.

    A path naming someone the interviewer does not interview answers 404,
    not 403, so the response does not confirm the id exists.
    """
    role, user = request_identity(request, db)
    if role != ROLE_INTERVIEWER:
        return
    path = request.url.path.rstrip("/") or "/"
    for pattern, kind in INTERVIEWER_PATHS:
        match = pattern.fullmatch(path)
        if match is None:
            continue
        if kind is None:
            return
        candidate_id = _candidate_for(db, kind, match.group("id"))
        if candidate_id is not None and candidate_id in (visible_candidate_ids(db, user) or set()):
            return
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=INTERVIEWER_SCOPE_DETAIL)
