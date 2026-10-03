"""Who may do what (ATS Phase B, spec 2026-10-03 section 8, Phase B).

One table, read by three consumers:

- the app-wide write gate, `enforce_read_only`, through ROUTE_PERMISSIONS;
- routes that need the acting user and a finer check, through `require`;
- the web app, which hides controls a role cannot use. Its copy,
  web/src/lib/role-permissions.json, is generated from this module by
  scripts/export_permissions.py and a test fails if it drifts.

Two read permissions (`score.before_feedback`, `reports.view`) are granted to
the demo role on purpose: the public demo shows every screen. The demo role
holds no write permission, and the write gate refuses it every write anyway.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

from backend.models.models import User
from backend.utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    ROLE_HIRING_MANAGER,
    ROLE_HIRING_TEAM,
    ROLE_INTERVIEWER,
    get_current_user,
)

JOBS_WRITE = "jobs.write"
CANDIDATES_ADD = "candidates.add"
PIPELINE_MOVE = "pipeline.move"
FEEDBACK_SUBMIT = "feedback.submit"
USERS_INVITE = "users.invite"
USERS_CHANGE_ROLE = "users.change_role"
DELETE_RECORDS = "records.delete"
SCORE_BEFORE_FEEDBACK = "score.before_feedback"
REPORTS_VIEW = "reports.view"
TEMPLATES_MANAGE = "templates.manage"
PROFILE_EDIT = "profile.edit"

ALL_PERMISSIONS = (
    JOBS_WRITE,
    CANDIDATES_ADD,
    PIPELINE_MOVE,
    FEEDBACK_SUBMIT,
    USERS_INVITE,
    USERS_CHANGE_ROLE,
    DELETE_RECORDS,
    SCORE_BEFORE_FEEDBACK,
    REPORTS_VIEW,
    TEMPLATES_MANAGE,
    PROFILE_EDIT,
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: frozenset(ALL_PERMISSIONS),
    ROLE_HIRING_MANAGER: frozenset(
        {
            JOBS_WRITE,
            CANDIDATES_ADD,
            PIPELINE_MOVE,
            FEEDBACK_SUBMIT,
            USERS_INVITE,
            SCORE_BEFORE_FEEDBACK,
            REPORTS_VIEW,
            TEMPLATES_MANAGE,
            PROFILE_EDIT,
        }
    ),
    ROLE_HIRING_TEAM: frozenset(
        {
            CANDIDATES_ADD,
            PIPELINE_MOVE,
            FEEDBACK_SUBMIT,
            SCORE_BEFORE_FEEDBACK,
            REPORTS_VIEW,
            PROFILE_EDIT,
        }
    ),
    ROLE_INTERVIEWER: frozenset({FEEDBACK_SUBMIT, PROFILE_EDIT}),
    ROLE_DEMO: frozenset({SCORE_BEFORE_FEEDBACK, REPORTS_VIEW}),
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "Admin",
    ROLE_HIRING_MANAGER: "Hiring manager",
    ROLE_HIRING_TEAM: "Hiring team",
    ROLE_INTERVIEWER: "Interviewer",
    ROLE_DEMO: "Read-only demo",
}


def can(role: Optional[str], permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role or "", frozenset())


def role_label(role: Optional[str]) -> str:
    return ROLE_LABELS.get(role or "", role or "Signed out")


def require(permission: str) -> Callable[..., User]:
    """A dependency that returns the acting user, or 403 in plain English."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not can(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({role_label(user.role)}) cannot do this.",
            )
        return user

    return dependency


# (method, path pattern, permission). Paths are matched after the trailing
# slash is stripped, with `fullmatch`. A mutating route that matches nothing
# here stays admin-only: forgetting to list a new route denies it rather than
# exposing it. Later phases append their own rows in their own plans.
ROUTE_PERMISSIONS: list[tuple[str, re.Pattern[str], str]] = [
    (method, re.compile(pattern), permission)
    for method, pattern, permission in [
        ("POST", r"/api/jobs", JOBS_WRITE),
        ("PUT", r"/api/jobs/\d+", JOBS_WRITE),
        ("DELETE", r"/api/jobs/\d+", DELETE_RECORDS),
        ("PUT", r"/api/jobs/\d+/pipeline", JOBS_WRITE),
        ("PUT", r"/api/jobs/\d+/stages/[a-z0-9_]+/default-interviewers", JOBS_WRITE),
        ("POST", r"/api/jobs/\d+/apply", CANDIDATES_ADD),
        ("POST", r"/api/candidates", CANDIDATES_ADD),
        ("PUT", r"/api/candidates/[^/]+", CANDIDATES_ADD),
        ("DELETE", r"/api/candidates/[^/]+", DELETE_RECORDS),
        ("POST", r"/api/candidates/[^/]+/(upload-resume|parsed-resume)", CANDIDATES_ADD),
        ("POST", r"/api/resume/(save-candidate|confirm)", CANDIDATES_ADD),
        ("POST", r"/api/applications/\d+/(advance|skip|reject|decline)", PIPELINE_MOVE),
        ("POST", r"/api/applications/\d+/interviews", PIPELINE_MOVE),
        ("DELETE", r"/api/interviews/\d+", PIPELINE_MOVE),
        ("POST", r"/api/interviews/\d+/feedback", FEEDBACK_SUBMIT),
        ("POST", r"/api/team/users", USERS_INVITE),
        ("PUT", r"/api/team/users/[^/]+/role", USERS_CHANGE_ROLE),
        ("DELETE", r"/api/team/users/[^/]+", DELETE_RECORDS),
        ("PUT", r"/api/team/me", PROFILE_EDIT),
        ("PUT", r"/api/team/me/password", PROFILE_EDIT),
    ]
]


def route_permission(method: str, path: str) -> Optional[str]:
    """The permission a mutating request needs, or None for admin-only."""
    normalized = path.rstrip("/") or "/"
    for route_method, pattern, permission in ROUTE_PERMISSIONS:
        if route_method == method and pattern.fullmatch(normalized):
            return permission
    return None
