import os, pathlib, pytest, asyncio
from backend.services.nebius_ai_service import get_nebius_ai_service
from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIResumeParser

pytestmark = pytest.mark.skip(
    reason=(
        "Nebius API key returns HTTP 401 as of 2026-08-27. Nebius is deprioritised "
        "in spec section 4.3 in favour of OpenRouter. Delete this file in Phase 2 "
        "when the provider chain is rebuilt."
    )
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample_resume.pdf"

@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("NEBIUS_API_KEY"), reason="Nebius key not set for integration test")
async def test_nebius_full_parse():
    service = get_nebius_ai_service()
    parser = NebiusAIResumeParser(service)
    parsed = await parser.parse_resume(str(SAMPLE_PDF))

    assert parsed.personal_info.name, "Nebius parser should extract a name"
    assert parsed.experience, "Nebius parser should extract experience blocks"
