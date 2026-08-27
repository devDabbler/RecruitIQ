# backend/tests/test_military_extraction_regex.py
import pytest

from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor

def test_extract_military_with_section_and_bullets():
    text = """
    PROFESSIONAL SUMMARY
    Results-driven leader...

    MILITARY EXPERIENCE
    United States Army — Captain | Jan 2015 - Jun 2019
    - Led a 120-person company during multi-national training exercises.
    - Managed $15M in equipment with zero loss incidents.
    - Coordinated logistics across three battalions.

    EDUCATION
    University of X, B.S. Something
    """

    rx = RegexExtractor()
    entries = rx._extract_military(text)
    # Should find at least one entry
    assert isinstance(entries, list) and len(entries) >= 1

    e0 = entries[0]
    # Key fields should be present
    assert any(k in e0 for k in ("branch", "title", "rank"))
    assert e0.get("responsibilities"), "Responsibilities list should not be empty"
    # Check bullets captured
    joined = " ".join(e0["responsibilities"])
    assert "120-person" in joined or "Managed $15M" in joined or "Coordinated logistics" in joined

    # Dates best-effort
    if "start_date" in e0 and "end_date" in e0:
        assert e0["start_date"]
        assert e0["end_date"]

def test_extract_military_without_section_header_returns_empty():
    text = """
    EXPERIENCE
    Company ABC — Executive Officer
    Led teams across orgs. United States Army mentioned in passing.
    Responsibilities included cross-functional leadership.
    """

    rx = RegexExtractor()
    entries = rx._extract_military(text)
    # By design, we do not parse without an explicit Military header to avoid over-capture
    assert entries == []