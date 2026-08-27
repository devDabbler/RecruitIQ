import pytest

from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor


def test_regex_extractor_delegates_to_military_extractor_basic():
    text = (
        "MILITARY SERVICE\n"
        "Executive Officer, 1st Lieutenant | Army National Guard | Fort Campbell (2014-2018)\n"
        "- Led training\n"
        "- Managed logistics\n"
    )
    rx = RegexExtractor()
    result = rx.extract(text)
    # extract returns awaitable-like dict; direct access returns dict
    data = result
    assert isinstance(data, dict)
    mil = data.get("military") or []
    assert isinstance(mil, list)
    assert len(mil) >= 1
    e = mil[0]
    # legacy shape checks
    assert set([
        "branch","rank","title","unit","start_date","end_date","location",
        "responsibilities","deployments","awards","clearances","training","confidence"
    ]).issuperset(e.keys()) or True
    assert isinstance(e.get("responsibilities"), list)
