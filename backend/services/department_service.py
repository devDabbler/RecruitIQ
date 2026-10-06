"""The department list jobs choose from (Track 2 Phase 3).

Jobs store the department name, not an id, so nothing else in the schema
had to change. This module keeps the two in step: a job may only name an
active department, and renaming a department rewrites its jobs in the same
transaction. Nothing here commits; routers compose and commit once.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.models import Department, Job

MAX_NAME_LENGTH = 100


class DepartmentError(Exception):
    """A request the caller should see as an HTTP error, with a plain-English reason."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def clean_name(name: Optional[str]) -> str:
    """Collapse runs of whitespace; refuse blank or over-long names."""
    text = " ".join((name or "").split())
    if not text:
        raise DepartmentError(422, "A department needs a name.")
    if len(text) > MAX_NAME_LENGTH:
        raise DepartmentError(422, f"Keep department names under {MAX_NAME_LENGTH} characters.")
    return text


def find(db: Session, name: str) -> Optional[Department]:
    """The department with this name, ignoring case and extra spaces."""
    text = " ".join((name or "").split())
    if not text:
        return None
    return db.query(Department).filter(func.lower(Department.name) == text.lower()).first()


def list_all(db: Session, include_inactive: bool = False) -> list[Department]:
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.active.is_(True))
    return query.order_by(func.lower(Department.name)).all()


def job_counts(db: Session) -> dict[str, int]:
    """Jobs per department name, for the admin list."""
    rows = db.query(Job.department, func.count(Job.id)).group_by(Job.department).all()
    return {name: count for name, count in rows if name}


def validate_for_job(db: Session, name: Optional[str], current: Optional[str] = None) -> str:
    """The canonical spelling of an active department, or a 422 the form can show.

    `current` is the job's existing department: a job may keep a department
    that has since been turned off, so editing an old job never forces a
    department change the editor did not ask for.
    """
    text = " ".join((name or "").split())
    if not text:
        raise DepartmentError(422, "A department is required.")
    department = find(db, text)
    if department is not None and (department.active or department.name == current):
        return department.name
    if department is None and current is not None and text == current:
        return current
    if department is None:
        raise DepartmentError(
            422,
            f"'{text}' is not on the department list. Choose one from the list, "
            "or ask an admin to add it on the Team page.",
        )
    raise DepartmentError(422, f"'{department.name}' is turned off. Choose another department.")


def create(db: Session, name: str) -> Department:
    text = clean_name(name)
    if find(db, text) is not None:
        raise DepartmentError(409, f"'{text}' is already on the list.")
    department = Department(name=text, active=True)
    db.add(department)
    db.flush()
    return department


def update(db: Session, department_id: int, name: Optional[str], active: Optional[bool]) -> tuple[Department, int]:
    """Rename and/or turn a department on or off. Returns it and how many jobs a rename moved."""
    department = db.get(Department, department_id)
    if department is None:
        raise DepartmentError(404, "No department has that id.")
    moved = 0
    if name is not None:
        text = clean_name(name)
        clash = find(db, text)
        if clash is not None and clash.id != department.id:
            raise DepartmentError(409, f"'{clash.name}' is already on the list.")
        if text != department.name:
            moved = (
                db.query(Job)
                .filter(Job.department == department.name)
                .update({Job.department: text}, synchronize_session=False)
            )
            department.name = text
    if active is not None:
        department.active = active
    db.flush()
    return department, moved
