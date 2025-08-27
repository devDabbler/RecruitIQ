# backend/services/ats_service.py
import asyncio
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Union

import httpx
from pydantic import BaseModel, Field

from backend.utils.config import Settings


logger = logging.getLogger(__name__)


class ATSProvider(str, Enum):
    """Supported ATS providers."""
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    CUSTOM = "custom"


class ATSConfig(BaseModel):
    """Configuration for an ATS integration."""
    provider: ATSProvider
    api_key: str
    base_url: str
    org_id: Optional[str] = None
    additional_headers: Dict[str, str] = Field(default_factory=dict)
    webhook_config: Optional[Dict[str, Any]] = None


class ATSIntegrationStatus(BaseModel):
    """Status of an ATS integration."""
    provider: ATSProvider
    status: str
    connected: bool
    last_sync: Optional[str] = None
    error_message: Optional[str] = None


class ATSService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http_client = httpx.AsyncClient(timeout=60.0)
        
        # Track configurations for each provider
        self.configurations: Dict[ATSProvider, ATSConfig] = {}
        
        # Track system mappings (field mappings between systems)
        self.field_mappings: Dict[ATSProvider, Dict[str, str]] = {}
        
        # Cache for rate limiting and efficiency
        self.cache_ttl = 300  # 5 minutes
        self.cache = {}
    
    async def close(self):
        """Close the HTTP client when service is shut down."""
        await self.http_client.aclose()
    
    async def configure_integration(self, config: ATSConfig) -> ATSIntegrationStatus:
        """Configure an ATS integration."""
        # Store the configuration
        self.configurations[config.provider] = config
        
        # Test the connection
        status = await self.test_connection(config.provider)
        
        # Initialize field mappings if needed
        if config.provider not in self.field_mappings:
            self.field_mappings[config.provider] = self._get_default_mappings(config.provider)
        
        return status
    
    def _get_default_mappings(self, provider: ATSProvider) -> Dict[str, str]:
        """Get default field mappings for a provider."""
        # These would be the default field mappings between our system and the ATS
        if provider == ATSProvider.GREENHOUSE:
            return {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email",
                "phone": "phone",
                "current_company": "current_company",
                "current_title": "current_title",
                "location": "location",
                "education": "education",
                "resume": "resume",
                "cover_letter": "cover_letter",
                "source": "source",
                "job_id": "job_id",
                "status": "status",
            }
        elif provider == ATSProvider.LEVER:
            return {
                "first_name": "name_given",
                "last_name": "name_family",
                "email": "email_address",
                "phone": "phone_number",
                "current_company": "company",
                "current_title": "position",
                "location": "location",
                "education": "education",
                "resume": "resume",
                "cover_letter": "cover_letter",
                "source": "source",
                "job_id": "posting_id",
                "status": "stage",
            }
        elif provider == ATSProvider.WORKDAY:
            return {
                "first_name": "firstName",
                "last_name": "lastName",
                "email": "emailAddress",
                "phone": "phoneNumber",
                "current_company": "currentEmployer",
                "current_title": "currentPosition",
                "location": "address",
                "education": "educationHistory",
                "resume": "resumeDocument",
                "cover_letter": "coverLetterDocument",
                "source": "source",
                "job_id": "jobRequisitionId",
                "status": "applicationStatus",
            }
        else:
            # Generic mappings for custom ATS
            return {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email",
                "phone": "phone",
                "current_company": "company",
                "current_title": "title",
                "location": "location",
                "education": "education",
                "resume": "resume",
                "cover_letter": "cover_letter",
                "source": "source",
                "job_id": "job_id",
                "status": "status",
            }
    
    async def test_connection(self, provider: ATSProvider) -> ATSIntegrationStatus:
        """Test the connection to an ATS provider."""
        if provider not in self.configurations:
            return ATSIntegrationStatus(
                provider=provider,
                status="Not configured",
                connected=False,
                error_message="Integration not configured",
            )
        
        config = self.configurations[provider]
        
        try:
            # Construct appropriate test endpoint based on provider
            if provider == ATSProvider.GREENHOUSE:
                url = f"{config.base_url}/v1/users/me"
                headers = self._get_headers(provider)
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                return ATSIntegrationStatus(
                    provider=provider,
                    status="Connected",
                    connected=True,
                    last_sync=None,
                )
                
            elif provider == ATSProvider.LEVER:
                url = f"{config.base_url}/opportunities"
                headers = self._get_headers(provider)
                params = {"limit": 1}
                
                response = await self.http_client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                return ATSIntegrationStatus(
                    provider=provider,
                    status="Connected",
                    connected=True,
                    last_sync=None,
                )
                
            elif provider == ATSProvider.WORKDAY:
                # Workday typically requires SOAP/XML or specific REST endpoints
                url = f"{config.base_url}/organizations/{config.org_id}"
                headers = self._get_headers(provider)
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                return ATSIntegrationStatus(
                    provider=provider,
                    status="Connected",
                    connected=True,
                    last_sync=None,
                )
                
            else:
                # Generic test for custom provider
                url = config.base_url
                headers = self._get_headers(provider)
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                return ATSIntegrationStatus(
                    provider=provider,
                    status="Connected",
                    connected=True,
                    last_sync=None,
                )
                
        except httpx.HTTPStatusError as e:
            return ATSIntegrationStatus(
                provider=provider,
                status="Connection Error",
                connected=False,
                error_message=f"HTTP error: {e.response.status_code} - {e.response.reason_phrase}",
            )
        except httpx.RequestError as e:
            return ATSIntegrationStatus(
                provider=provider,
                status="Connection Error",
                connected=False,
                error_message=f"Request error: {str(e)}",
            )
        except Exception as e:
            return ATSIntegrationStatus(
                provider=provider,
                status="Unknown Error",
                connected=False,
                error_message=str(e),
            )
    
    def _get_headers(self, provider: ATSProvider) -> Dict[str, str]:
        """Get headers for API requests to a provider."""
        if provider not in self.configurations:
            return {}
        
        config = self.configurations[provider]
        headers = {}
        
        if provider == ATSProvider.GREENHOUSE:
            headers["Authorization"] = f"Basic {config.api_key}"
        elif provider == ATSProvider.LEVER:
            headers["Authorization"] = f"Bearer {config.api_key}"
        elif provider == ATSProvider.WORKDAY:
            headers["Authorization"] = f"Bearer {config.api_key}"
            headers["Content-Type"] = "application/json"
        else:
            # For custom provider, use API key in header
            headers["Authorization"] = f"Bearer {config.api_key}"
            headers["Content-Type"] = "application/json"
        
        # Add any additional headers from config
        headers.update(config.additional_headers)
        
        return headers
    
    async def sync_jobs(self, provider: ATSProvider) -> List[Dict[str, Any]]:
        """Sync job listings from the ATS."""
        if provider not in self.configurations:
            raise ValueError(f"Provider {provider} not configured")
        
        config = self.configurations[provider]
        headers = self._get_headers(provider)
        
        # Check cache first
        cache_key = f"jobs_{provider}"
        cached = self.cache.get(cache_key)
        if cached and cached["timestamp"] + self.cache_ttl > asyncio.get_event_loop().time():
            return cached["data"]
        
        try:
            # Fetch jobs based on provider
            if provider == ATSProvider.GREENHOUSE:
                url = f"{config.base_url}/v1/jobs"
                params = {"status": "open"}
                
                response = await self.http_client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                jobs_data = response.json()
                transformed_jobs = self._transform_jobs(jobs_data, provider)
                
            elif provider == ATSProvider.LEVER:
                url = f"{config.base_url}/postings"
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                jobs_data = response.json()
                transformed_jobs = self._transform_jobs(jobs_data, provider)
                
            elif provider == ATSProvider.WORKDAY:
                url = f"{config.base_url}/jobRequisitions"
                params = {"status": "Open"}
                
                response = await self.http_client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                jobs_data = response.json()
                transformed_jobs = self._transform_jobs(jobs_data, provider)
                
            else:
                # Generic implementation for custom provider
                url = f"{config.base_url}/jobs"
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                jobs_data = response.json()
                transformed_jobs = self._transform_jobs(jobs_data, provider)
            
            # Update cache
            self.cache[cache_key] = {
                "timestamp": asyncio.get_event_loop().time(),
                "data": transformed_jobs,
            }
            
            return transformed_jobs
            
        except Exception as e:
            logger.exception(f"Error syncing jobs from {provider}: {str(e)}")
            raise
    
    def _transform_jobs(self, jobs_data: Any, provider: ATSProvider) -> List[Dict[str, Any]]:
        """Transform job data from ATS format to our platform's format."""
        transformed_jobs = []
        
        if provider == ATSProvider.GREENHOUSE:
            for job in jobs_data:
                transformed_job = {
                    "id": str(job.get("id")),
                    "title": job.get("title"),
                    "location": job.get("location", {}).get("name"),
                    "department": job.get("department", {}).get("name"),
                    "status": job.get("status"),
                    "created_at": job.get("created_at"),
                    "updated_at": job.get("updated_at"),
                    "external_url": job.get("absolute_url"),
                    "description": job.get("content"),
                    "metadata": {
                        "greenhouse_id": job.get("id"),
                        "external_id": job.get("external_id"),
                        "confidential": job.get("confidential"),
                        "job_post_id": job.get("job_post_id"),
                    },
                }
                transformed_jobs.append(transformed_job)
                
        elif provider == ATSProvider.LEVER:
            for job in jobs_data:
                transformed_job = {
                    "id": job.get("id"),
                    "title": job.get("text"),
                    "location": job.get("categories", {}).get("location"),
                    "department": job.get("categories", {}).get("department"),
                    "status": "open",  # Lever typically returns only open jobs
                    "created_at": job.get("createdAt"),
                    "updated_at": job.get("updatedAt"),
                    "external_url": job.get("hostedUrl"),
                    "description": job.get("description"),
                    "metadata": {
                        "lever_id": job.get("id"),
                        "team": job.get("categories", {}).get("team"),
                        "commitment": job.get("categories", {}).get("commitment"),
                    },
                }
                transformed_jobs.append(transformed_job)
                
        elif provider == ATSProvider.WORKDAY:
            for job in jobs_data:
                transformed_job = {
                    "id": job.get("id"),
                    "title": job.get("title"),
                    "location": job.get("locationName"),
                    "department": job.get("departmentName"),
                    "status": job.get("status"),
                    "created_at": job.get("createdTimestamp"),
                    "updated_at": job.get("modifiedTimestamp"),
                    "external_url": job.get("externalUrl"),
                    "description": job.get("description"),
                    "metadata": {
                        "workday_id": job.get("id"),
                        "requisition_id": job.get("requisitionId"),
                        "job_family": job.get("jobFamilyName"),
                    },
                }
                transformed_jobs.append(transformed_job)
                
        else:
            # Generic transformation for custom provider
            if isinstance(jobs_data, list):
                for job in jobs_data:
                    transformed_job = {
                        "id": job.get("id", ""),
                        "title": job.get("title", ""),
                        "location": job.get("location", ""),
                        "department": job.get("department", ""),
                        "status": job.get("status", ""),
                        "created_at": job.get("created_at", ""),
                        "updated_at": job.get("updated_at", ""),
                        "external_url": job.get("url", ""),
                        "description": job.get("description", ""),
                        "metadata": {
                            "external_id": job.get("external_id", ""),
                        },
                    }
                    transformed_jobs.append(transformed_job)
        
        return transformed_jobs