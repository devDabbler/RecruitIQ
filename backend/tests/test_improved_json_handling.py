"""Regression tests for the LLM JSON extraction/repair layer.

The motivating bug (found by evals, 2026-08-27): a model returned a *perfect*
resume JSON inside a ```json fence, and the repair layer returned a single
nested experience entry instead of the resume — every field scored 0.
"""
import json

import pytest

from backend.services.improved_json_handling import extract_json_from_llm_response

RESUME = {
    "personal_info": {
        "name": "Maya Chen",
        "email": "maya.chen@example.com",
        "phone": "555-201-3345",
        "location": "Seattle, WA",
    },
    "experience": [
        {
            "title": "Senior Data Engineer",
            "company": "Cascadia Analytics",
            "start_date": "2022",
            "end_date": "Present",
            "responsibilities": [
                "Designed Airflow DAGs orchestrating 40+ daily ETL jobs into Snowflake",
                "Cut pipeline failure rate 60% with Great Expectations data quality checks",
            ],
        },
        {
            "title": "Data Engineer",
            "company": "Pugetworks",
            "start_date": "2019",
            "end_date": "2022",
            "responsibilities": ["Built Kafka streaming ingestion at 50k msg/s"],
        },
    ],
    "education": [{"institution": "University of Washington", "degree": "BS"}],
    "skills": [{"name": "Python"}, {"name": "SQL"}],
}


def test_fenced_json_returns_whole_document_not_nested_fragment():
    """The exact production failure: valid JSON in a ```json fence."""
    response = "```json\n" + json.dumps(RESUME, indent=2) + "\n```"

    result = extract_json_from_llm_response(response)

    assert "personal_info" in result, f"lost the document, got keys: {list(result)}"
    assert result["personal_info"]["name"] == "Maya Chen"
    assert len(result["experience"]) == 2
    assert result["experience"][0]["company"] == "Cascadia Analytics"
    assert result["education"][0]["institution"] == "University of Washington"


def test_bare_json_object_round_trips():
    result = extract_json_from_llm_response(json.dumps(RESUME))
    assert result == RESUME


def test_json_with_leading_prose_is_recovered():
    response = "Here is the output in valid JSON format:\n" + json.dumps(RESUME)
    result = extract_json_from_llm_response(response)
    assert result["personal_info"]["email"] == "maya.chen@example.com"
    assert len(result["experience"]) == 2


def test_fence_without_json_tag():
    response = "```\n" + json.dumps(RESUME) + "\n```"
    result = extract_json_from_llm_response(response)
    assert result["personal_info"]["name"] == "Maya Chen"


def test_trailing_commas_are_repaired():
    malformed = '{"personal_info": {"name": "Ann Lee",}, "skills": [{"name": "Go"},],}'
    result = extract_json_from_llm_response(malformed)
    assert result["personal_info"]["name"] == "Ann Lee"


@pytest.mark.parametrize("junk", ["", "no json here at all", "{{{{"])
def test_unparseable_input_returns_valid_shape(junk):
    """Never raise — callers depend on a dict with the expected keys."""
    result = extract_json_from_llm_response(junk)
    assert isinstance(result, dict)
    assert "personal_info" in result
