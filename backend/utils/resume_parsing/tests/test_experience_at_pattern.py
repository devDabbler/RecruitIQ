import pytest

from backend.utils.resume_parsing.extractors.regex_extractor import extract_experience_blocks


@pytest.mark.asyncio
async def test_extract_experience_with_at_pattern():
    """Ensure experience lines with the pattern `<Title> at <Company> - <Location>` are parsed correctly."""

    resume_text = """
    EXPERIENCE
    Lead Product Data Scientist at Paypal - Palo Alto, CA
    July 2023 - Present
    • Designed a web app using speech recognition and RAG to provide insights for beta users.

    Senior Data Scientist at Udemy - Atlanta, GA
    January 2021 - June 2023
    • Built the Pricing Spectrum™ to guide a seamless pivot to a booking platform, ensuring revenue stability.
    """

    # We only need synchronous call because extract_experience_blocks is not async
    experiences = extract_experience_blocks(resume_text)

    assert len(experiences) >= 2, "Should detect at least two experience entries"

    first = experiences[0]
    assert first.get("title") == "Lead Product Data Scientist", "Failed to extract correct title"
    assert first.get("company") == "Paypal", "Failed to extract correct company"
    assert first.get("location") == "Palo Alto, CA", "Failed to extract correct location"
    assert first.get("start_date").lower().startswith("july 2023"), "Start date not parsed"
    assert first.get("end_date").lower() == "present", "End date not parsed correctly"

    # Validate description retains bullet text
    assert "Designed a web app" in first.get("description", ""), "Description missing or incomplete"
