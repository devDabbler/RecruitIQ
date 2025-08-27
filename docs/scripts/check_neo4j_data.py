import sys
import os
import logging
from pathlib import Path

# Add the parent directory to sys.path to allow imports
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.services.graph_service import get_graph_service
from backend.utils.config import get_settings

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_job_skills():
    """Check if jobs have skills associated in Neo4j"""
    settings = get_settings()
    graph_service = get_graph_service()
    
    if not graph_service or not graph_service.driver:
        logger.error("Could not connect to Neo4j database")
        return
    
    logger.info("Connected to Neo4j, checking job data...")
    
    try:
        # Query to check all jobs and their skills
        with graph_service.driver.session(database=graph_service.database) as session:
            # Get all jobs
            jobs_result = session.run("""
                MATCH (j:Job) 
                RETURN j.id as job_id, j.title as job_title
            """)
            
            jobs = list(jobs_result)
            if not jobs:
                logger.warning("No jobs found in Neo4j database")
                return
                
            logger.info(f"Found {len(jobs)} jobs in Neo4j")
            
            # Check if jobs have skills
            for job in jobs:
                job_id = job["job_id"]
                job_title = job["job_title"]
                
                # Check for skills
                skills_result = session.run("""
                    MATCH (j:Job {id: $job_id})-[:HAS_SKILL]->(s:Skill)
                    RETURN s.name as skill_name
                """, job_id=job_id)
                
                skills = list(skills_result)
                if not skills:
                    logger.warning(f"Job ID {job_id} ({job_title}) has NO skills in Neo4j")
                else:
                    skill_names = [skill["skill_name"] for skill in skills]
                    logger.info(f"Job ID {job_id} ({job_title}) has {len(skill_names)} skills: {', '.join(skill_names)}")
            
            # Also check if skills exist independently 
            skills_result = session.run("""
                MATCH (s:Skill)
                RETURN count(s) as skill_count
            """)
            
            skill_count = skills_result.single()["skill_count"]
            logger.info(f"Total number of skill nodes in Neo4j: {skill_count}")

            # Check HAS_SKILL relationships
            relationships_result = session.run("""
                MATCH ()-[r:HAS_SKILL]->()
                RETURN count(r) as rel_count
            """)
            
            rel_count = relationships_result.single()["rel_count"]
            logger.info(f"Total number of HAS_SKILL relationships in Neo4j: {rel_count}")
            
    except Exception as e:
        logger.error(f"Error checking Neo4j: {str(e)}")
            
if __name__ == "__main__":
    check_job_skills()
