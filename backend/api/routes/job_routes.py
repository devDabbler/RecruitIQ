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
from backend.scripts.sync_jobs_to_neo4j import JobSync

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
def sync_jobs_to_neo4j(
    request_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Synchronize specific jobs or all jobs from PostgreSQL ATS to Neo4j.
    
    Args:
        request_data: JSON with job_ids (optional)
        db: Database session
        background_tasks: FastAPI background tasks
        
    Returns:
        Status of the sync operation
    """
    job_ids = request_data.get("job_ids", [])
    
    try:
        # Initialize the JobSync class
        job_sync = JobSync()
        
        # If specific job IDs are provided, sync only those
        if job_ids:
            logger.info(f"Syncing specific jobs: {job_ids}")
            jobs_to_sync = []
            
            for job_id in job_ids:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    # Convert SQLAlchemy object to dictionary
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
                    
                    # Extract skills (comma-separated string to list)
                    if job.skills and isinstance(job.skills, str):
                        job_dict["skills"] = [skill.strip() for skill in job.skills.split(",") if skill.strip()]
                    else:
                        job_dict["skills"] = []
                    
                    jobs_to_sync.append(job_dict)
            
            # Ensure Neo4j indexes exist
            job_sync.ensure_neo4j_indexes()
            
            # Sync each job
            results = {"synced": [], "failed": []}
            for job in jobs_to_sync:
                success = job_sync.sync_job_to_neo4j(job)
                if success:
                    results["synced"].append(job["id"])
                else:
                    results["failed"].append(job["id"])
            
            job_sync.close()
            return {
                "status": "success",
                "message": f"Synced {len(results['synced'])} jobs, failed {len(results['failed'])} jobs",
                "details": results
            }
        else:
            # For syncing all jobs, run in background to not block the API
            def sync_all_jobs_background():
                try:
                    counts = job_sync.sync_all_jobs(active_only=True)
                    job_sync.close()
                    logger.info(f"Background job sync complete: {counts}")
                except Exception as e:
                    logger.error(f"Background job sync failed: {e}")
            
            # If background_tasks is available, use it
            if background_tasks:
                background_tasks.add_task(sync_all_jobs_background)
                return {
                    "status": "success", 
                    "message": "Job sync started in background"
                }
            else:
                # Otherwise run immediately (but this will block)
                counts = job_sync.sync_all_jobs(active_only=True)
                job_sync.close()
                return {
                    "status": "success",
                    "message": f"Synced all active jobs",
                    "details": counts
                }
            
    except Exception as e:
        logger.error(f"Error syncing jobs to Neo4j: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to sync jobs to Neo4j: {str(e)}"
        )
