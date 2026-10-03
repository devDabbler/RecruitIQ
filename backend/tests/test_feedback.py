"""Interviews, feedback, and default interviewers (ATS Phase B).

Uses `scoped_application` from conftest (its own job and application) so the
seeded application that test_pipeline relies on is never touched.
"""
from __future__ import annotations

import pytest

from backend.models.models import (
    ApplicationStage,
    Feedback,
    Interview,
    PipelineStage,
    StageDefaultInterviewer,
    User,
)


def test_models_import_and_map():
    assert Interview.__tablename__ == "interviews"
    assert Feedback.__tablename__ == "feedback"
    assert StageDefaultInterviewer.__tablename__ == "stage_default_interviewers"
    assert "interviews" in ApplicationStage.__mapper__.relationships
    assert "default_interviewers" in PipelineStage.__mapper__.relationships
    assert "name" in User.__table__.columns
    assert "timezone" in User.__table__.columns
