"""The department list (Track 2 Phase 3).

Anyone signed in may read it (the job form needs it, the demo shows it);
only an admin may add, rename, or turn one off. Plain `def` handlers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.departments import (
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentOut,
    DepartmentUpdate,
    DepartmentUpdateResponse,
)
from ..models.models import Department, User
from ..services import department_service
from ..utils.database import get_db
from ..utils.permissions import DEPARTMENTS_MANAGE, require

router = APIRouter(prefix="/departments")


def _out(department: Department, counts: dict[str, int]) -> DepartmentOut:
    return DepartmentOut(
        id=department.id,
        name=department.name,
        active=department.active,
        job_count=counts.get(department.name, 0),
    )


@router.get("", response_model=DepartmentListResponse)
def list_departments(include_inactive: bool = False, db: Session = Depends(get_db)) -> DepartmentListResponse:
    """Departments in name order; turned-off ones only with `include_inactive`."""
    counts = department_service.job_counts(db)
    return DepartmentListResponse(
        departments=[_out(d, counts) for d in department_service.list_all(db, include_inactive)]
    )


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require(DEPARTMENTS_MANAGE)),
) -> DepartmentOut:
    try:
        department = department_service.create(db, payload.name)
    except department_service.DepartmentError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    db.commit()
    db.refresh(department)
    return _out(department, {})


@router.put("/{department_id}", response_model=DepartmentUpdateResponse)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require(DEPARTMENTS_MANAGE)),
) -> DepartmentUpdateResponse:
    """Rename (its jobs move with it, in the same transaction) or turn on/off."""
    try:
        department, moved = department_service.update(db, department_id, payload.name, payload.active)
    except department_service.DepartmentError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    db.commit()
    db.refresh(department)
    return DepartmentUpdateResponse(
        department=_out(department, department_service.job_counts(db)), jobs_renamed=moved
    )
