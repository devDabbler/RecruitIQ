from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel
from ..utils.database import get_db
from ..services.service_registry import provide_crawler_service
from ..services.crawler_service import CrawlerService

router = APIRouter(prefix="/crawler")

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5
    crawl_type: str = "job"  # "job" or "company"

@router.post("/job-posting")
async def crawl_job_posting(
    url: str, 
    db: Session = Depends(get_db),
    crawler_service: CrawlerService = Depends(provide_crawler_service)
):
    """
    Crawl a job posting URL and extract relevant information.
    """
    try:
        job_data = await crawler_service.crawl_job_posting(url)
        return job_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error crawling job posting: {str(e)}")

@router.post("/company-profile")
async def crawl_company_profile(
    url: str, 
    db: Session = Depends(get_db),
    crawler_service: CrawlerService = Depends(provide_crawler_service)
):
    """
    Crawl a company profile URL and extract relevant information.
    """
    try:
        company_data = await crawler_service.crawl_company_profile(url)
        return company_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error crawling company profile: {str(e)}")

@router.post("/search-and-crawl")
async def search_and_crawl(
    request: SearchRequest,
    db: Session = Depends(get_db),
    crawler_service: CrawlerService = Depends(provide_crawler_service)
):
    """
    Search for relevant content based on a query and crawl the results.
    
    This endpoint leverages crawl4ai to find and extract information from web pages.
    """
    try:
        results = await crawler_service.search_and_crawl(
            query=request.query,
            crawl_type=request.crawl_type,
            max_results=request.max_results
        )
        return {
            "query": request.query,
            "crawl_type": request.crawl_type,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in search and crawl: {str(e)}")

@router.post("/scrape-url")
async def scrape_url(
    url: str,
    db: Session = Depends(get_db),
    crawler_service: CrawlerService = Depends(provide_crawler_service)
):
    """
    Scrape and chunk content from a URL using crawl4ai.
    
    This endpoint returns the content in a format suitable for further LLM processing.
    """
    try:
        results = await crawler_service.scrape_and_chunk_url(url)
        return {
            "url": url,
            "chunks": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping URL: {str(e)}") 