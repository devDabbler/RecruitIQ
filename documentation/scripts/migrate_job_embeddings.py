#!/usr/bin/env python
"""
Script to generate and store embeddings for existing jobs.
This should be run after the database migration that adds embedding columns to the jobs table.
"""
import os
import sys
import asyncio
import logging
from sqlalchemy.orm import Session

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.database import get_db, engine
from backend.models.models import Job
from backend.services.llm_service import LLMService
from backend.services.graph_service import GraphService
from backend.services.job_service import JobService
from backend.utils.config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def migrate_job_embeddings():
    """Generate and store embeddings for all existing jobs."""
    # Initialize services
    settings = Settings()
    llm_service = LLMService(settings)
    graph_service = GraphService(settings)
    job_service = JobService(llm_service, graph_service)
    
    # Create database session
    db = Session(engine)
    
    try:
        # Get all jobs
        jobs = db.query(Job).all()
        logger.info(f"Found {len(jobs)} jobs to migrate")
        
        # Process each job
        for i, job in enumerate(jobs):
            try:
                logger.info(f"Processing job {i+1}/{len(jobs)}: {job.id} - {job.title}")
                
                # Generate and store embeddings
                success = job_service.store_job_embeddings(db, job.id)
                
                if success:
                    logger.info(f"Successfully migrated job {job.id}")
                else:
                    logger.warning(f"Failed to migrate job {job.id}")
                
            except Exception as e:
                logger.error(f"Error migrating job {job.id}: {str(e)}")
                continue
        
        logger.info("Job embedding migration completed")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting job embedding migration")
    asyncio.run(migrate_job_embeddings())
    logger.info("Migration script completed")
