"""AI job description drafts (ATS Phase E).

`async def` because it awaits the provider chain. It takes no `get_db`
itself; `require()` is a sync dependency FastAPI runs in its threadpool.
Nothing is written to the database: the draft goes back into the job form
for a person to edit and save.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ..models.job_draft import JobDescriptionDraft, JobDraftRequest
from ..models.models import User
from ..services import job_description_draft as drafting
from ..services.llm.base import AllProvidersFailedError
from ..utils.permissions import JOBS_WRITE, require

router = APIRouter()


@router.post("/job-drafts/description", response_model=JobDescriptionDraft)
async def draft_job_description(
    payload: JobDraftRequest,
    user: User = Depends(require(JOBS_WRITE)),
) -> JobDescriptionDraft:
    try:
        return await drafting.draft(payload)
    except AllProvidersFailedError:
        raise HTTPException(
            status_code=503,
            detail="The drafting service is unavailable right now. Try again later, or write the description by hand.",
        )
    except (ValidationError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="The draft came back in a shape we could not use. Try again, or write the description by hand.",
        )
