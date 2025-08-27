import os
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class CrawlerConfig(BaseModel):
    max_depth: int = 3
    max_pages: int = 50
    respect_robots_txt: bool = True
    user_agent: str = "RecruitIQ Bot/1.0"
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 5

class CrawlerService:
    def __init__(self, settings=None):
        """
        Initialize the crawler service with either a CrawlerConfig or Settings object.
        
        Args:
            settings: Optional Settings object containing configuration for LLM services.
        """
        self.config = CrawlerConfig()
        
        # Initialize LLM service if settings are provided
        self.settings = settings
        self.llm_service = None
        self.embedding_model = None
        
        if settings:
            from .llm_service import LLMService
            self.llm_service = LLMService(settings)
            self.embedding_model = self.llm_service.embedding_model
        
        # Setup HTTP client with appropriate headers and timeout
        self.http_client = httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        
        # Setup text splitter for chunking content if needed
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n## ", "\n### ", "\n#### ", "\n", ". ", ", ", " ", ""],
            )
        except ImportError:
            self.text_splitter = None
            
        # Maintain visited URLs to avoid duplicate scraping
        self.visited_urls = set()
        
        # Define scraping limits
        self.max_pages_per_domain = 5
        self.max_total_pages = 20
        self.domain_counts = {}
    
    async def search_and_crawl(self, query: str, crawl_type: str = "job", max_results: int = 5) -> List[Dict[str, Any]]:
        """Compatibility method used by the assistant. Performs a lightweight web search
        emulation to generate URLs and then crawls them using existing helpers.
        This keeps behavior dynamic and avoids hardcoding providers.
        """
        try:
            # Reuse our existing query → terms → urls flow
            search_terms = await self._generate_search_terms(query)
            urls = await self._search_for_urls(search_terms, max_results=max_results)
            results: List[Dict[str, Any]] = []
            for url in urls:
                try:
                    if crawl_type == "company":
                        results.append(await self.crawl_company_profile(url))
                    else:
                        results.append(await self.crawl_job_posting(url))
                except Exception as e:
                    print(f"Crawl error for {url}: {e}")
            return results
        except Exception as e:
            raise Exception(f"search_and_crawl failed: {str(e)}")

    async def crawl_job_posting(self, url: str) -> Dict[str, Any]:
        """
        Crawl a job posting URL and extract relevant information.
        """
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract job details from the crawled content
            job_data = {
                "url": url,
                "title": self._extract_job_title(soup),
                "company": self._extract_company(soup),
                "location": self._extract_location(soup),
                "description": self._extract_description(soup),
                "requirements": self._extract_requirements(soup),
                "salary": self._extract_salary(soup),
                "raw_content": response.text
            }
            
            return job_data
        except Exception as e:
            raise Exception(f"Error crawling job posting: {str(e)}")
    
    async def crawl_company_profile(self, url: str) -> Dict[str, Any]:
        """
        Crawl a company profile URL and extract relevant information.
        """
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract company details from the crawled content
            company_data = {
                "url": url,
                "name": self._extract_company_name(soup),
                "description": self._extract_company_description(soup),
                "industry": self._extract_industry(soup),
                "size": self._extract_company_size(soup),
                "founded": self._extract_founded_year(soup),
                "raw_content": response.text
            }
            
            return company_data
        except Exception as e:
            raise Exception(f"Error crawling company profile: {str(e)}")
    
    def _extract_job_title(self, soup: BeautifulSoup) -> str:
        # Try common job title selectors
        selectors = [
            "h1.job-title",
            "h1.posting-title",
            "h1.position-title",
            ".job-header h1",
            "[data-qa='job-title']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Unknown Position"
    
    def _extract_company(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".company-name",
            ".employer-name",
            "[data-qa='employer']",
            ".posting-company"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Unknown Company"
    
    def _extract_location(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".job-location",
            ".posting-location",
            "[data-qa='location']",
            ".company-location"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Location Not Specified"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".job-description",
            ".posting-description",
            "[data-qa='description']",
            "#job-description"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return ""
    
    def _extract_requirements(self, soup: BeautifulSoup) -> List[str]:
        requirements = []
        selectors = [
            ".job-requirements",
            ".posting-requirements",
            "[data-qa='requirements']",
            "#job-requirements"
        ]
        for selector in selectors:
            elements = soup.select(f"{selector} li")
            if elements:
                requirements = [el.text.strip() for el in elements]
                break
        return requirements or ["No specific requirements listed"]
    
    def _extract_salary(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [
            ".job-salary",
            ".posting-salary",
            "[data-qa='salary']",
            ".compensation"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return None
    
    def _extract_company_name(self, soup: BeautifulSoup) -> str:
        selectors = [
            "h1.company-name",
            ".org-name",
            "[data-qa='company-name']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Unknown Company"
    
    def _extract_company_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".company-description",
            ".org-description",
            "[data-qa='company-description']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return ""
    
    def _extract_industry(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".company-industry",
            ".org-industry",
            "[data-qa='industry']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Industry Not Specified"
    
    def _extract_company_size(self, soup: BeautifulSoup) -> str:
        selectors = [
            ".company-size",
            ".org-size",
            "[data-qa='company-size']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return "Size Not Specified"
    
    def _extract_founded_year(self, soup: BeautifulSoup) -> Optional[int]:
        selectors = [
            ".company-founded",
            ".org-founded",
            "[data-qa='founded-year']"
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                try:
                    return int(element.text.strip())
                except ValueError:
                    pass
        return None 

    async def _search_for_urls(self, search_terms: List[str], max_results: int = 5) -> List[str]:
        """Search for URLs relevant to the search terms using a search API."""
        # In a real implementation, you would integrate with a search API like Google, Bing, etc.
        # For this POC, we'll simulate by generating relevant URLs
        
        # Placeholder for demonstration - in a real system, integrate with actual search API
        urls = []
        
        # Example domain list for simulation
        domains = [
            "levels.fyi", 
            "glassdoor.com",
            "linkedin.com/jobs",
            "indeed.com",
            "monster.com",
            "ziprecruiter.com",
            "dice.com",
            "techcrunch.com",
            "stackoverflow.com",
            "medium.com"
        ]
        
        import random
        
        for term in search_terms:
            # Number of results for this term
            num_results = min(3, max_results - len(urls))
            
            for _ in range(num_results):
                if len(urls) >= max_results:
                    break
                    
                domain = random.choice(domains)
                slug = term.lower().replace(" ", "-")
                url = f"https://www.{domain}/blog/{slug}"
                
                if url not in urls:
                    urls.append(url)
        
        # In a real implementation, you would:
        # 1. Call search API for each search term
        # 2. Extract and normalize URLs from results
        # 3. Filter and deduplicate URLs
        
        return urls[:max_results]
        
    async def crawl_from_query(self, query: str, max_results: int = 5) -> List[dict]:
        """Convert a query into search terms and crawl relevant pages."""
        # Generate search queries from the original query
        search_terms = await self._generate_search_terms(query)
        
        # Perform searches and collect URLs
        urls = await self._search_for_urls(search_terms, max_results=max_results)
        
        # Crawl the collected URLs
        results = []
        for url in urls:
            try:
                result = await self.crawl_job_posting(url)
                results.append(result)
            except Exception as e:
                # Log error but continue with other URLs
                print(f"Error crawling {url}: {str(e)}")
        
        return results
    
    async def _generate_search_terms(self, query: str) -> List[str]:
        """Convert a user query into multiple search terms."""
        # If we have an LLM service, use it to generate better search terms
        if self.llm_service:
            try:
                prompt = f"""Convert the following query into 3-5 specific search terms or phrases that would be good for searching about job market information. 
                Each term should be concise (2-4 words) and focused on a specific aspect of the query.
                Return the search terms as a comma-separated list with no other text.
                
                Query: {query}
                """
                
                search_terms_text = await self.llm_service.generate_text(prompt)
                return [term.strip() for term in search_terms_text.split(",") if term.strip()][:5]
            except Exception as e:
                # Fall back to simpler method if LLM fails
                print(f"Error generating search terms with LLM: {str(e)}")
                
        # Simple fallback approach: extract key noun phrases
        terms = []
        import re
        
        # Remove special characters and tokenize
        cleaned_query = re.sub(r'[^\w\s]', ' ', query)
        words = cleaned_query.lower().split()
        
        # Add the full query
        terms.append(query.strip())
        
        # Extract key phrases based on keywords
        job_keywords = ["job", "position", "career", "salary", "skills"]
        for keyword in job_keywords:
            if keyword in words:
                idx = words.index(keyword)
                # Try to get words around the keyword
                if idx > 0 and idx < len(words) - 1:
                    terms.append(f"{words[idx-1]} {words[idx]} {words[idx+1]}")
                elif idx > 0:
                    terms.append(f"{words[idx-1]} {words[idx]}")
                elif idx < len(words) - 1:
                    terms.append(f"{words[idx]} {words[idx+1]}")
        
        # Remove duplicates and limit number of terms
        return list(dict.fromkeys(terms))[:3]
        
    async def scrape_and_chunk_url(self, url: str) -> List[dict]:
        """Scrape a URL and break content into manageable chunks with metadata."""
        try:
            # Add to visited URLs
            self.visited_urls.add(url)
            
            # Fetch the page
            response = await self.http_client.get(url)
            response.raise_for_status()
            html_content = response.text
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements (nav, ads, etc.)
            for element in soup.select('nav, footer, script, style, [class*="ad"], [class*="sidebar"], [id*="sidebar"]'):
                element.decompose()
            
            # Get the main content
            main_content = soup.select_one('main, article, .content, #content, .post')
            if not main_content:
                main_content = soup.body
            
            # Extract the title
            title = soup.title.string if soup.title else ""
            if not title:
                h1 = soup.find('h1')
                title = h1.text.strip() if h1 else url
            
            # Extract text content
            text_content = main_content.get_text(separator='\n', strip=True) if main_content else soup.get_text(separator='\n', strip=True)
            
            # Chunk the content if we have a text splitter
            chunks = []
            if self.text_splitter and text_content:
                text_chunks = self.text_splitter.split_text(text_content)
                for i, chunk in enumerate(text_chunks):
                    chunks.append({
                        "url": url,
                        "title": title,
                        "chunk_id": i,
                        "content": chunk,
                        "metadata": {
                            "source": url,
                            "chunk_index": i,
                            "total_chunks": len(text_chunks)
                        }
                    })
            else:
                # No text splitter, use the whole content
                chunks.append({
                    "url": url,
                    "title": title,
                    "chunk_id": 0,
                    "content": text_content,
                    "metadata": {
                        "source": url,
                        "chunk_index": 0,
                        "total_chunks": 1
                    }
                })
            
            return chunks
        except Exception as e:
            print(f"Error scraping URL {url}: {str(e)}")
            return []

    async def analyze_job_posting(self, url: str) -> Dict[str, Any]:
        """
        Analyze a job posting URL and extract structured information.
        
        Args:
            url: The URL of the job posting to analyze
            
        Returns:
            Dict containing structured job posting information
        """
        try:
            # Use the existing crawl_job_posting method to get basic data
            job_data = await self.crawl_job_posting(url)
            
            # Extract skills from requirements if LLM service is available
            skills = []
            experience_level = "Not specified"
            
            if self.llm_service and job_data.get('requirements'):
                try:
                    # Use LLM to extract skills from requirements
                    skills_prompt = f"""
                    Extract technical skills and programming languages from the following job requirements:
                    
                    {job_data['requirements']}
                    
                    Return only a comma-separated list of skills, no additional text.
                    """
                    
                    skills_text = await self.llm_service.generate_text_async(
                        prompt=skills_prompt,
                        model="llama_70b",
                        max_tokens=200
                    )
                    
                    if skills_text:
                        skills = [skill.strip() for skill in skills_text.split(',') if skill.strip()]
                    
                    # Determine experience level
                    level_prompt = f"""
                    Based on the following job requirements, determine the experience level:
                    
                    {job_data['requirements']}
                    
                    Return only one of: "Entry Level", "Mid Level", "Senior Level", or "Not specified"
                    """
                    
                    level_text = await self.llm_service.generate_text_async(
                        prompt=level_prompt,
                        model="llama_70b",
                        max_tokens=50
                    )
                    
                    if level_text:
                        experience_level = level_text.strip()
                        
                except Exception as e:
                    print(f"Error extracting skills with LLM: {str(e)}")
                    # Fallback: extract basic skills using regex
                    import re
                    skill_patterns = [
                        r'\b(python|java|javascript|react|angular|vue|node|sql|aws|azure|docker|kubernetes|git|html|css|php|ruby|go|rust|swift|kotlin)\b',
                        r'\b(machine learning|data science|artificial intelligence|deep learning|nlp|computer vision)\b',
                        r'\b(agile|scrum|kanban|devops|ci/cd|microservices|api|rest|graphql)\b'
                    ]
                    
                    requirements_text = job_data.get('requirements', '')
                    for pattern in skill_patterns:
                        matches = re.findall(pattern, requirements_text.lower())
                        skills.extend(matches)
                    
                    # Remove duplicates
                    skills = list(set(skills))
            
            # Build the analysis result
            analysis_result = {
                "title": job_data.get('title', 'Unknown'),
                "company": job_data.get('company', 'Unknown'),
                "location": job_data.get('location', 'Unknown'),
                "skills": skills,
                "experience_level": experience_level,
                "salary": job_data.get('salary', 'Not specified'),
                "description": job_data.get('description', '')[:500] + '...' if len(job_data.get('description', '')) > 500 else job_data.get('description', ''),
                "requirements": job_data.get('requirements', []),
                "url": url,
                "analysis_timestamp": str(datetime.now())
            }
            
            return analysis_result
            
        except Exception as e:
            print(f"Error analyzing job posting {url}: {str(e)}")
            return {
                "title": "Error analyzing job posting",
                "company": "Unknown",
                "location": "Unknown",
                "skills": [],
                "experience_level": "Not specified",
                "salary": "Not specified",
                "description": f"Error: {str(e)}",
                "requirements": [],
                "url": url,
                "analysis_timestamp": str(datetime.now())
            }