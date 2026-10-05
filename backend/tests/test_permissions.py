"""The permission matrix (spec 2026-10-03 section 8, Phase B), pinned cell by cell.

Written out by hand on purpose: if someone edits ROLE_PERMISSIONS, this test
says which promise in the spec they just broke.
"""
from __future__ import annotations

import pytest

from backend.utils import permissions as p
from backend.utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    ROLE_HIRING_MANAGER,
    ROLE_HIRING_TEAM,
    ROLE_INTERVIEWER,
    STAFF_ROLES,
)

ADMIN, HM, TEAM, INT, DEMO = ROLE_ADMIN, ROLE_HIRING_MANAGER, ROLE_HIRING_TEAM, ROLE_INTERVIEWER, ROLE_DEMO

# (permission, roles that have it). Spec table rows, then the contract rows.
MATRIX = [
    (p.JOBS_WRITE, {ADMIN, HM}),
    (p.CANDIDATES_ADD, {ADMIN, HM, TEAM}),
    (p.PIPELINE_MOVE, {ADMIN, HM, TEAM}),
    (p.FEEDBACK_SUBMIT, {ADMIN, HM, TEAM, INT}),
    (p.USERS_INVITE, {ADMIN, HM}),
    (p.USERS_CHANGE_ROLE, {ADMIN}),
    (p.DELETE_RECORDS, {ADMIN}),
    (p.SCORE_BEFORE_FEEDBACK, {ADMIN, HM, TEAM, DEMO}),
    (p.REPORTS_VIEW, {ADMIN, HM, TEAM, DEMO}),
    (p.TEMPLATES_MANAGE, {ADMIN, HM}),
    (p.PROFILE_EDIT, {ADMIN, HM, TEAM, INT}),
    (p.AUDIT_VIEW, {ADMIN}),
]


@pytest.mark.parametrize(("permission", "holders"), MATRIX, ids=[m[0] for m in MATRIX])
def test_matrix_cell_by_cell(permission, holders):
    for role in (ADMIN, HM, TEAM, INT, DEMO):
        assert p.can(role, permission) is (role in holders), (role, permission)


def test_every_permission_is_in_the_matrix():
    assert {m[0] for m in MATRIX} == set(p.ALL_PERMISSIONS)


def test_unknown_and_missing_roles_can_do_nothing():
    for permission in p.ALL_PERMISSIONS:
        assert not p.can(None, permission)
        assert not p.can("", permission)
        assert not p.can("superuser", permission)


def test_staff_roles_are_the_four_non_demo_roles():
    assert set(STAFF_ROLES) == {ADMIN, HM, TEAM, INT}


def test_demo_holds_no_write_permission():
    writes = set(p.ALL_PERMISSIONS) - {p.SCORE_BEFORE_FEEDBACK, p.REPORTS_VIEW}
    assert not (p.ROLE_PERMISSIONS[DEMO] & writes)


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/jobs", p.JOBS_WRITE),
        ("PUT", "/api/jobs/12", p.JOBS_WRITE),
        ("DELETE", "/api/jobs/12", p.DELETE_RECORDS),
        ("PUT", "/api/jobs/12/pipeline", p.JOBS_WRITE),
        ("PUT", "/api/jobs/12/stages/hm_review/default-interviewers", p.JOBS_WRITE),
        ("POST", "/api/jobs/12/apply", p.CANDIDATES_ADD),
        ("POST", "/api/candidates", p.CANDIDATES_ADD),
        ("DELETE", "/api/candidates/abc", p.DELETE_RECORDS),
        ("POST", "/api/resume/save-candidate", p.CANDIDATES_ADD),
        ("POST", "/api/applications/7/advance", p.PIPELINE_MOVE),
        ("POST", "/api/applications/7/interviews", p.PIPELINE_MOVE),
        ("DELETE", "/api/interviews/3", p.PIPELINE_MOVE),
        ("POST", "/api/interviews/3/feedback", p.FEEDBACK_SUBMIT),
        ("POST", "/api/team/users", p.USERS_INVITE),
        ("PUT", "/api/team/users/abc/role", p.USERS_CHANGE_ROLE),
        ("DELETE", "/api/team/users/abc", p.DELETE_RECORDS),
        ("PUT", "/api/team/me", p.PROFILE_EDIT),
        ("PUT", "/api/team/me/password", p.PROFILE_EDIT),
        # Not listed: stays admin-only.
        ("POST", "/api/jobs/12/track-view", None),
        ("POST", "/api/cache/clear", None),
        ("POST", "/api/applications/7/promote", None),
    ],
)
def test_route_permission(method, path, expected):
    assert p.route_permission(method, path) == expected


def test_permissions_json_is_current():
    from scripts.export_permissions import TARGET, render

    assert TARGET.exists(), "run: poetry run python scripts/export_permissions.py"
    assert TARGET.read_text(encoding="utf-8") == render(), (
        "web/src/lib/role-permissions.json is stale; run: poetry run python scripts/export_permissions.py"
    )
