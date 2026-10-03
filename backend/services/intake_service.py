"""Putting a candidate on a job's pipeline (ATS Phase C).

The one way in. `apply_to_job`, `create_candidate` with a job, the resume
save path, and "Consider for another role" all call `add_to_job`, so a new
application always starts at the first enabled round with the candidate's
derived status synced, however it arrived. Like `pipeline_service`, nothing
here commits: callers compose and commit once.
"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication
from backend.services import pipeline_service as ps


class IntakeError(Exception):
    """A request the caller should see as an HTTP error, with a plain-English reason."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def add_to_job(
    db: Session,
    candidate_id: str,
    job_id: int,
    source: Optional[str] = "direct",
    cover_letter: Optional[str] = None,
) -> Tuple[JobApplication, bool]:
    """The candidate's application to this job, and whether it was just created.

    One application per candidate per job (spec decision 2): an existing one is
    returned untouched, whatever its status.
    """
    job = db.get(Job, job_id)
    if job is None:
        raise IntakeError(404, "Job not found")
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise IntakeError(404, "Candidate not found")

    existing = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == job_id, JobApplication.candidate_id == candidate_id)
        .first()
    )
    if existing is not None:
        return existing, False

    application = JobApplication(
        job_id=job_id,
        candidate_id=candidate_id,
        cover_letter=cover_letter,
        source=source or "direct",
    )
    db.add(application)
    job.applications = (job.applications or 0) + 1
    db.flush()
    ps.start_application(db, application)
    if not (candidate.position_applied or "").strip():
        candidate.position_applied = job.title
    return application, True
