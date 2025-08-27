# backend/services/market_intel_service.py
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import json

import httpx
from pydantic import BaseModel, Field

from backend.utils.config import Settings
from backend.services.llm_service import LLMService
# Modify the crawl_service import to avoid the error
# from backend.services.crawl_service import CrawlService

logger = logging.getLogger(__name__)

# Add a simple Document class to simulate crawl results
class Document(BaseModel):
    """Simple document model for crawled content."""
    content: str
    source: str
    score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SalaryData(BaseModel):
    """Model for salary data."""
    job_title: str
    location: str
    company_size: Optional[str] = None
    experience_level: Optional[str] = None
    median_salary: float
    salary_range_min: float
    salary_range_max: float
    currency: str = "USD"
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TalentPoolData(BaseModel):
    """Model for talent pool estimates."""
    job_title: str
    skills: List[str]
    location: str
    radius_miles: int = 50
    estimated_candidates: int
    active_seekers_percent: Optional[float] = None
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketTrendData(BaseModel):
    """Model for hiring trend data."""
    job_title: str
    location: Optional[str] = None
    trend_type: str  # e.g., "hiring_volume", "time_to_fill", "offer_acceptance_rate"
    time_period: str  # e.g., "last_30_days", "last_quarter", "year_over_year"
    value: Union[float, int, str]
    change_percent: Optional[float] = None
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Add a simple CrawlService class for use within this file
class CrawlService:
    """Simplified crawl service for web data."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client when service is shut down."""
        await self.client.aclose()
    
    async def crawl_from_query(self, query: str, max_results: int = 5) -> List[Document]:
        """
        Simulated web crawling from a search query.
        
        In a real implementation, this would:
        1. Search the web for the query
        2. Extract content from the top results
        3. Return the content as documents
        
        For this simplified version, we'll return mock data.
        """
        logger.info(f"Simulating web crawl for query: {query}")
        
        # Simulate network delay
        await asyncio.sleep(0.5)
        
        # Extract key terms from query
        terms = query.lower().split()
        
        # Generate different mock results based on the query
        if "salary" in query.lower():
            return [
                Document(
                    content=f"Average {terms[0]} salary in {terms[-1] if len(terms) > 2 else 'the US'} ranges from $80,000 to $120,000 depending on experience. Senior roles can earn up to $150,000.",
                    source="mock-glassdoor.com",
                    metadata={"confidence": "medium"}
                ),
                Document(
                    content=f"For {terms[0]} positions, companies typically pay between $90,000 and $130,000 annually. Top companies may offer $160,000 or more for experienced candidates.",
                    source="mock-levels.fyi",
                    metadata={"confidence": "high"}
                )
            ][:max_results]
        elif "talent" in query.lower() or "candidates" in query.lower():
            return [
                Document(
                    content=f"The {terms[0]} talent pool in {terms[-1] if len(terms) > 2 else 'major tech hubs'} has approximately 50,000 professionals with relevant skills.",
                    source="mock-linkedin.com",
                    metadata={"confidence": "medium"}
                ),
                Document(
                    content=f"Currently about 15% of {terms[0]} professionals are actively seeking new opportunities, with another 45% open to the right offer.",
                    source="mock-indeed.com",
                    metadata={"confidence": "medium"}
                )
            ][:max_results]
        else:
            return [
                Document(
                    content=f"General information about {' '.join(terms[:3])} industry trends shows growing demand in the current market.",
                    source="mock-industry-report.com",
                    metadata={"confidence": "low"}
                )
            ][:max_results]

# Update the MarketIntelService initialization to handle the case where crawl_service might be None
class MarketIntelService:
    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService,
        crawl_service: Optional[CrawlService] = None,
    ):
        self.settings = settings
        self.llm_service = llm_service
        
        # Initialize crawl service if not provided
        self.crawl_service = crawl_service or CrawlService(settings)
        
        # Setup HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Configure API keys
        self.api_keys = {
            "levels_fyi": settings.levels_fyi_api_key,
            "glassdoor": settings.glassdoor_api_key,
            "linkedin": settings.linkedin_api_key,
        }
        
        # Cache for efficient repeated queries
        self.cache_ttl = 86400  # 24 hours for market data
        self.cache = {}
    
    async def close(self):
        """Close the HTTP client when service is shut down."""
        await self.http_client.aclose()
    
    async def get_salary_data(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None,
        company_size: Optional[str] = None,
    ) -> List[SalaryData]:
        """Get salary benchmarks for a job title and location."""
        # Check cache
        cache_key = f"salary_{job_title}_{location}_{experience_level}_{company_size}"
        cached = self.cache.get(cache_key)
        if cached and cached["timestamp"] + self.cache_ttl > time.time():
            return cached["data"]
        
        results = []
        
        # Try to get data from multiple sources
        try:
            # Levels.fyi
            if self.api_keys.get("levels_fyi"):
                levels_data = await self._get_levels_fyi_salary(
                    job_title, location, experience_level
                )
                if levels_data:
                    results.append(levels_data)
            
            # Glassdoor
            if self.api_keys.get("glassdoor"):
                glassdoor_data = await self._get_glassdoor_salary(
                    job_title, location, experience_level
                )
                if glassdoor_data:
                    results.append(glassdoor_data)
            
            # LinkedIn
            if self.api_keys.get("linkedin"):
                linkedin_data = await self._get_linkedin_salary(
                    job_title, location, experience_level
                )
                if linkedin_data:
                    results.append(linkedin_data)
            
            # If no API data, try web crawling
            if not results:
                web_data = await self._crawl_salary_data(
                    job_title, location, experience_level
                )
                results.extend(web_data)
            
            # Update cache
            self.cache[cache_key] = {
                "timestamp": time.time(),
                "data": results,
            }
            
            return results
            
        except Exception as e:
            logger.exception(f"Error retrieving market intelligence data")
            # Return empty results on error
            return []
    
    async def _get_levels_fyi_salary(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None,
    ) -> Optional[SalaryData]:
        """Get salary data from Levels.fyi API."""
        # In a real implementation, call the Levels.fyi API
        # For POC, simulate a response
        
        # Simulated API call
        await asyncio.sleep(0.5)  # Simulate API latency
        
        # Simulated response based on job title and location
        if "software" in job_title.lower() or "engineer" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=120000,
                salary_range_min=100000,
                salary_range_max=150000,
                source="levels.fyi",
                metadata={
                    "total_reports": 500,
                    "confidence": "high",
                }
            )
        elif "product" in job_title.lower() and "manager" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=135000,
                salary_range_min=115000,
                salary_range_max=160000,
                source="levels.fyi",
                metadata={
                    "total_reports": 350,
                    "confidence": "high",
                }
            )
        elif "data" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=110000,
                salary_range_min=95000,
                salary_range_max=130000,
                source="levels.fyi",
                metadata={
                    "total_reports": 400,
                    "confidence": "medium",
                }
            )
        else:
            return None
    
    async def _get_glassdoor_salary(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None,
    ) -> Optional[SalaryData]:
        """Get salary data from Glassdoor API."""
        # Simulated API call
        await asyncio.sleep(0.5)  # Simulate API latency
        
        # Simulated response with different data than Levels.fyi
        if "software" in job_title.lower() or "engineer" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=115000,
                salary_range_min=95000,
                salary_range_max=140000,
                source="glassdoor",
                metadata={
                    "total_reports": 2500,
                    "confidence": "high",
                }
            )
        elif "product" in job_title.lower() and "manager" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=130000,
                salary_range_min=110000,
                salary_range_max=155000,
                source="glassdoor",
                metadata={
                    "total_reports": 1800,
                    "confidence": "high",
                }
            )
        elif "data" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=105000,
                salary_range_min=90000,
                salary_range_max=125000,
                source="glassdoor",
                metadata={
                    "total_reports": 2000,
                    "confidence": "high",
                }
            )
        else:
            # Fall back to generic estimation for other roles
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=85000,
                salary_range_min=70000,
                salary_range_max=110000,
                source="glassdoor",
                metadata={
                    "total_reports": 500,
                    "confidence": "medium",
                }
            )
    
    async def _get_linkedin_salary(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None,
    ) -> Optional[SalaryData]:
        """Get salary data from LinkedIn API."""
        # Simulated API call
        await asyncio.sleep(0.5)  # Simulate API latency
        
        # Simulated response with different data
        if "software" in job_title.lower() or "engineer" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=125000,
                salary_range_min=105000,
                salary_range_max=155000,
                source="linkedin",
                metadata={
                    "total_reports": 5000,
                    "confidence": "high",
                }
            )
        elif "product" in job_title.lower() and "manager" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=140000,
                salary_range_min=120000,
                salary_range_max=165000,
                source="linkedin",
                metadata={
                    "total_reports": 3500,
                    "confidence": "high",
                }
            )
        elif "data" in job_title.lower():
            return SalaryData(
                job_title=job_title,
                location=location,
                experience_level=experience_level or "mid-level",
                median_salary=115000,
                salary_range_min=100000,
                salary_range_max=135000,
                source="linkedin",
                metadata={
                    "total_reports": 4200,
                    "confidence": "high",
                }
            )
        else:
            return None
    
    async def _crawl_salary_data(
        self,
        job_title: str,
        location: str,
        experience_level: Optional[str] = None,
    ) -> List[SalaryData]:
        """Crawl salary data from web sources."""
        search_query = f"{job_title} salary {location} {experience_level or ''}"
        
        # Use the web crawler to find salary information
        chunks = await self.crawl_service.crawl_from_query(search_query, max_results=5)
        
        # Now use the LLM to extract structured salary data
        if not chunks:
            return []
        
        # Combine chunks into context
        context = "\n\n".join([chunk.content for chunk in chunks])
        
        prompt = f"""
        Extract salary information from the following text about {job_title} in {location}.
        If experience level is mentioned, include it: {experience_level or 'any experience level'}.
        
        Context:
        {context}
        
        Please extract the following information in JSON format:
        1. Median or average salary (numerical value only)
        2. Salary range minimum (numerical value only)
        3. Salary range maximum (numerical value only)
        4. Source of information (website or publication name)
        5. Confidence level (high, medium, low) based on specificity and recency
        
        Return the data as a JSON array of objects, each with these fields:
        - median_salary: number
        - salary_range_min: number
        - salary_range_max: number
        - source: string
        - confidence: string
        
        If multiple sources are found, include them as separate objects in the array.
        If no concrete salary data is found, return an empty array.
        """
        
        response = await self.llm_service.generate_text_async(
            prompt=prompt,
            model="mixtral",
            max_tokens=500,
        )
        
        try:
            # Parse the JSON response
            data = json.loads(response)
            
            # Convert to SalaryData objects
            result = []
            for item in data:
                result.append(
                    SalaryData(
                        job_title=job_title,
                        location=location,
                        experience_level=experience_level,
                        median_salary=item.get("median_salary", 0),
                        salary_range_min=item.get("salary_range_min", 0),
                        salary_range_max=item.get("salary_range_max", 0),
                        source=item.get("source", "web"),
                        metadata={
                            "confidence": item.get("confidence", "low"),
                            "extraction_method": "web_crawl",
                        }
                    )
                )
            
            return result
            
        except Exception as e:
            logger.exception(f"Error parsing salary data: {str(e)}")
            return []
    
    async def get_talent_pool_estimates(
        self,
        job_title: str,
        skills: List[str],
        location: str,
        radius_miles: int = 50,
    ) -> TalentPoolData:
        """Get estimates of available talent for a role."""
        # Check cache
        cache_key = f"talent_{job_title}_{','.join(skills)}_{location}_{radius_miles}"
        cached = self.cache.get(cache_key)
        if cached and cached["timestamp"] + self.cache_ttl > time.time():
            return cached["data"]
        
        try:
            # Try LinkedIn API first
            if self.api_keys.get("linkedin"):
                data = await self._get_linkedin_talent_pool(
                    job_title, skills, location, radius_miles
                )
                if data:
                    # Update cache
                    self.cache[cache_key] = {
                        "timestamp": time.time(),
                        "data": data,
                    }
                    return data
            
            # Fall back to estimation based on job title and location
            estimated_candidates = self._estimate_talent_pool(job_title, location)
            
            data = TalentPoolData(
                job_title=job_title,
                skills=skills,
                location=location,
                radius_miles=radius_miles,
                estimated_candidates=estimated_candidates,
                active_seekers_percent=15.0,  # Estimated percentage
                source="internal_estimate",
                metadata={
                    "confidence": "medium",
                    "estimation_method": "statistical",
                }
            )
            
            # Update cache
            self.cache[cache_key] = {
                "timestamp": time.time(),
                "data": data,
            }
            
            return data
            
        except Exception as e:
            logger.exception(f"Error retrieving market intelligence data")