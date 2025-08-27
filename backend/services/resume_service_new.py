from typing import Dict, Any
from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser
from backend.utils.resume_parsing.extractors.nlp_extractor import NLPExtractor
from backend.utils.cache.cache_utils import cache_result

class ResumeService:
    def __init__(self):
        self.parser = NebiusAIParser()
        self.nlp_extractor = NLPExtractor()
    
    @cache_result(expiry=86400)  # Cache for 24 hours
    async def parse_resume(self, resume_text: str, file_path: str = "") -> Dict[str, Any]:
        """Parse resume text and return structured data."""
        # First try the Nebius AI parser
        try:
            result = await self.parser.parse_resume(resume_text, file_path)
            # If the parser returns an empty or otherwise unusable result, fall back to NLP extraction
            if not result:
                # Empty dict / None / Falsey value
                return await self.nlp_extractor.extract(resume_text, file_path)
            return result
        except Exception as e:
            # Fall back to basic extraction if Nebius AI fails
            return await self.nlp_extractor.extract(resume_text, file_path)
