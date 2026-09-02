"""The website fallback must not promote degree abbreviations or skills to URLs.

Seen on the upload page 2026-09-02: a resume with no personal site showed
"Website: B.Tech". The regex fallback in `_extract_missing_fields` looks for
any `word.tld` token, and "B.Tech" is "B" + ".tech". The same pattern turns
"ASP.NET" and "Socket.IO" into websites, and it matches the domain half of an
email address unless the parsed email happens to be identical. These tests
pin the fallback to things that are actually URLs.
"""
from __future__ import annotations

import pytest

from backend.services.agent_framework.agents.resume_processing_agent import (
    ResumeProcessingAgent,
)


def make_bare_agent():
    agent = object.__new__(ResumeProcessingAgent)
    agent.resume_service = None
    return agent


async def website_from(text: str, email: str | None = "ravi.patel@email.com") -> str | None:
    agent = make_bare_agent()
    data = {
        "personal_info": {"name": "Ravi Patel", "email": email},
        "raw_text": text,
    }
    out = await agent._extract_missing_fields(data)
    return out["personal_info"].get("website")


@pytest.mark.asyncio
async def test_degree_abbreviation_is_not_a_website():
    text = """Ravi Patel
ravi.patel@email.com | 548-324-2987
https://linkedin.com/in/ravi-patel

EDUCATION
B.Tech in Computer Science, Pune University, 2019
M.Com, 2021
"""
    assert await website_from(text) is None


@pytest.mark.asyncio
async def test_dotted_technology_names_are_not_websites():
    text = """Ravi Patel
ravi.patel@email.com

SKILLS
Java 8, ASP.NET, VB.NET, Socket.IO, Node.js, ADO.NET
"""
    assert await website_from(text) is None


@pytest.mark.asyncio
async def test_email_domain_is_skipped_even_when_parsed_email_differs():
    """The LLM may miss or mangle the email; the fallback must not then
    resurrect its domain as a website."""
    text = """Jane Doe
jane@example.org | 555-1212
"""
    assert await website_from(text, email=None) is None


@pytest.mark.asyncio
async def test_real_personal_sites_still_extracted():
    assert await website_from("Jane Doe | jane@x.org | www.janedoe.dev\nB.Tech") == "www.janedoe.dev"
    assert await website_from("Jane Doe | https://janedoe.io/portfolio\nM.Tech") == "https://janedoe.io/portfolio"
    assert await website_from("Portfolio: janedoe.design\nB.Tech CS") == "janedoe.design"
    assert await website_from("Jane Doe | jane@x.org | janedoe.dev | 555-1212") == "janedoe.dev"
