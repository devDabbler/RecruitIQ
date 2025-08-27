"""
ResumeParser class moved here to decouple from parser.py and resolve circular imports.
"""
from typing import Any, Optional, TYPE_CHECKING, Dict
import logging
import re
import asyncio
from .models.resume_schema import (
    ResumeData, PersonalInfo, Education, Experience,
    Skill, Project, Certification, Language
)
from .processors.base_processor import BaseProcessor
from .processors.ocr_processor import OCRProcessor
from .processors.markdown_processor import MarkdownProcessor
from .processors.section_classifier_processor import SectionClassifierProcessor
from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser      

from pydantic import ValidationError

logger = logging.getLogger(__name__)


def create_compatible_parser(service: Any, config_path: Optional[str] = None) -> "NebiusAIParser":
    """
    Create a compatible parser that works with any service that has generate_text method.
    PREFERRED: Use Nebius AI service for resume parsing.

    Args:
        service: Any service that has a nebius_ai_service attribute or is a NebiusAIService itself
        config_path: Optional path to configuration file

    Returns:
        NebiusAIParser instance
    """
    logger = logging.getLogger(__name__)

    # First, try to get nebius_ai_service from the provided service
    if hasattr(service, 'nebius_ai_service') and service.nebius_ai_service:   
        logger.info(f"Using nebius_ai_service from {type(service).__name__}") 
        return NebiusAIParser()

    # If service is already a NebiusAIService, use it directly
    from backend.services.nebius_ai_service import NebiusAIService
    if isinstance(service, NebiusAIService):
        logger.info(f"Using service directly as it's already a NebiusAIService")
        return NebiusAIParser()

    # If we don't have Nebius AI available, try to initialize it
    try:
        from backend.services.nebius_ai_service import get_nebius_ai_service  
        logger.info("Attempting to initialize Nebius AI service directly")    
        nebius_service = get_nebius_ai_service()
        if nebius_service:
            logger.info("Successfully initialized Nebius AI service") 
        return NebiusAIParser()
    except Exception as e:
        logger.warning(f"Failed to initialize Nebius AI service directly: {e}")

        # CRITICAL: We no longer allow any fallbacks to non-Nebius services   
        # This is based on the user's explicit preference to use only Nebius AI (Phi-4)

        # Instead of silently allowing fallback, raise an error to ensure proper configuration
        error_msg = f"Service {type(service).__name__} cannot be used for resume parsing. Nebius AI service required."
        logger.critical(error_msg)
        print(f"\n\nCRITICAL ERROR: {error_msg}\n\n")
        raise ValueError(error_msg)

class ResumeParser:
    """
    Main resume parser orchestrator that coordinates between different parsing strategies.
    IMPORTANT: This parser uses Nebius AI (Phi-4) exclusively as the preferred backend.
    """
    def __init__(self, *args, **kwargs):
        """
        Initialize the resume parser.

        IMPORTANT: This system is configured to use ONLY Nebius AI (Phi-4) for resume parsing.
        Other LLM models (Ollama, mixtral-resume) are no longer supported.    

        This constructor supports multiple interface styles for backward compatibility:

        - New style: ResumeParser(llm_service=llm_service, parser=parser, verbose=False)
        - Old style: ResumeParser(storage_service=storage_service, llm_service=llm_service, ollama_service=None)

        In all cases, only Nebius AI is used for parsing regardless of what services are passed.
        """
        self.logger = logging.getLogger(__name__)

        # Extract parameters with backward compatibility
        storage_service = kwargs.get('storage_service', None)  # For old-style compatibility
        llm_service = kwargs.get('llm_service', None)
        parser = kwargs.get('parser', None)
        ollama_service = kwargs.get('ollama_service', None)  # Ignored, but accepted for compatibility
        self.verbose = kwargs.get('verbose', False)

        # Handle positional arguments for backward compatibility
        if args:
            if len(args) >= 1 and llm_service is None:
                # First positional arg could be llm_service or storage_service
                if hasattr(args[0], 'nebius_ai_service'):
                    llm_service = args[0]
                else:
                    storage_service = args[0]

            if len(args) >= 2 and llm_service is None:
                llm_service = args[1]

        # Get service from registry if not provided
        if llm_service is None:
            from backend.services.service_registry import provide_llm_service 
            llm_service = provide_llm_service()
            self.logger.info("Using LLM service from service registry")       

        self.llm_service = llm_service

        # Use provided parser or create one
        if parser is not None:
            # Verify the provided parser is actually using Nebius AI
            parser_class = parser.__class__.__name__
            if parser_class != "NebiusAIParser":
                error_msg = f"Invalid parser class: {parser_class}. Only NebiusAIParser is supported."
                self.logger.critical(error_msg)
                raise ValueError(error_msg)

            self.logger.info(f"Using provided {parser_class} for resume parsing")
            self.parser = parser
        else:
            # Force Nebius AI initialization if needed
            if not hasattr(llm_service, 'nebius_ai_service') or llm_service.nebius_ai_service is None:
                self.logger.info("Nebius AI service not initialized in LLM service. Forcing initialization...")
                # Force initialization - this will raise an exception if it fails
                if hasattr(llm_service, '_initialize_nebius_ai'):
                    success = llm_service._initialize_nebius_ai()
                    if not success:
                        raise RuntimeError("Failed to initialize Nebius AI - cannot proceed with resume parsing")
                else:
                    # Attempt to create directly using Nebius AI factory      
                    try:
                        from backend.services.nebius_ai_service import get_nebius_ai_service
                        nebius_service = get_nebius_ai_service()
                        if nebius_service:
                            # Add it to the llm_service for future reference  
                            llm_service.nebius_ai_service = nebius_service    
                        else:
                            raise RuntimeError("Failed to initialize Nebius AI service")
                    except Exception as e:
                        raise RuntimeError(f"Failed to initialize Nebius AI - cannot proceed with resume parsing: {e}")

            self.logger.info("Creating parser with Nebius AI service")        
            self.parser = create_compatible_parser(llm_service.nebius_ai_service)
        # Log the actual service being used
        parser_type = type(self.parser).__name__
        self.logger.info(f"Resume parser initialized with: {parser_type}")    

        self.processors = [
            OCRProcessor(),
            MarkdownProcessor(),
            SectionClassifierProcessor()
        ]
        # Legacy extractors are no longer used directly by the parser.        
        # The nebius_ai_parser encapsulates the entire extraction process.    
        # Secondary and tertiary extractors
        from .extractors.nlp_extractor import NLPExtractor
        from .extractors.regex_extractor import RegexExtractor
        self.extractors = [
            NLPExtractor(),  # spaCy-powered secondary extractor
            RegexExtractor(),  # regex fallback
        ]

    # ------------------------------------------------------------------      
    # Backward-compatibility helpers
    # ------------------------------------------------------------------      
    async def read_resume_text(self, file_path: str) -> str:
        """Extract raw text from a resume file (PDF/DOCX/TXT).
        Maintained for backward-compatibility with legacy tools like
        ``quick_extract.py`` and older tests which call
        ``await ResumeParser.read_resume_text()`` directly.
        The implementation mirrors the first part of ``parse_resume``.        
        """
        if file_path.lower().endswith('.pdf'):
            return await self._extract_text_from_pdf(file_path)
        if file_path.lower().endswith(('.doc', '.docx')):
            return await self._extract_text_from_docx(file_path)
        if file_path.lower().endswith('.txt'):
            async with asyncio.to_thread(open, file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        raise ValueError(f"Unsupported file type: {file_path}")

    async def parse_resume(self, file_path: str, strategy: str = 'fast') -> ResumeData:
        """Parse a resume file and return structured data.

        Args:
            file_path: Path to the resume file
            strategy: Parsing strategy (currently not used, kept for backward compatibility)

        Returns:
            ResumeData object containing structured resume information        

        Raises:
            ValueError: If file cannot be processed
            ValidationError: If extracted data doesn't match schema
        """
        try:
            self.logger.info(f"Starting resume parsing for {file_path}")      

            # Extract text from file
            if file_path.lower().endswith('.pdf'):
                text = await self._extract_text_from_pdf(file_path)
            elif file_path.lower().endswith(('.doc', '.docx')):
                text = await self._extract_text_from_docx(file_path)
            elif file_path.lower().endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            else:
                raise ValueError(f"Unsupported file type: {file_path}")       

            # Validate extracted text
            if not text or len(text.strip()) < 50:
                raise ValueError(f"Insufficient text extracted from file: {len(text)} characters")

            self.logger.info(f"Extracted {len(text)} characters from {file_path}")

            # ----------------------------------------------------------------
            # Primary: Nebius AI parser
            # ----------------------------------------------------------------
            try:
                nebius_result = await self.parser.parse_resume(text, file_path)
                # Convert dictionary result to ResumeData object
                if nebius_result and isinstance(nebius_result, dict):
                    # Import Military for military data processing
                    from backend.utils.resume_parsing.models.resume_schema import Military
                    
                    resume_data = ResumeData(
                        personal_info=PersonalInfo(
                            name=nebius_result.get('name', ''),
                            email=nebius_result.get('email', ''),
                            phone=nebius_result.get('phone', ''),
                            location=nebius_result.get('location', ''),       
                            linkedin=nebius_result.get('linkedin') or nebius_result.get('linkedin_url', '')
                        ),
                        education=[Education(**e) for e in nebius_result.get('education', [])],
                        experience=[Experience(**e) for e in nebius_result.get('experience', [])],
                        skills=[Skill(name=s['name'] if isinstance(s, dict) else s, category=s.get('category') if isinstance(s, dict) else None) for s in nebius_result.get('skills', [])],
                        projects=[],
                        certifications=[],
                        languages=[],
                        military=[Military(**m) for m in nebius_result.get('military', [])],
                        raw_text=text,
                    )
                else:
                    resume_data = None
            except Exception as nebius_exc:
                self.logger.error(f"Nebius AI parser failed: {nebius_exc}")   
                resume_data = None

            # ----------------------------------------------------------------
            # Secondary & tertiary extractors if Nebius result missing OR insufficient
            # ----------------------------------------------------------------
            MIN_EXP = 2
            if (not resume_data) or (not resume_data.experience) or (len(resume_data.experience) < MIN_EXP):
                self.logger.info("Invoking secondary extractors due to incomplete Nebius result")
                aggregate: Dict[str, Any] = {}
                for extractor in self.extractors:
                    try:
                        self.logger.info(f"Running extractor: {extractor.name}")
                        result = await extractor.extract(text, file_path)     
                        if result:
                            aggregate = result  # simple strategy: take first successful
                            break
                    except Exception as ext_exc:
                        self.logger.warning(f"Extractor {extractor.name} failed: {ext_exc}")
                if aggregate:
                    # Convert dict to minimal ResumeData so callers have consistent type
                    resume_obj = ResumeData(
                        personal_info=PersonalInfo(**aggregate.get("personal_info", {"name": "Unknown"})),
                        education=[Education(**e) for e in aggregate.get("education", [])],
                        experience=[Experience(**e) for e in aggregate.get("experience", [])],
                        skills=[Skill(name=s.get('name', s) if isinstance(s, dict) else s, category=s.get('category') if isinstance(s, dict) else None) for s in aggregate.get("skills", [])],
                        projects=[],
                        certifications=[],
                        languages=[],
                        military=[Military(**m) for m in aggregate.get("military", [])],
                        raw_text=text,
                    )
                    self._post_process_resume(resume_obj)
                    return resume_obj

            if not resume_data:
                self.logger.error("All extractors failed. Returning minimal ResumeData.")
                resume_obj = ResumeData(
                    personal_info=PersonalInfo(name="Extraction Failed"),     
                    education=[],
                    experience=[],
                    skills=[],
                    projects=[],
                    certifications=[],
                    languages=[],
                    raw_text=text,
                )
                self._post_process_resume(resume_obj)
                return resume_obj

            # --------------------------------------------------------------  
            # Final post-processing (cleanup across all extractor outputs)    
            # --------------------------------------------------------------  
            self._post_process_resume(resume_data)

            self.logger.info(f"Successfully parsed resume from {file_path}")  
            return resume_data

        except Exception as e:
            self.logger.error(f"Error parsing resume: {e}")
            raise ValueError(f"Failed to parse resume: {str(e)}")

    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file with enhanced structure preservation using pdfplumber."""
        text = ""
        try:
            # Use pdfplumber with layout-aware extraction
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # Try layout-aware extraction first
                    try:
                        # Extract text with better word boundary detection    
                        page_text = page.extract_text(
                            x_tolerance=3,  # Horizontal tolerance for word grouping
                            y_tolerance=3,  # Vertical tolerance for line grouping
                            layout=True,    # Preserve layout
                            x_density=7.25, # Character density
                            y_density=13    # Line density
                        )

                        if not page_text:
                            # Fallback to table extraction for structured content
                            tables = page.extract_tables()
                            if tables:
                                table_text = []
                                for table in tables:
                                    for row in table:
                                        if row:
                                            table_text.append(' '.join(str(cell) for cell in row if cell))
                                page_text = '\n'.join(table_text)
                            else:
                                # Final fallback to basic extraction
                                page_text = page.extract_text() or ""

                    except Exception as e:
                        self.logger.warning(f"Layout extraction failed for page, using basic: {e}")
                        page_text = page.extract_text() or ""

                    if page_text:
                        # Clean and preserve structure
                        page_text = self._clean_extracted_text(page_text)     
                        text += page_text + "\n\n"  # Double newline between pages
        except Exception as e:
            self.logger.warning(f"pdfplumber extraction failed: {e}")

            # Try pypdf as fallback
            try:
                import pypdf
                with open(file_path, "rb") as f:
                    pdf = pypdf.PdfReader(f)
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            # Clean and preserve structure
                            page_text = self._clean_extracted_text(page_text) 
                            text += page_text + "\n\n"
            except Exception as e2:
                self.logger.error(f"pypdf extraction also failed: {e2}")      
                raise

        # Final cleaning
        text = self._clean_extracted_text(text)
        return text

    def _clean_extracted_text(self, text: str) -> str:
        """Clean extracted text while preserving word boundaries and structure."""
        if not text:
            return text

        # Replace common PDF artifacts
        text = re.sub(r'\x00', '', text)  # Remove null bytes
        text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)  # Remove control chars

        # Fix broken word boundaries (common PDF extraction issue)
        # Rejoin words that were split across lines without hyphens
        text = re.sub(r'([a-z])\n([a-z])', r'\1\2', text)  # "Py\nthon" -> "Python"
        text = re.sub(r'([a-z])\s+([a-z])(?=\s|$)', lambda m: m.group(1) + m.group(2) if len(m.group(1)) + len(m.group(2)) <= 15 else m.group(0), text)     

        # Fix common word fragments
        word_fixes = {
            r'\bP\s+ython\b': 'Python',
            r'\bJava\s+Script\b': 'JavaScript',
            r'\bNode\s+js\b': 'Node.js',
            r'\bMy\s+SQL\b': 'MySQL',
            r'\bNum\s+Py\b': 'NumPy',
            r'\bGit\s+Hub\b': 'GitHub',
            r'\bambda\b': 'Lambda',
            r'\bython\b': 'Python',
            r'\bful\s+APIs\b': 'RESTful APIs',
            r'\b([A-Z])\s+([a-z]+)\b': r'\1\2',  # "A WS" -> "AWS"
        }

        for pattern, replacement in word_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)    

        # Normalize Unicode dashes and quotes
        text = re.sub(r'[\u2013\u2014\u2015]', '-', text)  # Em/en dashes to hyphens
        text = re.sub(r'[\u2018\u2019]', "'", text)  # Smart quotes to straight
        text = re.sub(r'[\u201c\u201d]', '"', text)  # Smart double quotes    
        text = re.sub(r'[\u2022\u2023\u25e6\u2043\u2219]', 'ΓÇó', text)  # Normalize bullets

        # Preserve newlines after bullet points and section headers
        text = re.sub(r'(ΓÇó[^\n]*)', r'\1\n', text)  # Ensure newline after bullets
        text = re.sub(r'^([A-Z][A-Z\s]{3,}):?\s*$', r'\1\n', text, flags=re.MULTILINE)  # Section headers

        # Fix common spacing issues
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add space between camelCase
        text = re.sub(r'(\d{4})([A-Za-z])', r'\1 \2', text)  # Space after years
        text = re.sub(r'([a-z])([\(])', r'\1 \2', text)  # Space before parentheses

        # Fix email and phone formatting
        text = re.sub(r'([a-zA-Z0-9])@([a-zA-Z0-9])', r'\1@\2', text)  # Fix broken emails
        text = re.sub(r'(\d{3})\s+(\d{3})\s+(\d{4})', r'\1-\2-\3', text)  # Phone numbers

        # Normalize whitespace while preserving structure
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single      
        text = re.sub(r'\n[ \t]+', '\n', text)  # Remove leading whitespace on lines
        text = re.sub(r'[ \t]+\n', '\n', text)  # Remove trailing whitespace on lines
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines  

        return text.strip()

    # ------------------------------------------------------------------      
    # Post-processing helpers
    # ------------------------------------------------------------------      
    _TRAILING_LOCATION_RE = re.compile(r"\s*[-,|]\s*[A-Z][A-Za-z\s]{2,}$")    
    _SKILL_NORMALIZATION_MAP = {
        "git hub": "GitHub",
        "java script": "JavaScript",
        "num py": "NumPy",
        "my sql": "MySQL",
        "shell scripting": "Shell Scripting",
        "cdn caching": "CDN Caching",
        "(i18n)": "Internationalization",
    }

    def _post_process_resume(self, resume_data: ResumeData) -> None:
        """Cleanup and schema consistency adjustments."""
        # Ensure personal_info is the correct type (some extractors may provide a string)
        if not isinstance(resume_data.personal_info, PersonalInfo):
            try:
                # If it's a dict, convert; if it's a str, wrap into name field
                if isinstance(resume_data.personal_info, dict):
                    resume_data.personal_info = PersonalInfo(**resume_data.personal_info)
                else:
                    resume_data.personal_info = PersonalInfo(name=str(resume_data.personal_info))
            except Exception as conv_e:
                self.logger.warning(f"Failed to normalise personal_info type: {conv_e}")
        """Lightweight cleanup for education institutions and skill names.""" 
        # Education clean-up
        for edu in resume_data.education or []:
            if edu.institution:
                edu.institution = re.sub(self._TRAILING_LOCATION_RE, "", edu.institution).strip()
        # Skill normalisation & deduplication
        seen = set()
        cleaned_skills = []
        for skill in resume_data.skills or []:
            name = skill.name or ""
            cleaned = re.sub(r"[^a-z0-9\+\.\- ]", "", name.lower()).strip()   
            normalised = self._SKILL_NORMALIZATION_MAP.get(cleaned, name.strip())
            normalised = re.sub(r"\s+", " ", normalised).strip()
            if normalised.isupper() or len(normalised) <= 4:
                normalised = normalised.upper()
            if normalised.lower() not in seen:
                seen.add(normalised.lower())
                skill.name = normalised
                cleaned_skills.append(skill)
        resume_data.skills = cleaned_skills

    async def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            import docx2txt
            return docx2txt.process(file_path)
        except Exception as e:
            self.logger.error(f"docx2txt extraction failed: {e}")
            raise
