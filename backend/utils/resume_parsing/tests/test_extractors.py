import pytest
from unittest.mock import MagicMock
from backend.utils.resume_parsing.extractors.ai_extractor import AIExtractor
from backend.utils.resume_parsing.extractors.nlp_extractor import NLPExtractor
from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor
from backend.utils.resume_parsing.extractors.base_extractor import BaseExtractor

# Dummy services for dependency injection
class DummyNebiusAIService:
    pass
class DummyLLMService:
    pass

# Sample resume text for extractor tests
SAMPLE_RESUME_TEXT = """
Clint Forest
Email: clint.forest@email.com | Phone: (555) 123-4567

EXPERIENCE
Software Engineer at Acme Corp
2018-2022
- Developed scalable backend systems
- Led migration to cloud infrastructure

EDUCATION
B.S. Computer Science, University of Example
2014-2018

SKILLS
Python, Java, SQL, Cloud, Leadership
"""

class TestAIExtractor:
    @pytest.mark.xfail(reason="AIExtractor may require external API/model access.")
    @pytest.mark.asyncio
    async def test_extract(self):
        """Test AIExtractor.extract returns structured data with expected fields."""
        extractor = AIExtractor(nebius_ai_service=DummyNebiusAIService())
        result = await extractor.extract(SAMPLE_RESUME_TEXT)
        assert isinstance(result, dict)
        assert 'education' in result
        assert 'experience' in result
        assert 'skills' in result

class TestNLPExtractor:
    @pytest.mark.xfail(reason="NLPExtractor may require spaCy model.")
    @pytest.mark.asyncio
    async def test_extract(self):
        """Test NLPExtractor.extract returns structured data with expected fields."""
        extractor = NLPExtractor(llm_service=DummyLLMService())
        result = await extractor.extract(SAMPLE_RESUME_TEXT)
        assert isinstance(result, dict)
        assert 'education' in result
        assert 'experience' in result
        assert 'skills' in result

class TestRegexExtractor:
    @pytest.mark.asyncio
    async def test_extract(self):
        """Test RegexExtractor.extract returns structured data with expected fields."""
        extractor = RegexExtractor()
        result = await extractor.extract(SAMPLE_RESUME_TEXT)
        assert isinstance(result, dict)
        assert 'education' in result
        assert 'experience' in result
        assert 'skills' in result

    def test_deduplicate_education_entries(self):
        """Test RegexExtractor._deduplicate_education_entries removes duplicates."""
        extractor = RegexExtractor()
        # Use a simple class to match the implementation's attribute access
        class Edu:
            def __init__(self, institution, degree):
                self.institution = institution
                self.degree = degree
        entries = [
            Edu('University of Example', 'B.S.'),
            Edu('University of Example', 'B.S.'),
            Edu('Another University', 'M.S.')
        ]
        deduped = extractor._deduplicate_education_entries(entries)
        assert len(deduped) == 2
        assert any(e.institution == 'Another University' for e in deduped)

class TestBaseExtractor:
    @pytest.mark.skip(reason="BaseExtractor is abstract and should not be instantiated.")
    def test_extract_not_implemented(self):
        """Test BaseExtractor.extract raises NotImplementedError."""
        extractor = BaseExtractor()
        with pytest.raises(NotImplementedError):
            extractor.extract('text') 