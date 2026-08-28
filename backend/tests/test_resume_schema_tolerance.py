"""ResumeData has to load what the parser actually wrote, not the ideal shape.

Found while capturing the Phase 3 response-shape baseline: GET /api/resume/{id}
answered 404 for eight of the thirty resumes in the development database. Not
because the rows were missing — because `Skill.name` was required while some
rows stored skills as plain strings, and because `Experience.title` was required
while some parses did not produce one. One incomplete line discarded the whole
record, and the router reported that as "not found".
"""
from __future__ import annotations

import pytest

from backend.utils.resume_parsing.models.resume_schema import (
    Education,
    Experience,
    ResumeData,
    Skill,
)


def test_skill_accepts_a_bare_string():
    assert Skill.model_validate("Python").name == "Python"


def test_skill_still_accepts_the_dict_form():
    skill = Skill.model_validate({"name": "SQL", "level": "advanced"})
    assert (skill.name, skill.level) == ("SQL", "advanced")


def test_resume_data_loads_a_mixed_skills_list():
    resume = ResumeData(skills=["Python", {"name": "SQL"}])
    assert [s.name for s in resume.skills] == ["Python", "SQL"]


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (Experience, {"company": "Analytical Engines"}),  # no title
        (Experience, {"title": "Engineer"}),  # no company
        (Education, {"degree": "BSc"}),  # no institution
    ],
)
def test_partial_entries_survive(model, payload):
    """A parser that missed a field should cost that field, not the resume."""
    assert model(**payload)


def test_free_text_dates_are_preserved_verbatim():
    """"Present" and "Jan 2019" are what resumes say; they must round-trip."""
    experience = Experience(title="Engineer", start_date="Jan 2019", end_date="Present")
    assert experience.start_date == "Jan 2019"
    assert experience.end_date == "Present"


def test_get_resume_reports_unreadable_data_as_such(admin_client, db_session, seed):
    """A row that exists but will not load is a 422, not a 404.

    The two used to be indistinguishable, so bad stored data presented as a
    broken link on the Candidate Detail screen.
    """
    from backend.models.models import Resume

    broken = Resume(
        candidate_id=seed["candidate_id"],
        file_id="seed-unreadable",
        file_name="broken.pdf",
        file_type="pdf",
        parsed_data={"experience": "this should be a list"},
    )
    db_session.add(broken)
    db_session.flush()

    response = admin_client.get(f"/api/resume/{broken.id}")
    assert response.status_code == 422
    assert "unreadable" in response.json()["detail"]

    db_session.delete(broken)
    db_session.flush()


def test_get_resume_still_404s_for_a_row_that_is_not_there(admin_client):
    assert admin_client.get("/api/resume/999999").status_code == 404
