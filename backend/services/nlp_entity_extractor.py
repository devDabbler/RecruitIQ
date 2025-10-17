"""Advanced NLP entity extraction using spaCy, fuzzy matching, and custom patterns."""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from fuzzywuzzy import fuzz, process
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Doc, Span

logger = logging.getLogger(__name__)


@dataclass
class EntityMatch:
    """Represents an extracted entity with confidence and metadata."""
    text: str
    label: str
    confidence: float
    start: int
    end: int
    method: str
    normalized_text: Optional[str] = None


class NLPEntityExtractor:
    """Advanced entity extractor using spaCy NER, fuzzy matching, and custom patterns."""
    
    def __init__(self):
        self.nlp = None
        self.matcher = None
        self.phrase_matcher = None
        self._initialize_spacy()
        self._initialize_knowledge_bases()
        self._setup_custom_patterns()
    
    def _initialize_spacy(self):
        """Initialize spaCy model with custom components."""
        try:
            # Try to load the English model
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm model")
        except OSError:
            try:
                # Fallback to smaller model
                self.nlp = spacy.load("en_core_web_md")
                logger.info("Loaded spaCy en_core_web_md model")
            except OSError:
                logger.warning("No spaCy model found, using blank English model")
                self.nlp = spacy.blank("en")
        
        # Initialize matchers
        self.matcher = Matcher(self.nlp.vocab)
        self.phrase_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
    
    def _initialize_knowledge_bases(self):
        """Initialize knowledge bases for fuzzy matching."""
        
        # Technical roles and their variations
        self.role_knowledge_base = {
            "software_engineer": [
                "software engineer", "software developer", "backend developer", 
                "frontend developer", "full stack developer", "web developer",
                "application developer", "systems developer", "software dev"
            ],
            "data_engineer": [
                "data engineer", "data engineering", "big data engineer",
                "etl developer", "data pipeline engineer", "data platform engineer"
            ],
            "data_scientist": [
                "data scientist", "data science", "machine learning engineer",
                "ml engineer", "ai engineer", "research scientist", "analytics engineer"
            ],
            "gen_ai_engineer": [
                "gen ai engineer", "gen ai", "generative ai engineer", "generative ai",
                "genai engineer", "llm engineer", "large language model engineer"
            ],
            "product_manager": [
                "product manager", "product management", "pm", "product owner",
                "senior product manager", "principal product manager"
            ],
            "devops_engineer": [
                "devops engineer", "devops", "site reliability engineer", "sre",
                "cloud engineer", "infrastructure engineer", "platform engineer"
            ],
            "security_engineer": [
                "security engineer", "cybersecurity engineer", "infosec engineer",
                "application security engineer", "cloud security engineer"
            ],
            "ui_ux_designer": [
                "ui designer", "ux designer", "ui/ux designer", "product designer",
                "user experience designer", "user interface designer"
            ],
            "qa_engineer": [
                "qa engineer", "quality assurance engineer", "test engineer",
                "sdet", "automation engineer", "testing engineer"
            ]
        }
        
        # Technical skills and technologies
        self.skills_knowledge_base = {
            "programming_languages": [
                "python", "java", "javascript", "typescript", "c++", "c#", "go",
                "rust", "kotlin", "swift", "php", "ruby", "scala", "r", "r programming", "r language"
            ],
            "web_technologies": [
                "react", "angular", "vue", "node.js", "express", "django",
                "flask", "spring", "laravel", "rails"
            ],
            "databases": [
                "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
                "cassandra", "dynamodb", "sqlite", "oracle"
            ],
            "cloud_platforms": [
                "aws", "azure", "gcp", "google cloud", "amazon web services",
                "microsoft azure", "kubernetes", "docker"
            ],
            "data_tools": [
                "spark", "hadoop", "kafka", "airflow", "snowflake", "databricks",
                "tableau", "power bi", "looker", "pandas", "numpy"
            ]
        }
        
        # Location patterns
        self.location_knowledge_base = [
            "san francisco", "new york", "seattle", "austin", "boston",
            "chicago", "los angeles", "denver", "atlanta", "miami",
            "remote", "hybrid", "on-site", "california", "texas", "washington"
        ]
        
        # Company types and names
        self.company_knowledge_base = [
            "google", "microsoft", "amazon", "apple", "meta", "netflix",
            "uber", "airbnb", "stripe", "salesforce", "oracle", "ibm",
            "startup", "big tech", "faang", "fortune 500"
        ]
    
    def _setup_custom_patterns(self):
        """Setup custom spaCy patterns for entity recognition."""
        
        # Role patterns
        role_patterns = [
            [{"LOWER": {"IN": ["senior", "junior", "lead", "principal", "staff"]}}, 
             {"LOWER": {"IN": ["software", "data", "machine", "product"]}},
             {"LOWER": {"IN": ["engineer", "scientist", "manager", "developer"]}}],
            
            [{"LOWER": {"IN": ["software", "data", "backend", "frontend", "full"]}},
             {"LOWER": {"IN": ["engineer", "developer", "stack"]}, "OP": "?"},
             {"LOWER": "developer", "OP": "?"}],
            
            [{"LOWER": "data"}, {"LOWER": {"IN": ["engineer", "scientist", "analyst"]}}],
            [{"LOWER": "machine"}, {"LOWER": "learning"}, {"LOWER": "engineer"}],
            [{"LOWER": "devops"}, {"LOWER": "engineer", "OP": "?"}],
            [{"LOWER": {"IN": ["ui", "ux"]}}, {"LOWER": "designer"}],
        ]
        
        for i, pattern in enumerate(role_patterns):
            self.matcher.add(f"ROLE_PATTERN_{i}", [pattern])
        
        # Skills patterns
        skill_patterns = [
            [{"LOWER": {"IN": ["python", "java", "javascript", "typescript", "react", "angular"]}},
             {"LOWER": {"IN": ["developer", "engineer", "experience"]}, "OP": "?"}],
            
            [{"LOWER": {"IN": ["aws", "azure", "gcp", "kubernetes", "docker"]}},
             {"LOWER": {"IN": ["experience", "certified", "expert"]}, "OP": "?"}],
        ]
        
        for i, pattern in enumerate(skill_patterns):
            self.matcher.add(f"SKILL_PATTERN_{i}", [pattern])
        
        # Add phrase patterns for known entities
        role_phrases = []
        for role_variants in self.role_knowledge_base.values():
            for variant in role_variants:
                role_phrases.append(self.nlp(variant))
        
        if role_phrases:
            self.phrase_matcher.add("ROLE_PHRASES", role_phrases)
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities using multiple NLP techniques."""
        
        doc = self.nlp(text)
        entities = {}
        
        # 1. spaCy NER extraction
        spacy_entities = self._extract_spacy_entities(doc)
        
        # 2. Custom pattern matching
        pattern_entities = self._extract_pattern_entities(doc)
        
        # 3. Fuzzy matching against knowledge bases
        fuzzy_entities = self._extract_fuzzy_entities(text)
        
        # 4. Regex-based extraction (fallback)
        regex_entities = self._extract_regex_entities(text)
        
        # Merge and prioritize entities
        merged_entities = self._merge_entity_results([
            spacy_entities, pattern_entities, fuzzy_entities, regex_entities
        ])
        
        # Normalize and validate entities
        final_entities = self._normalize_entities(merged_entities, text)
        
        return final_entities
    
    def _extract_spacy_entities(self, doc: Doc) -> Dict[str, EntityMatch]:
        """Extract entities using spaCy's built-in NER."""
        entities = {}
        
        for ent in doc.ents:
            entity_type = self._map_spacy_label_to_slot(ent.label_)
            if entity_type:
                entities[entity_type] = EntityMatch(
                    text=ent.text,
                    label=entity_type,
                    confidence=0.8,  # spaCy confidence
                    start=ent.start_char,
                    end=ent.end_char,
                    method="spacy_ner"
                )
        
        return entities
    
    def _extract_pattern_entities(self, doc: Doc) -> Dict[str, EntityMatch]:
        """Extract entities using custom spaCy patterns."""
        entities = {}
        
        matches = self.matcher(doc)
        phrase_matches = self.phrase_matcher(doc)
        
        all_matches = matches + phrase_matches
        
        for match_id, start, end in all_matches:
            span = doc[start:end]
            label_name = self.nlp.vocab.strings[match_id]
            
            if "ROLE" in label_name:
                entity_type = "role"
            elif "SKILL" in label_name:
                entity_type = "skills"
            else:
                continue
            
            entities[entity_type] = EntityMatch(
                text=span.text,
                label=entity_type,
                confidence=0.9,  # High confidence for pattern matches
                start=span.start_char,
                end=span.end_char,
                method="pattern_matching"
            )
        
        return entities
    
    def _extract_fuzzy_entities(self, text: str) -> Dict[str, EntityMatch]:
        """Extract entities using fuzzy string matching."""
        entities = {}
        text_lower = text.lower()
        
        # Fuzzy match roles
        role_match = self._fuzzy_match_roles(text_lower)
        if role_match:
            entities["role"] = role_match
        
        # Fuzzy match skills
        skills_matches = self._fuzzy_match_skills(text_lower)
        if skills_matches:
            entities["skills"] = skills_matches
        
        # Fuzzy match locations
        location_match = self._fuzzy_match_locations(text_lower)
        if location_match:
            entities["location"] = location_match
        
        return entities
    
    def _fuzzy_match_roles(self, text: str) -> Optional[EntityMatch]:
        """Fuzzy match against role knowledge base."""
        best_match = None
        best_score = 0
        best_normalized = None
        
        for normalized_role, variants in self.role_knowledge_base.items():
            for variant in variants:
                # Check if variant appears in text
                if variant in text:
                    score = 100  # Exact match
                else:
                    # Fuzzy match
                    score = fuzz.partial_ratio(variant, text)
                
                if score > best_score and score >= 70:  # Minimum threshold
                    best_score = score
                    best_match = variant
                    best_normalized = normalized_role.replace("_", " ")
        
        if best_match:
            # Find position in original text
            start = text.find(best_match.lower())
            if start == -1:
                start = 0
            
            return EntityMatch(
                text=best_match,
                label="role",
                confidence=best_score / 100.0,
                start=start,
                end=start + len(best_match),
                method="fuzzy_matching",
                normalized_text=best_normalized
            )
        
        return None
    
    def _fuzzy_match_skills(self, text: str) -> Optional[EntityMatch]:
        """Fuzzy match against skills knowledge base."""
        found_skills = []
        
        for category, skills in self.skills_knowledge_base.items():
            for skill in skills:
                if skill in text:
                    found_skills.append(skill)
                else:
                    # Fuzzy match for common misspellings
                    score = fuzz.partial_ratio(skill, text)
                    if score >= 85:  # High threshold for skills
                        found_skills.append(skill)
        
        if found_skills:
            skills_text = ", ".join(found_skills)
            return EntityMatch(
                text=skills_text,
                label="skills",
                confidence=0.8,
                start=0,
                end=len(skills_text),
                method="fuzzy_matching"
            )
        
        return None
    
    def _fuzzy_match_locations(self, text: str) -> Optional[EntityMatch]:
        """Fuzzy match against location knowledge base."""
        best_match, score = process.extractOne(
            text, self.location_knowledge_base, scorer=fuzz.partial_ratio
        )
        
        if score >= 80:  # High threshold for locations
            start = text.find(best_match.lower())
            if start == -1:
                start = 0
            
            return EntityMatch(
                text=best_match,
                label="location",
                confidence=score / 100.0,
                start=start,
                end=start + len(best_match),
                method="fuzzy_matching"
            )
        
        return None
    
    def _extract_regex_entities(self, text: str) -> Dict[str, EntityMatch]:
        """Extract entities using regex patterns (fallback)."""
        entities = {}
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            entities["email"] = EntityMatch(
                text=email_match.group(),
                label="email",
                confidence=0.95,
                start=email_match.start(),
                end=email_match.end(),
                method="regex"
            )
        
        # Years of experience
        exp_pattern = r'(\d+)[\s\-]*(?:years?|yrs?)[\s\-]*(?:of\s+)?(?:experience|exp)'
        exp_match = re.search(exp_pattern, text, re.IGNORECASE)
        if exp_match:
            entities["experience"] = EntityMatch(
                text=exp_match.group(),
                label="experience",
                confidence=0.9,
                start=exp_match.start(),
                end=exp_match.end(),
                method="regex"
            )
        
        return entities
    
    def _merge_entity_results(self, entity_lists: List[Dict[str, EntityMatch]]) -> Dict[str, EntityMatch]:
        """Merge entity results from different extraction methods."""
        merged = {}
        
        for entities in entity_lists:
            for entity_type, entity_match in entities.items():
                if entity_type not in merged:
                    merged[entity_type] = entity_match
                else:
                    # Keep the one with higher confidence
                    if entity_match.confidence > merged[entity_type].confidence:
                        merged[entity_type] = entity_match
        
        return merged
    
    def _normalize_entities(self, entities: Dict[str, EntityMatch], original_text: str) -> Dict[str, Any]:
        """Normalize and clean extracted entities."""
        normalized = {}
        
        for entity_type, entity_match in entities.items():
            if entity_match.normalized_text:
                normalized[entity_type] = entity_match.normalized_text
            else:
                # Clean and normalize the text
                cleaned_text = entity_match.text.strip()
                
                if entity_type == "role":
                    # Normalize role names
                    cleaned_text = self._normalize_role_name(cleaned_text)
                elif entity_type == "skills":
                    # Normalize skill names
                    cleaned_text = self._normalize_skills(cleaned_text)
                
                normalized[entity_type] = cleaned_text
        
        return normalized
    
    def _normalize_role_name(self, role: str) -> str:
        """Normalize role names to standard format."""
        role = role.lower().strip()
        
        # Common normalizations
        normalizations = {
            "software dev": "software developer",
            "backend dev": "backend developer",
            "frontend dev": "frontend developer",
            "full stack dev": "full stack developer",
            "data eng": "data engineer",
            "ml engineer": "machine learning engineer",
            "ai engineer": "machine learning engineer",
            "sre": "site reliability engineer",
            "pm": "product manager"
        }
        
        return normalizations.get(role, role)
    
    def _normalize_skills(self, skills: str) -> str:
        """Normalize skill names."""
        # Split multiple skills and normalize each
        skill_list = [s.strip().lower() for s in skills.split(",")]
        
        # Normalize individual skills
        normalizations = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "k8s": "kubernetes",
            "postgres": "postgresql"
        }
        
        normalized_skills = []
        for skill in skill_list:
            normalized_skills.append(normalizations.get(skill, skill))
        
        return ", ".join(normalized_skills)
    
    def _map_spacy_label_to_slot(self, spacy_label: str) -> Optional[str]:
        """Map spaCy entity labels to our slot types."""
        mapping = {
            "PERSON": "candidate_name",
            "ORG": "company",
            "GPE": "location",
            "MONEY": "salary",
            "DATE": "date",
            "TIME": "date"
        }
        return mapping.get(spacy_label)


# Global instance
_nlp_extractor = None


def get_nlp_extractor() -> NLPEntityExtractor:
    """Get the global NLP entity extractor instance."""
    global _nlp_extractor
    if _nlp_extractor is None:
        _nlp_extractor = NLPEntityExtractor()
    return _nlp_extractor
