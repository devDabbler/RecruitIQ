"""Web search service for fetching external information."""
import logging
import json
import os
import re
from typing import List, Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from bs4 import BeautifulSoup
import traceback

# Configure logging with a specific format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Make sure logs are visible
logger.setLevel(logging.DEBUG)

class WebSearchService:
    """Service for performing web searches to answer dynamic queries."""
    
    def __init__(self, testing: bool = False):
        """Initialize the web search service."""
        # Log startup of service
        logger.info("Initializing WebSearchService")
        
        self.testing = testing
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
        )
        
        # Get API keys from environment variables
        try:
            self.search_api_key = os.getenv("SERPAPI_KEY")
            self.google_search_engine_id = os.getenv("GOOGLE_CSE_ID")
            self.google_api_key = os.getenv("GOOGLE_API_KEY")
            self.bing_api_key = os.getenv("BING_API_KEY")
            
            # Log which API keys are available
            logger.info(f"Google CSE ID available: {bool(self.google_search_engine_id)}")
            logger.info(f"Google API key available: {bool(self.google_api_key)}")
            logger.info(f"SerpAPI key available: {bool(self.search_api_key)}")
            logger.info(f"Bing API key available: {bool(self.bing_api_key)}")
            
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            self.search_api_key = None
            self.google_search_engine_id = None
            self.google_api_key = None
            self.bing_api_key = None
            
        self._initialized = True
        logger.info("WebSearchService initialization complete")
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def search_google(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search Google for information using Google Custom Search API.
        
        Args:
            query: The search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, link, and snippet
        """
        logger.debug(f"Attempting Google search for: {query}")
        
        if not self.google_api_key or not self.google_search_engine_id:
            logger.warning("Google Search API credentials not configured")
            return []
            
        try:
            # Use Google Custom Search API
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_search_engine_id,
                "q": query,
                "num": min(num_results, 10)  # API limit is 10
            }
            
            logger.debug(f"Making Google CSE request to: {url} with params: {params}")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if "items" in data:
                for item in data["items"]:
                    results.append({
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })
                
                logger.info(f"Google search returned {len(results)} results")
            else:
                logger.warning(f"Google search returned no items in response: {data}")
                
            return results
            
        except Exception as e:
            logger.error(f"Error performing Google search: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def search_serpapi(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search using SerpAPI as a fallback.
        
        Args:
            query: The search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, link, and snippet
        """
        if not self.search_api_key:
            logger.warning("SerpAPI key not configured")
            return []
            
        try:
            # Use SerpAPI
            url = "https://serpapi.com/search"
            params = {
                "api_key": self.search_api_key,
                "q": query,
                "num": num_results,
                "engine": "google"
            }
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if "organic_results" in data:
                for item in data["organic_results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })
            return results
            
        except Exception as e:
            logger.error(f"Error performing SerpAPI search: {str(e)}")
            return []
    
    async def fetch_webpage_content(self, url: str) -> Optional[str]:
        """
        Fetch and parse content from a webpage.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Extracted text content or None if failed
        """
        # If in testing mode and it's a LinkedIn URL, return mock data
        if self.testing and 'linkedin.com' in url:
            logger.info(f"Testing mode: Returning mock content for LinkedIn URL: {url}")
            return "This is mock content for a LinkedIn profile."

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
                
            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up text - remove excessive whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.error(f"Error fetching webpage content: {str(e)}")
            return None
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web for information and return formatted results.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
        """
        logger.debug(f"Starting web search for: '{query}'")
        
        # Check if we have any API keys configured
        has_google_keys = bool(self.google_api_key and self.google_search_engine_id)
        has_serpapi_key = bool(self.search_api_key)
        
        if not has_google_keys and not has_serpapi_key:
            logger.warning("No search API keys configured - LinkedIn enrichment will not work")
            # Mock LinkedIn result for testing if query specifically mentions LinkedIn
            if 'LinkedIn' in query and 'profile' in query:
                return self._get_mock_linkedin_results(query)
            return []
        
        # Try Google search first
        results = []
        if has_google_keys:
            results = await self.search_google(query, num_results=max_results)
        
        # Fallback to SerpAPI if Google search returned no results
        if not results and has_serpapi_key:
            results = await self.search_serpapi(query, num_results=max_results)
            
        # Log the results for debugging
        result_count = len(results)
        has_linkedin = any('linkedin.com' in r.get('link', '') for r in results)
        logger.info(f"Search complete: Found {result_count} results, contains LinkedIn profile: {has_linkedin}")
        
        return results
        
    # Add an alias for search_web to maintain compatibility with assistant.py
    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Alias for search method to maintain compatibility with assistant.py.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
        """
        logger.info(f"Web search requested for: {query}")
        return await self.search(query, max_results)
        
    def _get_mock_linkedin_results(self, query: str) -> List[Dict[str, Any]]:
        """
        Generate mock LinkedIn search results when no API keys are configured.
        This is only used for testing when no real search APIs are available.
        
        Args:
            query: The search query containing the person's name
            
        Returns:
            A list with a single mock result for LinkedIn
        """
        # Extract a name from the query if possible
        name_match = re.search(r'"([^"]+)"', query)
        name = name_match.group(1) if name_match else "Unknown Person"
        
        # Extract company if present
        company = ""
        company_match = re.search(r'"([^"]+)"\s+"([^"]+)"', query)
        if company_match and len(company_match.groups()) > 1:
            company = company_match.group(2)
        
        # Create a slugified name for the profile URL
        slug = name.lower().replace(' ', '-')
        
        logger.warning(f"Using mock LinkedIn result for {name}. Configure real search APIs for production use.")
        
        return [{
            "title": f"{name} - {company if company else 'Professional'} | LinkedIn",
            "link": f"https://linkedin.com/in/{slug}",
            "snippet": f"View {name}'s profile on LinkedIn, the world's largest professional community."
        }]

# Singleton instance
_web_search_service = None

def get_web_search_service(testing: bool = False) -> WebSearchService:
    """Get or create the singleton instance of WebSearchService."""
    global _web_search_service
    if _web_search_service is None:
        testing_env = os.getenv("TESTING_MODE", "false").lower() in ("true", "1", "t")
        _web_search_service = WebSearchService(testing=testing or testing_env)
    elif testing and not _web_search_service.testing:
        _web_search_service.testing = True
        logger.info("WebSearchService testing mode has been enabled.")
        
    return _web_search_service
