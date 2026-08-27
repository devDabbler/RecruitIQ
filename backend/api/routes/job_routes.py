"""
Job-related API routes.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.utils.database import get_db
from backend.models.models import Job
from backend.services.job_service import JobService
# Neo4j sync removed - backend.scripts deleted in Phase 1a (Task 6)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("job_routes")

router = APIRouter()

@router.get("/api/jobs")
async def get_jobs(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """
    Get all jobs, optionally filtered by status.
    
    Args:
        status: Optional filter for job status (e.g., 'active', 'open')
        page: Page number (1-based)
        page_size: Number of items per page (max 100)
        sort_by: Field to sort by
        sort_order: Sort order ('asc' or 'desc')
        
    Returns:
        List of jobs with pagination info
    """
    # Validate page_size
    page_size = min(max(1, page_size), 100)  # Ensure page_size is between 1 and 100
    
    # Get database session
    db = next(get_db())
    try:
        # Build base query
        query = db.query(Job)
        
        # Apply status filter if provided
        if status:
            query = query.filter(Job.status == status)
        
        # Apply sorting
        if hasattr(Job, sort_by):
            sort_field = getattr(Job, sort_by)
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        
        # Apply pagination
        total_items = query.count()
        total_pages = (total_items + page_size - 1) // page_size
        offset = (page - 1) * page_size
        jobs = query.offset(offset).limit(page_size).all()
        
        # Convert to dictionary format
        job_list = []
        for job in jobs:
            try:
                job_dict = {
                    "id": job.id,
                    "title": job.title,
                    "department": job.department,
                    "job_overview": job.job_overview,
                    "required_qualifications": job.required_qualifications,
                    "location": job.location,
                    "location_type": job.location_type,
                    "job_type": job.job_type,
                    "experience_level": job.experience_level,
                    "status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None
                }
                
                # Handle skills (comma-separated string to list)
                if job.skills and isinstance(job.skills, str):
                    job_dict["skills"] = [skill.strip() for skill in job.skills.split(",") if skill.strip()]
                else:
                    job_dict["skills"] = []
                
                job_list.append(job_dict)
            except Exception as e:
                logger.error(f"Error processing job {job.id}: {str(e)}")
                continue
        
        # Return paginated response
        return {
            "results": job_list,
            "total": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
        
    except Exception as e:
        logger.error(f"Error fetching jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching jobs: {str(e)}"
        )
    finally:
        db.close()


@router.post("/api/jobs/sync-to-neo4j")
def sync_jobs_to_neo4j():
    """Neo4j sync endpoint removed in Phase 1a - Neo4j store is out of scope."""
    raise HTTPException(
        status_code=410,
        detail="Neo4j sync has been removed. Job search now uses PostgreSQL + pgvector."
    )
