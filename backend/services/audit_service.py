"""Audit log: who viewed, created, changed, exported or deleted candidate data.

Pilot plan Track 1 #3. `audit_request` is installed app-wide (first, before
the write gate and the interviewer scope) so a denied attempt is recorded
too, and so a route added later cannot opt out by forgetting a call.

What gets recorded:
- Only requests by signed-in staff accounts. The demo role and anonymous
  callers see only the synthetic public dataset (internal mode refuses them
  outright), and recording them would bury real access under page views.
- Only routes that `AUDITED_ROUTES` classifies. Every route in the app must
  match exactly one rule here or one in `NOT_AUDITED`; a test fails on an
  unclassified route, the way the erasure test fails on an unlisted table.

What a row holds: actor id and role, an action, the subject type and id, the
candidate it leads back to when one can be resolved, the route template
("PUT /api/candidates/{candidate_id}", never the raw URL, whose query string
can carry a searched name), the field names a change touched, and the
status code. Never values, never row copies: Slate's audit trigger stored
full rows and turned its audit table into a second copy of every resume.

Handlers that learn something the path does not say (the id of a candidate
they just created, the fields an update set) call `note`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.models.models import (
    ApplicationStage,
    AuditEvent,
    CandidatePitch,
    Interview,
    JobApplication,
    Resume,
)
from backend.utils.auth import STAFF_ROLES, request_identity
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

ACTIONS = ("view", "create", "update", "delete", "export", "process")

_ACTION_BY_METHOD = {
    "GET": "view",
    "HEAD": "view",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# Path parameters worth keeping as `detail`: a closed vocabulary chosen by
# the route (advance, reject, ...), never free text.
_DETAIL_PARAMS = ("action",)


@dataclass(frozen=True)
class AuditRule:
    pattern: re.Pattern[str]  # fullmatch against "METHOD /route/{template}"
    subject_type: str
    id_param: Optional[str] = None  # path parameter naming the subject
    action: Optional[str] = None  # None: derived from the HTTP method


def _rule(pattern: str, subject_type: str, id_param: Optional[str] = None, action: Optional[str] = None) -> AuditRule:
    return AuditRule(re.compile(pattern), subject_type, id_param, action)


AUDITED_ROUTES: list[AuditRule] = [
    # Candidates and everything filed under one.
    _rule(r"(GET|POST) /api/candidates/", "candidate"),
    _rule(r"GET /api/candidates/export\.csv", "candidate", action="export"),
    _rule(r"[A-Z]+ /api/candidates/\{candidate_id\}(/.+)?", "candidate", "candidate_id"),
    _rule(r"GET /api/jobs/(applications|saved)/\{candidate_id\}", "candidate", "candidate_id"),
    _rule(r"GET /api/tasks/candidate/\{candidate_id\}", "candidate", "candidate_id"),
    # Applications: stage moves, email, status links, the candidate view.
    _rule(r"POST /api/applications/\{application_id\}/\{action\}", "application", "application_id", "update"),
    _rule(r"[A-Z]+ /api/applications/\{application_id\}(/.+)?", "application", "application_id"),
    _rule(r"POST /api/applications/bulk/\{action\}", "application", action="update"),
    _rule(r"POST /api/jobs/\{job_id\}/apply", "application"),
    _rule(r"POST /api/jobs/\{job_id\}/save", "saved_job"),
    # Interviews and feedback.
    _rule(r"GET /api/interviews", "interview"),
    _rule(r"[A-Z]+ /api/interviews/\{interview_id\}(/feedback)?", "interview", "interview_id"),
    # Resumes: reading a stored one, parsing an upload, saving a parse.
    _rule(r"(GET|HEAD) /api/resume/\{resume_id\}(/preview|/view)?", "resume", "resume_id"),
    _rule(r"POST /api/resume/(parse|parse-direct)", "resume", action="process"),
    _rule(r"POST /api/resume/(save-candidate|confirm)", "resume", action="create"),
    # A job's candidates, scored or not.
    _rule(r"GET /api/jobs/\{job_id\}/(candidates|matching-candidates|pipeline)", "job", "job_id"),
    # Matching, search and the scoring traces behind them.
    _rule(r"POST /api/search/(match_candidates|match_jobs|match_report)", "match", action="view"),
    _rule(r"POST /api/enhanced-matching/(match-candidates|match-jobs)", "match", action="view"),
    _rule(r"GET /api/transparency/(match-trace|search-trace)", "match"),
    # The assistant and agents answer questions about candidates.
    _rule(r"POST /api/assistant/(chat|chat/stream|agent-task)", "assistant", action="view"),
    _rule(r"GET /api/assistant/task-status/\{task_id\}", "assistant", "task_id"),
    _rule(r"POST /api/agent/invoke", "assistant", action="view"),
    _rule(r"GET /api/agent/sessions/\{session_id\}/memories", "assistant", "session_id"),
    # Saved candidate pitches.
    _rule(r"POST /api/pitches/save", "pitch"),
    _rule(r"(GET|DELETE) /api/pitches/\{pitch_id\}", "pitch", "pitch_id"),
    _rule(r"GET /api/pitches/user/\{user_id\}", "pitch", "user_id"),
    # Staff accounts: who invited whom, who changed a role.
    _rule(r"POST /api/team/users", "user"),
    _rule(r"(PUT|DELETE) /api/team/users/\{user_id\}(/role)?", "user", "user_id"),
    # Reading the audit log is itself recorded.
    _rule(r"GET /api/audit-events", "audit"),
]

# Routes that never return or change anything about a candidate, with why.
NOT_AUDITED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), reason)
    for pattern, reason in [
        (r"GET (/|/health|/startup-performance|/api/resume/test)", "service status"),
        (r"[A-Z]+ /auth/.+", "sign-in and the caller's own account"),
        (r"[A-Z]+ /api/(cache|performance)/.+", "operations"),
        (r"[A-Z]+ /api/(crawler|intelligence)/.+", "public company and market data"),
        (r"(GET|POST) /api/jobs/?", "job postings"),
        (r"(GET|PUT|DELETE) /api/jobs/\{job_id\}", "job postings"),
        (r"POST /api/jobs/sync-to-neo4j", "job postings"),
        (r"POST /api/jobs/\{job_id\}/track-view", "job postings"),
        (r"PUT /api/jobs/\{job_id\}/pipeline", "a job's stage configuration"),
        (r"GET /api/jobs/\{job_id\}/default-interviewers", "a job's stage configuration"),
        (r"PUT /api/jobs/\{job_id\}/stages/\{stage_key\}/default-interviewers", "a job's stage configuration"),
        (r"POST /api/job-drafts/description", "job description drafting"),
        (r"[A-Z]+ /api/email-templates(/\{key\})?", "email templates"),
        (r"GET /api/tags", "tag counts"),
        (r"GET /api/candidates/skills_breakdown", "skill counts"),
        (r"GET /api/reports/.+", "aggregate counts"),
        (r"[A-Z]+ /api/tasks/(\{task_id\}(/complete)?|job/\{job_id\})?", "recruiter to-dos"),
        (r"POST /api/enhanced-matching/similar-jobs", "job to job matching"),
        (r"GET /api/transparency/(policy|upload-policy)", "published policy text"),
        (r"GET /api/public/status/\{token\}", "the candidate's own status page, no staff account"),
        (r"(GET|PUT) /api/team/me(/password)?", "the caller's own profile"),
        (r"GET /api/team/users", "staff directory"),
    ]
]


def endpoint_key(method: str, template: str) -> str:
    return f"{method} {template}"


def rule_for(method: str, template: str) -> Optional[AuditRule]:
    key = endpoint_key(method, template)
    for rule in AUDITED_ROUTES:
        if rule.pattern.fullmatch(key):
            return rule
    return None


def note(
    request: Request,
    *,
    candidate_ids: Optional[Iterable[str]] = None,
    subject_ids: Optional[Iterable[object]] = None,
    fields: Optional[Iterable[str]] = None,
) -> None:
    """Tell the audit log what the path does not say. Safe to call on any route.

    `candidate_ids`: candidates this request created or acted on.
    `subject_ids`: for bulk routes, one event is written per subject id.
    `fields`: names (never values) of the fields a change touched.
    """
    pending = getattr(request.state, "audit_note", None)
    if pending is None:
        pending = {"candidate_ids": [], "subject_ids": [], "fields": []}
        request.state.audit_note = pending
    if candidate_ids:
        pending["candidate_ids"].extend(str(c) for c in candidate_ids if c)
    if subject_ids:
        pending["subject_ids"].extend(str(s) for s in subject_ids)
    if fields:
        pending["fields"].extend(f for f in fields if f not in pending["fields"])


def candidate_for(db: Session, subject_type: str, subject_id: Optional[str]) -> Optional[str]:
    """The candidate a subject leads back to, or None."""
    if not subject_id:
        return None
    if subject_type == "candidate":
        return subject_id
    if subject_type == "pitch":
        pitch = db.get(CandidatePitch, subject_id)
        return pitch.candidate_id if pitch else None
    if not subject_id.isdigit():
        return None
    key = int(subject_id)
    if subject_type == "application":
        application = db.get(JobApplication, key)
        return application.candidate_id if application else None
    if subject_type == "resume":
        resume = db.get(Resume, key)
        return resume.candidate_id if resume else None
    if subject_type == "interview":
        row = (
            db.query(JobApplication.candidate_id)
            .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
            .join(Interview, Interview.application_stage_id == ApplicationStage.id)
            .filter(Interview.id == key)
            .first()
        )
        return row[0] if row else None
    return None


def _outcome_status(request: Request, error: Optional[BaseException]) -> int:
    if error is None:
        route = request.scope.get("route")
        return getattr(route, "status_code", None) or 200
    if isinstance(error, HTTPException):
        return error.status_code
    if isinstance(error, RequestValidationError):
        return 422
    return 500


def _write(
    db: Session,
    request: Request,
    *,
    actor_id: str,
    actor_role: str,
    rule: AuditRule,
    endpoint: str,
    path_subject_id: Optional[str],
    path_candidate_id: Optional[str],
    status_code: int,
) -> None:
    pending = getattr(request.state, "audit_note", None) or {}
    action = rule.action or _ACTION_BY_METHOD.get(request.method, "view")
    detail = next(
        (str(request.path_params[p])[:64] for p in _DETAIL_PARAMS if p in request.path_params), None
    )
    fields = sorted(pending.get("fields") or []) or None

    # (subject_id, candidate_id) pairs: one event each.
    pairs: list[tuple[Optional[str], Optional[str]]]
    if pending.get("subject_ids"):
        pairs = [(sid, candidate_for(db, rule.subject_type, sid)) for sid in pending["subject_ids"]]
    elif pending.get("candidate_ids"):
        pairs = [(path_subject_id or (cid if rule.subject_type == "candidate" else None), cid)
                 for cid in dict.fromkeys(pending["candidate_ids"])]
    else:
        candidate_id = path_candidate_id or _query_candidate(request)
        pairs = [(path_subject_id, candidate_id)]

    for subject_id, candidate_id in pairs:
        db.add(
            AuditEvent(
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                subject_type=rule.subject_type,
                subject_id=subject_id[:64] if subject_id else None,
                candidate_id=candidate_id,
                endpoint=endpoint[:200],
                detail=detail,
                fields=fields,
                status_code=status_code,
            )
        )
    _commit_keeping_loaded_state(db)


# Whether a failed request left flushed work it never committed. That work
# must not ride along with the audit row's commit, but a blanket rollback
# would also discard work the request never touched (the test suite flushes
# fixtures into one shared session). Two counters on the session: flushes so
# far, and the flush count at the last commit or rollback.
_FLUSHES = "audit_flushes"
_SETTLED = "audit_settled_at"


@event.listens_for(Session, "after_flush")
def _count_flush(session, _context) -> None:
    session.info[_FLUSHES] = session.info.get(_FLUSHES, 0) + 1


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _settle(session) -> None:
    session.info[_SETTLED] = session.info.get(_FLUSHES, 0)


def _discard_failed_work(db: Session, flushes_at_start: int) -> None:
    flushes = db.info.get(_FLUSHES, 0)
    flushed_by_request = flushes > max(flushes_at_start, db.info.get(_SETTLED, 0))
    if not db.is_active or db.new or db.dirty or db.deleted or flushed_by_request:
        db.rollback()


def _commit_keeping_loaded_state(db: Session) -> None:
    """Commit without expiring what the handler loaded.

    The response may still be streaming from ORM objects after this runs;
    an expired instance on a session about to close would raise instead of
    answering from what it already holds.
    """
    previous = db.expire_on_commit
    db.expire_on_commit = False
    try:
        db.commit()
    finally:
        db.expire_on_commit = previous


_UUID = re.compile(r"[0-9a-fA-F-]{36}")


def _query_candidate(request: Request) -> Optional[str]:
    """A candidate named in the query string (the transparency traces take one)."""
    value = request.query_params.get("candidate_id")
    return value if value and _UUID.fullmatch(value) else None


def audit_request(request: Request, db: Session = Depends(get_db)):
    """App-wide dependency: record this request if a staff account made it
    against an audited route. Never fails the request it is recording.

    The subject's candidate is resolved before the handler runs, because a
    delete removes the row that would answer that question afterwards.
    """
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    rule = rule_for(request.method, template) if template else None
    if rule is None:
        yield
        return
    role, user = request_identity(request, db)
    if user is None or role not in STAFF_ROLES:
        yield
        return
    # Read now: a rollback below expires the instance, and the request may
    # be deleting this very account.
    actor_id, actor_role = user.id, role

    path_subject_id = (
        str(request.path_params[rule.id_param])
        if rule.id_param and rule.id_param in request.path_params
        else None
    )
    try:
        path_candidate_id = candidate_for(db, rule.subject_type, path_subject_id)
    except Exception:
        logger.warning("Audit: could not resolve the candidate for %s", template, exc_info=True)
        db.rollback()
        path_candidate_id = None
    endpoint = endpoint_key(request.method, template)
    flushes_at_start = db.info.get(_FLUSHES, 0)

    error: Optional[BaseException] = None
    try:
        yield
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            if error is not None:
                _discard_failed_work(db, flushes_at_start)
            _write(
                db,
                request,
                actor_id=actor_id,
                actor_role=actor_role,
                rule=rule,
                endpoint=endpoint,
                path_subject_id=path_subject_id,
                path_candidate_id=path_candidate_id,
                status_code=_outcome_status(request, error),
            )
        except Exception:
            logger.error("Audit: failed to record %s by %s", endpoint, actor_id, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
