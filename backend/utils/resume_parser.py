# backend/utils/resume_parser.py
import spacy
import re
import os
import json
from PyPDF2 import PdfReader
import docx2txt
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple

from backend.services.llm_service import LLMService
from backend.utils.config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper function for thread-safe async execution
def run_async_in_thread(async_task):
    """Run an async task in a thread-safe way by creating a new event loop"""
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_task)
    finally:
        loop.close()

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_lg")
    logger.info("Successfully loaded spaCy model 'en_core_web_lg'")
except OSError:
    logger.warning("Spacy model 'en_core_web_lg' not found. Using 'en_core_web_sm' instead.")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.error("No spaCy model found. Please run 'python -m spacy download en_core_web_sm'")
        nlp = None


class ResumeParser:
    """
    A class to parse and extract information from resumes in various formats.
    """
    def __init__(self):
        self.text = ""
        self.doc = None
        self.parsed_data = {
            "personal_info": {},
            "education": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "certifications": []
        }
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a resume file and extract structured information.
        
        Args:
            file_path: Path to the resume file
            
        Returns:
            Dictionary containing parsed resume data
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Extract text based on file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == ".pdf":
            self.text = self._extract_text_from_pdf(file_path)
        elif file_extension in [".docx", ".doc"]:
            self.text = self._extract_text_from_docx(file_path)
        elif file_extension == ".txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                self.text = f.read()
        else:
            logger.error(f"Unsupported file format: {file_extension}")
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Process the text with spaCy if model is available
        if nlp:
            self.doc = nlp(self.text)
            
            # Extract information
            self._extract_personal_info()
            self._extract_education()
            self._extract_experience()
            self._extract_skills()
            
        return self.parsed_data
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file."""
        try:
            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from a DOCX file."""
        try:
            text = docx2txt.process(file_path)
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {str(e)}")
            return ""
    
    def _extract_personal_info(self) -> None:
        """Extract personal information such as name, email, phone, and location."""
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, self.text)
        if emails:
            self.parsed_data["personal_info"]["email"] = emails[0]
        
        # Extract phone number
        phone_pattern = r'(\+\d{1,3}[-\.\s]??)?\(?\d{3}\)?[-\.\s]?\d{3}[-\.\s]?\d{4}'
        phones = re.findall(phone_pattern, self.text)
        if phones:
            self.parsed_data["personal_info"]["phone"] = phones[0]
        
        # Extract name (assuming it's at the beginning of the resume)
        if self.doc:
            # Look for PERSON entities at the beginning of the document
            for ent in self.doc.ents:
                if ent.label_ == "PERSON" and ent.start < 50:  # Limit to beginning of document
                    self.parsed_data["personal_info"]["name"] = ent.text
                    break
        
        # Enhanced location/address extraction with improved reliability
        # Start with a clean set of candidates
        address_candidates = set()
        
        # Scan both the beginning (for contact info) and the whole document
        text_to_scan_contact = self.text[:2000]  # First ~2000 chars for contact info
        text_to_scan_full = self.text  # Full text for comprehensive search
        
        # Define clearer patterns with word boundaries to reduce false positives
        # US residential address patterns (highest priority)
        residential_address_pattern = r"\b\d{1,5}\s+[\w .'-]+\s*(?:Avenue|Ave|Boulevard|Blvd|Street|St|Road|Rd|Lane|Ln|Drive|Dr|Place|Pl|Court|Ct|Circle|Cir|Way|Terrace|Ter|Trail|Trl)\s*(?:NW|NE|SW|SE|N|S|E|W)?[,\s]+(?:[A-Za-z .'-]+[,\s]+)?[A-Za-z .'-]+[,\s]+[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?\b"  # Complete residential address
        
        # City, State, ZIP patterns
        city_state_zip_pattern = r"\b[A-Za-z .'-]+[,\s]+[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"  # e.g. Springfield, IL 62704
        city_state_pattern = r"\b[A-Za-z .'-]+[,\s]+[A-Z]{2}\b"  # e.g. Springfield, IL
        
        # International patterns
        intl_city_country_pattern = r"\b[A-Za-z .'-]+[,\s]+(?:UK|Canada|Australia|Germany|France|Japan|Italy|Spain|China|India|Brazil)\b"  # Named countries
        postal_code_pattern = r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b"  # e.g. UK postcodes
        
        # Search patterns ordered by specificity (most specific first)
        regex_patterns = [
            residential_address_pattern,  # Prioritize residential addresses
            city_state_zip_pattern, 
            city_state_pattern,
            intl_city_country_pattern, 
            postal_code_pattern
        ]
        
        # Explicitly check for location indicators nearby
        location_indicators = [
            r"(?i)\blocation\s*[:-]?\s*([^\n,]{3,50})", 
            r"(?i)\baddress\s*[:-]?\s*([^\n,]{3,50})", 
            r"(?i)\bbased in\s*[:-]?\s*([^\n,]{3,50})", 
            r"(?i)\blives in\s*[:-]?\s*([^\n,]{3,50})", 
            r"(?i)\bresides in\s*[:-]?\s*([^\n,]{3,50})"
        ]
        
        # First try explicit location indicators - these are highest priority
        for pattern in location_indicators:
            for text_to_search in [text_to_scan_contact, text_to_scan_full]:
                matches = re.findall(pattern, text_to_search)
                for match in matches:
                    address_candidates.add(match.strip())
        
        # Then try regex patterns
        for pattern in regex_patterns:
            # First search contact section
            for match in re.findall(pattern, text_to_scan_contact):
                address_candidates.add(match.strip())
                
            # If we didn't find matches in contact section, search full text
            if not address_candidates:
                for match in re.findall(pattern, text_to_scan_full):
                    address_candidates.add(match.strip())
        
        # Use spaCy NER as a backup to find location entities
        if self.doc and not address_candidates:  # Only use NER if we haven't found anything yet
            location_entities = []
            for ent in self.doc.ents:
                if ent.label_ in ["GPE", "LOC"]:
                    location_entities.append((ent.text.strip(), ent.label_))
            
            # Prioritize location entities with known state/country abbreviations
            for loc, label in location_entities:
                if re.search(r'[A-Z]{2}', loc):  # Has state abbreviation
                    address_candidates.add(loc)
            
            # If still nothing, add any location entities
            if not address_candidates:
                for loc, label in location_entities:
                    address_candidates.add(loc)
        
        # Deduplicate candidates
        address_candidates = list(dict.fromkeys(address_candidates))
        
        # Order by length/specificity - longer addresses are usually more complete
        prioritized = sorted(address_candidates, key=len, reverse=True)
        
        # LLM Validation Step with improved handling
        if prioritized:
            # Store all candidates in a special field that parse_service can access
            self.parsed_data["personal_info"]["_all_location_candidates"] = prioritized
            
            if len(prioritized) > 1:
                logger.info(f"Multiple possible addresses found: {prioritized}")
                # If we have multiple candidates, attempt LLM validation if enabled
                # Validate top 3 candidates at most to avoid token limits
                candidates_to_validate = prioritized[:3] 
                
                try:
                    llm_service = LLMService(Settings())
                    addresses_formatted = ', '.join([f"'{addr}'" for addr in candidates_to_validate])
                    prompt = f"""You are analyzing a resume to identify the candidate's current residential location or address.
                    
The following possible locations were extracted from the resume: {addresses_formatted}

Prioritize residential addresses with street numbers over work locations.
Extract ONLY the location in the format 'City, State/Province' or 'City, Country'. 
If a candidate contains a full street address (e.g., '654 Van Ray Ave NW Denver, CO'), extract ONLY the city and state part (e.g., 'Denver, CO').
Do NOT include job titles, company names, or other text.
If none appear valid, reply with 'NONE'. Only return the location with no explanation."""
                    
                    # Use a proper async-compatible approach that works in existing event loops
                    try:
                        # Create a future that can be used with await or in a new thread
                        future = llm_service.generate_text_async(
                            prompt=prompt,
                            temperature=0.1,
                            task_type="parsing"
                        )
                        
                        # Use ThreadPoolExecutor to run the async code in a separate thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            validated_address = executor.submit(
                                lambda: run_async_in_thread(future)
                            ).result()
                        
                        validated_address = validated_address.strip()
                        logger.info(f"LLM validation result: {validated_address}")
                        
                        # Check if LLM returned a valid address
                        if validated_address and validated_address != "NONE":
                            # Store the clean location directly
                            self.parsed_data["personal_info"]["location"] = validated_address
                            logger.info(f"Using LLM-validated location: {validated_address}")
                    except Exception as e:
                        logger.error(f"Error in asyncio execution: {str(e)}")
                        self.parsed_data["personal_info"]["location"] = prioritized[0]
                except Exception as e:
                    # Fallback to original behavior if LLM validation fails
                    logger.error(f"LLM validation failed: {str(e)}. Using first candidate.")
                    self.parsed_data["personal_info"]["location"] = prioritized[0]
            else:
                # Single candidate - still use LLM for validation to filter noise
                address = prioritized[0]
                try:
                    llm_service = LLMService(Settings())
                    prompt = f"""You are analyzing a resume to identify the candidate's current residential location.
                    
The following location was extracted: '{address}'

If this appears to be a residential address with a street number (e.g., '654 Van Ray Ave NW Denver, CO'), extract ONLY the city and state part (e.g., 'Denver, CO').
Otherwise, extract ONLY the geographical location in the format 'City, State/Province' or 'City, Country'.
Do NOT include job titles, company names, or other text.
If this is not a valid location, respond with 'NONE'."""

                    try:
                        # Use a proper async-compatible approach that works in existing event loops
                        future = llm_service.generate_text_async(
                            prompt=prompt,
                            temperature=0.1,
                            task_type="parsing"
                        )
                        
                        # Use ThreadPoolExecutor to run the async code in a separate thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            validated_address = executor.submit(
                                lambda: run_async_in_thread(future)
                            ).result()
                        
                        validated_address = validated_address.strip()
                        
                        if validated_address and validated_address != "NONE":
                            self.parsed_data["personal_info"]["location"] = validated_address
                            logger.info(f"Single candidate validated: {validated_address}")
                        else:
                            logger.info("Single address candidate was rejected by LLM")
                            self.parsed_data["personal_info"]["location"] = ""
                    except Exception as e:
                        logger.error(f"Error in asyncio for single candidate: {str(e)}")
                        self.parsed_data["personal_info"]["location"] = address
                except Exception as e:
                    # Fallback to original behavior
                    logger.error(f"LLM validation failed for single address: {str(e)}. Using original address.")
    def _extract_education(self) -> None:
        """Extract education information using both NLP and LLM methods."""
        # Define education-related keywords
        education_keywords = [
            "education", "university", "college", "institute", "academy", "school",
            "bachelor", "master", "phd", "doctorate", "degree", "diploma",
            "b.s.", "m.s.", "b.a.", "m.a.", "b.tech", "m.tech", "b.e.", "m.e."
        ]
        
        # Find education section
        education_text = self._extract_section(education_keywords, ["experience", "employment", "work", "career"])
        
        if not education_text:
            # If no specific education section found, use full text as fallback
            education_text = self.text
        
        # First attempt with LLM extraction
        try:
            # Try to extract education with LLM
            llm_results = self._extract_education_llm(education_text)
            if llm_results and isinstance(llm_results, list) and len(llm_results) > 0:
                logger.info(f"Successfully extracted education via LLM: {len(llm_results)} entries")
                self.parsed_data["education"] = llm_results
                return
            else:
                logger.warning("LLM extraction returned no education data, falling back to NLP methods")
        except Exception as e:
            logger.error(f"LLM education extraction failed: {e}, falling back to NLP methods")
        
        # NLP-based extraction as fallback
        # Process education text to extract institutions and degrees
        education_entries = []
        lines = education_text.split('\n')
        current_education = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # More comprehensive degree pattern that captures full degree names
            degree_pattern = r'(Bachelor(?:\'s)?(?:\s+of\s+(?:Science|Arts|Engineering|Business|Fine Arts))?|Master(?:\'s)?(?:\s+of\s+(?:Science|Arts|Engineering|Business|Fine Arts))?|Ph\.?D\.?|Doctorate|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|M\.?B\.?A\.?|B\.?E\.?)(?:\s+(?:in|of|on)\s+([\w\s&]+))?'
            
            degree_match = re.search(degree_pattern, line, re.IGNORECASE)
            if degree_match:
                # If we already have a partial education entry, complete it
                if current_education and ("institution" in current_education or "degree" in current_education):
                    # Complete existing entry
                    if degree_match.group(1) and "degree" not in current_education:
                        current_education["degree"] = degree_match.group(1).strip()
                    
                    # Extract field of study if present
                    if degree_match.group(2) and "field_of_study" not in current_education:
                        current_education["field_of_study"] = degree_match.group(2).strip()
                    
                    # Only add if we have at least an institution
                    if "institution" in current_education:
                        education_entries.append(current_education)
                    
                    current_education = {}
                
                # Start new education entry with degree
                degree_type = degree_match.group(1).strip()
                current_education["degree"] = degree_type
                
                # Extract field of study if present
                if degree_match.group(2):
                    current_education["field_of_study"] = degree_match.group(2).strip()
                
                # Try to extract graduation year
                year_match = re.search(r'\b(19|20)\d{2}\b', line)
                if year_match:
                    end_year = year_match.group()
                    current_education["end_date"] = end_year
                
                # Try to extract GPA
                gpa_match = re.search(r'GPA[:\s]+([0-4]\.\d+)', line, re.IGNORECASE)
                if gpa_match:
                    current_education["gpa"] = float(gpa_match.group(1))
            
            # Look for institution information using various methods
            institution_match = re.search(r'\b([A-Z][A-Za-z\s&\.,\-\']+(?:University|College|Institute|School|Academy))', line)
            if institution_match:
                if "institution" not in current_education:
                    current_education["institution"] = institution_match.group(1).strip()
            elif self.doc and "institution" not in current_education:
                # Use spaCy NER as fallback
                doc = nlp(line)
                for ent in doc.ents:
                    if ent.label_ == "ORG" and len(ent.text) > 5:  
                        # Filter out short org names & verify it looks like an academic institution
                        potential_institution = ent.text.strip()
                        academic_keywords = ["university", "college", "institute", "school"]
                        if any(keyword in potential_institution.lower() for keyword in academic_keywords):
                            current_education["institution"] = potential_institution
                            break
        
        # Add the last education entry if it has meaningful information
        if current_education and ("institution" in current_education or "degree" in current_education):
            education_entries.append(current_education)
        
        if education_entries:
            self.parsed_data["education"] = education_entries
        else:
            logger.warning("No education entries found with NLP extraction")
            
    def _extract_education_llm(self, education_text: str = None) -> List[Dict[str, Any]]:
        """Extract education information using Nebius AI (Phi-4)."""
        if education_text is None:
            education_text = self.text
            
        try:
            # Use lazy import to avoid circular dependencies
            from backend.services.llm_service import LLMService
            from backend.utils.config import Settings
            
            # Use LLMService instead of direct Nebius import
            llm_service = LLMService(Settings())
            
            # Create targeted prompt for education extraction
            prompt = f"""You are an expert resume parser. Analyze the following resume text and extract ONLY the education information in a structured JSON format.

**EDUCATION EXTRACTION REQUIREMENTS:**
- Always extract COMPLETE education information including institution, degree type, and field of study
- Look for degree types like: B.S., B.A., Bachelor of Science, Master of Arts, M.S., PhD, etc.
- Look for degree fields like: Computer Science, Business Administration, Engineering, etc.
- Common degree patterns: "Bachelor of Science in Computer Science", "B.S. in Computer Science", "Master's in Business Administration"
- If only institution is explicitly mentioned but degree can be inferred from context, include the degree
- Parse the entire resume for education info, not just dedicated education sections
- Education dates should be extracted when available
- If a degree is specified but missing its type, use the field of study to infer a likely degree type

**Expected JSON Format:**
```json
[
  {{
    "institution": "University Name",
    "degree": "Degree Type (e.g., Bachelor of Science, Master's, etc.)",
    "field_of_study": "Field of Study (e.g., Computer Science, Engineering, etc.)",
    "start_date": "Start Date (if available)",
    "end_date": "End Date (if available)"
  }},
  // Additional education entries...
]
```

**Resume Text:**
```text
{education_text}
```

Your response must be a single, valid JSON array as described above. Do not include any explanatory text or markdown formatting around the JSON.
"""
            
            # Call LLM service which will use Nebius AI internally
            try:
                # Use ThreadPoolExecutor to run the async code in a separate thread
                import concurrent.futures
                future = llm_service.generate_text_async(
                    prompt=prompt,
                    temperature=0.1,
                    task_type="parsing",
                    max_tokens=8192
                )
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    response = executor.submit(
                        lambda: run_async_in_thread(future)
                    ).result()
            except Exception as inner_e:
                logger.error(f"Error calling LLM service: {inner_e}")
                raise
            
            # Parse the response
            cleaned_text = response.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            
            cleaned_text = cleaned_text.strip()
            
            # Parse as JSON
            education_data = json.loads(cleaned_text)
            logger.info(f"Successfully extracted education data via LLM: {education_data}")
            return education_data
            
        except Exception as e:
            logger.error(f"Error extracting education via LLM: {e}")
            return []

    def _extract_experience(self) -> None:
        """Extract work experience information."""
        # Define work experience related keywords
        experience_keywords = [
            "experience", "employment", "work history", "professional experience",
            "career", "job history", "work experience"
        ]
        
        # Find experience section
        experience_text = self._extract_section(experience_keywords, ["education", "skills", "projects"])
        
        if not experience_text:
            return
        
        # Process experience text
        lines = experience_text.split('\n')
        current_experience = {}
        current_description = []
        
        for line in lines:
            if not line.strip():
                continue
            
            # Look for job title and company patterns
            job_company_match = re.search(r'(.*?)\s+(?:at|@|,)\s+(.*)', line, re.IGNORECASE)
            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+\d{4}\s*-\s*(Present|Current|Now|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+\d{4})', line, re.IGNORECASE)
            
            if job_company_match or date_match:
                # Save previous experience if exists
                if current_experience and "title" in current_experience:
                    if current_description:
                        current_experience["description"] = " ".join(current_description)
                    self.parsed_data["experience"].append(current_experience)
                    current_experience = {}
                    current_description = []
                
                if job_company_match:
                    current_experience["title"] = job_company_match.group(1).strip()
                    current_experience["company"] = job_company_match.group(2).strip()
                
                if date_match:
                    current_experience["start_date"] = date_match.group(1).strip()
                    current_experience["end_date"] = date_match.group(2).strip()
            
            # If not a job title/company/date line, consider it part of the description
            elif current_experience and "title" in current_experience:
                if line.strip().startswith(('-', '•', '*', '✓')):
                    # It's a bullet point, add it to the description
                    current_description.append(line.strip())
                elif re.search(r'^\s*[A-Z]', line):  # Line starts with capital letter
                    current_description.append(line.strip())
        
        # Add the last experience entry if exists
        if current_experience and "title" in current_experience:
            if current_description:
                current_experience["description"] = " ".join(current_description)
            self.parsed_data["experience"].append(current_experience)
    
    def _extract_skills(self) -> None:
        """Extract skills from the resume."""
        # Define skill-related keywords
        skill_keywords = [
            "skills", "technical skills", "technologies", "tools", "languages",
            "competencies", "expertise", "proficiencies"
        ]
        
        # Common programming languages and technologies
        tech_skills = set([
            "python", "java", "javascript", "typescript", "c++", "c#", "ruby", 
            "php", "swift", "kotlin", "go", "rust", "scala", "perl", "r", 
            "html", "css", "sql", "nosql", "react", "angular", "vue", "node.js", 
            "django", "flask", "spring", "express", "asp.net", "laravel", 
            "bootstrap", "jquery", "redux", "graphql", "rest", "soap",
            "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "gitlab", 
            "github", "bitbucket", "terraform", "ansible", "linux", "unix", 
            "windows", "macos", "android", "ios", "git", "svn", "mercurial",
            "postgresql", "mysql", "oracle", "mongodb", "dynamodb", "cassandra", 
            "redis", "elasticsearch", "solr", "kafka", "rabbitmq", "activemq",
            "machine learning", "deep learning", "data science", "ai", "artificial intelligence",
            "numpy", "pandas", "scikit-learn", "tensorflow", "pytorch", "keras"
        ])
        
        # Find skills section
        skills_text = self._extract_section(skill_keywords, ["experience", "education", "projects"])
        
        if not skills_text:
            # If no skills section found, try to extract skills from the entire document
            skills_text = self.text
        
        # Extract skills
        found_skills = set()
        
        # Look for skills in skills_text
        for skill in tech_skills:
            skill_pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(skill_pattern, skills_text, re.IGNORECASE):
                found_skills.add(skill)
        
        # Convert to list and sort
        self.parsed_data["skills"] = sorted(list(found_skills))
    
    def _extract_section(self, start_keywords: List[str], end_keywords: List[str]) -> str:
        """
        Extract a section from the resume text.
        
        Args:
            start_keywords: Keywords that indicate the start of the section
            end_keywords: Keywords that indicate the end of the section
            
        Returns:
            Extracted section text
        """
        section_text = ""
        
        # Create patterns for section headers
        start_pattern = r'(?i)(?:^|\n)(?:\s*)(?:' + '|'.join(start_keywords) + r')(?:\s*|\:)'
        end_pattern = r'(?i)(?:^|\n)(?:\s*)(?:' + '|'.join(end_keywords) + r')(?:\s*|\:)'
        
        # Find the section
        match = re.search(start_pattern, self.text)
        if match:
            start_pos = match.end()
            end_match = re.search(end_pattern, self.text[start_pos:])
            
            if end_match:
                end_pos = start_pos + end_match.start()
                section_text = self.text[start_pos:end_pos].strip()
            else:
                section_text = self.text[start_pos:].strip()
        
        return section_text


def parse_resume(file_path: str) -> Dict[str, Any]:
    """
    Utility function to parse a resume file.
    
    Args:
        file_path: Path to the resume file
        
    Returns:
        Dictionary containing parsed resume data
    """
    parser = ResumeParser()
    return parser.parse(file_path) 