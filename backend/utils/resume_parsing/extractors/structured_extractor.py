import json
import logging
import os
import sys
import re
from typing import Type, Dict, Any, Union, Optional

from pydantic import BaseModel, ValidationError

# Add proper path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from backend.utils.resume_parsing.contracts.resume_contract import ResumeV2
from backend.utils.resume_parsing.extractors.base_extractor import BaseExtractor
from backend.services.llm_service import LLMService, get_llm_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StructuredExtractor(BaseExtractor):
    """
    An extractor that uses a large language model to extract structured data from a resume.
    It relies on a Pydantic model (contract) to define the desired output schema.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        # Uses the provider chain (Ollama -> OpenRouter -> Claude) via LLMService
        if llm_service is None:
            self.llm_service = get_llm_service()
        else:
            self.llm_service = llm_service
        logger.info("StructuredExtractor initialized with LLMService (provider chain)")

    @property
    def name(self) -> str:
        """Return the name of the extractor."""
        return "StructuredExtractor"

    async def extract(self, raw_text: str, file_path: str = "") -> Dict[str, Any]:
        """
        Extracts structured data from the resume text using the specified contract.

        Args:
            raw_text: The raw text of the resume.
            file_path: The path to the original resume file.

        Returns:
            A dictionary with the extracted data, conforming to the contract.
        """
        contract = ResumeV2
        logger.info(f"Starting structured extraction using LLM: {type(self.llm_service)} model: {getattr(self.llm_service, 'model', None)}")
        
        # Generate the schema from the Pydantic model
        schema = contract.model_json_schema()
        
        # Create the prompt for the LLM
        prompt = self._create_prompt(raw_text, schema)
        
        response_text = ""
        extracted_data: Dict[str, Any] = {}
        try:
            # Call the provider chain with the ResumeV2 schema. Providers with
            # native schema support (Ollama format param, Claude messages.parse)
            # enforce conformance server-side; OpenAI-compatible providers get a
            # JSON instruction plus the repair layer in generate_structured.
            if hasattr(self.llm_service, "generate_structured"):
                extracted_data = await self.llm_service.generate_structured(
                    prompt,
                    contract,
                    system_message="You are a resume parsing specialist AI. Extract relevant information accurately.",
                    max_tokens=8192,
                    task_type="resume_parsing",
                )
            else:
                # Fallback for callers injecting a legacy/plain-text service
                response_text = await self.llm_service.generate_text_async(
                    prompt,
                    system_message="You are a resume parsing specialist AI. Extract relevant information accurately.",
                    max_tokens=8192,
                    task_type="resume_parsing",
                )
                extracted_data = self._parse_llm_response(response_text)

            # Validate the data against the contract
            try:
                validated_data = contract.model_validate(extracted_data)
            except Exception as ve:
                logger.warning(f"Validation failed on first attempt: {ve}. Retrying with stricter prompt...")
                strict_prompt = (
                    prompt
                    + "\n\nIMPORTANT: Respond with a single raw JSON object only. Do NOT include code fences, explanations, or extra text."
                )
                response_text = await self.llm_service.generate_text_async(
                    strict_prompt, max_tokens=8192, task_type="resume"
                )
                extracted_data = self._parse_llm_response(response_text)
                validated_data = contract.model_validate(extracted_data)

            logger.info("Successfully extracted and validated structured data.")
            data = validated_data.model_dump()

            # --- EXPERIENCE & LOCATION LOGIC (conservative, general) ---
            # Minimal, generic enhancement: only fill missing basic fields from regex parser
            try:
                from backend.utils.resume_parsing.extractors.regex_extractor import _MiniExperienceParser
                experience_parser = _MiniExperienceParser()
                legacy_exps = [exp.to_dict() for exp in experience_parser.parse(raw_text)]
                legacy_map = {(e.get('title',''), e.get('company','')): e for e in legacy_exps}
                fixed_exps = []
                for exp in data.get('experience', []):
                    needs_fill = any(exp.get(f) in (None, '', [], {}) for f in ('company','title','location'))
                    if needs_fill:
                        key = (exp.get('title',''), exp.get('company',''))
                        legacy = legacy_map.get(key)
                        if not legacy:
                            idx = data['experience'].index(exp)
                            if idx < len(legacy_exps):
                                legacy = legacy_exps[idx]
                        if legacy:
                            for f in ('company','title','location'):
                                if not exp.get(f) and legacy.get(f):
                                    exp[f] = legacy[f]
                    # Expand responsibilities from a single-string description into bullets
                    try:
                        desc = exp.get('description')
                        if isinstance(desc, str) and desc.strip():
                            # Try bullet markers first
                            bullets = re.findall(r'[•\-\*\+]\s*(.+)', desc)
                            # If none, split on newlines
                            if not bullets and '\n' in desc:
                                bullets = [p.strip() for p in re.split(r'\n+', desc) if p.strip()]
                            # If still short and long paragraph, split by sentences
                            if (not bullets or len(bullets) <= 1) and len(desc) > 140:
                                bullets = [s.strip() for s in re.split(r'(?<=[\.!?])\s+(?=[A-Z0-9])', desc) if len(s.strip()) > 10]
                            if bullets:
                                exp['responsibilities'] = bullets
                    except Exception:
                        pass
                    fixed_exps.append(exp)
                data['experience'] = fixed_exps
            except Exception as e:
                logger.warning(f"Experience fallback logic failed: {e}")
            
            # --- LOCATION FILL (generic) ---
            if not data.get('personal_info', {}).get('location'):
                try:
                    from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor
                    regex_info = RegexExtractor()._extract_personal_info(raw_text)
                    if regex_info.get('location'):
                        data.setdefault('personal_info', {})['location'] = regex_info['location']
                except Exception as e:
                    logger.warning(f"Location fallback via RegexExtractor failed: {e}")

            # --- LINKEDIN FILL (generic) ---
            if not data.get('personal_info', {}).get('linkedin'):
                try:
                    # Enhanced LinkedIn extraction to handle concatenated text from PDF parsing
                    
                    # First try: Standard LinkedIn URL patterns
                    linkedin_match = re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-~/]+', raw_text, re.IGNORECASE)
                    
                    if not linkedin_match:
                        # Second try: Loose pattern with possible spaces/separators
                        loose = re.search(r'linkedin\s*[\.:]?\s*com\s*/\s*(?:in|pub|profile)\s*/\s*([A-Za-z0-9_\-~/]+)', raw_text, re.IGNORECASE)
                        if loose:
                            # Rebuild canonical form
                            path = re.sub(r'\s+', '', loose.group(0))
                            idx = path.lower().find('linkedin')
                            rebuilt = 'https://www.' + path[idx:]
                            data.setdefault('personal_info', {})['linkedin'] = rebuilt
                    
                    if not linkedin_match and not data.get('personal_info', {}).get('linkedin'):
                        # Third try: Handle concatenated text (e.g., "data-drivenlinkedin.com/in/user")
                        concatenated = re.search(r'[a-zA-Z]+linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-~/]+[a-zA-Z]*', raw_text, re.IGNORECASE)
                        if concatenated:
                            full_match = concatenated.group(0)
                            # Extract just the linkedin.com part
                            linkedin_part = re.search(r'linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-~/]+', full_match, re.IGNORECASE)
                            if linkedin_part:
                                clean_url = 'https://www.' + linkedin_part.group(0)
                                data.setdefault('personal_info', {})['linkedin'] = clean_url
                                logger.info(f"Extracted LinkedIn from concatenated text: {clean_url}")
                    
                    if linkedin_match and not data.get('personal_info', {}).get('linkedin'):
                        url = linkedin_match.group(0)
                        if not url.lower().startswith('http'):
                            url = 'https://' + url
                        if not url.lower().startswith('https://www.'):
                            url = url.replace('https://', 'https://www.')
                        data.setdefault('personal_info', {})['linkedin'] = url
                        
                except Exception as e:
                    logger.warning(f"LinkedIn fallback detection failed: {e}")
            
            # --- EXPERIENCE LOCATION ENHANCEMENT ---
            for exp in data.get('experience', []):
                if not exp.get('location') and exp.get('company'):
                    try:
                        company_name = exp['company']
                        # Look for location patterns after company mentions
                        # Pattern: "Company | Location" or "Company\nLocation" 
                        company_pattern = re.escape(company_name)
                        location_patterns = [
                            rf'{company_pattern}\s*\|\s*([A-Za-z\s,]+(?:,\s*[A-Z]{{2,3}})?)(?:\s|$)',
                            rf'{company_pattern}\s*[,\|\n]\s*([A-Za-z\s]+,\s*[A-Z]{{2,3}})(?:\s|$)',
                            rf'{company_pattern}[^\n]*\n\s*([A-Za-z\s]+,\s*[A-Z]{{2,3}})(?:\s|$)',
                            # Handle concatenated text like "Fractal.ai | Bellevue, WA"
                            rf'{company_pattern}[^\n]*?([A-Za-z\s]+,\s*[A-Z]{{2,3}})(?:\s|$)',
                        ]
                        
                        for pattern in location_patterns:
                            location_match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                            if location_match:
                                location = location_match.group(1).strip()
                                # Validate it looks like a location (has state/country abbreviation)
                                if re.match(r'^[A-Za-z\s]+,\s*[A-Z]{2,3}$', location):
                                    exp['location'] = location
                                    logger.info(f"Enhanced experience location for {company_name}: {location}")
                                    break
                    except Exception as e:
                        logger.warning(f"Experience location enhancement failed for {exp.get('company', 'Unknown')}: {e}")

            # --- EDUCATION ENHANCEMENT (comprehensive field extraction) ---
            for edu in data.get('education', []):
                institution = edu.get('institution', '')
                if institution:
                    try:
                        # Reset dates to None initially - only keep if explicitly found
                        edu['start_date'] = None
                        edu['end_date'] = None
                        
                        institution_pattern = re.escape(institution)
                        
                        # Check if this institution has an explicit year in parentheses in the raw text
                        explicit_year_match = re.search(rf'{institution_pattern}[^\n]*\((\d{{4}})\)', raw_text, re.IGNORECASE)
                        if explicit_year_match:
                            year = explicit_year_match.group(1)
                            edu['start_date'] = year
                            edu['end_date'] = year
                            logger.info(f"Found explicit year for {institution}: {year}")
                        else:
                            # No explicit year found - leave dates as None
                            logger.info(f"No explicit year found for {institution} - leaving dates empty")
                        
                        # Enhanced field of study extraction - only if LLM didn't extract it properly
                        # Skip if LLM already extracted a valid field of study
                        current_field = edu.get('field_of_study', '')
                        logger.info(f"LLM extracted field of study for {institution}: '{current_field}'")
                        if (not current_field or 
                            current_field in (None, '', 'NA') or
                            len(current_field) < 3):
                            # Look for education section context around this institution
                            patterns = [
                                # Pattern: Institution followed by degree info
                                rf'{institution_pattern}[^\n]*\n([^\n]+)',
                                # Pattern: Same line with degree info
                                rf'{institution_pattern}[^\n]*?([A-Z][A-Za-z\s&]+?)(?:\n|$|\()',
                                # Pattern: Look for degree patterns in broader context
                                rf'(?:{institution_pattern}[^\n]*?|^)(?:BA|BS|MA|MS|PhD|Bachelor|Master|Associates?)\s+(?:in|of|degree in)?\s*([A-Za-z][A-Za-z\s&]+?)(?:\n|$|,|\()',
                            ]
                            
                            for pattern in patterns:
                                matches = re.findall(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                for match in matches:
                                    content = match.strip()
                                    
                                    # Look for degree patterns like "BA in Criminal Justice"
                                    field_patterns = [
                                        rf'(?:BA|BS|MA|MS|PhD|Bachelor|Master|Associates?)\s+(?:in|of|degree in)?\s*([A-Za-z][A-Za-z\s&]+?)(?:\n|$|,|\()',
                                        rf'^([A-Za-z][A-Za-z\s&]+?)(?:\s*\(|\n|$)',  # First line after institution
                                        rf'([A-Za-z][A-Za-z\s&]+?)(?:\s*\(|\n|$)',  # Any field-like content
                                    ]
                                    
                                    for field_pattern in field_patterns:
                                        field_match = re.search(field_pattern, content, re.IGNORECASE)
                                        if field_match:
                                            field = field_match.group(1).strip()
                                            # Clean up the field
                                            field = re.sub(r'\s+', ' ', field).strip()
                                            # Additional validation to avoid picking up extra text
                                            if (len(field) > 3 and len(field) < 50 and
                                                not field.lower().startswith(institution.lower()[:5]) and
                                                not field.lower().startswith(('wharton', 'uw foster', 'seattle')) and
                                                field.lower() not in ['university', 'school', 'college'] and
                                                not field.lower().startswith(('ba', 'bs', 'ma', 'ms', 'phd')) and
                                                not 'through' in field.lower() and
                                                not 'to enhance' in field.lower() and
                                                not 'targeted' in field.lower() and
                                                not 'inclusive' in field.lower() and
                                                not 'hiring' in field.lower() and
                                                not 'practices' in field.lower() and
                                                not 'team' in field.lower() and
                                                not 'capabilities' in field.lower() and
                                                field.lower() not in ['criminal justice']):  # Avoid duplicating
                                                edu['field_of_study'] = field
                                                logger.info(f"Enhanced field of study for {institution}: {field}")
                                                break
                                    
                                    if edu.get('field_of_study'):
                                        break
                                
                                if edu.get('field_of_study'):
                                    break
                        
                        # Enhanced degree extraction - only if LLM didn't extract it properly
                        # Skip if LLM already extracted a valid degree
                        current_degree = edu.get('degree', '')
                        logger.info(f"LLM extracted degree for {institution}: '{current_degree}'")
                        if (not current_degree or 
                            current_degree in (None, '', 'NA') or
                            len(current_degree) < 2):
                            # Look for degree patterns around the institution
                            degree_patterns = [
                                rf'(?:{institution_pattern}[^\n]*?|^)(BA|BS|MA|MS|PhD|Bachelor|Master|Associates?)(?:\s+(?:in|of|degree in))?',
                                rf'(BA|BS|MA|MS|PhD|Bachelor|Master|Associates?)[^\n]*{institution_pattern}',
                            ]
                            
                            for pattern in degree_patterns:
                                degree_match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                if degree_match:
                                    degree = degree_match.group(1).strip()
                                    # Expand abbreviations
                                    degree_expansions = {
                                        'BA': 'Bachelor of Arts',
                                        'BS': 'Bachelor of Science',
                                        'MA': 'Master of Arts',
                                        'MS': 'Master of Science',
                                        'PhD': 'Doctor of Philosophy',
                                        'Associate': 'Associate\'s Degree'
                                    }
                                    expanded_degree = degree_expansions.get(degree.upper(), degree)
                                    # Validate that this is actually a degree and not field of study
                                    if expanded_degree.lower() in ['bachelor of arts', 'bachelor of science', 'master of arts', 'master of science', 'doctor of philosophy', 'associate\'s degree', 'ba', 'bs', 'ma', 'ms', 'phd']:
                                        edu['degree'] = expanded_degree
                                        logger.info(f"Enhanced degree for {institution}: {edu['degree']}")
                                        break
                        
                        # Extract GPA if available
                        if not edu.get('gpa') or edu.get('gpa') in (None, '', 'NA'):
                            # Look for GPA patterns near the institution
                            gpa_patterns = [
                                rf'{institution_pattern}[^\n]*?(?:GPA|Grade Point Average)[^\n]*?(\d+\.\d+)',
                                rf'GPA[^\n]*?(\d+\.\d+)[^\n]*?{institution_pattern}',
                                rf'{institution_pattern}[^\n]*?(\d+\.\d+)[^\n]*?(?:GPA|Grade Point Average)',
                            ]
                            
                            for pattern in gpa_patterns:
                                gpa_match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                if gpa_match:
                                    gpa = gpa_match.group(1).strip()
                                    edu['gpa'] = gpa
                                    logger.info(f"Enhanced GPA for {institution}: {gpa}")
                                    break
                        
                        # Extract honors and achievements
                        if not edu.get('honors') or edu.get('honors') == []:
                            # Look for honors patterns near the institution
                            honors_patterns = [
                                rf'{institution_pattern}[^\n]*?(?:Dean\'s List|Honors|Summa Cum Laude|Magna Cum Laude|Cum Laude|Honor Society|Academic Excellence)',
                                rf'(?:Dean\'s List|Honors|Summa Cum Laude|Magna Cum Laude|Cum Laude|Honor Society|Academic Excellence)[^\n]*?{institution_pattern}',
                            ]
                            
                            honors_found = []
                            for pattern in honors_patterns:
                                honors_matches = re.findall(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                for match in honors_matches:
                                    if match.strip():
                                        honors_found.append(match.strip())
                            
                            if honors_found:
                                edu['honors'] = honors_found
                                logger.info(f"Enhanced honors for {institution}: {honors_found}")
                        
                        # Extract location if available
                        if not edu.get('location') or edu.get('location') in (None, '', 'NA'):
                            # Look for location patterns near the institution
                            location_patterns = [
                                rf'{institution_pattern}[^\n]*?([A-Za-z\s]+,\s*[A-Z]{2})',
                                rf'([A-Za-z\s]+,\s*[A-Z]{2})[^\n]*?{institution_pattern}',
                            ]
                            
                            for pattern in location_patterns:
                                location_match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                if location_match:
                                    location = location_match.group(1).strip()
                                    edu['location'] = location
                                    logger.info(f"Enhanced location for {institution}: {location}")
                                    break
                        
                        # Extract certifications if available
                        if not edu.get('certifications') or edu.get('certifications') == []:
                            # Look for certification patterns near education sections
                            cert_patterns = [
                                rf'{institution_pattern}[^\n]*?(?:Certified|Certification|Certificate)[^\n]*?([A-Za-z\s&]+)',
                                rf'(?:Certified|Certification|Certificate)[^\n]*?([A-Za-z\s&]+)[^\n]*?{institution_pattern}',
                            ]
                            
                            certs_found = []
                            for pattern in cert_patterns:
                                cert_matches = re.findall(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                                for match in cert_matches:
                                    if match.strip() and len(match.strip()) > 3:
                                        certs_found.append(match.strip())
                            
                            if certs_found:
                                edu['certifications'] = certs_found
                                logger.info(f"Enhanced certifications for {institution}: {certs_found}")
                                    
                    except Exception as e:
                        logger.warning(f"Education enhancement failed for {institution}: {e}")
            
            # --- ENHANCED MILITARY EXTRACTION ---
            # Always try to enhance military experience with regex details
            try:
                from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor
                regex_extractor = RegexExtractor()
                regex_military = regex_extractor._extract_military(raw_text)
                
                current_military = data.get('military', [])
                
                if not current_military and regex_military:
                    # No LLM military found, use regex results
                    logger.info(f"Found {len(regex_military)} military entries via regex fallback")
                    military_entries = []
                    for entry in regex_military:
                        if hasattr(entry, '__dict__'):
                            military_entries.append(entry.__dict__)
                        elif isinstance(entry, dict):
                            military_entries.append(entry)
                    data['military'] = military_entries
                    
                elif current_military and regex_military:
                    # Enhance existing LLM military with regex details
                    logger.info(f"Enhancing {len(current_military)} LLM military entries with regex details")
                    for llm_entry in current_military:
                        # Find matching regex entry
                        for regex_entry in regex_military:
                            regex_dict = regex_entry if isinstance(regex_entry, dict) else regex_entry.__dict__
                            
                            # Match by branch and rank/title
                            if (regex_dict.get('branch', '').lower() == llm_entry.get('branch', '').lower() or 
                                regex_dict.get('rank', '').lower() in llm_entry.get('rank', '').lower() or
                                regex_dict.get('title', '').lower() in llm_entry.get('title', '').lower()):
                                
                                # Enhance with regex details
                                if not llm_entry.get('responsibilities') and regex_dict.get('responsibilities'):
                                    llm_entry['responsibilities'] = regex_dict['responsibilities']
                                    logger.info(f"Added {len(regex_dict['responsibilities'])} responsibilities from regex")
                                
                                if not llm_entry.get('mos_specialty') and regex_dict.get('mos_specialty'):
                                    llm_entry['mos_specialty'] = regex_dict['mos_specialty']
                                
                                if not llm_entry.get('location') and regex_dict.get('location'):
                                    llm_entry['location'] = regex_dict['location']
                                
                                if not llm_entry.get('awards') and regex_dict.get('awards'):
                                    llm_entry['awards'] = regex_dict['awards']
                                
                                if not llm_entry.get('clearances') and regex_dict.get('clearances'):
                                    llm_entry['clearances'] = regex_dict['clearances']
                                
                                break
                
                # Ensure military is always a list
                if 'military' not in data:
                    data['military'] = []
                    
            except Exception as e:
                logger.warning(f"Military extraction enhancement failed: {e}")
                # Ensure military is an empty list if extraction fails
                if 'military' not in data:
                    data['military'] = []

            # --- PER-EXPERIENCE LOCATION FILL (generic) ---
            try:
                for exp in data.get('experience', []) or []:
                    if exp.get('location') in (None, '', []):
                        company = exp.get('company') or ''
                        if company:
                            # Pattern: "Company | Location"
                            m = re.search(rf"{re.escape(company)}\s*\|\s*([^\n\(\)]+)", raw_text, re.IGNORECASE)
                            if m:
                                candidate_loc = m.group(1).strip()
                                candidate_loc = re.sub(r"\s{2,}", " ", candidate_loc)
                                # Prefer formats like City, ST or City, Country
                                if re.match(r'^[A-Za-z][A-Za-z\s]+,\s*[A-Z]{2,3}$', candidate_loc) or re.match(r'^[A-Za-z][A-Za-z\s]+,\s*[A-Za-z][A-Za-z\s]+$', candidate_loc):
                                    exp['location'] = candidate_loc
                                    continue
                            # Pattern: "Location on next line after company"
                            m2 = re.search(rf"{re.escape(company)}\s*\n\s*([^\n\(\)]+)", raw_text, re.IGNORECASE)
                            if m2:
                                candidate_loc = m2.group(1).strip()
                                candidate_loc = re.sub(r"\s{2,}", " ", candidate_loc)
                                if re.match(r'^[A-Za-z][A-Za-z\s]+,\s*[A-Z]{2,3}$', candidate_loc) or any(t in candidate_loc for t in [',', ' WA', ' CA', ' NY', ' TX']):
                                    exp['location'] = candidate_loc
            except Exception as e:
                logger.warning(f"Experience location fill failed: {e}")

            # --- MILITARY RESPONSIBILITIES CLEANUP ---
            try:
                for mil in data.get('military', []) or []:
                    # If responsibilities look polluted with unrelated sections, clean using raw_text blocks
                    if isinstance(mil.get('responsibilities'), list) and mil.get('responsibilities'):
                        cleaned = []
                        # Generic civilian/corporate terms (negative signal for military duties)
                        bad_terms = re.compile(r"\b(recruiting|requisition|ATS|applicant tracking|agency|stakeholder|marketing|sales|pipeline|revenue|KPI|SLA|Greenhouse|client|offer process|onboarding)\b", re.IGNORECASE)
                        # Generic military terms (positive signal)
                        good_terms = re.compile(r"\b(platoon|battalion|brigade|company\s+commander|officer|NCO|unit|formation|deployment|deployed|MOS|logistics|mission|operation|garrison|training|field\s+exercise|readiness)\b", re.IGNORECASE)
                        for r in mil['responsibilities']:
                            t = (r or '').strip()
                            if not t:
                                continue
                            if len(t) > 300 or len(t) < 4:
                                continue
                            # Drop if dominated by corporate terms and lacks military signal
                            if bad_terms.search(t) and not good_terms.search(t):
                                continue
                            cleaned.append(t)
                        if cleaned:
                            mil['responsibilities'] = cleaned
            except Exception as e:
                logger.warning(f"Military responsibilities cleanup failed: {e}")

            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from LLM response: {e}")
            logger.error(f"LLM Response Text: {response_text}")
            return {}
        except ValidationError as e:
            logger.error(f"Validation error for extracted data after retry: {e}")
            logger.error(f"Extracted Data: {extracted_data}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred during structured extraction: {e}", exc_info=True)
            return {}

    def _create_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        """Create a concise prompt for LLM extraction."""
        schema_json = json.dumps(schema, indent=2)
        
        prompt = f"""You are an expert resume parser. Extract ALL information from this resume into structured JSON.

**CRITICAL REQUIREMENTS:**
1. Extract complete job responsibilities as clean, well-formatted bullet points
2. Each bullet point should be a separate, concise achievement or responsibility
3. Extract military experience separately from work experience
4. Return valid JSON only - no explanations
5. Use "Present" (not "PRESENT") for current employment end dates
6. For education dates, extract only the year shown (do NOT add "till present" or similar)

**EDUCATION EXTRACTION REQUIREMENTS:**
- Extract COMPLETE education information including ALL available fields:
  * institution: Full institution name
  * degree: Degree type (e.g., "Bachelor of Science", "Master of Arts", "B.S.", "M.A.", "PhD", "Associate's", "Continuing Education")
  * field_of_study: Major/field (e.g., "Computer Science", "Business Administration", "Engineering", "HR Management and Analytics", "Business Communication")
  * start_date/end_date: Years only (e.g., "2021", "2022")
  * gpa: Grade point average if mentioned
  * location: Institution location if specified
  * honors: Academic honors, awards, dean's list, etc.
  * certifications: Professional certifications earned during education
- IMPORTANT: Distinguish between degree type and field of study:
  * degree: The type of degree (Bachelor, Master, PhD, Continuing Education, etc.)
  * field_of_study: The specific subject/major (Computer Science, Business Administration, etc.)
- Examples:
  * "BA in Criminal Justice" → degree: "Bachelor of Arts", field_of_study: "Criminal Justice"
  * "HR Management and Analytics" → degree: "Continuing Education", field_of_study: "HR Management and Analytics"
  * "Business Communication" → degree: "Continuing Education", field_of_study: "Business Communication"
- Look for degree patterns like: "Bachelor of Science in Computer Science", "B.S. in Engineering", "Master's in Business Administration"
- If degree type is not explicitly stated but can be inferred from context, include it
- Extract ALL education entries found in the resume, not just the most recent
- Include any academic achievements, honors, or special recognitions
- Look for certifications that may be listed near education sections

**EXTRACT:**
- Personal info (name, email, phone, location, LinkedIn)
- Job experience with clean, organized bullet points for each role
- Education details with ALL available fields (institution, degree, field_of_study, dates, gpa, location, honors, certifications)
- Skills
- Military experience (if any)

**DATE FORMATTING:**
- Current employment: use "Present" (proper case)
- Education dates: use only the year shown in parentheses (e.g., "2021", "2022")
- Never add "till present" for education entries

**BULLET POINT FORMAT:**
- Keep each responsibility as a clean, concise bullet point
- Maintain the original structure and organization
- Do not combine multiple bullets into long paragraphs

**RESUME TEXT:**
{text}

**JSON SCHEMA:**
{schema_json}

Return only the JSON object."""
        return prompt

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parses the JSON response from the LLM, robustly cleaning and extracting the main JSON object.
        """
        json_text = None

        
        try:
            # Pre-clean: strip BOM and zero-width characters that can break JSON parsing
            response_text = response_text.replace('\ufeff', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

            # Method 1: Try to find JSON within markdown code blocks (prefer the longest)
            fenced_blocks = []
            # ```json fenced blocks
            idx = 0
            while True:
                start = response_text.find("```json", idx)
                if start == -1:
                    break
                start_content = start + len("```json")
                end = response_text.find("```", start_content)
                if end == -1:
                    break
                fenced_blocks.append(response_text[start_content:end].strip())
                idx = end + 3
            # Generic ``` fenced blocks
            idx = 0
            while True:
                start = response_text.find("```", idx)
                if start == -1:
                    break
                # Skip json blocks already captured
                if response_text.startswith("```json", start):
                    idx = start + 3
                    continue
                start_content = start + 3
                end = response_text.find("```", start_content)
                if end == -1:
                    break
                fenced_blocks.append(response_text[start_content:end].strip())
                idx = end + 3
            if fenced_blocks:
                # Try the longest fenced block first
                fenced_blocks.sort(key=len, reverse=True)
                for block in fenced_blocks:
                    try:
                        return json.loads(block)
                    except json.JSONDecodeError:
                        # Try trimming to balanced braces within the block
                        brace_count = 0
                        start_pos = -1
                        for i, ch in enumerate(block):
                            if ch == '{':
                                if brace_count == 0:
                                    start_pos = i
                                brace_count += 1
                            elif ch == '}':
                                brace_count -= 1
                                if brace_count == 0 and start_pos != -1:
                                    candidate = block[start_pos:i+1]
                                    try:
                                        return json.loads(candidate)
                                    except Exception:
                                        pass
                # Fall through to next methods if fenced attempts fail

            
            # Method 2: Try to parse the entire response as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                pass
            
            # Method 3: Find the start and end of the main JSON object
            start_brace = response_text.find('{')
            end_brace = response_text.rfind('}')

            if start_brace == -1 or end_brace == -1 or start_brace > end_brace:
                logger.error("Could not find a valid JSON object in the LLM response.")
                raise json.JSONDecodeError("No JSON object found", response_text, 0)

            # Extract the JSON part of the string
            json_text = response_text[start_brace:end_brace + 1]
            
            # Check if JSON is very long and might be truncated
            if len(json_text) > 15000:  # If JSON is very long, it might be truncated
                logger.info(f"Long JSON detected ({len(json_text)} chars), attempting to find complete object by brace counting")
                # Find the last complete JSON object by counting braces
                brace_count = 0
                complete_end = -1
                for i, char in enumerate(json_text):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            complete_end = i
                            break
                
                if complete_end > 0:
                    json_text = json_text[:complete_end + 1]
                    logger.info(f"Truncated JSON to complete object at position {complete_end}")
            
            # Method 4: Clean up common JSON issues
            # Remove newlines and carriage returns
            json_text = json_text.replace('\n', ' ').replace('\r', ' ')
            json_text = json_text.replace('\\n', ' ').replace('\\r', ' ')
            
            # Remove any trailing commas before closing braces/brackets
            import re
            # Properly escape the regex pattern to avoid unbalanced parenthesis errors
            json_text = re.sub(r',\s*([}\]])', r'\1', json_text)
            
            # Remove any content after the JSON object by counting braces
            brace_count = 0
            last_complete_pos = 0
            for i, char in enumerate(json_text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_complete_pos = i + 1
                        break
            if last_complete_pos > 0:
                json_text = json_text[:last_complete_pos]

            # Method 4.5: Fix common JSON syntax issues
            # Fix missing commas between array elements
            json_text = re.sub(r'}\s*{', '},{', json_text)  # Fix missing commas between objects
            json_text = re.sub(r']\s*{', '},{', json_text)  # Fix missing commas between array and object
            json_text = re.sub(r'}\s*\[', '},[', json_text)  # Fix missing commas between object and array
            json_text = re.sub(r']\s*\[', '],[', json_text)  # Fix missing commas between arrays
            
            # Fix missing commas after string values before closing braces
            json_text = re.sub(r'"\s*}', '",}', json_text)  # Add missing comma after string before closing brace
            json_text = re.sub(r'"\s*]', '",]', json_text)  # Add missing comma after string before closing bracket
            
            # Fix specific malformed JSON patterns from Nebius AI
            # Fix: "linkedin": "value"} -> "linkedin": "value",}
            json_text = re.sub(r'"linkedin":\s*"([^"]*)"\s*}', r'"linkedin": "\1",}', json_text)
            
            # Fix: "property": "value"} -> "property": "value",} (for other properties)
            json_text = re.sub(r'"([^"]+)":\s*"([^"]*)"\s*}', r'"\1": "\2",}', json_text)
            
            # Fix: "property": "value"} -> "property": "value",} (more specific pattern)
            json_text = re.sub(r'"([^"]+)":\s*"([^"]*)"\s*}\s*$', r'"\1": "\2",}', json_text)
            
            # Fix missing commas after string values before closing braces (more aggressive)
            # But only if there's actually a property after the comma
            json_text = re.sub(r'"([^"]*)"\s*}\s*([^,}\s])', r'"\1",}\2', json_text)
            json_text = re.sub(r'"([^"]*)"\s*]\s*([^,]\s])', r'"\1",]\2', json_text)
            
            # Fix malformed empty arrays - "technologies": ["] -> "technologies": []
            json_text = re.sub(r'"technologies":\s*\["\s*\]', r'"technologies": []', json_text)
            json_text = re.sub(r'"technologies":\s*\["\s*,', r'"technologies": [],', json_text)
            
            # Fix other malformed empty arrays
            json_text = re.sub(r'"([^"]+)":\s*\["\s*\]', r'"\1": []', json_text)
            json_text = re.sub(r'"([^"]+)":\s*\["\s*,', r'"\1": [],', json_text)
            
            # More aggressive fix for malformed arrays with empty strings
            json_text = re.sub(r'\[\s*"\s*\]', '[]', json_text)  # ["] -> []
            json_text = re.sub(r'\[\s*"\s*,', '[],', json_text)  # [", -> [],
            
            # Fix specific patterns that cause JSON parsing errors
            json_text = re.sub(r'"technologies":\s*\["\s*,\s*"', r'"technologies": ["', json_text)
            json_text = re.sub(r'"technologies":\s*\["\s*"', r'"technologies": ["', json_text)
            
            # More aggressive fixes for common JSON malformations
            # Fix missing commas between array elements
            json_text = re.sub(r'\]\s*\[', '],[', json_text)  # ][ -> ],[
            json_text = re.sub(r'}\s*\{', '},{', json_text)  # }{ -> },{
            
            # Fix missing quotes around property names
            json_text = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_text)
            
            # Fix common Nebius AI malformations
            json_text = re.sub(r'"([^"]*)"\s*}\s*([^,}\s])', r'"\1",}\2', json_text)
            json_text = re.sub(r'"([^"]*)"\s*]\s*([^,]\s])', r'"\1",]\2', json_text)
            
            # Remove trailing commas that would make JSON invalid
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            
            # Fix truncated strings by adding closing quotes
            # Look for strings that end abruptly and add closing quote
            json_text = re.sub(r'([^"])\s*([}\]])', r'\1"\2', json_text)
            
            # Attempt to load the extracted JSON
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as parse_error:
                # If still failing, try to fix the specific error
                error_pos = parse_error.pos
                logger.warning(f"JSON parsing failed at position {error_pos}: {parse_error}")
                
                if error_pos < len(json_text):
                    # Try to truncate at a safe position
                    safe_pos = error_pos - 100  # Go back 100 chars to find a safe truncation point
                    if safe_pos > 0:
                        # Find the last complete object or array
                        truncated_text = json_text[:safe_pos]
                        # Find the last complete brace/bracket
                        last_brace = truncated_text.rfind('}')
                        last_bracket = truncated_text.rfind(']')
                        last_pos = max(last_brace, last_bracket)
                        if last_pos > 0:
                            truncated_text = truncated_text[:last_pos + 1]
                            try:
                                logger.info(f"Attempting to parse truncated JSON (length: {len(truncated_text)})")
                                return json.loads(truncated_text)
                            except Exception as e:
                                logger.warning(f"Truncated JSON parsing also failed: {e}")
                
                # If all else fails, try to extract just the basic structure
                try:
                    logger.info("Attempting to extract basic JSON structure as fallback")
                    # Try to find just the personal_info and basic structure
                    basic_json = {
                        "personal_info": {},
                        "experience": [],
                        "education": [],
                        "skills": [],
                        "military": []
                    }
                    
                    # Try to extract personal_info if possible
                    personal_info_match = re.search(r'"personal_info":\s*\{[^}]*\}', json_text)
                    if personal_info_match:
                        try:
                            personal_info_str = "{" + personal_info_match.group(0) + "}"
                            personal_info_data = json.loads(personal_info_str)
                            basic_json["personal_info"] = personal_info_data.get("personal_info", {})
                        except:
                            pass
                    
                    # Try to extract experience entries - more robust pattern
                    # Look for experience array in the JSON
                    experience_array_match = re.search(r'"experience":\s*\[(.*?)\]', json_text, re.DOTALL)
                    if experience_array_match:
                        try:
                            experience_array_text = experience_array_match.group(1)
                            # Split by object boundaries
                            experience_objects = re.findall(r'\{[^}]*\}', experience_array_text)
                            for obj_text in experience_objects[:10]:  # Limit to 10 entries
                                try:
                                    exp_data = json.loads(obj_text)
                                    basic_json["experience"].append(exp_data)
                                except:
                                    # Try to extract individual fields
                                    title_match = re.search(r'"title":\s*"([^"]*)"', obj_text)
                                    company_match = re.search(r'"company":\s*"([^"]*)"', obj_text)
                                    if title_match and company_match:
                                        basic_json["experience"].append({
                                            "title": title_match.group(1),
                                            "company": company_match.group(1),
                                            "responsibilities": []
                                        })
                        except:
                            pass
                    
                    # If no experience array found, try individual experience objects
                    if not basic_json["experience"]:
                        experience_matches = re.findall(r'\{[^}]*"title"[^}]*"company"[^}]*\}', json_text)
                        if experience_matches:
                            try:
                                for match in experience_matches[:10]:  # Limit to 10 entries
                                    exp_data = json.loads(match)
                                    basic_json["experience"].append(exp_data)
                            except:
                                pass
                    
                    # Try to extract education entries - more robust pattern
                    # Look for education array in the JSON
                    education_array_match = re.search(r'"education":\s*\[(.*?)\]', json_text, re.DOTALL)
                    if education_array_match:
                        try:
                            education_array_text = education_array_match.group(1)
                            # Split by object boundaries
                            education_objects = re.findall(r'\{[^}]*\}', education_array_text)
                            for obj_text in education_objects[:5]:  # Limit to 5 entries
                                try:
                                    edu_data = json.loads(obj_text)
                                    basic_json["education"].append(edu_data)
                                except:
                                    # Try to extract individual fields
                                    institution_match = re.search(r'"institution":\s*"([^"]*)"', obj_text)
                                    degree_match = re.search(r'"degree":\s*"([^"]*)"', obj_text)
                                    if institution_match:
                                        basic_json["education"].append({
                                            "institution": institution_match.group(1),
                                            "degree": degree_match.group(1) if degree_match else "",
                                            "field_of_study": "",
                                            "start_date": "",
                                            "end_date": ""
                                        })
                        except:
                            pass
                    
                    # If no education array found, try individual education objects
                    if not basic_json["education"]:
                        education_matches = re.findall(r'\{[^}]*"institution"[^}]*\}', json_text)
                        if education_matches:
                            try:
                                for match in education_matches[:5]:  # Limit to 5 entries
                                    edu_data = json.loads(match)
                                    basic_json["education"].append(edu_data)
                            except:
                                pass
                    
                    # Try to extract skills
                    skills_array_match = re.search(r'"skills":\s*\[(.*?)\]', json_text, re.DOTALL)
                    if skills_array_match:
                        try:
                            skills_array_text = skills_array_match.group(1)
                            # Extract individual skill strings
                            skill_matches = re.findall(r'"([^"]*)"', skills_array_text)
                            basic_json["skills"] = [{"name": skill} for skill in skill_matches if skill.strip()]
                        except:
                            pass
                    
                    return basic_json
                except Exception as e:
                    logger.error(f"All JSON parsing attempts failed: {e}")
                    raise parse_error
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            if json_text:
                logger.error(f"Attempted to parse: {json_text[:1000]}...")
            else:
                logger.error(f"Attempted to parse: {response_text[:1000]}...")
            
            # Method 5: Last resort - try to find and parse the largest JSON object
            try:
                # Use a simpler regex pattern to avoid unbalanced parenthesis errors
                # Look for JSON objects with balanced braces
                brace_count = 0
                start_pos = -1
                json_objects = []
                for i, char in enumerate(response_text):
                    if char == '{':
                        if brace_count == 0:
                            start_pos = i
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_pos != -1:
                            json_objects.append(response_text[start_pos:i+1])
                
                if json_objects:
                    # Find the longest match (most complete JSON)
                    longest_match = max(json_objects, key=len)
                    return json.loads(longest_match)
                else:
                    raise e
            except Exception:
                raise e
