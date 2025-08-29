"""Intent detection and processing for chatbot interactions."""
import backend.patches  # Windows compatibility patches

import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import asyncio
from datetime import datetime

from backend.services.llm_service import get_llm_service
from backend.utils.config import Settings
settings = Settings()
from backend.services.web_search_service import get_web_search_service
from backend.services.crawler_service import CrawlerService
from backend.utils.text_sanitizer import clean_generated_text

# Get the configured service instances
from .travel_service import TravelService
from .semantic_intent_router import SemanticIntentRouter

logger = logging.getLogger(__name__)

class IntentProcessor:
    """Detects and processes user intents from messages."""
    
    def __init__(self, llm_service=None):
        """
        Initialize the intent processor.
        
        Args:
            llm_service: Optional LLM service instance
        """
        self.llm_service = llm_service
        logger.debug(f"[IntentProcessor.__init__] llm_service: {self.llm_service}")
        self._initialized = False
        self.web_search_service = None
        self.crawler_service = None
        self.travel_service = None  # Add travel service
        
        # Initialize semantic intent router if enabled
        self.semantic_router = None
        if settings.INTENT_ROUTER_MODE in ["semantic", "hybrid"]:
            try:
                if self.llm_service:
                    self.semantic_router = SemanticIntentRouter(self.llm_service)
                    logger.info(f"Initialized semantic intent router in {settings.INTENT_ROUTER_MODE} mode")
            except Exception as e:
                logger.error(f"Failed to initialize semantic intent router: {e}")
        
        # Store conversation history for context-aware processing
        self.conversation_history = []
        
        # Intent classification thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
        
        # Enhanced regular expression patterns for common intents with comprehensive synonyms and variations
        self.intent_patterns = {
            # Travel and commute intents - ENHANCED SECTION
            "travel_time": [
                r"(how long|what's the|what is the|how much time|travel time|commute time|journey time|trip time|duration|how far|distance)( does it take| is| takes)?( to)? (travel|commute|get|go|drive|fly|take the train|take a train|take the bus|take the bus|ride|walk|bike|cycle)( from| between)? (?P<origin>[^?]*?)( to| and| vs| versus)( the)?(?P<destination>[^?]*?)(\?|$)",
                r"(commute|travel|journey|trip|drive|flight|ride)( time| duration)?( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)",
                r"(distance|how far|how long)( is it)?( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)",
                r"(driving|flight|train|bus|walking|biking|cycling)( time| duration)?( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)",
                r"(what's the best way|how do I get|how to get|directions|route|path)( to)? (travel|commute|get|go|reach|arrive)( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)",
                r"(boston|nyc|new york|san francisco|los angeles|chicago|miami|seattle|denver|atlanta|philadelphia|washington dc|portland|austin|dallas|houston)( to)? (boston|nyc|new york|san francisco|los angeles|chicago|miami|seattle|denver|atlanta|philadelphia|washington dc|portland|austin|dallas|houston)( travel| commute| distance| time)?",
                # Enhanced train-specific patterns
                r"(train|by train|take.*train|amtrak|rail).*?(from|between|to).*?(boston|nyc|new york|philadelphia|washington|dc|baltimore|providence)",
                r"(commute|travel|trip).*?(from|between).*?(boston|new york|nyc).*?(by train|train|amtrak)",
                r"(how long|time|duration).*?(train|by train|amtrak).*?(boston|nyc|new york|philadelphia)"
            ],
            "transportation_options": [
                r"(what are the|transportation options|ways to travel|how to get|transport methods|travel options|commute options)( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)",
                r"(public transport|public transportation|transit options|train schedule|bus schedule|flight options|transportation modes|ways to commute)( from| between)? (?P<origin>[^?]*?)( to| and)(?P<destination>[^?]*?)(\?|$)"
            ],
            # Market research and sourcing viability (HIGH PRIORITY - must come before applications_count)
            "market_research": [
                # City viability snapshot - with and without "externally" - HIGH PRIORITY
                r"(externally[, ]+)?(assess|analyze|evaluate|conduct market analysis on) the (sourcing )?viability (for|of hiring) (a |an )?(?P<seniority>senior|mid|entry|lead|principal)? ?(?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)(,? over the last (?P<time_range>[^.]+))?",
                r"(externally[, ]+)?(what's|what is|how is) the (talent market|market|sourcing viability) (like|for) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                r"(externally[, ]+)?(market analysis|market research|talent analysis) (on|for) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                r"(externally[, ]+)?(conduct|perform|do) (market analysis|market research) (on|for|regarding) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                # More specific patterns to catch the production question - HIGHEST PRIORITY
                r"(can you|could you|please) (conduct|perform|do) (market analysis|market research) (on|for|regarding) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                r"(can you|could you|please) (assess|analyze|evaluate) (the )?(viability|market|talent market) (for|of) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                r"(can you|could you|please) (conduct|perform|do) (market analysis|market research) (on|for|regarding) the (viability|feasibility) (of|for) (?P<role>[^ ]+[^,]*) in (?P<city>[^,]+)",
                # Two-city comparison
                r"(externally[, ]+)?(compare|compare the viability of) (sourcing )?(?P<seniority>senior|mid|entry|lead|principal)? ?(?P<role>[^ ]+[^,]*) in (?P<non_tech_city>[^ ]+(?: [^ ]+)*?) vs (?P<tech_hub_city>[^ ]+(?: [^ ]+)*)",
                r"(externally[, ]+)?(how does|how do) hiring (?P<role>[^ ]+[^,]*) in (?P<non_tech_city>[^ ]+(?: [^ ]+)*?) compare to (?P<tech_hub_city>[^ ]+(?: [^ ]+)*)",
                # Shortlist non–tech hubs
                r"(externally[, ]+)?(identify|find|list) the top (?P<num_cities>\d+) non–?tech hub (us|u\.s\.) cities to source (?P<role>[^.]+)",
                r"(externally[, ]+)?(what are|which are) the best non–?tech hub cities for hiring (?P<role>[^ ]+[^,]*)",
                # Sourcing plan
                r"(externally[, ]+)?(create|generate|develop) a sourcing plan for (?P<role>[^ ]+[^,]*) in (?P<city>[^:]+)",
                # Hiring‑manager briefing
                r"(externally[, ]+)?(prepare|create|generate) (a |an )?(briefing|executive briefing) (for hiring managers|for managers) on (hiring challenges|the challenges of hiring) (?P<role>[^ ]+[^,]*) in (?P<city>[^:]+)",
                # Data‑only JSON for dashboards
                r"(externally[, ]+)?(return|generate|provide) only valid json for (?P<role>[^ ]+[^,]*) in (?P<city>[^ ]+[^,]*)(?: .*?last (?P<time_range>[^.]+))?"
            ],
            # Database query intents
            "candidate_count": [
                r"(how many|count|number of|total|quantity of) candidates? (do we have|are there|in the database|in our system|available|stored|saved)",
                # Robust handling for common grammar/typo variants: 'are this database', 'in this database', 'in database'
                r"(how many|count|number of|total|quantity of) candidates? (are|is)? (this|the|our)? ?database",
                r"(how many|count|number of|total|quantity of) candidates? (are|is)? (in|on)? ?(this|the|our)? ?database",
                r"(candidate|applicant|professional|talent) (count|total)",
                r"(how many|count|total number of) (people|applicants|professionals|candidates|talent) (do we have|are there|in our system|in the database|in this database)"
            ],
            "job_count": [
                r"(how many|count|number of|total|quantity of) jobs? (do we have|are there|in the database|in our system|available|posted|open)",
                r"(job|position|opening|role|opportunity) count|total",
                r"(how many|count|total number of) (positions|openings|roles|jobs|opportunities) (do we have|are there|available)"
            ],
            "applications_count": [
                # How many applicants/applied for a role/job - more specific to avoid conflicts
                r"(how many|number of|count of) (candidates|applicants|applications) (have )?(applied|applied to|applied for) (the |this |that )?(?P<role>[^?!.]+?)( role| job)?(\?|\.|!|$)",
                r"(how many|number of|count of) (applications|applicants) (for|to) (the )?(?P<role>[^?!.]+?)( role| job)?(\?|\.|!|$)",
                r"(applications|applicants) (for|to) (the )?(?P<role>[^?!.]+?)( role| job).*(how many|count|number)(\?|\.|!|$)"
            ],
            # More specific patterns to avoid conflicts with market research - EXCLUDE market research keywords
            "search_candidates": [
                # Priority 1: Skills-based patterns (highest priority) - ENHANCED
                r"(find|search|show|get|locate|discover|identify) (me |all |the )?candidates? (with|who have|who know|knowing|expertise in|experience in|skilled in|proficient in|familiar with) (?P<skills>[^?]*?)(\?|\.|!|$|\s)",
                r"(who|which candidates?|what candidates?) (know|have|are skilled in|have experience in|are proficient in|are familiar with) (?P<skills>[^?]*?)(\?|\.|!|$|\s)",
                r"(candidates?|professionals?|developers?|engineers?) (with|who have|skilled in|experienced in) (?P<skills>[^?]*?)(\?|\.|!|$|\s)",
                # Priority 1.5: Enhanced skills patterns for "all candidates with X" format
                r"(find|search|show|get|locate|discover|identify) (me |all |the )?candidates? (with|who have|who know|knowing|expertise in|experience in|skilled in|proficient in|familiar with) (?P<skills>[^?]*?)(\?|\.|!|$|\s)",
                r"(show me all|find me all|get all|display all|list all) candidates? (with|who have|who know|knowing|expertise in|experience in|skilled in|proficient in|familiar with) (?P<skills>[^?]*?)(\?|\.|!|$|\s)",
                # Priority 2: Role-based patterns with "all" handling (only when no skills context)
                r"(find|search|show|get|locate|discover|identify) (me |all |the )?candidates? (for|in|with|specializing in) (?P<role>[a-zA-Z ]+)(?!\s+with)(\?|\.|!|$|\s)",
                r"(look for|seek|find) (?P<role>[a-zA-Z ]+) (candidates?|professionals?|developers?|engineers?)(\?|\.|!|$|\s)",
                # Priority 3: "All" patterns (lowest priority, only when no skills/role context)
                r"(find me all|show me all|get all|display all|list all) (?P<role>[a-zA-Z ]+) candidates?(?!\s+with)(\?|\.|!|$|\s)",
                r"(find|search|show|get|locate|discover|identify) (me |all |the )?(?P<role>[a-zA-Z ]+) candidates?(\?|\.|!|$|\s)"
            ],
            # Email generation intents - ENHANCED WITH CLEAR DISTINCTION
            "recruiter_outreach_email": [
                # HIGHEST PRIORITY: Handle "our job [role]" syntax specifically - most specific first
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop).*?(?:recruiter|recruitment|hiring|talent acquisition|talent|hr|human resources)?.*?(?:outreach |cold |initial |contact |introductory |first |opening )?email.*?(?:to|for|sent to|addressed to).*?(?:our job|the job|job)\s+(?P<role>(?:[a-zA-Z]+(?:\s+[a-zA-Z]+)*))(?:\s+(?:position|role))?(?:[\.\?!]|$)",
                
                # SECOND PRIORITY: "to candidates for our job [role]" pattern
                r"(write|create|draft|compose|prepare|craft|build|formulate|develop).*?(?:recruiter)?.*?email.*?(?:to|for).*?candidates.*?(?:for|about).*?(?:our job|the job|job)\s+(?P<role>(?:[a-zA-Z]+(?:\s+[a-zA-Z]+)*))(?:\s+(?:position|role))?(?:[\.\?!]|$)",

                # Variant: role before candidates e.g., "email to potential data scientist candidates"
                r"(write|create|draft|compose|prepare|craft|build|formulate|develop) (a |an )?(recruiter )?email (to|for|addressed to) (a |an )?(potential |prospective )?(?P<role>[^?!.]+?) candidates?(\?|$|\s)",

                # HIGHEST PRIORITY: Explicit recruiter-to-candidate patterns
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?(recruiter|recruitment|hiring|talent acquisition|talent|hr|human resources) (outreach|cold|initial|contact|introductory|first|opening) email (to|for|sent to|addressed to) (a |an )?(prospective |potential |candidate |job seeker )?(?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s? (for|about|regarding|concerning)(\?|$|\s)",
                r"(recruiter|recruitment|hiring|talent acquisition|talent|hr|human resources) (outreach|cold|initial|contact|introductory|first|opening) email (to|for|sent to|addressed to) (a |an )?(prospective |potential |candidate |job seeker )?(?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s? (for|about|regarding|concerning)(\?|$|\s)",
                r"(draft|create|write|compose|prepare|craft|build|formulate|develop) (a |an )?outreach email (from|by) (a |an )?recruiter (to|for|addressed to) (a |an )?(?:candidate|professional)s? (for|about|regarding|concerning) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",
                r"(write|create|draft|compose|prepare|craft|build|formulate|develop) (a |an )?recruiter email (to|for|addressed to) (a |an )?(potential |prospective |candidate |job seeker )?(?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",

                # HIGH PRIORITY: Candidate pitch/outreach patterns (recruiter perspective)
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?candidate (pitch|outreach) email (to|for|sent to|addressed to) (a |an )?(prospective |potential )?candidate (for|about|regarding|concerning) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",
                r"(draft|create|write|compose|prepare|craft|build|formulate|develop) (a |an )?(candidate pitch|outreach email) (to|for|sent to|addressed to) (a |an )?(prospective |potential )?candidate (about|regarding|concerning) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",

                # MEDIUM PRIORITY: Generic email to candidates (must exclude application context)
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?email (to|for|sent to|addressed to) (a |an )?(prospective |potential |candidate |job seeker )?candidates? (for|about|regarding|concerning) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(?!.*(apply|application|applying|job I want|position I want|role I want|why I\'m|why I am|great fit|qualified for))(\?|$|\s)",

                # LOWER PRIORITY: Action-based patterns
                r"(message|contact|reach out to|connect with) (potential |prospective )?candidates? (for|about|regarding) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",
                r"(recruitment|hiring|talent) (message|communication|correspondence) (for|about|regarding) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)",
                r"(prospect|recruit|approach) (candidates?|professionals?) (for|about|regarding) (?P<role>(?:senior |junior |lead |principal |staff )?[A-Za-z -]+(?: engineer| developer| scientist| analyst| manager| specialist))s?(\?|$|\s)"
            ],
            "candidate_pitch_email": [
                # HIGHEST PRIORITY: Explicit candidate-to-company patterns with application intent
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?email (to|for|sent to|addressed to) (a |an )?(company|employer|hiring manager|recruiter|organization|business) (about|regarding|concerning) (a |an |the )?(?P<role>[^?]*?) (I want to apply for|I want|I'm applying for|I am applying for|position|job|role)(\?|$|\s)",
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?email (to|for|sent to|addressed to) (a |an )?(hiring manager|recruiter|company|employer) (about|regarding|concerning) (a |an |the )?(?P<role>[^?]*?) (and why I'm|and why I am|explaining why I'm|explaining why I am) (a |an )?(great fit|good fit|qualified|suitable|perfect|ideal)(\?|$|\s)",
                
                # HIGH PRIORITY: Explicit candidate application patterns
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?(candidate|job seeker|applicant|professional|individual) (pitch|application|cover letter|email|proposal|presentation|introduction) (to|for|sent to|addressed to) (a |an )?(company|employer|hiring manager|recruiter|organization|business) (for|about|regarding|concerning) (?P<role>[^?]*?)(\?|$|\s)",
                r"(candidate|job seeker|applicant|professional|individual) (pitch|application|cover letter|email|proposal|presentation|introduction) (to|for|sent to|addressed to) (a |an )?(company|employer|hiring manager|recruiter|organization|business) (for|about|regarding|concerning) (?P<role>[^?]*?)(\?|$|\s)",
                
                # MEDIUM PRIORITY: Application-specific patterns
                r"(generate|create|write|draft|compose|prepare|craft|build|formulate|develop) (a |an )?(pitch|application|cover letter|email|proposal|presentation|introduction) (from|by) (a |an )?(candidate|job seeker|applicant|professional|individual) (to|for|sent to|addressed to) (a |an )?(company|employer|hiring manager|recruiter|organization|business) (for|about|regarding|concerning) (?P<role>[^?]*?)(\?|$|\s)",
                r"(pitch|application|cover letter|email|proposal|presentation|introduction) (from|by) (a |an )?(candidate|job seeker|applicant|professional|individual) (to|for|sent to|addressed to) (a |an )?(company|employer|hiring manager|recruiter|organization|business) (for|about|regarding|concerning) (?P<role>[^?]*?)(\?|$|\s)",
                
                # LOWER PRIORITY: Generic application patterns
                r"(job|position|role) (application|pitch|proposal) (email|letter|message) (for|about|regarding) (?P<role>[^?]*?)(\?|$|\s)",
                r"(apply|pitch|present) (for|to) (?P<role>[^?]*?) (position|job|role)(\?|$|\s)",
                r"(cover letter|application letter|introductory email) (for|about|regarding) (?P<role>[^?]*?)(\?|$|\s)"
            ],
            "candidate_outreach": [
                r"(contact|reach out to|message|email|call|connect with|get in touch with) (a |an )?(candidate|applicant|professional|individual) (?P<candidate>[^?]*?)(\?|$|\s)",
                r"(outreach|communication|correspondence) (to|with) (a |an )?(candidate|applicant|professional|individual) (?P<candidate>[^?]*?)(\?|$|\s)",
                r"(follow up|check in|touch base) (with) (?P<candidate>[^?]*?)(\?|$|\s)"
            ],
            "view_profile": [
                r"(show|view|display|get|see|access|open) (?P<candidate>.*?)('s)? (profile|resume|information|details|background|history)",
                r"(profile|resume|information|details|background|history)( for| of) (?P<candidate>.*)",
                r"(look at|examine|review) (?P<candidate>.*?)('s)? (profile|resume)(\?|$|\s)"
            ],
            "job_match": [
                r"match (?P<candidate>.*) (with|to) (?P<job>.*)",
                r"find (jobs|roles|positions|opportunities) for (?P<candidate>.*)",
                r"(which|what) (jobs|roles|positions|opportunities) (match|fit|suit|are suitable for) (?P<candidate>.*)",
                r"(recommend|suggest) (jobs|roles|positions) (for|to) (?P<candidate>.*)"
            ],
            "salary_info": [
                r"(what|how much|what is|what are) (is |are )?the (salary|compensation|pay|earnings|income|wages|hourly rate|hourly pay|annual pay|monthly pay|yearly pay)(.*?)(for|of) (?P<role>.*)",
                r"(how much|what) (do|does) (?P<role>.*) (make|earn|get paid|receive|take home|bring in)",
                r"(salary|compensation|pay) (range|information|details|statistics|data|scale|band|bracket|level) for (?P<role>.*)",
                r"(what|how much) (is|are) (?P<role>.*) (paid|earning|making|compensated|receiving)",
                r"(average|median|typical|expected|standard|normal|usual) (salary|pay|compensation|income|earnings) for (?P<role>.*?)( in| with| at)? (?P<location>.*)?",
                r"what should I (pay|offer|compensate|provide) (a|an) (?P<role>.*)",
                r"what('s| is) a (good|fair|competitive|reasonable|appropriate|suitable) (salary|offer|package|compensation|pay) for (?P<role>.*)",
                r"(salary|pay|compensation) (for|of) (?P<role>.*)(\?|$|\s)",
                r"(how much|what) (does|do) (?P<role>.*) (typically|usually|normally) (make|earn|get paid)(\?|$|\s)"
            ],
            "company_info": [
                r"(information|details|facts|data|background) (about|on|for|regarding) (?P<company>.*)",
                r"(what|tell me about|how is) (is |are )?(?P<company>.*) (as a company|as an employer|as an organization)",
                r"(who is|what is) (?P<company>.*) (company|organization|business)?",
                r"(benefits|culture|work life|work environment|perks|advantages) (at|in|of) (?P<company>.*)",
                r"(tell me|what do you know|find information|get details) (about|on|regarding) (?P<company>.*)",
                r"(company|organization|business) (profile|overview|information) (for|of) (?P<company>.*)"
            ],
            "skill_info": [
                r"(what|which) (are|is) (the )?(most|top|best|important|key|valuable|in-demand|critical|essential|required|necessary) (skills|technologies|tools|competencies|expertise|knowledge|qualifications|requirements)( needed| required| useful| valuable| important)?( for| in)? (?P<role>.*)",
                r"skills (for|to become|needed for|required for|essential for|important for) (?P<role>.*)",
                r"(?P<role>.*) (skills|qualifications|requirements|competencies|expertise|knowledge)",
                r"(what|which) (skills|technologies|tools) (are needed|do you need|are required|are essential) (for|to become) (?P<role>.*)",
                r"(learn|study|master|acquire) (skills|technologies|tools) (for|to become) (?P<role>.*)"
            ],
            "candidate_breakdown": [
                r"(breakdown|distribution|categorization) of candidates by (?P<attribute>.*)",
                r"(what|tell me|show me) (kinds|types) of candidates (we have|in the (database|system))",
                r"(breakdown|show|list) candidates by (?P<attribute>role|roles|position|positions|job|jobs|title|titles|skill|skills|location|locations|experience|field|seniority)",
                r"how many candidates (do we have|are there) (for each|by|per) (?P<attribute>role|roles|position|positions|job|jobs|title|titles|skill|skills|location|locations|experience|field|seniority)"
            ],
            "candidate_comparison": [
                r"compare (the |)candidates? (?P<candidate1>.*?) (and|with|to|vs|versus) (?P<candidate2>.*)",
                r"(who is|which candidate is) (better|stronger|more qualified|more experienced)( for| in| at)? (?P<job>.*?)(:|,|\?| -) (?P<candidate1>.*?) (or|vs|versus) (?P<candidate2>.*)",
                r"differences? between (?P<candidate1>.*?) and (?P<candidate2>.*?)('s| in terms of| regarding| for) (qualifications|experience|skills|background)"
            ],
            "skill_gap_analysis": [
                r"(what|which) skills (does|do) (?P<candidate>.*?) (need|lack|missing|require) (for|to qualify for|to be considered for) (?P<job>.*)",
                r"(skill|experience|qualification) gaps? (for|of) (?P<candidate>.*?) (for|to match|to qualify for) (?P<job>.*)",
                r"how (can|could|should) (?P<candidate>.*?) improve (to qualify for|to be considered for|to match|to be competitive for) (?P<job>.*)"
            ],
            "hiring_timeline": [
                r"how long (will it take|does it take|should it take) to (hire|recruit|find|onboard) (a|an) (?P<role>.*?)(\?|$|\s)",
                r"(what is|what's) the (average|typical|expected|normal) (time|timeline|timeframe|duration) (for|to) (hire|recruit|fill) (a|an) (?P<role>.*?)(\?|$|\s)",
                r"(estimate|project|forecast) (the|) (hiring|recruitment|onboarding) (time|timeline|process) for (a|an) (?P<role>.*?)(\?|$|\s)"
            ],
            "market_trends": [
                r"(what are|what's|tell me about) the (current|latest|recent|today's) (market|industry|hiring|recruitment|job) trends (for|in|related to) (?P<domain>.*)",
                r"(how is|what's) the (job|employment|hiring|talent) market (for|in) (?P<domain>.*)",
                r"demand for (?P<skill>.*?) (skills|expertise|professionals|talent) (in|at|with) (?P<location>.*)"
            ],
            "advanced_matching": [
                r"(find|match|show|identify) (the best|top|qualified|ideal) candidates? for (?P<job>.*?)(\?|$|\s)",
                r"which candidates? (would be|is|are|matches|fit|suits|qualifies) (best|well|good|ideal) for (?P<job>.*?)(\?|$|\s)",
                r"(who|which candidates?) (can|could|should|would) (we|I) (consider|interview|recruit|hire|contact) for (?P<job>.*?)(\?|$|\s)"
            ],
            "web_search": [
                r"(search|look up|find information on|find info on|find) (for |about |on )?(?P<query>.*)",
                r"(google|web search|search the web for) (?P<query>.*)",
                r"(find|get|tell me) (market|industry) (data|information|stats|statistics|figures) (on|for|about) (?P<query>.*)",
                r"(research|look into|gather information about) (?P<query>.*)",
                r"what (can you find|information exists|data is available) (about|on|for) (?P<query>.*)"
            ],
            "job_posting_analysis": [
                r"(analyze|review|check|evaluate) (this |the )?job posting( at| from| on)? (?P<url>https?://\S+)",
                r"what (can you tell|do you think) about (this |the )?job( posting| listing| description)( at| from| on)? (?P<url>https?://\S+)",
                r"extract (information|details|requirements) from (this |the )?job( posting| listing)( at| from| on)? (?P<url>https?://\S+)"
            ],
            "company_research": [
                r"(research|get information about|tell me about) (the company|the organization|the employer) (?P<company>.*)",
                r"(find|get|extract) (details|information|data) (about|on) (?P<company>.*?) (from|at|on) (?P<url>https?://\S+)",
                r"what (is|do you know about) (?P<company>.*?) (based on|from|according to) (?P<url>https?://\S+)",
                r"(crawl|scrape|extract from) (?P<url>https?://\S+) (about|for|on) (?P<company>.*)"
            ],
            "minimum_wage": [
                r"(what is|current|latest)? ?(the )?(minimum wage|legal minimum wage|lowest wage|base wage|minimum hourly wage|minimum hourly pay|lowest legal wage|minimum salary requirement)( in| for)? (?P<location>.*)",
                r"minimum wage( in| for)? (?P<location>.*)",
                r"current minimum wage( in| for)? (?P<location>.*)",
                r"legal pay rate( in| for)? (?P<location>.*)",
                r"state minimum wage( in| for)? (?P<location>.*)",
                r"what('s| is) the (minimum|lowest) (wage|pay|salary)( in| for| of)? (?P<location>.*)",
                r"how (much|little) (is|can) (someone|a worker|an employee) (legally )?(be )?(paid|earn)( in| for)? (?P<location>.*)"
            ],
            "labor_law": [
                r"(what is|tell me about|explain|describe)? ?(the )?(overtime law|labor law|employment law|work hour law|break law|rest law|holiday law|paid leave|sick leave|maternity leave|paternity leave|legal requirements|labor regulations|employee rights|worker rights|legal protections)( in| for)? (?P<location>.*)",
                r"overtime law(s)?( in| for)? (?P<location>.*)",
                r"labor law(s)?( in| for)? (?P<location>.*)",
                r"employment law(s)?( in| for)? (?P<location>.*)",
                r"work hour law(s)?( in| for)? (?P<location>.*)",
                r"(legal|legally required) (breaks|rest periods|overtime|benefits)( in| for)? (?P<location>.*)",
                r"(pto|paid time off|vacation|sick day|leave) (requirements|laws|regulations|policies)( in| for)? (?P<location>.*)",
                r"what are (employers|companies) (legally )?(required|obligated) to (provide|offer|give)( in| for)? (?P<location>.*)",
                r"what are (employee|worker) rights( regarding| for| about| on)? ([a-zA-Z ]+)( in| for)? (?P<location>.*)"
            ]
        }
        
        # Comprehensive synonym mappings for better intent detection
        self.intent_synonyms = {
            # Action synonyms
            "generate": ["create", "write", "draft", "compose", "prepare", "craft", "build", "formulate", "develop", "make", "produce"],
            "find": ["search", "show", "get", "locate", "discover", "identify", "look for", "seek", "find", "retrieve"],
            "show": ["display", "get", "see", "access", "open", "view", "present", "reveal"],
            "tell": ["inform", "explain", "describe", "share", "provide", "give", "offer"],
            
            # Email-related synonyms
            "email": ["message", "correspondence", "communication", "letter", "note", "mail"],
            "pitch": ["application", "proposal", "presentation", "introduction", "cover letter", "submission"],
            "outreach": ["contact", "communication", "approach", "connection", "engagement"],
            
            # Role synonyms
            "candidate": ["applicant", "professional", "individual", "job seeker", "talent", "person"],
            "recruiter": ["hiring manager", "talent acquisition", "hr", "human resources", "recruitment"],
            "company": ["employer", "organization", "business", "firm", "corporation"],
            
            # Travel synonyms
            "travel": ["commute", "journey", "trip", "drive", "ride", "walk", "bike", "cycle"],
            "time": ["duration", "length", "period", "span"],
            "distance": ["how far", "length", "span"],
            
            # Salary synonyms
            "salary": ["compensation", "pay", "earnings", "income", "wages", "remuneration"],
            "how much": ["what", "what is", "what are", "amount", "figure"],
            
            # Search synonyms
            "search": ["find", "search", "candidates", "professionals", "developers", "engineers", "with", "who have", "skilled", "experienced", "python", "java", "react", "javascript"],
            "candidates": ["professionals", "developers", "engineers", "people", "applicants"],
            
            # Information synonyms
            "information": ["details", "facts", "data", "background", "info", "particulars"],
            "about": ["regarding", "concerning", "on", "for", "related to"],
        }
        
        # Enhanced fuzzy matching keywords for each intent
        self.intent_keywords = {
            "travel_time": ["travel", "commute", "journey", "trip", "drive", "fly", "train", "bus", "time", "duration", "how long", "distance", "how far", "from", "to", "between"],
            "search_candidates": ["find", "search", "candidates", "professionals", "developers", "engineers", "with", "who have", "skilled", "experienced", "python", "java", "react", "javascript"],
            "recruiter_outreach_email": ["recruiter", "outreach", "email", "generate", "create", "write", "draft", "candidates", "prospective", "potential", "hiring", "talent"],
            "candidate_pitch_email": ["candidate", "pitch", "email", "application", "cover letter", "generate", "create", "write", "draft", "company", "employer", "job seeker"],
            "salary_info": ["salary", "pay", "compensation", "how much", "earnings", "income", "wages", "make", "earn", "get paid", "average", "typical"],
            "company_info": ["company", "employer", "organization", "information", "details", "about", "culture", "benefits", "work life"],
            "applications_count": ["how many", "applied", "applications", "applicants", "count", "number of"],
            "market_research": ["market", "analysis", "research", "viability", "talent", "sourcing", "assess", "evaluate", "conduct", "feasibility", "hiring", "manager", "briefing", "compare", "identify", "create", "plan", "json", "externally"],
            "web_search": ["search", "find", "information", "about", "what", "how", "tell me", "look up", "research"],
            "general_question": ["what", "how", "why", "when", "where", "who", "help", "hello", "hi", "can you", "could you"],
        }
    
    async def initialize(self) -> bool:
        """Initialize the intent processor with service dependencies."""
        try:
            logger.info("IntentProcessor: Starting initialization...")
            
            # Get service registry
            from .service_registry import get_service_registry
            registry = get_service_registry()
            
            # Initialize web search service
            try:
                self.web_search_service = get_web_search_service()
                if self.web_search_service:
                    logger.info("IntentProcessor: Web search service available")
                else:
                    logger.warning("IntentProcessor: Web search service not available")
            except Exception as e:
                logger.error(f"IntentProcessor: Failed to initialize web search service: {e}")
                self.web_search_service = None
            
            # Initialize crawler service
            try:
                self.crawler_service = registry.crawler_service
                if self.crawler_service:
                    logger.info("IntentProcessor: Crawler service available")
                else:
                    logger.warning("IntentProcessor: Crawler service not available")
            except Exception as e:
                logger.error(f"IntentProcessor: Failed to initialize crawler service: {e}")
                self.crawler_service = None
            
            # Initialize travel service
            try:
                self.travel_service = registry.travel_service
                logger.info("IntentProcessor: Travel service initialized")
            except Exception as e:
                logger.error(f"IntentProcessor: Failed to initialize travel service: {e}")
                self.travel_service = None
            
            # Initialize communications service
            try:
                self.communications_service = registry.communications_service
                if self.communications_service:
                    logger.info("IntentProcessor: Communications service available")
                else:
                    logger.warning("IntentProcessor: Communications service not available")
            except Exception as e:
                logger.error(f"IntentProcessor: Failed to initialize communications service: {e}")
                self.communications_service = None
            
            self._initialized = True
            logger.info("IntentProcessor: Successfully initialized")
            return True
            
        except Exception as e:
            logger.error(f"IntentProcessor: Initialization failed: {e}")
            self._initialized = False
            return False
        
    def process_candidate_search(self, entities, message):
        """
        Process the search_candidates intent in a database-agnostic way.
        
        Args:
            entities: Dict containing detected entities
            message: Original user message
            
        Returns:
            Dict with updated entities that don't rely on specific database field names
        """
        role = entities.get('role', '')
        skills = entities.get('skills', '')
        domain = entities.get('domain', '')
        
        # Try to extract role from message if not found in entities
        if not role:
            if "data scientist" in message.lower():
                role = "data scientist"
            elif "find me all" in message.lower():
                # Extract any role mentioned after "find me all"
                role_match = re.search(r"find me all ([a-zA-Z ]+) candidates", message.lower())
                if role_match:
                    role = role_match.group(1).strip()
            elif "software" in message.lower() or "developer" in message.lower():
                # Extract common tech roles
                role_match = re.search(r"(software|senior|junior|full.?stack|back.?end|front.?end|dev|developer|engineer)", message.lower())
                if role_match:
                    role = role_match.group(0).strip()
                
        # Try to extract skills from message if not found in entities
        if not skills:
            common_skills = ["python", "java", "javascript", "c#", "c++", "sql", "react", "node", 
                            "angular", "aws", "azure", "machine learning", "data science"]
            
            for skill in common_skills:
                if skill in message.lower():
                    skills = skill
                    break
        
        # Update entities with extracted information
        updated_entities = entities.copy()
        if role:
            updated_entities['role'] = role
        if skills:
            updated_entities['skills'] = skills
        if domain:
            updated_entities['domain'] = domain
            
        return updated_entities
        
    async def detect_intent(self, message: str, conversation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enhanced intent detection with semantic routing and confidence gating.
        """
        logger.info(f"detect_intent: Received message: '{message}' (mode: {settings.INTENT_ROUTER_MODE})")
        
        # Input validation and preprocessing
        message = message.strip()
        if not message:
            return self._empty_query_response()
        
        if len(message) > 2000:
            return self._query_too_long_response()
        
        # Store in conversation history
        self._update_conversation_history(message, conversation_context)
        
        # Route based on configured mode
        if settings.INTENT_ROUTER_MODE == "semantic" and self.semantic_router:
            return await self._semantic_intent_detection(message, conversation_context)
        elif settings.INTENT_ROUTER_MODE == "hybrid" and self.semantic_router:
            return await self._hybrid_intent_detection(message, conversation_context)
        else:
            # Legacy mode - use existing detection strategies
            return await self._legacy_intent_detection(message, conversation_context)

    async def _semantic_intent_detection(self, message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Pure semantic intent detection using the semantic router."""
        try:
            result = await self.semantic_router.route_intent(message, conversation_context)
            return await self._apply_confidence_gating(result, message, conversation_context)
        except Exception as e:
            logger.error(f"Semantic intent detection failed: {e}")
            # Fallback to legacy detection
            return await self._legacy_intent_detection(message, conversation_context)

    async def _hybrid_intent_detection(self, message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Hybrid intent detection combining semantic and legacy approaches."""
        try:
            # Try semantic first
            semantic_result = await self.semantic_router.route_intent(message, conversation_context)
            
            # If semantic has high confidence, use it
            if semantic_result.get("confidence", 0) >= self.semantic_router.high_threshold:
                logger.info(f"Hybrid: Using semantic result (confidence: {semantic_result['confidence']})")
                return await self._apply_confidence_gating(semantic_result, message, conversation_context)
            
            # Try legacy detection for comparison
            legacy_result = await self._legacy_intent_detection(message, conversation_context)
            
            # Choose the better result
            if legacy_result.get("confidence", 0) > semantic_result.get("confidence", 0):
                logger.info(f"Hybrid: Using legacy result (confidence: {legacy_result['confidence']})")
                return legacy_result
            else:
                logger.info(f"Hybrid: Using semantic result (confidence: {semantic_result['confidence']})")
                return await self._apply_confidence_gating(semantic_result, message, conversation_context)
                
        except Exception as e:
            logger.error(f"Hybrid intent detection failed: {e}")
            # Fallback to legacy detection
            return await self._legacy_intent_detection(message, conversation_context)

    async def _legacy_intent_detection(self, message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy intent detection using existing strategies."""
        # Try multiple detection strategies in order
        detection_strategies = [
            ('direct_pattern', self._try_direct_pattern_detection),
            ('llm_detection', self._try_llm_detection),
            ('fuzzy_matching', self._try_fuzzy_detection),
            ('contextual_inference', self._try_contextual_inference),
            ('keyword_clustering', self._try_keyword_clustering)
        ]
        
        best_result = None
        best_confidence = 0
        
        for strategy_name, strategy_func in detection_strategies:
            try:
                result = await strategy_func(message, conversation_context)
                if result and result.get('confidence', 0) > best_confidence:
                    best_result = result
                    best_confidence = result['confidence']
                    logger.info(f"Strategy '{strategy_name}' produced result with confidence {best_confidence}")
                    
                    # If we have high confidence, stop trying other strategies
                    if best_confidence > 0.85:
                        break
            except Exception as e:
                logger.error(f"Strategy '{strategy_name}' failed: {e}")
                continue
        
        # If all strategies failed or produced low confidence
        if not best_result or best_confidence < 0.3:
            best_result = self._generate_clarification_response(message, conversation_context)
        
        # Post-process the result
        best_result = self._post_process_intent_result(best_result, message, conversation_context)
        
        # Update conversation context
        if conversation_context is not None:
            self._update_context_with_result(conversation_context, best_result)
        
        return best_result

    async def _apply_confidence_gating(self, result: Dict[str, Any], message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply confidence gating with clarifying questions for ambiguous intents."""
        confidence = result.get("confidence", 0)
        intent = result.get("intent", "general_question")
        missing_slots = result.get("missing_slots", [])
        
        # Log telemetry data
        self._log_intent_telemetry(result, message, conversation_context)
        
        # High confidence: execute directly
        if confidence >= self.semantic_router.high_threshold:
            logger.info(f"High confidence ({confidence:.2f}): executing {intent} directly")
            return self._finalize_intent_result(result, message, conversation_context)
        
        # Medium confidence: execute with soft confirmation
        elif confidence >= self.semantic_router.mid_threshold:
            logger.info(f"Medium confidence ({confidence:.2f}): executing {intent} with soft confirmation")
            result = self._add_soft_confirmation(result)
            return self._finalize_intent_result(result, message, conversation_context)
        
        # Low confidence or missing required slots: ask clarifying questions
        else:
            logger.info(f"Low confidence ({confidence:.2f}) or missing slots {missing_slots}: requesting clarification")
            
            # Check if we have a pending clarification context
            if conversation_context and conversation_context.get("pending_intent"):
                # User is responding to a previous clarifying question
                return await self._handle_clarification_response(result, message, conversation_context)
            
            # Generate clarifying question
            if self.semantic_router and missing_slots:
                clarifying_question = self.semantic_router.generate_clarifying_question(
                    intent, missing_slots, result.get("entities", {})
                )
                
                if clarifying_question:
                    return self._create_clarification_response(result, clarifying_question, conversation_context)
            
            # Fallback to generic clarification
            return self._generate_generic_clarification(result, message, conversation_context)

    def _add_soft_confirmation(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add soft confirmation prompt to medium confidence results."""
        result["soft_confirmation"] = True
        result["confirmation_prompt"] = "Is this what you're looking for? Let me know if you need something different."
        return result

    def _create_clarification_response(self, result: Dict[str, Any], clarifying_question: Dict[str, Any], conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a response that asks for clarification."""
        
        # Store pending intent in conversation context
        if conversation_context is not None:
            conversation_context["pending_intent"] = result["intent"]
            conversation_context["pending_entities"] = result.get("entities", {})
            conversation_context["pending_slot"] = clarifying_question["slot_name"]
        
        question_text = clarifying_question["question"]
        if clarifying_question.get("options"):
            options_text = " Options: " + ", ".join(f"'{opt}'" for opt in clarifying_question["options"])
            question_text += options_text
        
        return {
            "intent": "clarification_needed",
            "entities": result.get("entities", {}),
            "confidence": 1.0,
            "requires_clarification": True,
            "clarification_question": question_text,
            "clarifying_slot": clarifying_question["slot_name"],
            "clarifying_options": clarifying_question.get("options"),
            "context_updates": conversation_context or {}
        }

    async def _handle_clarification_response(self, result: Dict[str, Any], message: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user response to a clarifying question."""
        
        pending_intent = conversation_context.get("pending_intent")
        pending_entities = conversation_context.get("pending_entities", {})
        pending_slot = conversation_context.get("pending_slot")
        
        if not pending_intent or not pending_slot:
            # Clear pending state and treat as new query
            conversation_context.pop("pending_intent", None)
            conversation_context.pop("pending_entities", None)
            conversation_context.pop("pending_slot", None)
            return await self.detect_intent(message, conversation_context)
        
        # Fill the missing slot with user's response
        pending_entities[pending_slot] = message.strip()
        
        # Clear pending state
        conversation_context.pop("pending_intent", None)
        conversation_context.pop("pending_entities", None)
        conversation_context.pop("pending_slot", None)
        
        # Create final result with filled slot
        final_result = {
            "intent": pending_intent,
            "entities": pending_entities,
            "confidence": 0.9,  # High confidence after clarification
            "method": "clarification_completed",
            "missing_slots": []
        }
        
        return self._finalize_intent_result(final_result, message, conversation_context)

    def _generate_generic_clarification(self, result: Dict[str, Any], message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a generic clarification response."""
        return {
            "intent": "clarification_needed",
            "entities": result.get("entities", {}),
            "confidence": 1.0,
            "requires_clarification": True,
            "clarification_question": "I'm not sure I understand what you're looking for. Could you please provide more details or rephrase your request?",
            "context_updates": conversation_context or {}
        }

    def _finalize_intent_result(self, result: Dict[str, Any], message: str, conversation_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Finalize the intent result with post-processing."""
        result = self._post_process_intent_result(result, message, conversation_context)
        
        # Update conversation context
        if conversation_context is not None:
            self._update_context_with_result(conversation_context, result)
        
        return result

    def _log_intent_telemetry(self, result: Dict[str, Any], message: str, conversation_context: Optional[Dict[str, Any]]):
        """Log structured telemetry for intent detection metrics."""
        telemetry_data = {
            "detected_intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "entities": list(result.get("entities", {}).keys()),
            "missing_slots": result.get("missing_slots", []),
            "method": result.get("method", "unknown"),
            "message_length": len(message),
            "has_context": bool(conversation_context),
            "asked_clarification": result.get("requires_clarification", False)
        }
        
        logger.info(f"Intent telemetry: {json.dumps(telemetry_data)}")

    def _empty_query_response(self) -> Dict[str, Any]:
        """Generate response for empty queries."""
        return {
            "intent": "clarification_needed",
            "entities": {},
            "confidence": 1.0,
            "requires_clarification": True,
            "clarification_question": "I need a question or request to assist you. What would you like to know?",
            "context_updates": {}
        }

    def _query_too_long_response(self) -> Dict[str, Any]:
        """Generate response for overly long queries."""
        return {
            "intent": "query_too_long",
            "entities": {},
            "confidence": 1.0,
            "requires_clarification": True,
            "clarification_question": "Your message is too long. Please try a shorter query (under 2000 characters).",
            "context_updates": {}
        }

    def _update_conversation_history(self, message: str, context: Optional[Dict[str, Any]]):
        """Update conversation history with the new message."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": message,
            "user_id": context.get("user_id") if context else None
        }
        
        self.conversation_history.append(entry)
        
        # Keep only last 10 entries to prevent memory issues
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

    async def _try_direct_pattern_detection(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Try direct pattern matching first."""
        intent, entities = self._match_patterns(message)
        
        if intent:
            return {
                "intent": intent,
                "entities": entities,
                "confidence": 0.9,
                "detection_method": "pattern_matching",
                "context_updates": {}
            }
        
        return None

    async def _try_llm_detection(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Try LLM-based detection."""
        if not self.llm_service:
            return None
        
        try:
            result = await self._llm_intent_detection(message, context)
            result["detection_method"] = "llm"
            return result
        except Exception as e:
            logger.error(f"LLM detection failed: {e}")
            return None

    async def _try_fuzzy_detection(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Try fuzzy matching detection."""
        result = self._fuzzy_match_intents(message.lower())
        if result:
            result["detection_method"] = "fuzzy_matching"
            result["context_updates"] = {}
        return result

    async def _try_contextual_inference(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Try contextual inference."""
        result = self._infer_intent_from_context(message)
        if result:
            result["confidence"] = result.get("confidence", 0.6)
            result["detection_method"] = "contextual_inference"
            result["context_updates"] = {}
        return result

    async def _try_keyword_clustering(self, message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Try keyword clustering as a last resort.
        Groups keywords to identify probable intent.
        """
        message_lower = message.lower()
        
        # Keyword clusters for different intent categories
        clusters = {
            'recruitment': {
                'keywords': ['hire', 'recruit', 'candidate', 'applicant', 'talent', 'sourcing'],
                'intents': ['search_candidates', 'candidate_sourcing_strategy', 'advanced_matching']
            },
            'travel': {
                'keywords': ['travel', 'commute', 'distance', 'route', 'transportation', 'drive', 'fly'],
                'intents': ['travel_time', 'transportation_options']
            },
            'compensation': {
                'keywords': ['salary', 'pay', 'wage', 'compensation', 'earn', 'income', 'money'],
                'intents': ['salary_info', 'minimum_wage']
            },
            'analytics': {
                'keywords': ['count', 'how many', 'number', 'statistics', 'breakdown', 'distribution'],
                'intents': ['candidate_count', 'job_count', 'candidate_breakdown']
            },
            'communication': {
                'keywords': ['email', 'message', 'reach out', 'contact', 'pitch', 'outreach'],
                'intents': ['recruiter_outreach_email', 'candidate_pitch_email', 'candidate_outreach']
            }
        }
        
        # Count keyword matches per cluster
        cluster_scores = {}
        for cluster_name, cluster_data in clusters.items():
            score = sum(1 for keyword in cluster_data['keywords'] if keyword in message_lower)
            if score > 0:
                cluster_scores[cluster_name] = score
        
        if not cluster_scores:
            return None
        
        # Get the best matching cluster
        best_cluster = max(cluster_scores.items(), key=lambda x: x[1])
        cluster_name, score = best_cluster
        
        # Select most likely intent from the cluster
        possible_intents = clusters[cluster_name]['intents']
        
        # Try to match against specific patterns for intents in the cluster
        for intent in possible_intents:
            if intent in self.intent_patterns:
                # Do a lighter check for pattern presence
                for pattern in self.intent_patterns[intent]:
                    if re.search(pattern, message_lower, re.IGNORECASE):
                        entities = self._extract_entities_for_intent(intent, message)
                        return {
                            "intent": intent,
                            "entities": entities,
                            "confidence": 0.65,
                            "detection_method": "keyword_clustering",
                            "context_updates": {}
                        }
        
        # If no specific pattern matched, return the first intent with low confidence
        return {
            "intent": possible_intents[0],
            "entities": {},
            "confidence": 0.5,
            "detection_method": "keyword_clustering",
            "context_updates": {}
        }

    def _generate_clarification_response(self, message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a clarification response when intent cannot be determined.
        """
        # Analyze what might be unclear
        message_lower = message.lower()
        
        # Generate contextual clarification
        clarification = "I'm not sure what you're asking about. "
        
        if any(word in message_lower for word in ['candidate', 'person', 'applicant']):
            clarification += "Are you looking to search for candidates, view candidate information, or something else?"
        elif any(word in message_lower for word in ['job', 'position', 'opening']):
            clarification += "Are you asking about job postings, job matching, or job statistics?"
        elif any(word in message_lower for word in ['travel', 'go', 'get']):
            clarification += "Are you asking about travel time or transportation options? Please specify the origin and destination."
        else:
            clarification += "Could you please rephrase your question or provide more details?"
        
        return {
            "intent": "clarification_needed",
            "entities": {},
            "confidence": 0.0,
            "requires_clarification": True,
            "clarification_question": clarification,
            "original_query": message,
            "context_updates": {}
        }

    def _post_process_intent_result(self, result: Dict[str, Any], message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post-process the intent detection result for consistency and completeness.
        """
        # Ensure all required fields are present
        result.setdefault('confidence', 0.5)
        result.setdefault('entities', {})
        result.setdefault('context_updates', {})
        result.setdefault('detection_method', 'unknown')
        
        # Determine confidence level
        result['confidence_level'] = self._determine_confidence_level(result['confidence'])
        
        # Check if clarification is needed
        result['requires_clarification'] = result['confidence'] < self.confidence_thresholds['medium']
        
        if result['requires_clarification'] and 'clarification_question' not in result:
            result['clarification_question'] = self._generate_clarification_question(
                message, result['intent'], result['entities']
            )
        
        # Special handling for certain intents
        if result['intent'] == 'search_candidates':
            result['entities'] = self.process_candidate_search(result['entities'], message)
            # If the user explicitly requests external/online search for candidates,
            # repurpose to web_search to avoid mixing DB results with web results.
            message_lower = message.lower()
            external_markers = [
                "externally", "outside the database", "outside database",
                "online", "on the web", "on web", "search the web", "search online"
            ]
            if ("candidate" in message_lower) and any(m in message_lower for m in external_markers):
                result['context_updates']['redirected_from'] = 'search_candidates'
                result['intent'] = 'web_search'
                # Pass the original message as the query to keep behavior dynamic
                result['entities'] = {"query": message}
        
        # Add message context
        result['original_message'] = message
        result['message_length'] = len(message)
        result['timestamp'] = datetime.now().isoformat()
        
        return result

    def _update_context_with_result(self, context: Dict[str, Any], result: Dict[str, Any]):
        """
        Update conversation context with the detection result.
        """
        context['last_intent'] = result['intent']
        context['last_entities'] = result.get('entities', {})
        context['last_confidence'] = result.get('confidence', 0)
        context['last_detection_method'] = result.get('detection_method', 'unknown')
        
        # Apply any context updates from the result
        for key, value in result.get('context_updates', {}).items():
            context[key] = value
        
        # Track intent history
        if 'intent_history' not in context:
            context['intent_history'] = []
        
        context['intent_history'].append({
            'intent': result['intent'],
            'confidence': result['confidence'],
            'timestamp': result.get('timestamp', datetime.now().isoformat())
        })
        
        # Keep only last 5 intents
        if len(context['intent_history']) > 5:
            context['intent_history'] = context['intent_history'][-5:]
        
    async def generate_general_response(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """ 
        Generate a response for general queries using the LLM.
        This handles queries that don't fit specific intents.
        """
        if not self.llm_service:
            return "I'm sorry, I'm having trouble processing general queries at the moment. Please try asking about specific candidates, jobs, or recruitment-related topics."
        
        # Build context for the LLM
        context_info = ""
        if context:
            recent_intents = context.get('intent_history', [])[-3:]
            if recent_intents:
                context_info = "Recent conversation topics: " + ", ".join([h['intent'] for h in recent_intents])
        
        system_prompt = """You are a helpful AI recruitment assistant. You can help with:
        - Finding and searching for candidates
        - Job matching and recruitment strategies
        - Salary and compensation information
        - Travel and commute information
        - Company research and market trends
        - Writing recruitment emails
        - General HR and recruitment advice
        
        If the user's query is outside these areas, provide a helpful response while gently guiding them back to recruitment-related topics.
        Be conversational, helpful, and professional."""
        
        prompt = f"""
        {context_info}
        
        User query: {message}
        
        Provide a helpful response. If this seems like a recruitment-related query that might need specific data, 
        suggest how the user could rephrase it to get better results.
        """
        
        try:
            response = await self.llm_service.generate_text_async(
                prompt=prompt,
                system_message=system_prompt
            )
            return response
        except Exception as e:
            logger.error(f"Error generating general response: {e}")
            return "I apologize, but I'm having trouble understanding your request. Could you please rephrase it or ask about specific recruitment-related topics?"

    def _extract_role_from_message(self, message: str) -> Optional[str]:
        """
        Extract role from message when pattern matching fails.
        
        Args:
            message: User message
            
        Returns:
            Extracted role or None
        """
        message_lower = message.lower()
        
        # Common role patterns with case preservation - ORDER MATTERS: Most specific first
        role_patterns = [
            # Data-related roles (most specific first to avoid conflicts)
            ("data engineer", r"data engineer"),
            ("senior data engineer", r"senior data engineer"),
            ("junior data engineer", r"junior data engineer"),
            ("lead data engineer", r"lead data engineer"),
            ("principal data engineer", r"principal data engineer"),
            ("data engineering", r"data engineering"),
            ("data scientist", r"data scientist"),
            ("senior data scientist", r"senior data scientist"),
            ("data analyst", r"data analyst"),
            
            # AI/ML roles
            ("gen ai", r"gen ai"),
            ("generative ai", r"generative ai"),
            ("AI engineer", r"ai engineer"),
            ("machine learning engineer", r"machine learning engineer"),
            ("ml engineer", r"ml engineer"),
            
            # Software roles
            ("software engineer", r"software engineer"),
            ("senior software engineer", r"senior software engineer"),
            ("frontend developer", r"frontend developer"),
            ("backend developer", r"backend developer"),
            ("full stack developer", r"full stack developer"),
            ("devops engineer", r"devops engineer"),
            
            # Business roles
            ("product manager", r"product manager"),
            ("project manager", r"project manager"),
            ("business analyst", r"business analyst"),
            ("marketing", r"marketing"),
            ("sales", r"sales")
        ]
        
        # Check patterns in order (most specific first)
        for role_name, pattern in role_patterns:
            if pattern in message_lower:
                return role_name
        
        # Enhanced fallback logic - be more specific to avoid conflicts
        if "gen ai" in message_lower or "generative ai" in message_lower:
            return "gen ai"
        elif "ai engineer" in message_lower or ("ai" in message_lower and "engineer" in message_lower):
            return "AI engineer"
        elif "data engineer" in message_lower or ("data" in message_lower and "engineer" in message_lower):
            return "data engineer"
        elif "data scientist" in message_lower or ("data" in message_lower and "scientist" in message_lower):
            return "data scientist"
        elif "software" in message_lower or "developer" in message_lower:
            return "software engineer"
        elif "data" in message_lower:
            return "data scientist"  # Only if no other data role matches
        elif "marketing" in message_lower:
            return "marketing"
        else:
            return "data scientist"  # Default fallback

    def _match_patterns(self, message: str) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Enhanced pattern matching with fuzzy matching and confidence scoring.
{{ ... }}
        """
        message_lower = message.lower()
        logger.info(f"_match_patterns: Processing message: '{message_lower}'")
        
        # Store all matches with confidence scores
        potential_matches = []
        
        # Priority order remains the same
        intent_priority = [
            "travel_time", "transportation_options", "market_research",
            "candidate_count", "job_count", "applications_count", "search_candidates", 
            "candidate_sourcing_strategy", "candidate_outreach",
            "view_profile", "job_match", "salary_info", "company_info", 
            "skill_info", "candidate_breakdown", "candidate_comparison", 
            "skill_gap_analysis", "hiring_timeline", "market_trends", 
            "advanced_matching", "recruiter_outreach_email", 
            "candidate_pitch_email", "minimum_wage", "labor_law",
            "job_posting_analysis", "company_research", "web_search"
        ]
        
        for intent in intent_priority:
            if intent in self.intent_patterns:
                for pattern in self.intent_patterns[intent]:
                    match = re.search(pattern, message_lower, re.IGNORECASE)
                    if match:
                        # Calculate match confidence based on match coverage
                        match_start = match.start()
                        match_end = match.end()
                        coverage = (match_end - match_start) / len(message_lower)
                        
                        # Extract entities
                        entities = match.groupdict()
                        cleaned_entities = self._clean_entities(entities, intent, message)
                        
                        # Calculate entity confidence
                        entity_confidence = self._calculate_entity_confidence(cleaned_entities, intent)
                        
                        # Combined confidence
                        total_confidence = (coverage * 0.6 + entity_confidence * 0.4)
                        
                        potential_matches.append({
                            'intent': intent,
                            'entities': cleaned_entities,
                            'confidence': total_confidence,
                            'pattern': pattern
                        })
        
        # If no exact matches, try fuzzy matching
        if not potential_matches:
            fuzzy_match = self._fuzzy_match_intents(message_lower)
            if fuzzy_match:
                potential_matches.append(fuzzy_match)
        
        # Select best match
        if potential_matches:
            best_match = max(potential_matches, key=lambda x: x['confidence'])
            if best_match['confidence'] > 0.5:  # Threshold for acceptance
                # Disambiguate email direction if needed
                disamb_intent = self._disambiguate_email_direction(message_lower, best_match['intent'])
                if disamb_intent != best_match['intent']:
                    logger.info(f"Disambiguated email intent from {best_match['intent']} to {disamb_intent} based on message direction")
                    best_match['intent'] = disamb_intent
                logger.info(f"Selected match: {best_match['intent']} with confidence {best_match['confidence']}")
                return best_match['intent'], best_match['entities']
        
        # Try contextual intent inference as last resort
        contextual_intent = self._infer_intent_from_context(message)
        if contextual_intent:
            return contextual_intent['intent'], contextual_intent['entities']
        
        return None, {}

    def _clean_entities(self, entities: Dict[str, str], intent: str, message: str) -> Dict[str, str]:
        """
        Enhanced entity cleaning with context-aware processing.
        """
        cleaned_entities = {}
        
        for key, value in entities.items():
            if value:
                cleaned_value = value.strip()
                # Remove common trailing punctuation to avoid mismatches like 'data engineering.'
                cleaned_value = cleaned_value.rstrip('?.!,;:')
                cleaned_value = cleaned_value.replace(',', '')
                
                # Intent-specific cleaning
                if key == 'role':
                    cleaned_value = self._normalize_role_name(cleaned_value, message)
                elif key == 'company':
                    cleaned_value = self._normalize_company_name(cleaned_value)
                elif key == 'location':
                    cleaned_value = self._normalize_location(cleaned_value)
                elif key in ['origin', 'destination']:
                    cleaned_value = self._normalize_place_name(cleaned_value)
                
                if cleaned_value and len(cleaned_value) > 2:
                    cleaned_entities[key] = cleaned_value
        
        # Try to extract missing entities based on intent
        if intent and not cleaned_entities:
            cleaned_entities = self._extract_missing_entities(intent, message)
        
        return cleaned_entities

    def _calculate_entity_confidence(self, entities: Dict[str, str], intent: str) -> float:
        """
        Calculate confidence based on entity completeness for the intent.
        """
        required_entities = {
            'travel_time': ['origin', 'destination'],
            'transportation_options': ['origin', 'destination'],
            'search_candidates': ['role', 'skills'],  # at least one
            'salary_info': ['role'],
            'company_info': ['company'],
            'minimum_wage': ['location'],
            'labor_law': ['location'],
            'recruiter_outreach_email': ['role'],
            'candidate_pitch_email': ['role']
        }
        
        if intent not in required_entities:
            return 0.8  # Default confidence if no specific requirements
        
        required = required_entities[intent]
        found = sum(1 for req in required if req in entities and entities[req])
        
        # For intents that need at least one of multiple entities
        if intent == 'search_candidates' and found > 0:
            return 1.0
        
        return found / len(required) if required else 0.8

    def _disambiguate_email_direction(self, message_lower: str, intent: str) -> str:
        """
        Enhanced email direction disambiguation based on explicit direction cues.
        - recruiter_outreach_email: FROM recruiter TO candidate(s) - recruiting/outreach perspective
        - candidate_pitch_email: FROM candidate TO company/recruiter/hiring manager - job application perspective
        """
        if intent not in ["candidate_pitch_email", "recruiter_outreach_email"]:
            return intent

        # HIGHEST PRIORITY: Strong recruiter-to-candidate signals
        strong_recruiter_signals = [
            "candidate pitch", "candidate outreach", "outreach email to", "outreach to candidate",
            "outreach to candidates", "reach out to candidate", "reach out to candidates", 
            "contact candidate", "contact candidates", "message candidate", "message candidates",
            "connect with candidate", "connect with candidates", "prospective candidate",
            "potential candidate", "to a candidate", "to candidates", "email to candidate",
            "email to candidates", "recruiting email", "recruitment email", "talent outreach"
        ]
        
        # HIGHEST PRIORITY: Strong candidate-to-company signals  
        strong_candidate_signals = [
            "to a hiring manager", "to hiring manager", "to the hiring manager",
            "to a company", "to the company", "to an employer", "to employer",
            "job I want to apply", "position I want", "role I want", "why I'm a great fit",
            "why I am a great fit", "why I'm qualified", "why I am qualified",
            "I want to apply", "I'm applying", "I am applying", "application to",
            "apply to", "applying for", "cover letter", "job application"
        ]

        # Check strong signals first
        if any(sig in message_lower for sig in strong_recruiter_signals):
            return "recruiter_outreach_email"
        if any(sig in message_lower for sig in strong_candidate_signals):
            return "candidate_pitch_email"

        # MEDIUM PRIORITY: Context-based disambiguation
        # Check for "about xyz role" patterns - need to determine direction
        if "about" in message_lower and ("role" in message_lower or "position" in message_lower):
            # If it mentions candidate/prospective in same context = recruiter outreach
            if any(word in message_lower for word in ["candidate", "prospective", "potential", "talent"]):
                return "recruiter_outreach_email"
            # If it mentions company/employer context = candidate application
            elif any(word in message_lower for word in ["company", "employer", "hiring", "organization"]):
                return "candidate_pitch_email"

        # LOWER PRIORITY: General keyword fallbacks
        if ("outreach" in message_lower or "reach out" in message_lower) and "candidate" in message_lower:
            return "recruiter_outreach_email"
        
        if ("pitch" in message_lower or "application" in message_lower) and any(word in message_lower for word in ["company", "hiring manager", "employer", "organization"]):
            return "candidate_pitch_email"

        # DEFAULT: If no clear signals, maintain original intent
        return intent

    def _fuzzy_match_intents(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Perform enhanced fuzzy matching using synonyms and keyword analysis when exact patterns fail.
        """
        message_lower = message.lower()
        
        # Enhanced intent scoring with synonyms
        intent_scores = {}
        
        for intent, keywords in self.intent_keywords.items():
            score = 0
            matched_keywords = []
            
            # Check direct keyword matches
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            # Check synonym matches
            for base_word, synonyms in self.intent_synonyms.items():
                if base_word in message_lower:
                    score += 1
                    matched_keywords.append(base_word)
                for synonym in synonyms:
                    if synonym in message_lower:
                        score += 0.8  # Slightly lower score for synonyms
                        matched_keywords.append(synonym)
            
            # Normalize score by message length and keyword count
            if score > 0:
                normalized_score = score / (len(keywords) * 0.5)  # Normalize by expected keyword density
                intent_scores[intent] = {
                    'score': normalized_score,
                    'matched_keywords': matched_keywords,
                    'raw_score': score
                }
        
        # Enhanced entity extraction for top-scoring intents
        best_intents = sorted(intent_scores.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
        
        for intent, score_data in best_intents:
            # Guard: ensure applications_count only fires on true count questions about applications
            if intent == 'applications_count':
                count_terms = ["how many", "count", "number of"]
                apply_terms = ["applied", "applications", "applicants"]
                has_count = any(term in message_lower for term in count_terms)
                has_apply = any(term in message_lower for term in apply_terms)
                if not (has_count and has_apply):
                    continue
            if score_data['score'] >= 0.3:  # Minimum threshold for consideration
                entities = self._extract_entities_for_intent(intent, message)
                
                # Calculate confidence based on entity completeness
                entity_confidence = self._calculate_entity_confidence(entities, intent)
                
                # Combine keyword score with entity confidence
                final_confidence = (score_data['score'] * 0.7) + (entity_confidence * 0.3)
                
                if final_confidence >= 0.4:  # Minimum final confidence threshold
                    return {
                        "intent": intent,
                        "confidence": final_confidence,
                        "entities": entities,
                        "method": "fuzzy_match",
                        "matched_keywords": score_data['matched_keywords'],
                        "raw_score": score_data['raw_score']
                    }
        
        # Special handling for email-related intents with enhanced synonym matching
        email_keywords = ["email", "message", "draft", "write", "create", "generate", "compose"]
        email_actions = ["recruiter", "outreach", "candidate", "pitch", "application", "cover letter"]
        
        email_action_count = sum(1 for action in email_actions if action in message_lower)
        email_keyword_count = sum(1 for keyword in email_keywords if keyword in message_lower)
        
        if email_keyword_count >= 1 and email_action_count >= 1:
            # Determine email type based on context
            if any(word in message_lower for word in ["recruiter", "outreach", "prospective", "potential"]):
                intent = "recruiter_outreach_email"
            elif any(word in message_lower for word in ["candidate", "pitch", "application", "cover letter", "job seeker"]):
                intent = "candidate_pitch_email"
            else:
                intent = "recruiter_outreach_email"  # Default
            
            entities = self._extract_entities_for_intent(intent, message)
            return {
                "intent": intent,
                "confidence": 0.6,
                "entities": entities,
                "method": "fuzzy_email_match",
                "matched_keywords": [kw for kw in email_keywords + email_actions if kw in message_lower]
            }
        
        # Enhanced travel detection
        travel_keywords = ["travel", "commute", "journey", "trip", "drive", "fly", "train", "bus", "time", "duration", "how long", "distance", "how far"]
        travel_action_count = sum(1 for keyword in travel_keywords if keyword in message_lower)
        
        if travel_action_count >= 2:
            # Check for origin/destination patterns
            origin_match = re.search(r'from\s+([a-zA-Z\s]+?)(?:\s+to|\s+and)', message_lower)
            dest_match = re.search(r'to\s+([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message_lower)
            
            entities = {}
            if origin_match:
                entities['origin'] = origin_match.group(1).strip()
            if dest_match:
                entities['destination'] = dest_match.group(1).strip()
            
            if entities:
                return {
                    "intent": "travel_time",
                    "confidence": 0.7,
                    "entities": entities,
                    "method": "fuzzy_travel_match",
                    "matched_keywords": [kw for kw in travel_keywords if kw in message_lower]
                }
        
        # Enhanced search detection
        search_keywords = ["find", "search", "candidates", "professionals", "developers", "engineers", "with", "who have", "skilled", "experienced"]
        search_action_count = sum(1 for keyword in search_keywords if keyword in message_lower)
        
        if search_action_count >= 2:
            # Extract role or skills
            role_match = re.search(r'(data scientist|software engineer|developer|analyst|manager|engineer|python|java|react)', message_lower)
            entities = {}
            if role_match:
                entities['role'] = role_match.group(1).strip()
            
            return {
                "intent": "search_candidates",
                "confidence": 0.6,
                "entities": entities,
                "method": "fuzzy_search_match",
                "matched_keywords": [kw for kw in search_keywords if kw in message_lower]
            }
        
        return None

    def _infer_intent_from_context(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Infer intent from context when pattern matching fails.
        """
        # Analyze message structure and keywords
        message_lower = message.lower()
        
        # Question patterns
        question_patterns = {
            'how_many': r'^(how many|what\'s the (number|count)|total)',
            'where': r'^(where|which location|what place)',
            'who': r'^(who|which person|which candidate)',
            'what': r'^(what|which)',
            'when': r'^(when|what time|how long)',
            'why': r'^(why|what\'s the reason)',
            'comparison': r'(better|worse|versus|vs|compare|difference)'
        }
        
        question_type = None
        for q_type, pattern in question_patterns.items():
            if re.search(pattern, message_lower):
                question_type = q_type
                break
        
        # Context-based inference rules
        if question_type == 'how_many':
            if any(word in message_lower for word in ['candidate', 'applicant', 'person']):
                return {'intent': 'candidate_count', 'entities': {}}
            elif any(word in message_lower for word in ['job', 'position', 'opening']):
                return {'intent': 'job_count', 'entities': {}}
        
        elif question_type == 'when':
            if any(word in message_lower for word in ['hire', 'recruit', 'onboard']):
                role = self._extract_role_from_message(message)
                return {'intent': 'hiring_timeline', 'entities': {'role': role} if role else {}}
        
        elif question_type == 'comparison':
            # Look for candidate names
            candidate_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
            candidates = re.findall(candidate_pattern, message)
            if len(candidates) >= 2:
                return {
                    'intent': 'candidate_comparison',
                    'entities': {
                        'candidate1': candidates[0],
                        'candidate2': candidates[1]
                    }
                }
        
        # Keyword-based inference
        keyword_intents = {
            ('email', 'draft', 'write', 'create'): self._infer_email_intent(message),
            ('skill', 'gap', 'missing', 'need'): 'skill_gap_analysis',
            ('trend', 'market', 'industry'): 'market_trends',
            ('breakdown', 'distribution', 'statistics'): 'candidate_breakdown'
        }
        
        for keywords, intent in keyword_intents.items():
            if all(kw in message_lower for kw in keywords):
                if isinstance(intent, dict):
                    return intent
                else:
                    return {'intent': intent, 'entities': self._extract_entities_for_intent(intent, message)}
        
        return None

    def _infer_email_intent(self, message: str) -> Dict[str, Any]:
        """
        Specialized inference for email-related intents.
        """
        message_lower = message.lower()
        role = self._extract_role_from_message(message)
        
        # Directional keywords
        if any(phrase in message_lower for phrase in ['from recruiter', 'recruiter to', 'reach out to candidate']):
            return {'intent': 'recruiter_outreach_email', 'entities': {'role': role or 'general'}}
        elif any(phrase in message_lower for phrase in ['from candidate', 'candidate to', 'apply to company']):
            return {'intent': 'candidate_pitch_email', 'entities': {'role': role or 'general'}}
        
        # Default based on other keywords
        if 'recruiter' in message_lower or 'outreach' in message_lower:
            return {'intent': 'recruiter_outreach_email', 'entities': {'role': role or 'general'}}
        else:
            return {'intent': 'candidate_pitch_email', 'entities': {'role': role or 'general'}}

    def _extract_entities_for_intent(self, intent: str, message: str) -> Dict[str, str]:
        """
        Extract entities based on the intent type.
        """
        entities = {}
        message_lower = message.lower()
        
        if intent in ['skill_gap_analysis', 'candidate_comparison']:
            # Extract candidate names
            name_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
            names = re.findall(name_pattern, message)
            if names:
                entities['candidate'] = names[0]
                if len(names) > 1 and intent == 'candidate_comparison':
                    entities['candidate1'] = names[0]
                    entities['candidate2'] = names[1]
        
        if intent in ['market_trends', 'skill_gap_analysis']:
            # Extract domain/skill
            tech_keywords = ['ai', 'machine learning', 'data science', 'software', 
                            'cloud', 'devops', 'security', 'blockchain']
            for keyword in tech_keywords:
                if keyword in message_lower:
                    entities['domain'] = keyword
                    break
        
        # Always try to extract role if relevant
        if intent in ['hiring_timeline', 'salary_info', 'skill_info', 'candidate_pitch_email', 'recruiter_outreach_email']:
            role = self._extract_role_from_message(message)
            if role:
                entities['role'] = role
        
        return entities

    def _normalize_role_name(self, role: str, full_message: str) -> str:
        """
        Normalize role names to standard forms.
        """
        # Remove common noise words
        noise_words = ['the', 'a', 'an', 'for', 'about', 'position', 'role', 'job', 'opening']
        words = role.lower().split()
        cleaned_words = [w for w in words if w not in noise_words]
        cleaned_role = ' '.join(cleaned_words).strip()
        
        # Map common variations to standard names
        role_mapping = {
            'dev': 'developer',
            'eng': 'engineer',
            'sr': 'senior',
            'jr': 'junior',
            'ml': 'machine learning',
            'ai': 'artificial intelligence',
            'sw': 'software',
            'swe': 'software engineer',
            'sde': 'software development engineer',
            'pm': 'product manager',
            'po': 'product owner',
            'ba': 'business analyst',
            'qa': 'quality assurance',
            'devops': 'devops engineer',
            'fe': 'frontend',
            'be': 'backend',
            'fs': 'full stack'
        }
        
        # Apply mappings
        for abbr, full in role_mapping.items():
            if abbr in cleaned_role.split():
                cleaned_role = cleaned_role.replace(abbr, full)
        
        # If role is too short or empty, try to extract from full message
        if len(cleaned_role) < 3:
            return self._extract_role_from_message(full_message) or role
        
        return cleaned_role.title()

    def _normalize_company_name(self, company: str) -> str:
        """
        Normalize company names.
        """
        # Remove common suffixes
        suffixes = ['inc', 'incorporated', 'llc', 'ltd', 'limited', 'corp', 'corporation', 'company', 'co']
        company_lower = company.lower().strip()
        
        for suffix in suffixes:
            if company_lower.endswith(suffix):
                company_lower = company_lower[:-len(suffix)].strip()
        
        # Capitalize properly
        return ' '.join(word.capitalize() for word in company_lower.split())

    def _normalize_location(self, location: str) -> str:
        """
        Normalize location names.
        """
        # Common abbreviations
        state_abbrevs = {
            'ny': 'new york',
            'nyc': 'new york city',
            'la': 'los angeles',
            'sf': 'san francisco',
            'dc': 'washington dc',
            'philly': 'philadelphia',
            'vegas': 'las vegas'
        }
        
        location_lower = location.lower().strip()
        
        # Replace abbreviations
        for abbrev, full in state_abbrevs.items():
            if location_lower == abbrev:
                return full.title()
        
        return location.title()

    def _normalize_place_name(self, place: str) -> str:
        """
        Normalize place names for travel queries.
        """
        # Similar to location normalization but more extensive
        place_mapping = {
            'boston': 'Boston, MA',
            'nyc': 'New York City, NY',
            'new york': 'New York City, NY',
            'sf': 'San Francisco, CA',
            'san fran': 'San Francisco, CA',
            'la': 'Los Angeles, CA',
            'chicago': 'Chicago, IL',
            'miami': 'Miami, FL',
            'seattle': 'Seattle, WA',
            'denver': 'Denver, CO',
            'atlanta': 'Atlanta, GA',
            'philly': 'Philadelphia, PA',
            'philadelphia': 'Philadelphia, PA',
            'dc': 'Washington, DC',
            'washington dc': 'Washington, DC',
            'portland': 'Portland, OR',
            'austin': 'Austin, TX',
            'dallas': 'Dallas, TX',
            'houston': 'Houston, TX'
        }
        
        place_lower = place.lower().strip()
        return place_mapping.get(place_lower, place.title())

    def _analyze_conversation_context(self, current_intent: str) -> float:
        """
        Analyze conversation history for context that might boost confidence.
        
        Args:
            current_intent: The current detected intent
            
        Returns:
            Confidence boost value between 0 and 0.2
        """
        if len(self.conversation_history) <= 1:
            return 0.0  # No previous context
        
        # Get previous queries
        prev_queries = [item["query"] for item in self.conversation_history[:-1]]
        
        # Look for related topics in previous queries
        related_terms = {
            "interview_travel": ["interview", "travel", "office", "arrival"],
            "relocation": ["move", "relocate", "housing", "commute"],
            "office_visit": ["visit", "office", "tour", "building"],
            "candidate_travel": ["candidate", "travel", "transportation", "arrangements"],
            "search_candidates": ["candidate", "find", "search", "database"],
            "recruiter_outreach_email": ["email", "recruiter", "outreach", "candidate"],
            "candidate_pitch_email": ["email", "pitch", "candidate", "company"],
            "salary_info": ["salary", "pay", "compensation", "earnings"],
            "company_info": ["company", "employer", "organization"],
            "skill_info": ["skills", "technologies", "expertise", "qualifications"]
        }
        
        # Check if current intent terms were mentioned in previous queries
        if current_intent in related_terms:
            terms = related_terms[current_intent]
            prev_text = " ".join(prev_queries).lower()
            
            matches = sum(term.lower() in prev_text for term in terms)
            if matches >= 2:
                return 0.2  # Strong context boost
            elif matches >= 1:
                return 0.1  # Slight context boost
                
        return 0.0
    
    def _determine_confidence_level(self, confidence: float) -> str:
        """
        Determine confidence level category based on confidence score.
        
        Args:
            confidence: Confidence score between 0 and 1
            
        Returns:
            Confidence level string: "high", "medium", or "low"
        """
        for level, threshold in self.confidence_thresholds.items():
            if confidence >= threshold:
                return level
        return "low"
    
    def _generate_clarification_question(self, query: str, intent: str, entities: Dict[str, List[str]]) -> str:
        """
        Generate a clarification question based on detected intent and missing information.
        
        Args:
            query: Original query
            intent: Detected intent
            entities: Extracted entities
            
        Returns:
            Clarification question string
        """
        if intent == "travel_time":
            if "origin" not in entities and "destination" not in entities:
                return "Could you specify the origin and destination locations?"
            elif "origin" not in entities:
                return "Where are you traveling from?"
            elif "destination" not in entities:
                return "Where are you traveling to?"
                
        elif intent == "search_candidates":
            if "role" not in entities and "skills" not in entities:
                return "What type of candidates are you looking for? (e.g., role, skills, experience)"
                
        elif intent == "recruiter_outreach_email":
            if "role" not in entities:
                return "What role are you recruiting for?"
                
        elif intent == "candidate_pitch_email":
            if "role" not in entities:
                return "What role is the candidate applying for?"
                
        elif intent == "salary_info":
            if "role" not in entities:
                return "What role are you asking about salary information for?"
                
        elif intent == "company_info":
            if "company" not in entities:
                return "Which company would you like information about?"
                
        # Generic clarification for low confidence
        return "Could you please provide more details about your request?"
    
    def _handle_llm_unavailable(self, message: str) -> Dict[str, Any]:
        """
        Handle intent detection when LLM service is unavailable.
        Provides enhanced fallbacks for common query types.
        
        Args:
            message: User message to analyze
            
        Returns:
            Dict with intent data using pattern matching
        """
        # Enhanced fallback for skill-related questions when LLM is unavailable
        message_lower = message.lower()
        
        # Check for skill-related questions
        if "what skills" in message_lower and ("data scientist" in message_lower or "data science" in message_lower):
            return {"intent": "skill_info", "entities": {"role": "data scientist"}, "confidence": 0.85}
        elif "skills" in message_lower and "valuable" in message_lower and "data" in message_lower:
            return {"intent": "skill_info", "entities": {"role": "data scientist"}, "confidence": 0.8}
        elif any(term in message_lower for term in ["skills", "technologies", "tools", "expertise"]) and any(role in message_lower for role in ["software engineer", "developer", "programmer"]):
            return {"intent": "skill_info", "entities": {"role": "software engineer"}, "confidence": 0.8}
            
        # Check for database queries
        if any(term in message_lower for term in ["how many", "count", "number of"]):
            if any(term in message_lower for term in ["candidates", "applicants", "people"]):
                return {"intent": "candidate_count", "entities": {}, "confidence": 0.8}
            elif any(term in message_lower for term in ["jobs", "positions", "openings"]):
                return {"intent": "job_count", "entities": {}, "confidence": 0.8}
                
        # Check for salary information
        if any(term in message_lower for term in ["salary", "pay", "compensation", "earn", "income"]):
            for role in ["data scientist", "software engineer", "developer", "engineer", "manager"]:
                if role in message_lower:
                    return {"intent": "salary_info", "entities": {"role": role}, "confidence": 0.75}
        
        # Default to general question with low confidence
        return {"intent": "general_question", "entities": {}, "confidence": 0.3}
    
    async def _llm_intent_detection(self, message: str, conversation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Use the LLM service to detect intent from a message.
        
        Args:
            message: User message to analyze
            conversation_context: Optional conversation context
            
        Returns:
            Dict with intent data from LLM
        """
        # Ensure LLM service is available
        logger.debug(f"[IntentProcessor._llm_intent_detection] llm_service: {self.llm_service}")
        if not self.llm_service:
            logger.warning("LLM service not available for intent detection")
            return self._handle_llm_unavailable(message)
            
        # Check if the LLM service has the necessary methods
        if not hasattr(self.llm_service, 'generate_text_async'):
            logger.warning("LLM service doesn't have the required generate_text_async method")
            return self._handle_llm_unavailable(message)
            
        # Continue with LLM-based intent detection if service is available
        
        # Extract context signals that help distinguish database vs web search
        contexts = []
        if conversation_context:
            prev_intent = conversation_context.get("last_intent", "")
            prev_entities = conversation_context.get("last_entities", {})
            # Get the last few messages if they exist in context
            last_messages = []
            if "history" in conversation_context and isinstance(conversation_context["history"], list):
                last_messages = conversation_context["history"][-3:] if len(conversation_context["history"]) > 0 else []
            
            # Add previous intent as context
            if prev_intent:
                contexts.append(f"Previous intent: {prev_intent}")
                
            # Add database availability signal
            if "db_available" in conversation_context:
                contexts.append(f"Database {'is' if conversation_context['db_available'] else 'is not'} available")
            
            # Add previous message if it exists
            if last_messages:
                last_user_msgs = [msg["content"] for msg in last_messages if msg["role"] == "user"]
                if last_user_msgs:
                    contexts.append(f"Previous user query: {last_user_msgs[-1]}")
        
        # Identify database-related keywords in the message
        database_keywords = ["database", "candidates", "our system", "our candidates", "we have", "in our",
                            "resume", "applicant", "profile", "breakdown", "show me", "find", "search", 
                            "count", "how many", "view", "display", "get"]
        
        web_search_keywords = ["market", "industry", "trends", "statistics", "average", "standard", 
                              "typical", "laws", "regulations", "requirements", "commonly", "generally",
                              "usually", "across the industry", "in the market", "best practice", "latest"]
        
        db_keyword_matches = [kw for kw in database_keywords if kw.lower() in message.lower()]
        web_keyword_matches = [kw for kw in web_search_keywords if kw.lower() in message.lower()]
        
        if db_keyword_matches:
            contexts.append(f"Database-related keywords found: {', '.join(db_keyword_matches[:3])}")
        
        if web_keyword_matches:
            contexts.append(f"Web search keywords found: {', '.join(web_keyword_matches[:3])}")
            
        # Build the system prompt with available intents
        system_prompt = """
        You are an intent detection AI for a recruiting assistant. Your job is to understand what the user is asking about and categorize their message into one of the following intents, extracting relevant entities:

        - travel_time: Get travel/commute time, distance, or directions between two locations (TRAVEL API - extract 'origin', 'destination', and optionally 'mode')
        - transportation_options: Get available transportation methods or compare travel modes between two locations (TRAVEL API - extract 'origin', 'destination', and optionally 'mode')
        - candidate_count: Count of candidates in the database (DATABASE QUERY)
        - job_count: Count of jobs in the database (DATABASE QUERY)
        - search_candidates: Search for candidates with specific skills or attributes in the database (DATABASE QUERY)
        - recruiter_outreach_email: Generate an email FROM a recruiter TO prospective candidates (EMAIL GENERATION - extract 'role')
        - candidate_pitch_email: Generate an email FROM a candidate TO a company/employer (EMAIL GENERATION - extract 'role')
        - candidate_outreach: Contacting specific candidates (ACTION)
        - view_profile: Viewing candidate profiles in the database (DATABASE QUERY)
        - job_match: Matching candidates to jobs in the database (DATABASE QUERY)
        - salary_info: Information about salary ranges (WEB SEARCH - requires specific role and optional location)
        - company_info: Information about companies (WEB SEARCH - requires company name)
        - candidate_breakdown: Statistics about candidates in the database (DATABASE QUERY)
        - candidate_comparison: Compare candidates in the database (DATABASE QUERY)
        - skill_gap_analysis: Analyze skill gaps for candidates (MIXED - database + LLM)
        - hiring_timeline: Timelines for hiring (WEB SEARCH)
        - market_trends: Information about market trends (WEB SEARCH - requires domain)
        - advanced_matching: Advanced candidate-job matching in the database (DATABASE QUERY)
        - web_search: Search the web for information not in the database (WEB SEARCH - extract the 'query' the user wants to search for)
        - job_posting_analysis: Analyze a job posting (WEB SEARCH - extract the 'url' to analyze)
        - company_research: Research a company (WEB SEARCH - extract the 'company' and optionally 'url')
        - minimum_wage: Minimum wage information (WEB SEARCH - extract 'location', should be a state, city or country)
        - labor_law: Labor law information (WEB SEARCH - extract 'location' and specific 'topic' if mentioned)
        - general_question: Any other general query (LLM)

        For travel_time and transportation_options intents, always extract the 'origin' and 'destination' locations, and if the user specifies a mode of transport (e.g., driving, train, flight, walking), include it as 'mode'.

        CRITICAL EMAIL INTENT DISAMBIGUATION:
        1. recruiter_outreach_email: When user asks for an email FROM a recruiter TO candidates (e.g., "create a recruiter outreach email sent to prospective candidates")
        2. candidate_pitch_email: When user asks for an email FROM a candidate TO a company (e.g., "create a candidate pitch email to a company")
        
        IMPORTANT DISAMBIGUATION RULES:
        1. Queries about "our candidates", "in our database", "we have", "candidates with", or "find candidates" should use DATABASE QUERY intents
        2. Queries about "average", "typical", "industry", "trends", "laws", "regulations" should use WEB SEARCH intents
        3. For ambiguous queries like "Tell me about software engineers" or "What skills are valuable for data scientists?", these are general informational requests. Use 'web_search' if they require external knowledge, or 'general_question' if they can be answered generally. DO NOT use database-related intents like 'search_candidates' or 'advanced_matching' unless the user specifically asks about candidates 'in our database' or similar.
        4. For skill-related queries, determine if they're asking about candidates with those skills (DATABASE QUERY: search_candidates) or general information about those skills (WEB SEARCH or general_question).
        5. When a user asks about salaries, it should be "salary_info" intent, not web_search
        6. When a user asks about minimum wage or labor laws, use the specific intents, not web_search
        7. If user explicitly mentions "search the web" or "find online", always use web_search intent
        8. ONLY use 'advanced_matching' if the query explicitly asks to 'find', 'match', 'show', 'identify', 'consider', or 'find the best/ideal' CANDIDATES for a specific JOB or role description. General questions about roles or skills are NOT 'advanced_matching'.
        9. For email generation, carefully distinguish between recruiter outreach (recruiter TO candidates) and candidate pitch (candidate TO company)

        For each intent, extract relevant entities mentioned in the message.
        Your response should be valid JSON with the following format:
        {
            "intent": "intent_name",
            "entities": {
                "entity1": "value1",
                "entity2": "value2"
            },
            "confidence": 0.0 to 1.0,
            "reasoning": "Brief explanation of why you chose this intent"
        }
        """
        
        # Add context information to the prompt if available
        if contexts:
            context_str = "\n".join(contexts)
            prompt = f"""
            Context information:
            {context_str}
            
            User message: {message}
            
            Based on the message and context, determine the most appropriate intent.
            """
        else:
            prompt = f"User message: {message}\n\nDetermine the most appropriate intent."
            
        try:
            # Get response from LLM service
            response_text = await self.llm_service.generate_text_async(
                prompt=prompt,
                system_message=system_prompt
            )
            # Ensure we get a string from the LLM response (handles AIMessage or similar objects)
            if hasattr(response_text, "content"):
                response_text = response_text.content
            response_text = str(response_text).strip()
            # Find JSON block if surrounded by text
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
                
            # Parse the JSON response
            import json
            try:
                result = json.loads(response_text)
                logger.debug(f"LLM intent detection result: {result}")
                
                # Store reasoning in context for debugging if provided
                if "reasoning" in result:
                    if conversation_context is not None:
                        conversation_context["intent_reasoning"] = result["reasoning"]
                    # Remove reasoning from result as it's not expected in the return format
                    reasoning = result.pop("reasoning", "")
                    logger.debug(f"Intent reasoning: {reasoning}")
                
                # Default confidence if not provided
                if "confidence" not in result:
                    result["confidence"] = 0.7
                    
                # Add specific signals for ambiguous queries
                if result["intent"] == "general_question" and (db_keyword_matches or web_keyword_matches):
                    if len(db_keyword_matches) > len(web_keyword_matches):
                        # More database-related keywords than web search keywords
                        logger.info("Changing general_question to search_candidates based on keyword analysis")
                        result["intent"] = "search_candidates"
                        result["confidence"] = 0.6
                    elif len(web_keyword_matches) > len(db_keyword_matches):
                        # More web search keywords than database-related keywords
                        logger.info("Changing general_question to web_search based on keyword analysis")
                        result["intent"] = "web_search" 
                        result["entities"] = {"query": message}
                        result["confidence"] = 0.6
                
                # For salary queries, ensure they use salary_info intent
                if ("salary" in message.lower() or "pay" in message.lower() or "earn" in message.lower()) and "role" in result.get("entities", {}):
                    if result["intent"] != "salary_info":
                        logger.info(f"Changing {result['intent']} to salary_info based on salary keywords")
                        result["intent"] = "salary_info"
                
                # SIMPLE deterministic routing for email direction per user guidance
                lower = message.lower()
                if any(v in lower for v in ["draft", "create", "compose", "write"]) and "email" in lower:
                    # Candidate-facing outreach
                    if ("candidate" in lower or "prospective candidate" in lower) and not any(x in lower for x in ["hiring manager", "employer", "company"]):
                        if result.get("intent") != "recruiter_outreach_email":
                            logger.info(f"Forcing intent to recruiter_outreach_email based on simple candidate phrasing")
                            result["intent"] = "recruiter_outreach_email"
                            # ensure role
                            ents = result.get("entities", {})
                            if not ents.get("role"):
                                extracted = self._extract_role_from_message(message)
                                if extracted:
                                    ents["role"] = self._normalize_role_name(extracted, message)
                            result["entities"] = ents
                    # Hiring manager / application pitch
                    elif any(x in lower for x in ["hiring manager", "apply", "application", "i'm a great fit", "im a great fit", "why i'm a great fit", "why im a great fit"]):
                        if result.get("intent") != "candidate_pitch_email":
                            logger.info(f"Forcing intent to candidate_pitch_email based on simple hiring manager/apply phrasing")
                            result["intent"] = "candidate_pitch_email"
                            ents = result.get("entities", {})
                            if not ents.get("role"):
                                extracted = self._extract_role_from_message(message)
                                if extracted:
                                    ents["role"] = self._normalize_role_name(extracted, message)
                            result["entities"] = ents

                # Enhanced email intent disambiguation (apply regardless of 'email' keyword)
                if result["intent"] in ["candidate_pitch_email", "recruiter_outreach_email"]:
                    message_lower_local = message.lower()
                    before_intent = result["intent"]
                    # Existing heuristic tweaks
                    if any(term in message_lower_local for term in [
                        "recruiter", "recruitment", "hiring", "talent acquisition", "outreach", "sent to",
                        "prospective", "potential", "reach out", "outbound", "cold outreach", "email to candidate",
                        "outreach email to candidate", "outreach email to candidates"
                    ]):
                        if result["intent"] != "recruiter_outreach_email":
                            logger.info(f"Changing {result['intent']} to recruiter_outreach_email based on recruiter/outreach keywords")
                            result["intent"] = "recruiter_outreach_email"
                    elif any(term in message_lower_local for term in [
                        "candidate", "job seeker", "applicant", "pitch", "application", "cover letter",
                        "from candidate", "by candidate", "apply to", "to hiring manager"
                    ]):
                        if result["intent"] != "candidate_pitch_email":
                            logger.info(f"Changing {result['intent']} to candidate_pitch_email based on candidate/application keywords")
                            result["intent"] = "candidate_pitch_email"

                    # Final pass using shared disambiguator for consistency
                    result["intent"] = self._disambiguate_email_direction(message_lower_local, result["intent"]) 
                    if result["intent"] != before_intent:
                        logger.info(f"Disambiguated email direction: {before_intent} -> {result['intent']}")
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Raw response: {response_text}")
                return {"intent": "general_question", "entities": {}, "confidence": 0.3}
                
        except Exception as e:
            logger.error(f"LLM intent detection failed: {e}")
            # Return a default intent
            return {"intent": "general_question", "entities": {}, "confidence": 0.3}
    
    async def process_intent(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Enhanced intent processing with better error handling and fallbacks.
        """
        logger.info(f"Processing intent: {intent} with entities: {entities}")
        
        # Initialize if not already done
        if not self._initialized:
            await self.initialize()
        
        # Final guard: re-apply email direction disambiguation and ensure role extraction
        try:
            if intent in ["candidate_pitch_email", "recruiter_outreach_email"]:
                before_intent = intent
                intent = self._disambiguate_email_direction(message.lower(), intent)
                if intent != before_intent:
                    logger.info(f"Final guard disambiguated email direction: {before_intent} -> {intent}")
                # Ensure role exists for email handlers
                if not entities.get("role"):
                    extracted_role = self._extract_role_from_message(message) or entities.get("role")
                    if extracted_role:
                        entities["role"] = self._normalize_role_name(extracted_role, message)
        except Exception as e:
            logger.warning(f"Email disambiguation guard skipped due to error: {e}")

        # Intent handlers mapping
        intent_handlers = {
            # Travel intents
            "travel_time": self._handle_travel_time,
            "transportation_options": self._handle_transportation_options,
            
            # Web search intents
            "web_search": self._handle_web_search,
            "company_info": self._handle_company_info,
            "job_posting_analysis": self._handle_job_posting_analysis,
            "company_research": self._handle_company_research,
            "market_trends": self._handle_market_trends,
            "minimum_wage": self._handle_minimum_wage,
            "labor_law": self._handle_labor_law,
            # Market research
            "market_research": self._handle_market_research,
            
            # Email generation intents
            "candidate_pitch_email": self._handle_candidate_pitch_email,
            "recruiter_outreach_email": self._handle_recruiter_outreach_email,
            
            # General intents
            "general_question": self._handle_general_question,
            "clarification_needed": self._handle_clarification_needed
        }
        
        # Get the appropriate handler
        handler = intent_handlers.get(intent)
        
        if handler:
            try:
                # Call the handler with error recovery
                result = await self._call_handler_with_recovery(handler, intent, entities, message)
                return result
            except Exception as e:
                logger.error(f"Handler for {intent} failed: {e}")
                return self._create_error_response(intent, str(e))
        else:
            # No specific handler - try to process generically
            return await self._handle_unknown_intent(intent, entities, message)

    async def _call_handler_with_recovery(self, handler, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Call a handler with error recovery mechanisms.
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                result = await handler(intent, entities, message)
                
                # Validate result
                if self._validate_handler_result(result):
                    return result
                else:
                    logger.warning(f"Invalid result from handler for {intent}")
                    if retry_count < max_retries:
                        retry_count += 1
                        # Try to fix entities and retry
                        entities = self._attempt_entity_recovery(intent, entities, message)
                        continue
                    else:
                        return self._create_error_response(intent, "Handler returned invalid result")
                        
            except Exception as e:
                logger.error(f"Handler error (attempt {retry_count + 1}): {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    await asyncio.sleep(0.5 * retry_count)  # Exponential backoff
                else:
                    raise

    def _validate_handler_result(self, result: Dict[str, Any]) -> bool:
        """
        Validate that a handler result has the required fields.
        """
        required_fields = ["intent_processed"]
        return all(field in result for field in required_fields)

    def _attempt_entity_recovery(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Attempt to recover missing or invalid entities.
        """
        recovered_entities = entities.copy()
        
        # Intent-specific recovery rules
        if intent == "travel_time" and (not entities.get("origin") or not entities.get("destination")):
            # Try to extract locations from message
            location_pattern = r'(?:from|between)\s+([A-Za-z\s]+?)\s+(?:to|and)\s+([A-Za-z\s]+?)(?:\?|$|\.)'
            match = re.search(location_pattern, message, re.IGNORECASE)
            if match:
                recovered_entities["origin"] = match.group(1).strip()
                recovered_entities["destination"] = match.group(2).strip()
        
        elif intent in ["salary_info", "recruiter_outreach_email", "candidate_pitch_email"] and not entities.get("role"):
            # Try to extract role
            role = self._extract_role_from_message(message)
            if role:
                recovered_entities["role"] = role
        
        return recovered_entities

    def _create_error_response(self, intent: str, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error response.
        """
        return {
            "intent_processed": False,
            "intent": intent,
            "error": error_message,
            "error_type": "processing_error",
            "suggestions": self._get_error_suggestions(intent, error_message)
        }

    def _get_error_suggestions(self, intent: str, error_message: str) -> List[str]:
        """
        Get helpful suggestions based on the error.
        """
        suggestions = []
        
        if "missing" in error_message.lower() or "required" in error_message.lower():
            if intent == "travel_time":
                suggestions.append("Please specify both origin and destination locations")
            elif intent in ["salary_info", "recruiter_outreach_email"]:
                suggestions.append("Please specify the job role you're asking about")
        
        if "service unavailable" in error_message.lower():
            suggestions.append("The required service is temporarily unavailable. Please try again later.")
        
        return suggestions

    async def _handle_unknown_intent(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle intents that don't have specific handlers.
        """
        logger.warning(f"No handler for intent: {intent}")
        
        # Try to provide a helpful response using the LLM
        if self.llm_service:
            try:
                response = await self.generate_general_response(message)
                return {
                    "intent_processed": True,
                    "intent": intent,
                    "response_type": "general",
                    "response": response,
                    "handled_by": "llm_fallback"
                }
            except Exception as e:
                logger.error(f"LLM fallback failed: {e}")
        
        return {
            "intent_processed": False,
            "intent": intent,
            "error": f"No handler available for intent: {intent}",
            "suggestion": "Please try rephrasing your question or ask about specific recruitment topics."
        }

    async def _handle_general_question(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle general questions using the LLM.
        """
        response = await self.generate_general_response(message)
        return {
            "intent_processed": True,
            "intent": intent,
            "response_type": "general",
            "response": response
        }

    async def _handle_clarification_needed(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle cases where clarification is needed.
        """
        # The clarification question should already be in the entities or we generate one
        clarification = entities.get("clarification_question", 
                                    "Could you please provide more details about what you're looking for?")
        
        return {
            "intent_processed": True,
            "intent": intent,
            "response_type": "clarification",
            "response": clarification,
            "original_query": entities.get("original_query", message)
        }

    # Add these handler methods for specific intents:

    async def _handle_travel_time(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Enhanced travel time handler with better error handling."""
        if not self.travel_service:
            return {
                "intent_processed": False,
                "error": "Travel service is not available"
            }
        
        origin = entities.get("origin", "")
        destination = entities.get("destination", "")
        
        if not origin or not destination:
            # Try to extract from message one more time
            entities = self._attempt_entity_recovery(intent, entities, message)
            origin = entities.get("origin", "")
            destination = entities.get("destination", "")
            
            if not origin or not destination:
                return {
                    "intent_processed": False,
                    "error": "Both origin and destination are required for travel time queries",
                    "missing_entities": ["origin", "destination"] if not origin and not destination else ["origin"] if not origin else ["destination"]
                }
        
        try:
            travel_data = await self.travel_service.get_travel_info(
                origin=origin,
                destination=destination,
                query=message
            )
            
            if travel_data.get("has_results"):
                formatted_response = self.travel_service.format_travel_response(travel_data, message)
                return {
                    "intent_processed": True,
                    "response_type": "travel_time",
                    "travel_data": travel_data,
                    "formatted_response": formatted_response,
                    "source": "travel_service"
                }
            else:
                return {
                    "intent_processed": False,
                    "error": f"Could not find travel information for {origin} to {destination}",
                    "suggestion": "Please check the location names and try again"
                }
                
        except Exception as e:
            logger.error(f"Travel service error: {e}")
            return {
                "intent_processed": False,
                "error": f"Travel service error: {str(e)}",
                "suggestion": "Please try again later or check your location names"
            }

    async def _handle_web_search(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Enhanced web search handler."""
        query = entities.get("query", message)
        
        # Try multiple search services in order of preference
        search_services = []
        if self.crawler_service:
            search_services.append(("crawler", self.crawler_service))
        if self.web_search_service:
            search_services.append(("web_search", self.web_search_service))
        
        if not search_services:
            return {
                "intent_processed": False,
                "error": "No search services available"
            }
        
        last_error = None
        for service_name, service in search_services:
            try:
                if service_name == "crawler":
                    search_results = await service.search_and_crawl(
                        query=query,
                        crawl_type="job",
                        max_results=3
                    )
                else:
                    search_results = await service.search(query)
                
                if search_results:
                    return {
                        "intent_processed": True,
                        "response_type": "web_search",
                        "query": query,
                        "results": search_results,
                        "source": service_name
                    }
            except Exception as e:
                logger.error(f"{service_name} search failed: {e}")
                last_error = str(e)
                continue
        
        return {
            "intent_processed": False,
            "error": f"Search failed: {last_error or 'Unknown error'}",
            "suggestion": "Please try rephrasing your search query"
        }

    async def _handle_market_research(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Handle market research style questions using MarketResearchService + web search.
        Supports:
          - city viability snapshot
          - two-city comparison (non-tech vs hub)
          - shortlist non-tech hubs
          - sourcing plan for a city
          - hiring-manager briefing
          - data-only JSON for dashboards
        """
        try:
            # Lazy import to avoid circulars
            from backend.services.service_registry import provide_market_research_service
            market_service = provide_market_research_service()

            role = entities.get("role") or self._extract_role_from_message(message) or "professional"
            city = entities.get("city")
            time_range = entities.get("time_range")

            # Determine sub-intent by keywords in message to keep this dynamic
            lower = message.lower()
            
            # Route to appropriate centralized method
            if "compare" in lower and (" vs " in lower or " versus " in lower):
                # Two-city comparison
                city1 = entities.get("non_tech_city")
                city2 = entities.get("tech_hub_city")
                if city1 and city2:
                    result = await market_service.generate_city_comparison(
                        role=role,
                        city1=city1,
                        city2=city2,
                        seniority=entities.get("seniority")
                    )
                    if result["status"] == "success":
                        return {
                            "intent_processed": True,
                            "response_type": "market_research",
                            "response": result["comparison"],
                            "sources": result.get("sources_city1", []) + result.get("sources_city2", []),
                            "entities": {"role": role, "city1": city1, "city2": city2, "mode": "compare"}
                        }
            
            elif "identify the top" in lower or ("top" in lower and "cities" in lower):
                # Non-tech hub shortlist
                num_cities = int(entities.get("num_cities", 5))
                result = await market_service.generate_non_tech_hub_shortlist(
                    role=role,
                    num_cities=num_cities
                )
                if result["status"] == "success":
                    return {
                        "intent_processed": True,
                        "response_type": "market_research",
                        "response": result["shortlist"],
                        "sources": result.get("sources", []),
                        "entities": {"role": role, "num_cities": num_cities, "mode": "shortlist"}
                    }
            
            elif "sourcing plan" in lower:
                # Sourcing plan
                if city:
                    result = await market_service.generate_sourcing_plan(
                        role=role,
                        city=city
                    )
                    if result["status"] == "success":
                        return {
                            "intent_processed": True,
                            "response_type": "market_research",
                            "response": result["plan"],
                            "sources": result.get("sources", []),
                            "entities": {"role": role, "city": city, "mode": "plan"}
                        }
            
            elif "briefing" in lower:
                # Hiring manager briefing
                if city:
                    result = await market_service.generate_hiring_manager_briefing(
                        role=role,
                        city=city
                    )
                    if result["status"] == "success":
                        return {
                            "intent_processed": True,
                            "response_type": "market_research",
                            "response": result["briefing"],
                            "sources": result.get("sources", []),
                            "entities": {"role": role, "city": city, "mode": "briefing"}
                        }
            
            elif "return only valid json" in lower or "only valid json" in lower or lower.strip().endswith("json"):
                # JSON-only data
                if city:
                    result = await market_service.generate_json_report(
                        role=role,
                        city=city,
                        time_range=time_range
                    )
                    if result["status"] == "success":
                        return {
                            "intent_processed": True,
                            "response_type": "market_research",
                            "response": json.dumps(result["data"], indent=2),
                            "sources": result.get("sources", []),
                            "entities": {"role": role, "city": city, "mode": "json"}
                        }
            
            else:
                # Default: City viability snapshot
                if city:
                    result = await market_service.generate_city_viability_report(
                        role=role,
                        city=city,
                        seniority=entities.get("seniority"),
                        time_range=time_range,
                        include_actions=True
                    )
                    if result["status"] == "success":
                        return {
                            "intent_processed": True,
                            "response_type": "market_research",
                            "response": result["analysis"],
                            "sources": result.get("sources", []),
                            "entities": {"role": role, "city": city, "mode": "snapshot"}
                        }
            
            # If we get here, something went wrong
            return {
                "intent_processed": False,
                "error": "Could not determine market research mode or missing required parameters",
                "suggestion": "Please specify a city and role clearly, or use one of the supported formats."
            }
            
        except Exception as e:
            logger.error(f"Market research handler failed: {e}")
            return {
                "intent_processed": False,
                "error": f"Market research failed: {str(e)}",
                "suggestion": "Try adjusting the role/title wording or add 'externally' to force web research."
            }

    async def _handle_candidate_pitch_email(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Enhanced candidate pitch email handler."""
        if not self.llm_service:
            return {
                "intent_processed": False,
                "error": "Email generation service is not available"
            }
        
        role = entities.get("role", "").strip()
        if not role or len(role) < 3:
            role = self._extract_role_from_message(message) or "professional"
        
        role = self._normalize_role_name(role, message)
        
        try:
            prompt = f"""
            Generate a professional and engaging pitch email from a {role} candidate to a company. 
            
            The email should:
            1. Have a compelling subject line that grabs attention
            2. Start with a personalized greeting (use placeholder [Hiring Manager Name])
            3. Introduce the candidate with a strong opening statement
            4. Highlight 3-4 key achievements relevant to {role} positions
            5. Explain unique value proposition
            6. Include specific skills and technologies
            7. Express enthusiasm for the company (use placeholder [Company Name])
            8. Include a clear call to action
            9. End with professional signature (use placeholder [Your Name])
            
            Make it concise (under 250 words), impactful, and tailored for {role} positions.
            Use placeholders for personalization: [Company Name], [Hiring Manager Name], [Your Name], [Your Contact].
            """
            
            pitch_email = await self.llm_service.generate_text_async(
                prompt=prompt,
                system_message=f"You are an expert career coach helping {role} professionals write compelling pitch emails."
            )
            
            return {
                "intent_processed": True,
                "response_type": "candidate_pitch_email",
                "role": role,
                "pitch_email": pitch_email,
                "message_type": "formatted_text",
                "customization_hints": ["Replace [Company Name] with target company", 
                                    "Replace [Hiring Manager Name] with actual name if known",
                                    "Replace [Your Name] and [Your Contact] with your details"]
            }
        except Exception as e:
            logger.error(f"Error generating pitch email: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not generate pitch email: {str(e)}",
                "suggestion": f"Please try again or specify a different role (current: {role})"
            }
    
    def is_initialized(self) -> bool:
        """Check if the intent processor has been initialized."""
        return self._initialized

    def learn_from_feedback(self, message: str, detected_intent: str, correct_intent: str, entities: Dict[str, Any]):
        """
        Learn from user corrections to improve future intent detection.
        This is a simple implementation - in production, you'd want to persist this data.
        """
        if not hasattr(self, 'intent_corrections'):
            self.intent_corrections = []
        
        self.intent_corrections.append({
            "message": message,
            "detected": detected_intent,
            "correct": correct_intent,
            "entities": entities,
            "timestamp": datetime.now().isoformat()
        })
        
        # In a production system, you would:
        # 1. Store this in a database
        # 2. Periodically retrain your models
        # 3. Update pattern matching rules
        # 4. Fine-tune the LLM prompts
        
        logger.info(f"Learned correction: '{detected_intent}' -> '{correct_intent}' for message: '{message}'")
    
    def _extract_missing_entities(self, intent: str, message: str) -> Dict[str, str]:
        """
        Extract missing entities for a given intent from the message.
        """
        entities = {}
        message_lower = message.lower()
        
        if intent == "travel_time":
            # Extract origin and destination
            origin_match = re.search(r'from\s+([a-zA-Z\s]+?)(?:\s+to|\s+and)', message_lower)
            dest_match = re.search(r'to\s+([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message_lower)
            
            if origin_match:
                entities['origin'] = origin_match.group(1).strip()
            if dest_match:
                entities['destination'] = dest_match.group(1).strip()
                
        elif intent in ["search_candidates", "recruiter_outreach_email", "candidate_pitch_email"]:
            # Priority 1: Extract skills from "with X experience" patterns
            skills_match = re.search(r'with\s+([^?]*?)\s+(?:experience|skills?|knowledge|expertise)', message_lower)
            if skills_match:
                entities['skills'] = skills_match.group(1).strip()
            
            # Priority 2: Extract skills from "who have X" patterns
            if not entities.get('skills'):
                who_have_match = re.search(r'who\s+have\s+([^?]*?)(?:\?|$|\s)', message_lower)
                if who_have_match:
                    entities['skills'] = who_have_match.group(1).strip()
            
            # Priority 3: Extract skills from "skilled in X" patterns
            if not entities.get('skills'):
                skilled_in_match = re.search(r'skilled\s+in\s+([^?]*?)(?:\?|$|\s)', message_lower)
                if skilled_in_match:
                    entities['skills'] = skilled_in_match.group(1).strip()
            
            # Priority 4: Extract from "find me all X candidates" pattern (only if no skills found)
            if not entities.get('skills') and not entities.get('role'):
                find_match = re.search(r'find\s+(?:me\s+)?all\s+([^?]*?)\s+candidates', message_lower)
                if find_match:
                    role_text = find_match.group(1).strip()
                    # Don't extract "all" as a role
                    if role_text.lower() != 'all':
                        entities['role'] = role_text
                else:
                    # Try to extract from "show me X candidates" pattern
                    show_match = re.search(r'show\s+(?:me\s+)?([^?]*?)\s+candidates', message_lower)
                    if show_match:
                        role_text = show_match.group(1).strip()
                        # Don't extract "all" as a role
                        if role_text.lower() != 'all':
                            entities['role'] = role_text
            
            # Priority 5: Fallback - extract any technical terms that might be skills
            if not entities.get('skills') and not entities.get('role'):
                # Look for common technical terms in the message
                technical_terms = [
                    'python', 'java', 'javascript', 'react', 'angular', 'vue', 'node', 'sql', 'mongodb',
                    'aws', 'azure', 'docker', 'kubernetes', 'machine learning', 'ai', 'artificial intelligence',
                    'data science', 'devops', 'frontend', 'backend', 'full stack', 'mobile', 'ios', 'android',
                    'php', 'ruby', 'go', 'rust', 'c++', 'c#', '.net', 'spring', 'django', 'flask', 'express'
                ]
                
                found_skills = []
                for term in technical_terms:
                    if term in message_lower:
                        found_skills.append(term)
                
                if found_skills:
                    entities['skills'] = ', '.join(found_skills)
        
        elif intent == "salary_info":
            # Extract role for salary queries
            role_match = re.search(r'(?:for|of|about)\s+(?:a\s+)?([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message_lower)
            if role_match:
                entities['role'] = role_match.group(1).strip()
                
        elif intent == "company_info":
            # Extract company name
            company_match = re.search(r'(?:about|on|for|regarding)\s+([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message_lower)
            if company_match:
                entities['company'] = company_match.group(1).strip()
        
        return entities

    async def _handle_transportation_options(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle transportation options intent.
        """
        try:
            origin = entities.get('origin', '')
            destination = entities.get('destination', '')
            
            if not origin or not destination:
                return {
                    "intent_processed": False,
                    "error": "Missing origin or destination",
                    "suggestion": "Please specify both origin and destination cities"
                }
            
            # Use travel service to get transportation options
            if self.travel_service:
                options_data = await self.travel_service.get_transportation_options(origin, destination)
                
                if options_data and options_data.get('options'):
                    formatted_response = f"Transportation options from {origin} to {destination}:\n\n"
                    
                    for option in options_data['options']:
                        mode = option.get('mode', 'Unknown')
                        duration = option.get('duration', 'Unknown')
                        cost = option.get('cost', 'Unknown')
                        
                        formatted_response += f"**{mode}**: {duration} duration"
                        if cost != 'Unknown':
                            formatted_response += f", {cost}"
                        formatted_response += "\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "transportation_options",
                        "formatted_response": formatted_response,
                        "options_data": options_data,
                        "origin": origin,
                        "destination": destination
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No transportation options found",
                        "suggestion": "Please check the city names and try again"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Travel service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error handling transportation options: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not get transportation options: {str(e)}",
                "suggestion": "Please try again or check your input"
            }

    async def _handle_recruiter_outreach_email(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle recruiter outreach email intent.
        """
        try:
            role = entities.get('role', '')
            if not role:
                return {
                    "intent_processed": False,
                    "error": "Missing role information",
                    "suggestion": "Please specify the role you're recruiting for"
                }

            # --- Dynamic Job Matching Logic ---
            matched_job_obj = None
            similarity_threshold = 0.55  # Lowered threshold for better matching
            try:
                import logging
                debug_logger = logging.getLogger("recruiter_job_matching")
                debug_logger.setLevel(logging.DEBUG)
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                if not debug_logger.hasHandlers():
                    debug_logger.addHandler(handler)

                # Obtain JobService and DB session from registry
                job_service = getattr(self, 'job_service', None)
                if not job_service and hasattr(self, 'service_registry'):
                    job_service = getattr(self.service_registry, 'job_service', None)
                db = getattr(self, 'db', None)
                if not db and hasattr(self, 'service_registry'):
                    db = getattr(self.service_registry, 'db', None)
                if job_service and db:
                    jobs = job_service.get_jobs(db, status="open")
                    if jobs:
                        # Prepare embedding model
                        llm_service = getattr(job_service, 'llm_service', None)
                        if llm_service:
                            embedding_model = llm_service.get_embedding_model()
                            # Generate embedding for role (query)
                            import numpy as np
                            from backend.utils.cache_utils import get_embedding_cached
                            role_embedding = None
                            try:
                                role_embedding = get_embedding_cached(embedding_model, role)
                                if hasattr(role_embedding, 'tolist'):
                                    role_embedding = role_embedding.tolist()
                                elif isinstance(role_embedding, np.ndarray):
                                    role_embedding = role_embedding.tolist()
                            except Exception:
                                role_embedding = None
                            if role_embedding:
                                # For each job, compute similarity
                                best_sim = -1.0
                                best_job = None
                                for job in jobs:
                                    # Convert job to dict for embedding
                                    job_data = {
                                        "id": job.id,
                                        "title": job.title,
                                        "department": job.department,
                                        "job_overview": getattr(job, 'job_overview', ''),
                                        "required_qualifications": getattr(job, 'required_qualifications', ''),
                                        "location": getattr(job, 'location', ''),
                                        "location_type": getattr(job, 'location_type', ''),
                                        "job_type": getattr(job, 'job_type', ''),
                                        "experience_level": getattr(job, 'experience_level', ''),
                                        "skills": job.skills.split(",") if isinstance(job.skills, str) and job.skills else []
                                    }
                                    job_embeds = job_service.create_embeddings(job_data)
                                    job_desc_embed = job_embeds.get("description", [])
                                    # Only compare if embedding exists
                                    if job_desc_embed and len(job_desc_embed) == len(role_embedding):
                                        # Cosine similarity
                                        a = np.array(role_embedding)
                                        b = np.array(job_desc_embed)
                                        sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
                                        if sim > best_sim:
                                            best_sim = sim
                                            best_job = job_data
                                print(f"[DEBUG] Best similarity: {best_sim:.4f} for job: {best_job['title'] if best_job else None} (ID: {best_job['id'] if best_job else None})")
                                if best_sim >= similarity_threshold:
                                    matched_job_obj = best_job
            except Exception as match_exc:
                logger.warning(f"Job matching failed: {match_exc}")
            # --- End Dynamic Job Matching ---

            # Use communications service to generate recruiter email
            if self.communications_service:
                result = await self.communications_service.generate_recruiter_outreach_email(
                    role=role,
                    job_data=matched_job_obj
                )
                email_body = result.get("body", "")
                from backend.utils.text_sanitizer import clean_generated_text
                email_body = clean_generated_text(email_body)
                subject_lines = result.get("subject_lines", [])
                return {
                    "intent_processed": True,
                    "response_type": "recruiter_outreach_email",
                    "role": role,
                    "email_body": email_body,
                    "subject_lines": subject_lines,
                    "email_content": email_body,
                    "message_type": "formatted_text",
                    "job_match": matched_job_obj
                }
            else:
                return {
                    "intent_processed": False,
                    "error": "Communications service not available",
                    "suggestion": "Please try again later"
                }
        except Exception as e:
            logger.error(f"Error generating recruiter outreach email: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not generate recruiter email: {str(e)}",
                "suggestion": "Please try again or specify a different role"
            }


    async def _handle_company_info(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle company information intent.
        """
        try:
            company = entities.get('company', '')
            if not company:
                return {
                    "intent_processed": False,
                    "error": "Missing company name",
                    "suggestion": "Please specify which company you want information about"
                }
            
            # Use web search service to get company information
            if self.web_search_service:
                query = f"information about {company} company"
                search_results = await self.web_search_service.search_web(query)
                
                if search_results and search_results.get('results'):
                    # Format the results
                    formatted_response = f"Here's what I found about {company}:\n\n"
                    
                    for i, result in enumerate(search_results['results'][:3], 1):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('content', 'No description'))
                        
                        formatted_response += f"{i}. **{title}**\n{snippet}\n\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "company_info",
                        "formatted_response": formatted_response,
                        "company": company,
                        "search_results": search_results
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No company information found",
                        "suggestion": "Please check the company name and try again"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Web search service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error getting company information: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not get company information: {str(e)}",
                "suggestion": "Please try again or check the company name"
            }

    async def _handle_job_posting_analysis(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle job posting analysis intent.
        """
        try:
            # Extract job posting URL or content from message
            url_match = re.search(r'https?://[^\s]+', message)
            if url_match:
                job_url = url_match.group(0)
                
                # Use crawler service to analyze job posting
                if self.crawler_service:
                    analysis_result = await self.crawler_service.analyze_job_posting(job_url)
                    
                    if analysis_result:
                        formatted_response = f"Job Posting Analysis:\n\n"
                        formatted_response += f"**Title**: {analysis_result.get('title', 'Unknown')}\n"
                        formatted_response += f"**Company**: {analysis_result.get('company', 'Unknown')}\n"
                        formatted_response += f"**Location**: {analysis_result.get('location', 'Unknown')}\n"
                        formatted_response += f"**Skills Required**: {', '.join(analysis_result.get('skills', []))}\n"
                        formatted_response += f"**Experience Level**: {analysis_result.get('experience_level', 'Unknown')}\n"
                        
                        return {
                            "intent_processed": True,
                            "response_type": "job_posting_analysis",
                            "formatted_response": formatted_response,
                            "analysis_result": analysis_result,
                            "job_url": job_url
                        }
                    else:
                        return {
                            "intent_processed": False,
                            "error": "Could not analyze job posting",
                            "suggestion": "Please check the URL and try again"
                        }
                else:
                    return {
                        "intent_processed": False,
                        "error": "Crawler service not available",
                        "suggestion": "Please try again later"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "No job posting URL found",
                    "suggestion": "Please provide a job posting URL to analyze"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing job posting: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not analyze job posting: {str(e)}",
                "suggestion": "Please try again or check the URL"
            }

    async def _handle_company_research(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle company research intent.
        """
        try:
            company = entities.get('company', '')
            if not company:
                return {
                    "intent_processed": False,
                    "error": "Missing company name",
                    "suggestion": "Please specify which company to research"
                }
            
            # Use web search service for comprehensive company research
            if self.web_search_service:
                query = f"comprehensive research about {company} company business model revenue employees"
                search_results = await self.web_search_service.search_web(query)
                
                if search_results and search_results.get('results'):
                    formatted_response = f"Company Research for {company}:\n\n"
                    
                    for i, result in enumerate(search_results['results'][:5], 1):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('content', 'No description'))
                        
                        formatted_response += f"{i}. **{title}**\n{snippet}\n\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "company_research",
                        "formatted_response": formatted_response,
                        "company": company,
                        "search_results": search_results
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No company research results found",
                        "suggestion": "Please check the company name and try again"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Web search service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error researching company: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not research company: {str(e)}",
                "suggestion": "Please try again or check the company name"
            }

    async def _handle_market_trends(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle market trends intent.
        """
        try:
            # Extract industry or market from message
            industry_match = re.search(r'(?:in|for|about)\s+([a-zA-Z\s]+?)(?:\s+industry|\s+market|\?|$)', message.lower())
            industry = industry_match.group(1).strip() if industry_match else "technology"
            
            # Use web search service to get market trends
            if self.web_search_service:
                query = f"latest market trends {industry} industry 2024"
                search_results = await self.web_search_service.search_web(query)
                
                if search_results and search_results.get('results'):
                    formatted_response = f"Market Trends for {industry.title()} Industry:\n\n"
                    
                    for i, result in enumerate(search_results['results'][:4], 1):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('content', 'No description'))
                        
                        formatted_response += f"{i}. **{title}**\n{snippet}\n\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "market_trends",
                        "formatted_response": formatted_response,
                        "industry": industry,
                        "search_results": search_results
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No market trends found",
                        "suggestion": "Please try a different industry or check your query"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Web search service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error getting market trends: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not get market trends: {str(e)}",
                "suggestion": "Please try again or specify a different industry"
            }

    async def _handle_minimum_wage(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle minimum wage intent.
        """
        try:
            # Extract location from message
            location_match = re.search(r'(?:in|for|at)\s+([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message.lower())
            location = location_match.group(1).strip() if location_match else "United States"
            
            # Use web search service to get minimum wage information
            if self.web_search_service:
                query = f"minimum wage {location} 2024 current rate"
                search_results = await self.web_search_service.search_web(query)
                
                if search_results and search_results.get('results'):
                    formatted_response = f"Minimum Wage Information for {location.title()}:\n\n"
                    
                    for i, result in enumerate(search_results['results'][:3], 1):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('content', 'No description'))
                        
                        formatted_response += f"{i}. **{title}**\n{snippet}\n\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "minimum_wage",
                        "formatted_response": formatted_response,
                        "location": location,
                        "search_results": search_results
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No minimum wage information found",
                        "suggestion": "Please check the location and try again"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Web search service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error getting minimum wage information: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not get minimum wage information: {str(e)}",
                "suggestion": "Please try again or check the location"
            }

    async def _handle_labor_law(self, intent: str, entities: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Handle labor law intent.
        """
        try:
            # Extract specific labor law topic from message
            topic_match = re.search(r'(?:about|regarding|on)\s+([a-zA-Z\s]+?)(?:\?|$|\s|\.)', message.lower())
            topic = topic_match.group(1).strip() if topic_match else "employment law"
            
            # Use web search service to get labor law information
            if self.web_search_service:
                query = f"labor law {topic} employment regulations"
                search_results = await self.web_search_service.search_web(query)
                
                if search_results and search_results.get('results'):
                    formatted_response = f"Labor Law Information about {topic.title()}:\n\n"
                    
                    for i, result in enumerate(search_results['results'][:4], 1):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('content', 'No description'))
                        
                        formatted_response += f"{i}. **{title}**\n{snippet}\n\n"
                    
                    return {
                        "intent_processed": True,
                        "response_type": "labor_law",
                        "formatted_response": formatted_response,
                        "topic": topic,
                        "search_results": search_results
                    }
                else:
                    return {
                        "intent_processed": False,
                        "error": "No labor law information found",
                        "suggestion": "Please try a different topic or check your query"
                    }
            else:
                return {
                    "intent_processed": False,
                    "error": "Web search service not available",
                    "suggestion": "Please try again later"
                }
                
        except Exception as e:
            logger.error(f"Error getting labor law information: {e}")
            return {
                "intent_processed": False,
                "error": f"Could not get labor law information: {str(e)}",
                "suggestion": "Please try again or specify a different topic"
            }

# Singleton instance
_intent_processor = None

def get_intent_processor() -> IntentProcessor:
    """Get or create the singleton instance of IntentProcessor."""
    global _intent_processor
    if _intent_processor is None:
        _intent_processor = IntentProcessor()
    return _intent_processor 
