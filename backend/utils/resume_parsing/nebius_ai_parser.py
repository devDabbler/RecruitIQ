import logging
import os
import asyncio
from typing import Dict, Any, Optional

from .contracts.resume_contract import ResumeV2
from .extractors.structured_extractor import StructuredExtractor
from .extractors.regex_extractor import RegexExtractor
from backend.utils.resume_parsing.loaders.document_loader import DocumentLoaderConfig, DocumentLoaderFactory
from .processors.intelligent_text_processor import IntelligentTextProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NebiusAIParser:
    """
    A comprehensive resume parser that orchestrates document loading, text processing,
    and data extraction using a primary structured extractor with a fallback to a regex-based extractor.
    """
    
    def __init__(self, use_ocr: bool = True):
        config = DocumentLoaderConfig(ocr_enabled=use_ocr)
        self.document_loader = DocumentLoaderFactory.create_loader("", config)
        self.text_processor = IntelligentTextProcessor()
        self.structured_extractor = StructuredExtractor()
        self.legacy_extractor = RegexExtractor()
        # --- Nebius AI config check ---
        try:
            from backend.services.nebius_ai_service import get_nebius_ai_service
            nebius_service = get_nebius_ai_service()
            logger.info(f"Nebius AI endpoint: {getattr(nebius_service, 'endpoint', 'unknown')}")
            logger.info(f"Nebius API key present: {'***' if getattr(nebius_service, 'api_key', None) else 'MISSING'}")
        except Exception as e:
            logger.warning(f"Nebius AI service config could not be loaded at init: {e}")
        # Warn if LLM service is not Nebius
        if getattr(self.structured_extractor, 'llm_service', None) is None:
            logger.warning("StructuredExtractor.llm_service is None! Nebius AI will not be used.")
        elif 'nebius' not in str(type(self.structured_extractor.llm_service)).lower():
            logger.warning(f"StructuredExtractor.llm_service is not NebiusAIService: {type(self.structured_extractor.llm_service)}")

    
    async def parse_resume(self, raw_text: str, resume_path: str = "") -> Dict[str, Any]:
        """
        Parse a resume given raw extracted text using ONLY Nebius AI (Phi-4).
        """
        logger.info(f"Parsing resume (provided text) for: {resume_path or 'unknown path'} [Nebius AI ONLY]")
        try:
            processed_text_result = await self.text_processor.process(raw_text)
            processed_text = processed_text_result["processed_text"]
            logger.info(f"Text processed. Processed length: {len(processed_text)} characters.")
            logger.info("Calling StructuredExtractor (Nebius AI)...")
            extracted_data = await self.structured_extractor.extract(processed_text)
            if not self._is_extraction_successful(extracted_data):
                logger.warning("Nebius AI extraction failed or returned empty/weak result. Falling back to RegexExtractor.")
                # Fallback to RegexExtractor
                try:
                    fallback_data = self.legacy_extractor.extract(processed_text)
                    logger.info("Successfully parsed resume using RegexExtractor fallback.")
                    return self._convert_v2_to_legacy(ResumeV2.model_validate(fallback_data))
                except Exception as fallback_e:
                    logger.critical(f"Both Nebius AI and RegexExtractor failed: {fallback_e}")
                    raise RuntimeError(f"Nebius AI extraction failed and RegexExtractor fallback also failed: {fallback_e}")
            logger.info("Successfully parsed resume using StructuredExtractor (Nebius AI).")
            return self._convert_v2_to_legacy(ResumeV2.model_validate(extracted_data))
        except Exception as e:
            logger.critical(f"Nebius AI resume parsing failed: {e}", exc_info=True)
            # Try fallback to RegexExtractor on the original text
            try:
                logger.warning("Attempting RegexExtractor fallback due to Nebius AI failure.")
                fallback_data = self.legacy_extractor.extract(raw_text)
                logger.info("Successfully parsed resume using RegexExtractor fallback.")
                return self._convert_v2_to_legacy(ResumeV2.model_validate(fallback_data))
            except Exception as fallback_e:
                logger.critical(f"Both Nebius AI and RegexExtractor fallback failed: {fallback_e}")
                raise RuntimeError(f"Nebius AI extraction failed and RegexExtractor fallback also failed: {fallback_e}")

    async def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Asynchronously parse a resume from a file path.

        This avoids calling asyncio.run inside an already-running event loop.
        """
        logger.info(f"Starting async file-based resume parsing for: {file_path}")
        try:
            document = self.document_loader.load(file_path)
            # Handle list of DocumentPage objects
            if isinstance(document, list) and len(document) > 0:
                raw_text = "\n".join([page.content for page in document])
            elif hasattr(document, 'text'):
                raw_text = document.text
            else:
                raise ValueError(f"Unexpected document format: {type(document)}")

            logger.info(f"Document loaded. Raw text length: {len(raw_text)} characters.")
            return await self.parse_resume(raw_text, file_path)
        except Exception as e:
            logger.error(f"Async file-based parsing failed for {file_path}: {e}", exc_info=True)
            # Attempt legacy fallback on raw text if possible
            try:
                raw_text = ""
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        from PyPDF2 import PdfReader
                        pdf_reader = PdfReader(f)
                        for page in pdf_reader.pages:
                            raw_text += page.extract_text() or ""
                legacy_data = self.legacy_extractor.extract(raw_text)
                return legacy_data
            except Exception as final_e:
                logger.critical(f"Last-ditch legacy parsing also failed for {file_path}: {final_e}", exc_info=True)
                return {"error": str(final_e), "status": "Failed"}

    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse a resume from a file path (synchronous wrapper)."""
        logger.info(f"Starting resume parsing for: {file_path}")
        try:
            document = self.document_loader.load(file_path)
            # Fix: Handle list of DocumentPage objects
            if isinstance(document, list) and len(document) > 0:
                # Combine all pages into single text
                raw_text = "\n".join([page.content for page in document])
            elif hasattr(document, 'text'):
                raw_text = document.text
            else:
                raise ValueError(f"Unexpected document format: {type(document)}")
            
            logger.info(f"Document loaded. Raw text length: {len(raw_text)} characters.")
            # Reuse async method in sync context
            return asyncio.run(self.parse_resume(raw_text, file_path))
        except Exception as e:
            logger.error(f"An unexpected error occurred during the parsing of {file_path}: {e}", exc_info=True)
            # Fallback to legacy extractor on raw text if possible
            try:
                raw_text = ""
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        from PyPDF2 import PdfReader
                        pdf_reader = PdfReader(f)
                        for page in pdf_reader.pages:
                            raw_text += page.extract_text() or ""
                legacy_data = self.legacy_extractor.extract(raw_text)
                return legacy_data
            except Exception as final_e:
                logger.critical(f"Last-ditch legacy parsing also failed for {file_path}: {final_e}", exc_info=True)
                return {"error": str(final_e), "status": "Failed"}
    
    def _is_extraction_successful(self, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        # Support both 'experience' (current schema) and 'work_experience' (older schema)
        experience_list = data.get('experience')
        if experience_list is None:
            experience_list = data.get('work_experience', [])
        experience_count = len(experience_list)
        education_count = len(data.get('education', []))
        return experience_count > 0 or education_count > 0

    def _merge_data(self, primary_data: Dict, fallback_data: Dict) -> Dict:
        if not self._is_extraction_successful(primary_data):
            logger.info("Primary data is weak. Using fallback data as the base.")
            return fallback_data
        return self._convert_v2_to_legacy(ResumeV2.model_validate(primary_data))

    def _convert_v2_to_legacy(self, resume_v2: ResumeV2) -> Dict[str, Any]:
        logger.info("Converting ResumeV2 contract to legacy dictionary format.")
        # Resolve top-level location robustly: support string or structured objects
        pi = resume_v2.personal_info if resume_v2.personal_info else None
        # Prefer explicit location, else fall back to address
        resolved_location: Optional[str] = None
        if pi is not None:
            loc = getattr(pi, 'location', None)
            addr = getattr(pi, 'address', None)
            if isinstance(loc, str) and loc.strip():
                resolved_location = loc.strip()
            elif hasattr(loc, 'city'):
                # In case future models return a structured object
                parts = [
                    getattr(loc, 'city', None),
                    getattr(loc, 'state', None) or getattr(loc, 'region', None),
                    getattr(loc, 'country', None)
                ]
                resolved_location = ", ".join([p for p in parts if isinstance(p, str) and p.strip()]) or None
            elif isinstance(addr, str) and addr.strip():
                resolved_location = addr.strip()

        personal_info_dict = {
            'name': resume_v2.personal_info.name if resume_v2.personal_info else None,
            'email': resume_v2.personal_info.email if resume_v2.personal_info else None,
            'phone': resume_v2.personal_info.phone if resume_v2.personal_info else None,
            'location': resolved_location,
            'linkedin': resume_v2.personal_info.linkedin if resume_v2.personal_info else None,
        }

        legacy_dict = {
            **personal_info_dict,
            'name': resume_v2.personal_info.name if resume_v2.personal_info else None,
            'email': resume_v2.personal_info.email if resume_v2.personal_info else None,
            'phone': resume_v2.personal_info.phone if resume_v2.personal_info else None,
            'location': resolved_location,
            'linkedin': resume_v2.personal_info.linkedin if resume_v2.personal_info else None,
            'summary': getattr(resume_v2, 'summary', ''),
            'education': [
                {
                    'institution': edu.institution,
                    'degree': edu.degree,
                    'field_of_study': edu.field_of_study,
                    'gpa': getattr(edu, 'gpa', None),
                    'start_date': edu.start_date,
                    'end_date': edu.end_date
                } for edu in resume_v2.education
            ],
            'experience': [
                {
                    'company': exp.company,
                    'title': exp.title,
                    'start_date': exp.start_date,
                    'end_date': "Present" if str(exp.end_date).upper() == "PRESENT" else exp.end_date,
                    'description': '\n'.join(exp.responsibilities) if getattr(exp, 'responsibilities', None) and isinstance(getattr(exp, 'responsibilities'), (list, tuple)) else (getattr(exp, 'description', '') if isinstance(getattr(exp, 'description', ''), str) else str(getattr(exp, 'description', '')))
                } for exp in getattr(resume_v2, 'experience', []) or getattr(resume_v2, 'work_experience', [])
            ],
            # Output skills as list of dicts to satisfy downstream agent expectations
            'skills': [
                (
                    {'name': skill.name, **({'category': getattr(skill, 'category')}
                    if getattr(skill, 'category', None) else {})}
                    if hasattr(skill, 'name') else {'name': str(skill)}
                )
                for skill in resume_v2.skills
            ],
            # Include military experience in legacy format
            'military': [
                {
                    'branch': mil.branch,
                    'rank': mil.rank,
                    'title': mil.title,
                    'start_date': mil.start_date,
                    'end_date': mil.end_date,
                    'mos_specialty': mil.mos_specialty,
                    'location': mil.location,
                    'responsibilities': mil.responsibilities,
                    'deployments': mil.deployments,
                    'awards': mil.awards,
                    'clearances': mil.clearances,
                    'training': mil.training
                } for mil in getattr(resume_v2, 'military', [])
            ],
            'personal_info': personal_info_dict
        }
        return legacy_dict

    
