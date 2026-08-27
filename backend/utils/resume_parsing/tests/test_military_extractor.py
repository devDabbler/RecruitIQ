import pytest

from backend.utils.resume_parsing.extractors.military_extractor import MilitaryExtractor


def test_section_with_header_and_bullets():
    text = (
        "MILITARY EXPERIENCE\n"
        "Captain, 82nd Airborne Division – Fort Bragg (2012–2016)\n"
        "- Led platoon level operations in airborne infantry\n"
        "- Coordinated training and logistics across battalion\n"
    )
    entries = MilitaryExtractor.extract(text)
    assert entries, "Should extract at least one entry"
    e = entries[0]
    assert (e.branch is None) or (e.branch in {"Army","Navy","Air Force","Marines","Coast Guard","National Guard","Space Force"})
    assert e.title or e.rank
    assert e.start_date == "2012"
    assert e.end_date == "2016"
    assert e.location in {"Fort Bragg", "Fort Liberty"}
    assert len(e.responsibilities) >= 1


def test_no_header_fallback_detection():
    text = (
        "Professional Experience\n"
        "Platoon Leader, US Army, Camp Pendleton (2010 to 2013)\n"
        "• Managed training schedules and readiness\n"
    )
    entries = MilitaryExtractor.extract(text)
    assert entries, "Fallback scan should detect military block"
    e = entries[0]
    assert e.branch in {"Army"}
    assert e.start_date == "2010"
    assert e.end_date == "2013"
    assert e.location == "Camp Pendleton"


def test_present_dates_and_guard():
    text = (
        "Service\n"
        "Staff Sergeant, Army National Guard | Norfolk (Jan 2018 – Present)\n"
        "- Oversaw readiness\n"
        "- Led training events\n"
    )
    entries = MilitaryExtractor.extract(text)
    assert entries
    e = entries[0]
    assert e.end_date == "Present"
    assert e.start_date in {"2018", "2018-01"}
    assert e.confidence >= 0.4
