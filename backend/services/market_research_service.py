"""
Enhanced Market Research Service for dynamic salary benchmarking and market intelligence.
Provides experience-based salary analysis using real-time market data.
"""
import json
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

from backend.services.web_search_service import WebSearchService
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class MarketResearchService:
    """Enhanced market research service for dynamic salary benchmarking and market intelligence."""

    def __init__(self, web_search_service: WebSearchService, llm_service: LLMService):
        self.web_search_service = web_search_service
        self.llm_service = llm_service

        # Experience level mappings
        self.experience_levels = {
            "entry": {"years": "0-2", "description": "Entry Level"},
            "mid": {"years": "3-5", "description": "Mid Level"},
            "senior": {"years": "6-10", "description": "Senior Level"},
            "lead": {"years": "10+", "description": "Lead/Principal Level"}
        }

        # Industry-specific salary multipliers for different locations
        self.location_multipliers = {
            "San Francisco, CA": 1.4,
            "New York, NY": 1.35,
            "Seattle, WA": 1.25,
            "Austin, TX": 1.1,
            "Denver, CO": 1.15,
            "Boston, MA": 1.3,
            "Los Angeles, CA": 1.25,
            "Chicago, IL": 1.2,
            "Atlanta, GA": 1.05,
            "Dallas, TX": 1.05
        }

    # ============================================================================
    # CENTRALIZED MARKET RESEARCH METHODS - Callable from anywhere in the system
    # ============================================================================

    async def generate_city_viability_report(
        self,
        role: str,
        city: str,
        seniority: Optional[str] = None,
        time_range: Optional[str] = None,
        include_actions: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive city viability snapshot for sourcing a role.

        Args:
            role: Job role/title to research
            city: City to analyze
            seniority: Optional seniority level (entry, mid, senior, lead)
            time_range: Optional time range (e.g., "6 months", "12 months")
            include_actions: Whether to include actionable sourcing tactics

        Returns:
            Comprehensive city viability report
        """
        try:
            # Build search query
            seniority_text = f" {seniority}" if seniority else ""
            time_text = f" over the last {time_range}" if time_range else ""

            search_query = f"talent market {role}{seniority_text} {city} job postings salary demand supply{time_text}"

            # Collect market data
            results = await self.web_search_service.search(search_query, max_results=8)

            # Build analysis prompt
            prompt = f"""
            Generate a comprehensive city viability snapshot for sourcing {role}{seniority_text} in {city}{time_text}.

            Include:
            - Estimated talent supply (high/medium/low with reasoning)
            - Active postings volume and trend
            - Major employers hiring this role
            - University pipeline strength
            - Salary bands and market rates
            - Cost-of-living impact on hiring
            - Remote work willingness
            - Expected time-to-fill
            - Key risks and challenges
            {"- 3 actionable sourcing tactics" if include_actions else ""}

            Use recent, reputable sources and provide specific data where available.
            Format as a structured report with clear sections.
            """

            # Generate analysis
            analysis = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=1500,
                task_type="market_research"
            )

            return {
                "status": "success",
                "report_type": "city_viability",
                "role": role,
                "city": city,
                "seniority": seniority,
                "time_range": time_range,
                "analysis": analysis,
                "sources": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating city viability report: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate city viability report: {str(e)}"
            }

    async def generate_city_comparison(
        self,
        role: str,
        city1: str,
        city2: str,
        seniority: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a two-city comparison for sourcing viability.

        Args:
            role: Job role/title to research
            city1: First city (typically non-tech hub)
            city2: Second city (typically tech hub)
            seniority: Optional seniority level

        Returns:
            Two-city comparison report
        """
        try:
            seniority_text = f" {seniority}" if seniority else ""

            # Collect data for both cities
            query1 = f"talent market {role}{seniority_text} {city1} job demand salary"
            query2 = f"talent market {role}{seniority_text} {city2} job demand salary"

            results1 = await self.web_search_service.search(query1, max_results=5)
            results2 = await self.web_search_service.search(query2, max_results=5)

            # Build comparison prompt
            prompt = f"""
            Compare the viability of sourcing {role}{seniority_text} in {city1} vs {city2}.

            Cover these aspects for each city:
            - Talent pool size and availability
            - Job postings density and volume
            - Competition intensity from other employers
            - Salary deltas and compensation differences
            - Relocation/remote work feasibility
            - Hiring risk and challenges

            Provide a clear recommendation on which city offers better sourcing prospects
            and include a confidence level (high/medium/low) with reasoning.

            Format as a structured comparison with clear pros/cons for each city.
            """

            # Generate comparison
            comparison = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=1500,
                task_type="market_research"
            )

            return {
                "status": "success",
                "report_type": "city_comparison",
                "role": role,
                "city1": city1,
                "city2": city2,
                "seniority": seniority,
                "comparison": comparison,
                "sources_city1": results1,
                "sources_city2": results2,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating city comparison: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate city comparison: {str(e)}"
            }

    async def generate_non_tech_hub_shortlist(
        self,
        role: str,
        num_cities: int = 5
    ) -> Dict[str, Any]:
        """
        Generate a shortlist of top non-tech hub US cities for sourcing a role.

        Args:
            role: Job role/title to research
            num_cities: Number of cities to include in shortlist

        Returns:
            Shortlist of non-tech hub cities with rationale
        """
        try:
            search_query = f"best non-tech hub cities US {role} talent market job opportunities"
            results = await self.web_search_service.search(search_query, max_results=6)

            prompt = f"""
            Identify the top {num_cities} non-tech hub US cities to source {role}.

            Rank by these factors:
            - Talent availability and supply
            - Salary favorability (lower cost of living)
            - Employer landscape and job opportunities
            - University feeder strength
            - Competition index (lower is better)
            - Expected time-to-fill

            For each city, provide:
            - City name and state
            - 1-2 line rationale for inclusion
            - Key advantages for sourcing this role

            Focus on cities that are NOT major tech hubs (avoid SF, NYC, Seattle, Austin, etc.).
            """

            shortlist = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=1200,
                task_type="market_research"
            )

            return {
                "status": "success",
                "report_type": "non_tech_hub_shortlist",
                "role": role,
                "num_cities": num_cities,
                "shortlist": shortlist,
                "sources": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating non-tech hub shortlist: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate non-tech hub shortlist: {str(e)}"
            }

    async def generate_sourcing_plan(
        self,
        role: str,
        city: str
    ) -> Dict[str, Any]:
        """
        Generate a detailed sourcing plan for a role in a specific city.

        Args:
            role: Job role/title to source
            city: Target city for sourcing

        Returns:
            Comprehensive sourcing plan
        """
        try:
            search_query = f"sourcing strategies {role} {city} recruitment channels LinkedIn meetups"
            results = await self.web_search_service.search(search_query, max_results=6)

            prompt = f"""
            Create a comprehensive sourcing plan for {role} in {city}.

            Include:
            - Top channels (LinkedIn, meetups, Slack groups, universities)
            - Sample Boolean search strings for LinkedIn/Indeed
            - Outreach angle and messaging approach
            - Weekly activity targets and timeline
            - Key risks and mitigation strategies
            - Local networking opportunities and events

            Make it practical and actionable for recruiters.
            """

            plan = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=1500,
                task_type="market_research"
            )

            return {
                "status": "success",
                "report_type": "sourcing_plan",
                "role": role,
                "city": city,
                "plan": plan,
                "sources": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating sourcing plan: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate sourcing plan: {str(e)}"
            }

    async def generate_hiring_manager_briefing(
        self,
        role: str,
        city: str
    ) -> Dict[str, Any]:
        """
        Generate a 1-page briefing for hiring managers on hiring challenges.

        Args:
            role: Job role/title to hire
            city: Target city for hiring

        Returns:
            Hiring manager briefing document
        """
        try:
            search_query = f"hiring challenges {role} {city} talent shortage recruitment difficulties"
            results = await self.web_search_service.search(search_query, max_results=6)

            prompt = f"""
            Prepare a 1-page briefing for a hiring manager on the challenges of hiring {role} in {city}.

            Structure as:
            - Executive Summary: Why it's hard to hire this role in this city
            - Evidence: Market data, competition, supply constraints
            - Salary/Competition Pressures: Current market rates and competitive landscape
            - Realistic Timelines: Expected time-to-fill and hiring cycle
            - 3 Alternatives: Remote work, adjacent cities, level adjustment
            - Recommendations: Actionable next steps

            Keep it concise, data-driven, and executive-friendly.
            """

            briefing = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=1200,
                task_type="market_research"
            )

            return {
                "status": "success",
                "report_type": "hiring_manager_briefing",
                "role": role,
                "city": city,
                "briefing": briefing,
                "sources": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating hiring manager briefing: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate hiring manager briefing: {str(e)}"
            }

    async def generate_json_report(
        self,
        role: str,
        city: str,
        time_range: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON-only data for dashboards and integrations.

        Args:
            role: Job role/title to research
            city: Target city
            time_range: Optional time range
            schema: Optional custom JSON schema to follow

        Returns:
            JSON data structure for dashboards
        """
        try:
            # Default schema if none provided
            if not schema:
                schema = {
                    "talent_supply_estimate": "string",
                    "postings_volume": "number",
                    "top_companies": ["string"],
                    "universities": ["string"],
                    "salary_bands": {
                        "p50": "string",
                        "p75": "string"
                    },
                    "cost_of_living_index": "number",
                    "competition_index": "number",
                    "remote_readiness": "number",
                    "time_to_fill_estimate_days": "number",
                    "risks": ["string"],
                    "recommendations": ["string"]
                }

            time_text = f" for the last {time_range}" if time_range else ""
            search_query = f"job market data {role} {city} salary postings demand{time_text}"
            results = await self.web_search_service.search(search_query, max_results=5)

            # Build schema-specific prompt
            schema_str = json.dumps(schema, indent=2)
            prompt = f"""
            Return ONLY valid JSON for {role} in {city}{time_text}.

            Required JSON structure:
            {schema_str}

            Use the provided market data to populate these fields with realistic values.
            Return ONLY the JSON object - no explanations, no markdown formatting.
            Start with {{ and end with }}.
            """

            json_response = await self.llm_service.generate_text_async(
                prompt=prompt,
                max_tokens=800,
                task_type="market_research"
            )

            # Clean and parse JSON
            cleaned_json = self._extract_json_from_response(json_response)
            try:
                parsed_data = json.loads(cleaned_json)
            except json.JSONDecodeError:
                # Fallback to structured data
                parsed_data = self._generate_fallback_json_data(role, city, schema)

            return {
                "status": "success",
                "report_type": "json_data",
                "role": role,
                "city": city,
                "time_range": time_range,
                "data": parsed_data,
                "sources": results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating JSON report: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate JSON report: {str(e)}"
            }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from AI response that might contain extra text."""
        # Clean the response first
        cleaned_response = response.strip()

        # Remove any markdown code blocks
        cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
        cleaned_response = re.sub(r'```\s*$', '', cleaned_response)

        # Try to find JSON object in the response using balanced braces
        brace_count = 0
        start_pos = -1
        json_objects = []

        for i, char in enumerate(cleaned_response):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    json_objects.append(cleaned_response[start_pos:i + 1])

        if json_objects:
            # Return the longest match (most likely the main JSON)
            longest_match = max(json_objects, key=len)
            return longest_match

        # If no balanced JSON found, try simple regex as fallback
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, cleaned_response, re.DOTALL)

        if matches:
            longest_match = max(matches, key=len)
            return longest_match

        # If no JSON found, return the original response
        return cleaned_response

    def _generate_fallback_json_data(self, role: str, city: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback JSON data when parsing fails."""
        # Get location multiplier for realistic data
        location_multiplier = self.location_multipliers.get(f"{city}, CA", 1.0)

        # Generate realistic fallback data based on schema
        fallback_data = {
            "talent_supply_estimate": "medium",
            "postings_volume": int(50 * location_multiplier),
            "top_companies": ["Local Tech Company", "Regional Employer", "National Corp"],
            "universities": ["Local University", "State College"],
            "salary_bands": {
                "p50": f"${int(80000 * location_multiplier):,}",
                "p75": f"${int(100000 * location_multiplier):,}"
            },
            "cost_of_living_index": round(100 * location_multiplier),
            "competition_index": 7,
            "remote_readiness": 75,
            "time_to_fill_estimate_days": 45,
            "risks": ["Limited local talent pool", "Competition from larger markets"],
            "recommendations": ["Consider remote options", "Expand search radius", "Offer competitive compensation"]
        }

        return fallback_data

    # ============================================================================
    # EXISTING METHODS (keeping for backward compatibility)
    # ============================================================================

    async def get_comprehensive_salary_benchmark(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive salary benchmark for all experience levels or specific level.

        Args:
            job_title: Job title to research
            location: Location for salary data
            experience_level: Optional specific level (entry, mid, senior, lead)

        Returns:
            Comprehensive salary benchmark data
        """
        try:
            # Generate experience-specific search queries
            search_queries = self._generate_search_queries(job_title, location)

            # Collect real-time market data
            market_data = await self._collect_market_data(search_queries)

            # Analyze and structure the data
            benchmark_data = await self._analyze_salary_data(
                job_title, location, market_data, experience_level
            )

            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "data": benchmark_data
            }

        except Exception as e:
            logger.error(f"Error in comprehensive salary benchmark: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate salary benchmark: {str(e)}"
            }

    def _generate_search_queries(self, job_title: str, location: str) -> Dict[str, str]:
        """Generate experience-specific search queries."""
        queries = {}

        for level, info in self.experience_levels.items():
            if level == "entry":
                queries[level] = f'"{job_title}" entry level salary {location} {info["years"]} years experience'
            elif level == "mid":
                queries[level] = f'"{job_title}" mid level salary {location} {info["years"]} years experience'
            elif level == "senior":
                queries[level] = f'"{job_title}" senior salary {location} {info["years"]} years experience'
            elif level == "lead":
                queries[level] = f'"{job_title}" lead principal salary {location} {info["years"]} years experience'

        return queries

    async def _collect_market_data(self, queries: Dict[str, str]) -> Dict[str, str]:
        """Collect market data for all experience levels."""
        market_data = {}

        for level, query in queries.items():
            try:
                results = await self.web_search_service.search(query)
                market_data[level] = results
                logger.info(f"Collected market data for {level} level")
            except Exception as e:
                logger.error(f"Error collecting data for {level} level: {e}")
                market_data[level] = ""

        return market_data

    async def _analyze_salary_data(
        self,
        job_title: str,
        location: str,
        market_data: Dict[str, str],
        specific_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze collected market data and generate structured salary benchmarks."""

        # Create comprehensive analysis prompt
        prompt = self._create_analysis_prompt(job_title, location, market_data, specific_level)

        try:
            # Get AI analysis
            analysis_response = await self.llm_service.generate_text_async(
                prompt,
                max_tokens=1500,
                task_type="market_research"
            )

            # Clean the response to extract JSON
            cleaned_response = self._extract_json_from_response(analysis_response)

            # Parse JSON response
            try:
                analysis_data = json.loads(cleaned_response)
                logger.info("Successfully parsed JSON response from Nebius AI")
                return self._enhance_analysis_data(analysis_data, location)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Cleaned response: {cleaned_response[:500]}...")
                logger.error(f"Raw response: {analysis_response[:500]}...")
                # Fallback to structured parsing
                return self._parse_fallback_response(analysis_response, job_title, location, specific_level)

        except Exception as e:
            logger.error(f"Error in salary data analysis: {e}")
            return self._generate_fallback_benchmark(job_title, location)

    def _create_analysis_prompt(
        self,
        job_title: str,
        location: str,
        market_data: Dict[str, str],
        specific_level: Optional[str] = None
    ) -> str:
        """Create comprehensive analysis prompt."""

        level_filter = f" for {specific_level} level" if specific_level else ""

        prompt = f"""
        Analyze the following real-time market data to provide a comprehensive salary benchmark for '{job_title}' in '{location}'{level_filter}.

        REQUIRED OUTPUT FORMAT (JSON only):
        {{
            "job_title": "{job_title}",
            "location": "{location}",
            "analysis_date": "{datetime.now().strftime('%Y-%m-%d')}",
            "salary_benchmarks": {{
                "entry_level": {{
                    "range": "X-Y",
                    "average": "Z",
                    "percentile_25": "A",
                    "percentile_75": "B",
                    "description": "Entry level (0-2 years experience)"
                }},
                "mid_level": {{
                    "range": "X-Y",
                    "average": "Z",
                    "percentile_25": "A",
                    "percentile_75": "B",
                    "description": "Mid level (3-5 years experience)"
                }},
                "senior_level": {{
                    "range": "X-Y",
                    "average": "Z",
                    "percentile_25": "A",
                    "percentile_75": "B",
                    "description": "Senior level (6-10 years experience)"
                }},
                "lead_level": {{
                    "range": "X-Y",
                    "average": "Z",
                    "percentile_25": "A",
                    "percentile_75": "B",
                    "description": "Lead level (10+ years experience)"
                }}
            }},
            "market_insights": {{
                "demand_level": "high/medium/low",
                "growth_trend": "percentage",
                "key_factors": ["factor1", "factor2", "factor3"]
            }},
            "data_quality": "high/medium/low",
            "sources": "Based on current market data from multiple sources"
        }}

                CRITICAL REQUIREMENTS:
         1. Entry level must be significantly lower than senior level
         2. Clear progression: entry < mid < senior < lead
         3. Consider {location} cost of living adjustments
         4. Use realistic ranges based on current market data
         5. Return ONLY valid JSON, no additional text or explanations
         6. Ensure all salary figures are in USD
         7. Do not include any markdown formatting or code blocks
         8. Start your response with {{ and end with }}

        Market Data by Experience Level:
        Entry Level Data: {market_data.get('entry', 'No data available')}
        Mid Level Data: {market_data.get('mid', 'No data available')}
        Senior Level Data: {market_data.get('senior', 'No data available')}
        Lead Level Data: {market_data.get('lead', 'No data available')}

        JSON Response:
        """

        return prompt

    def _enhance_analysis_data(self, analysis_data: Dict[str, Any], location: str) -> Dict[str, Any]:
        """Enhance analysis data with additional insights."""

        # Add location-specific adjustments
        location_multiplier = self.location_multipliers.get(location, 1.0)

        # Add metadata
        analysis_data["metadata"] = {
            "location_multiplier": location_multiplier,
            "analysis_method": "AI-powered market research",
            "data_freshness": "real-time"
        }

        return analysis_data

    def _get_location_adjusted_salaries(self, job_title: str, location: str) -> Dict[str, Dict[str, str]]:
        """Get realistic salary ranges adjusted for location and job title."""

        # Base salaries for different job types (national average)
        base_salaries = {
            "Software Engineer": {
                "entry_level": {"range": "70K-110K", "average": "90K"},
                "mid_level": {"range": "110K-160K", "average": "135K"},
                "senior_level": {"range": "160K-220K", "average": "190K"},
                "lead_level": {"range": "220K-300K", "average": "260K"}
            },
            "Product Manager": {
                "entry_level": {"range": "80K-120K", "average": "100K"},
                "mid_level": {"range": "120K-180K", "average": "150K"},
                "senior_level": {"range": "180K-250K", "average": "215K"},
                "lead_level": {"range": "250K-350K", "average": "300K"}
            },
            "Data Scientist": {
                "entry_level": {"range": "85K-125K", "average": "105K"},
                "mid_level": {"range": "125K-180K", "average": "152K"},
                "senior_level": {"range": "180K-250K", "average": "215K"},
                "lead_level": {"range": "250K-350K", "average": "300K"}
            }
        }

        # Get base salary for job title (default to Software Engineer if not found)
        job_salaries = base_salaries.get(job_title, base_salaries["Software Engineer"])

        # Apply location multiplier
        location_multiplier = self.location_multipliers.get(location, 1.0)

        # Adjust salaries for location
        adjusted_salaries = {}
        for level, salary_data in job_salaries.items():
            # Parse range and average
            range_str = salary_data["range"]
            avg_str = salary_data["average"]

            # Extract numbers and apply multiplier
            try:
                low, high = map(lambda x: int(x.replace('K', '')), range_str.split('-'))
                avg = int(avg_str.replace('K', ''))

                # Apply location multiplier
                adjusted_low = int(low * location_multiplier)
                adjusted_high = int(high * location_multiplier)
                adjusted_avg = int(avg * location_multiplier)

                adjusted_salaries[level] = {
                    "range": f"{adjusted_low}K-{adjusted_high}K",
                    "average": f"{adjusted_avg}K"
                }
            except (ValueError, AttributeError):
                # If parsing fails, use original values
                adjusted_salaries[level] = salary_data

        return adjusted_salaries

    def _parse_fallback_response(self, response: str, job_title: str, location: str, specific_level: Optional[str] = None) -> Dict[str, Any]:
        """Parse fallback response when JSON parsing fails."""
        logger.warning("JSON parsing failed, using fallback parsing")

        # Get location-adjusted base salaries
        base_salaries = self._get_location_adjusted_salaries(job_title, location)

        # If specific level requested, return only that level
        if specific_level and specific_level in base_salaries:
            return {
                "job_title": job_title,
                "location": location,
                "analysis_date": datetime.now().strftime('%Y-%m-%d'),
                "salary_benchmarks": {
                    specific_level: base_salaries[specific_level]
                },
                "note": f"Fallback data for {specific_level} level - original response parsing failed",
                "data_quality": "low"
            }

        # Return all levels
        return {
            "job_title": job_title,
            "location": location,
            "analysis_date": datetime.now().strftime('%Y-%m-%d'),
            "salary_benchmarks": base_salaries,
            "note": "Fallback data - original response parsing failed",
            "raw_response": response[:500] + "..." if len(response) > 500 else response,
            "data_quality": "low"
        }

    def _generate_fallback_benchmark(self, job_title: str, location: str) -> Dict[str, Any]:
        """Generate fallback benchmark when analysis fails."""
        logger.warning("Using fallback benchmark generation")

        # Get location-adjusted salaries
        base_salaries = self._get_location_adjusted_salaries(job_title, location)

        return {
            "job_title": job_title,
            "location": location,
            "analysis_date": datetime.now().strftime('%Y-%m-%d'),
            "salary_benchmarks": base_salaries,
            "note": "Fallback benchmark - analysis service unavailable",
            "data_quality": "low"
        }
