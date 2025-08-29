"""Intent schema definitions for semantic intent detection."""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import re


class SlotType(Enum):
    """Types of slots for intent parameters."""
    TEXT = "text"
    EMAIL = "email"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    ROLE = "role"
    SKILLS = "skills"
    LOCATION = "location"
    DATE = "date"
    COMPANY = "company"


@dataclass
class SlotDefinition:
    """Definition of a slot (parameter) for an intent."""
    name: str
    type: SlotType
    description: str
    required: bool = False
    default_value: Optional[Any] = None
    validation_pattern: Optional[str] = None
    options: Optional[List[str]] = None
    examples: Optional[List[str]] = None


@dataclass
class ClarifyingQuestion:
    """A clarifying question for missing or ambiguous slots."""
    slot_name: str
    question: str
    question_type: str = "open"  # "open", "multiple_choice", "yes_no"
    options: Optional[List[str]] = None
    followup_questions: Optional[List[str]] = None


@dataclass
class IntentDefinition:
    """Complete definition of an intent."""
    name: str
    description: str
    synonyms: List[str]
    required_slots: List[SlotDefinition]
    optional_slots: List[SlotDefinition]
    patterns: List[str]
    negative_keywords: List[str]
    priority: int = 1
    confidence_threshold: float = 0.6
    clarifying_questions: List[ClarifyingQuestion] = None
    examples: List[str] = None

    def __post_init__(self):
        if self.clarifying_questions is None:
            self.clarifying_questions = []
        if self.examples is None:
            self.examples = []


class IntentRegistry:
    """Registry for managing intent definitions."""
    
    def __init__(self):
        self.intents: Dict[str, IntentDefinition] = {}
        self._initialize_default_intents()
    
    def register_intent(self, intent: IntentDefinition):
        """Register a new intent definition."""
        self.intents[intent.name] = intent
    
    def get_intent(self, name: str) -> Optional[IntentDefinition]:
        """Get an intent definition by name."""
        return self.intents.get(name)
    
    def get_all_intents(self) -> Dict[str, IntentDefinition]:
        """Get all registered intents."""
        return self.intents.copy()
    
    def get_intents_by_priority(self) -> List[IntentDefinition]:
        """Get intents sorted by priority (highest first)."""
        return sorted(self.intents.values(), key=lambda x: x.priority, reverse=True)
    
    def _initialize_default_intents(self):
        """Initialize the default set of intents."""
        
        # Recruiter Outreach Email Intent
        self.register_intent(IntentDefinition(
            name="recruiter_outreach_email",
            description="Generate personalized recruiter outreach emails to candidates",
            synonyms=[
                "recruiter email", "outreach email", "candidate email", "recruiting email",
                "sourcing email", "talent acquisition email", "headhunter email"
            ],
            required_slots=[
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="The job role/position being recruited for",
                    required=True,
                    examples=["software engineer", "data scientist", "product manager"]
                )
            ],
            optional_slots=[
                SlotDefinition(
                    name="company",
                    type=SlotType.COMPANY,
                    description="Company name",
                    required=False
                ),
                SlotDefinition(
                    name="skills",
                    type=SlotType.SKILLS,
                    description="Required skills or technologies",
                    required=False
                ),
                SlotDefinition(
                    name="location",
                    type=SlotType.LOCATION,
                    description="Job location",
                    required=False
                )
            ],
            patterns=[
                r"(?i)generate.*recruiter.*(?:email|outreach).*(?:for|to).*(\w+)",
                r"(?i)(?:write|create|draft).*(?:recruiter|outreach).*email.*(\w+)",
                r"(?i)recruiter.*email.*(?:for|about).*(\w+)",
                r"(?i)outreach.*email.*(\w+).*(?:role|position)"
            ],
            negative_keywords=["application", "apply", "resume submission", "job posting"],
            priority=8,
            confidence_threshold=0.7,
            clarifying_questions=[
                ClarifyingQuestion(
                    slot_name="role",
                    question="What specific role are you recruiting for?",
                    question_type="open",
                    examples=["software engineer", "data scientist", "product manager"]
                )
            ],
            examples=[
                "Generate a recruiter outreach email for software engineer",
                "Create recruiting email for data scientist position",
                "Write outreach email to candidates for product manager role"
            ]
        ))
        
        # Candidate Pitch Email Intent
        self.register_intent(IntentDefinition(
            name="candidate_pitch_email",
            description="Generate pitch emails from candidates to companies",
            synonyms=[
                "candidate email", "pitch email", "application email", "cover letter email",
                "job application email", "candidate outreach"
            ],
            required_slots=[
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="The role the candidate is applying for",
                    required=True
                )
            ],
            optional_slots=[
                SlotDefinition(
                    name="company",
                    type=SlotType.COMPANY,
                    description="Target company name",
                    required=False
                ),
                SlotDefinition(
                    name="skills",
                    type=SlotType.SKILLS,
                    description="Candidate's key skills",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:generate|create|write).*(?:candidate|pitch).*email.*(?:for|to).*(\w+)",
                r"(?i)(?:application|cover letter).*email.*(\w+)",
                r"(?i)candidate.*(?:pitch|outreach).*(\w+)"
            ],
            negative_keywords=["recruiter", "sourcing", "headhunter"],
            priority=7,
            confidence_threshold=0.7,
            clarifying_questions=[
                ClarifyingQuestion(
                    slot_name="role",
                    question="What role is the candidate applying for?",
                    question_type="open"
                )
            ]
        ))
        
        # Search Candidates Intent
        self.register_intent(IntentDefinition(
            name="search_candidates",
            description="Search for candidates based on criteria",
            synonyms=[
                "find candidates", "search talent", "look for candidates", "candidate search",
                "talent search", "find developers", "search engineers", "locate candidates"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="skills",
                    type=SlotType.SKILLS,
                    description="Required skills or technologies",
                    required=False
                ),
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="Job role or title",
                    required=False
                ),
                SlotDefinition(
                    name="location",
                    type=SlotType.LOCATION,
                    description="Geographic location",
                    required=False
                ),
                SlotDefinition(
                    name="experience",
                    type=SlotType.TEXT,
                    description="Years of experience",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:find|search|look for|locate).*(?:candidates|talent|developers|engineers)",
                r"(?i)(?:candidates|talent).*(?:with|having).*(\w+)",
                r"(?i)search.*(?:for|candidates).*(\w+).*(?:skills|experience)"
            ],
            negative_keywords=["email", "outreach", "contact"],
            priority=9,
            confidence_threshold=0.6,
            clarifying_questions=[
                ClarifyingQuestion(
                    slot_name="skills",
                    question="What specific skills or technologies are you looking for?",
                    question_type="open"
                ),
                ClarifyingQuestion(
                    slot_name="role",
                    question="What role or job title are you searching for?",
                    question_type="open"
                )
            ]
        ))
        
        # Market Research Intent
        self.register_intent(IntentDefinition(
            name="market_research",
            description="Conduct market research on roles, salaries, or hiring trends",
            synonyms=[
                "market analysis", "salary research", "compensation analysis", "hiring trends",
                "market data", "industry research", "talent market", "salary benchmarking"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="Job role to research",
                    required=False
                ),
                SlotDefinition(
                    name="location",
                    type=SlotType.LOCATION,
                    description="Geographic market",
                    required=False
                ),
                SlotDefinition(
                    name="metric",
                    type=SlotType.TEXT,
                    description="What to research (salary, demand, etc.)",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:market|salary|compensation).*(?:research|analysis|data)",
                r"(?i)(?:hiring|talent).*(?:trends|market)",
                r"(?i)(?:what|how much).*(?:salary|pay|compensation).*(\w+)",
                r"(?i)market.*(?:for|analysis).*(\w+)"
            ],
            negative_keywords=["find", "search", "candidates", "email"],
            priority=6,
            confidence_threshold=0.6
        ))
        
        # Travel Time Intent
        self.register_intent(IntentDefinition(
            name="travel_time",
            description="Calculate travel time between locations",
            synonyms=[
                "travel duration", "commute time", "distance", "how long to travel",
                "travel estimate", "journey time", "drive time"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="origin",
                    type=SlotType.LOCATION,
                    description="Starting location",
                    required=False
                ),
                SlotDefinition(
                    name="destination",
                    type=SlotType.LOCATION,
                    description="Destination location",
                    required=False
                ),
                SlotDefinition(
                    name="transport_mode",
                    type=SlotType.TEXT,
                    description="Mode of transportation",
                    required=False,
                    options=["driving", "walking", "transit", "cycling"]
                )
            ],
            patterns=[
                r"(?i)(?:how long|travel time|commute).*(?:from|to).*(\w+).*(?:to|from).*(\w+)",
                r"(?i)(?:distance|time).*between.*(\w+).*(?:and|to).*(\w+)",
                r"(?i)(?:drive|travel).*time.*(\w+).*(\w+)"
            ],
            negative_keywords=["candidates", "email", "search", "hire"],
            priority=5,
            confidence_threshold=0.8
        ))
        
        # Job Analysis Intent
        self.register_intent(IntentDefinition(
            name="job_analysis",
            description="Analyze job descriptions or requirements",
            synonyms=[
                "job description analysis", "role analysis", "position analysis",
                "job requirements", "analyze job", "job breakdown"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="job_description",
                    type=SlotType.TEXT,
                    description="Job description text",
                    required=False
                ),
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="Job role",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:analyze|analysis).*(?:job|role|position)",
                r"(?i)job.*(?:description|requirements).*(?:analysis|breakdown)",
                r"(?i)(?:break down|examine).*(?:job|role)"
            ],
            negative_keywords=["search", "find", "candidates"],
            priority=4,
            confidence_threshold=0.7
        ))
        
        # Sourcing Strategy Intent
        self.register_intent(IntentDefinition(
            name="sourcing_strategy",
            description="Get advice on sourcing strategies for specific roles",
            synonyms=[
                "sourcing advice", "recruitment strategy", "hiring strategy",
                "talent acquisition strategy", "sourcing tips", "recruitment guidance"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="Role to source for",
                    required=False
                ),
                SlotDefinition(
                    name="difficulty",
                    type=SlotType.TEXT,
                    description="Sourcing difficulty or challenge",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:sourcing|recruitment).*(?:strategy|advice|tips)",
                r"(?i)how.*(?:source|recruit|find).*(\w+)",
                r"(?i)(?:best|good).*(?:way|approach).*(?:source|recruit).*(\w+)",
                r"(?i)(?:strategy|advice).*(?:for|sourcing).*(\w+)"
            ],
            negative_keywords=["email", "specific candidates", "search database"],
            priority=6,
            confidence_threshold=0.7
        ))
        
        # Interview Questions Intent
        self.register_intent(IntentDefinition(
            name="interview_questions",
            description="Generate interview questions for specific roles",
            synonyms=[
                "interview prep", "interview questions", "screening questions",
                "technical questions", "behavioral questions", "interview guide"
            ],
            required_slots=[
                SlotDefinition(
                    name="role",
                    type=SlotType.ROLE,
                    description="Role to create questions for",
                    required=True
                )
            ],
            optional_slots=[
                SlotDefinition(
                    name="question_type",
                    type=SlotType.TEXT,
                    description="Type of questions",
                    required=False,
                    options=["technical", "behavioral", "cultural", "screening", "all"]
                ),
                SlotDefinition(
                    name="experience_level",
                    type=SlotType.TEXT,
                    description="Experience level",
                    required=False,
                    options=["junior", "mid", "senior", "lead", "executive"]
                )
            ],
            patterns=[
                r"(?i)(?:interview|screening).*questions.*(?:for|about).*(\w+)",
                r"(?i)(?:generate|create).*questions.*(\w+).*(?:interview|role)",
                r"(?i)(?:technical|behavioral).*questions.*(\w+)"
            ],
            negative_keywords=["candidates", "search", "email"],
            priority=5,
            confidence_threshold=0.7,
            clarifying_questions=[
                ClarifyingQuestion(
                    slot_name="role",
                    question="What role are you creating interview questions for?",
                    question_type="open"
                )
            ]
        ))
        
        # General Question Intent (fallback)
        self.register_intent(IntentDefinition(
            name="general_question",
            description="General questions or requests that don't fit specific intents",
            synonyms=[
                "general query", "question", "help", "assistance", "information",
                "explain", "what is", "how to", "unclear request"
            ],
            required_slots=[],
            optional_slots=[
                SlotDefinition(
                    name="query",
                    type=SlotType.TEXT,
                    description="The general question or request",
                    required=False
                )
            ],
            patterns=[
                r"(?i)(?:what|how|why|when|where).*",
                r"(?i)(?:help|assist|support).*",
                r"(?i)(?:explain|tell me|show me).*"
            ],
            negative_keywords=[],
            priority=1,  # Lowest priority - fallback intent
            confidence_threshold=0.3
        ))


# Global registry instance
_intent_registry = None


def get_intent_registry() -> IntentRegistry:
    """Get the global intent registry instance."""
    global _intent_registry
    if _intent_registry is None:
        _intent_registry = IntentRegistry()
    return _intent_registry


def register_custom_intent(intent: IntentDefinition):
    """Register a custom intent with the global registry."""
    registry = get_intent_registry()
    registry.register_intent(intent)


def get_intent_by_name(name: str) -> Optional[IntentDefinition]:
    """Get an intent definition by name from the global registry."""
    registry = get_intent_registry()
    return registry.get_intent(name)
