import pathlib, pytest, os
from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
SAMPLE_TXT = FIXTURES_DIR / "sample_resume.txt"
SAMPLE_PDF = FIXTURES_DIR / "sample_resume.pdf" if (FIXTURES_DIR / "sample_resume.pdf").exists() and (FIXTURES_DIR / "sample_resume.pdf").stat().st_size > 0 else None
PATHS = [SAMPLE_TXT] + ([SAMPLE_PDF] if SAMPLE_PDF else [])

@pytest.mark.parametrize("resume_path", PATHS)
@pytest.mark.asyncio
async def test_parse_end_to_end(resume_path: pathlib.Path):
    """Run real parser on sample files and assert key fields are populated."""
    text = resume_path.read_text(encoding='utf-8', errors='ignore')
    extractor = RegexExtractor()
    result_dict = await extractor.extract(text)
    
    # quick objects for assertions


    # Education sanity
    assert result_dict["education"], "Education list should not be empty"

    # Experience sanity
    assert result_dict["experience"], "Experience list should not be empty"

    # Skills sanity
    assert len(result_dict["skills"]) >= 5
