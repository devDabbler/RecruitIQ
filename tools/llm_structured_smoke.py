"""Live smoke test: structured extraction through the provider chain.

Usage: poetry run python tools/llm_structured_smoke.py
"""
import asyncio
import json

from backend.services.llm_service import get_llm_service
from backend.utils.resume_parsing.contracts.resume_contract import ResumeV2
from backend.utils.resume_parsing.extractors.structured_extractor import ExtractionContract

FAKE_RESUME = """
Jordan Rivera
jordan.rivera@example.com | (555) 201-4433 | Austin, TX
linkedin.com/in/jordanrivera

EXPERIENCE
Senior Data Engineer, Acme Analytics | Austin, TX | 2021 - Present
- Built ETL pipelines processing 2TB daily using Python and Airflow
- Led migration from Redshift to Snowflake

Data Analyst, RetailCo | 2018 - 2021
- Automated weekly sales reporting with SQL and Tableau

EDUCATION
University of Texas at Austin - BS in Computer Science (2018)

SKILLS
Python, SQL, Airflow, Snowflake, Tableau
"""


async def main():
    service = get_llm_service()
    data = await service.generate_structured(
        f"Extract this resume into the JSON schema.\n\nRESUME:\n{FAKE_RESUME}",
        ExtractionContract,
        system_message="You are a resume parsing specialist AI.",
        max_tokens=4096,
    )
    print(json.dumps(data, indent=2, default=str)[:2000])
    validated = ResumeV2.model_validate(data)
    pi = validated.personal_info
    assert pi.email == "jordan.rivera@example.com", pi.email
    assert len(validated.experience) >= 2, len(validated.experience)
    print("\nOK: schema-validated, name=%r, %d experiences, %d skills" % (
        pi.name, len(validated.experience), len(validated.skills)))


if __name__ == "__main__":
    asyncio.run(main())
