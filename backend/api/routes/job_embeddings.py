"""
API routes for job embedding generation.
"""

import os
import sys
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.scripts.generate_job_embeddings import generate_job_embeddings
from backend.scripts.sync_jobs_to_neo4j import JobSync

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("job_embeddings_api")

router = APIRouter()

class JobEmbeddingRequest(BaseModel):
    force_update: bool = False
    job_ids: Optional[List[int]] = None

@router.post("/api/jobs/generate-embeddings")
async def generate_embeddings(
    request: JobEmbeddingRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate embeddings for jobs and store them in Neo4j.
    
    If job_ids is provided, only generate embeddings for those jobs.
    If force_update is True, regenerate embeddings even if they already exist.
    
    Args:
        request: JobEmbeddingRequest with optional force_update and job_ids
        background_tasks: FastAPI background tasks
        
    Returns:
        Status message
    """
    try:
        # Run in background to avoid blocking the API
        def run_embedding_generation():
            try:
                job_ids = request.job_ids if request.job_ids else None
                force_update = request.force_update
                
                logger.info(f"Starting job embedding generation with force_update={force_update}, job_ids={job_ids}")
                result = generate_job_embeddings(force_update=force_update, job_ids=job_ids)
                logger.info(f"Job embedding generation complete: {result}")
            except Exception as e:
                logger.error(f"Error in background job embedding generation: {e}", exc_info=True)
        
        background_tasks.add_task(run_embedding_generation)
        
        return {
            "status": "success",
            "message": "Job embedding generation started in background"
        }
    except Exception as e:
        logger.error(f"Error initiating job embedding generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start job embedding generation: {str(e)}"
        )

@router.post("/api/jobs/sync-and-generate-embeddings")
async def sync_and_generate_embeddings(
    request: JobEmbeddingRequest,
    background_tasks: BackgroundTasks
):
    """
    Sync jobs from PostgreSQL to Neo4j and generate embeddings.
    
    This is a complete solution that:
    1. Syncs jobs from PostgreSQL to Neo4j
    2. Ensures vector indexes exist with correct dimensions
    3. Generates embeddings for all jobs
    
    Args:
        request: JobEmbeddingRequest with optional force_update and job_ids
        background_tasks: FastAPI background tasks
        
    Returns:
        Status message
    """
    try:
        # Run in background to avoid blocking the API
        def run_sync_and_embedding():
            try:
                job_ids = request.job_ids if request.job_ids else None
                force_update = request.force_update
                
                # Step 1: Initialize JobSync and ensure Neo4j indexes
                logger.info("Initializing JobSync and ensuring Neo4j indexes")
                job_sync = JobSync()
                job_sync.ensure_neo4j_indexes()
                
                # Step 2: Sync jobs from PostgreSQL to Neo4j
                logger.info(f"Syncing jobs from PostgreSQL to Neo4j with job_ids={job_ids}")
                if job_ids:
                    # Get jobs from PostgreSQL
                    postgres_jobs = []
                    db = job_sync.SessionLocal()
                    try:
                        for job_id in job_ids:
                            job = db.query(job_sync.Job).filter(job_sync.Job.id == job_id).first()
                            if job:
                                job_dict = {
                                    "id": job.id,
                                    "title": job.title,
                                    "department": job.department,
                                    "job_overview": job.job_overview,
                                    "required_qualifications": job.required_qualifications,
                                    "location": job.location,
                                    "job_type": job.job_type,
                                    "experience_level": job.experience_level,
                                    "status": job.status,
                                }
                                
                                # Extract skills
                                if job.skills and isinstance(job.skills, str):
                                    job_dict["skills"] = [skill.strip() for skill in job.skills.split(",") if skill.strip()]
                                else:
                                    job_dict["skills"] = []
                                
                                postgres_jobs.append(job_dict)
                    finally:
                        db.close()
                    
                    # Sync each job to Neo4j
                    for job in postgres_jobs:
                        job_sync.sync_job_to_neo4j(job)
                else:
                    # Sync all active jobs
                    job_sync.sync_all_jobs(active_only=True)
                
                # Step 3: Generate embeddings using the script
                logger.info(f"Generating embeddings for jobs with force_update={force_update}")
                result = generate_job_embeddings(force_update=force_update, job_ids=job_ids)
                
                # Close connections
                job_sync.close()
                
                logger.info(f"Job sync and embedding generation complete: {result}")
                return result
            except Exception as e:
                logger.error(f"Error in background job sync and embedding generation: {e}", exc_info=True)
                return {"error": str(e)}
        
        background_tasks.add_task(run_sync_and_embedding)
        
        return {
            "status": "success",
            "message": "Job sync and embedding generation started in background"
        }
    except Exception as e:
        logger.error(f"Error initiating job sync and embedding generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start job sync and embedding generation: {str(e)}"
        )

@router.get("/api/jobs/verify-neo4j-setup")
async def verify_neo4j_setup():
    """
    Verify Neo4j setup for job analysis.
    
    Checks:
    1. Neo4j connection
    2. Vector indexes existence and dimensions
    3. Job counts in Neo4j
    4. Jobs with embeddings
    
    Returns:
        Status information
    """
    try:
        job_sync = JobSync()
        try:
            verification = job_sync.verify_job_sync()
            return {
                "status": "success",
                "message": "Neo4j setup verification complete",
                "details": verification
            }
        finally:
            job_sync.close()
    except Exception as e:
        logger.error(f"Error verifying Neo4j setup: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify Neo4j setup: {str(e)}"
        )
