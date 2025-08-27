#!/usr/bin/env python3
"""
Script to clear ALL jobs from PostgreSQL and Neo4j, then repopulate with jobs from PDF files.
This script will:
1. Clear all existing jobs from PostgreSQL and Neo4j
2. Extract job descriptions from the provided PDFs
3. Create new jobs with proper embeddings and graph storage
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Database connections
import psycopg2
from neo4j import GraphDatabase

# PDF processing
try:
    import PyPDF2
except ImportError:
    print("⚠️  PyPDF2 not found. Installing...")
    os.system("pip install PyPDF2")
    import PyPDF2

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent / "backend"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
POSTGRESQL_CONFIG = {
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': int(os.environ.get('PG_PORT', '5432')),
    'database': os.environ.get('PG_DATABASE', 'ats_db'),
    'user': os.environ.get('PG_USER', 'admin'),
    'password': os.environ.get('PG_PASSWORD', 'cadjhosea2024$$')
}

NEO4J_CONFIG = {
    'uri': os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.environ.get('NEO4J_USER', 'neo4j'),
    'password': os.environ.get('NEO4J_PASSWORD', 'cadjhosea2024$$'),
    'database': os.environ.get('NEO4J_DATABASE', 'neo4j')
}

class JobDatabaseManager:
    """Manages job data operations across PostgreSQL and Neo4j"""
    
    def __init__(self):
        self.pg_conn = None
        self.neo4j_driver = None
        self.job_service = None
        self.llm_service = None
        self.graph_service = None
    
    def connect_databases(self) -> bool:
        """Connect to both PostgreSQL and Neo4j databases"""
        # Connect to PostgreSQL
        try:
            self.pg_conn = psycopg2.connect(**POSTGRESQL_CONFIG)
            self.pg_conn.autocommit = False
            logger.info("✓ Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"✗ Failed to connect to PostgreSQL: {str(e)}")
            return False
        
        # Connect to Neo4j
        try:
            self.neo4j_driver = GraphDatabase.driver(
                NEO4J_CONFIG['uri'],
                auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
            )
            # Test connection
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                result = session.run("RETURN 1")
                result.single()
            logger.info("✓ Connected to Neo4j")
        except Exception as e:
            logger.error(f"✗ Failed to connect to Neo4j: {str(e)}")
            return False
        
        # Initialize services
        try:
            from backend.services.job_service import JobService
            from backend.services.llm_service import LLMService
            from backend.services.graph_service import GraphService
            from backend.utils.database import SessionLocal
            from backend.models.models import Job
            
            self.llm_service = LLMService()
            self.graph_service = GraphService()
            self.job_service = JobService(self.llm_service, self.graph_service)
            logger.info("✓ Initialized services")
        except Exception as e:
            logger.error(f"✗ Failed to initialize services: {str(e)}")
            return False
        
        return True
    
    def get_job_counts(self) -> Dict[str, int]:
        """Get current job counts from both databases"""
        counts = {'postgresql_jobs': 0, 'neo4j_job_nodes': 0, 'neo4j_job_relationships': 0}
        
        # PostgreSQL counts
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            counts['postgresql_jobs'] = cursor.fetchone()[0]
            cursor.close()
        except Exception as e:
            logger.error(f"Error getting PostgreSQL job count: {str(e)}")
        
        # Neo4j counts
        try:
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                # Count job nodes
                result = session.run("MATCH (j:Job) RETURN count(j) as count")
                counts['neo4j_job_nodes'] = result.single()["count"]
                
                # Count job relationships
                result = session.run("MATCH (j:Job)-[r]->() RETURN count(r) as count")
                counts['neo4j_job_relationships'] = result.single()["count"]
        except Exception as e:
            logger.error(f"Error getting Neo4j job counts: {str(e)}")
        
        return counts
    
    def clear_all_jobs(self) -> bool:
        """Clear all jobs from both PostgreSQL and Neo4j"""
        logger.info("🗑️  Starting job cleanup...")
        
        # Clear PostgreSQL jobs
        try:
            cursor = self.pg_conn.cursor()
            
            # Delete job-related data in correct order
            cursor.execute("DELETE FROM candidate_pitches WHERE job_id IS NOT NULL")
            pitches_deleted = cursor.rowcount
            logger.info(f"✓ Deleted {pitches_deleted} candidate pitches")
            
            cursor.execute("DELETE FROM jobs")
            jobs_deleted = cursor.rowcount
            logger.info(f"✓ Deleted {jobs_deleted} jobs from PostgreSQL")
            
            self.pg_conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"✗ Failed to clear PostgreSQL jobs: {str(e)}")
            self.pg_conn.rollback()
            return False
        
        # Clear Neo4j jobs
        try:
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                # Delete job relationships first
                result = session.run("MATCH (j:Job)-[r]->() DELETE r RETURN count(r) as deleted")
                rel_deleted = result.single()["deleted"]
                logger.info(f"✓ Deleted {rel_deleted} job relationships from Neo4j")
                
                # Delete job nodes
                result = session.run("MATCH (j:Job) DELETE j RETURN count(j) as deleted")
                job_deleted = result.single()["deleted"]
                logger.info(f"✓ Deleted {job_deleted} job nodes from Neo4j")
        except Exception as e:
            logger.error(f"✗ Failed to clear Neo4j jobs: {str(e)}")
            return False
        
        logger.info("✅ Successfully cleared all jobs from both databases")
        return True
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file"""
        logger.info(f"📄 Extracting text from: {pdf_path}")
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                logger.info(f"✓ Extracted {len(text)} characters from {len(reader.pages)} pages")
                return text.strip()
        except Exception as e:
            logger.error(f"✗ Error extracting text from PDF: {str(e)}")
            return ""
    
    def parse_job_description(self, text: str, filename: str) -> Dict[str, Any]:
        """Parse job description text into structured data"""
        logger.info(f"🔍 Parsing job description from {filename}")
        
        # Basic job parsing logic - can be enhanced with LLM if needed
        job_data = {
            'title': 'Software Engineer',  # Default values
            'department': 'Engineering',
            'location': 'Remote',
            'location_type': 'remote',
            'job_type': 'full_time',
            'experience_level': 'mid_level',
            'status': 'open',
            'job_overview': '',
            'required_qualifications': '',
            'skills': []
        }
        
        # Extract title based on filename
        if 'software_development' in filename.lower():
            job_data.update({
                'title': 'Software Development Engineer',
                'department': 'Engineering',
                'experience_level': 'senior_level',
                'skills': ['Python', 'Java', 'AWS', 'Docker', 'Kubernetes', 'REST APIs', 'Microservices']
            })
        elif 'data_scientist' in filename.lower():
            job_data.update({
                'title': 'Data Scientist',
                'department': 'Data Science',
                'experience_level': 'mid_level',
                'skills': ['Python', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn']
            })
        
        # Use the first 500 characters as job overview
        if len(text) > 100:
            job_data['job_overview'] = text[:500] + "..." if len(text) > 500 else text
            job_data['required_qualifications'] = text[500:1000] + "..." if len(text) > 1000 else text[500:]
        else:
            job_data['job_overview'] = text
        
        logger.info(f"✓ Parsed job: {job_data['title']}")
        return job_data
    
    async def create_job_with_embeddings(self, job_data: Dict[str, Any]) -> Optional[int]:
        """Create a job in PostgreSQL with embeddings and Neo4j storage"""
        logger.info(f"💼 Creating job: {job_data['title']}")
        
        try:
            from backend.utils.database import SessionLocal
            from backend.models.models import Job
            
            # Use SQLAlchemy session
            db = SessionLocal()
            
            # Convert skills list to comma-separated string for DB
            skills_str = ",".join(job_data.get('skills', [])) if job_data.get('skills') else None
            job_data_copy = job_data.copy()
            job_data_copy['skills'] = skills_str
            
            # Create job in database
            db_job = Job(**job_data_copy)
            db.add(db_job)
            db.commit()
            db.refresh(db_job)
            
            logger.info(f"✓ Created job {db_job.id} in PostgreSQL")
            
            # Generate and store embeddings
            try:
                success = self.job_service.store_job_embeddings(db, db_job.id)
                if success:
                    logger.info(f"✓ Generated and stored embeddings for job {db_job.id}")
                else:
                    logger.warning(f"⚠️  Failed to generate embeddings for job {db_job.id}")
            except Exception as e:
                logger.error(f"✗ Error generating embeddings: {str(e)}")
            
            db.close()
            return db_job.id
            
        except Exception as e:
            logger.error(f"✗ Error creating job: {str(e)}")
            if 'db' in locals():
                db.close()
            return None
    
    def close_connections(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("✓ Closed PostgreSQL connection")
        
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("✓ Closed Neo4j connection")

async def main():
    """Main function to orchestrate the job clearing and population"""
    logger.info("🚀 Starting job database refresh...")
    
    # PDF files to process
    pdf_files = [
        "software_development_engineer.pdf",
        "data_scientist_job_description.pdf"
    ]
    
    # Check if PDF files exist
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            logger.error(f"✗ PDF file not found: {pdf_file}")
            return
    
    # Initialize database manager
    manager = JobDatabaseManager()
    
    try:
        # Connect to databases
        if not manager.connect_databases():
            logger.error("✗ Failed to connect to databases")
            return
        
        # Show current counts
        initial_counts = manager.get_job_counts()
        logger.info(f"📊 Current job counts: PostgreSQL={initial_counts['postgresql_jobs']}, "
                   f"Neo4j nodes={initial_counts['neo4j_job_nodes']}, "
                   f"Neo4j relationships={initial_counts['neo4j_job_relationships']}")
        
        # Ask for confirmation
        response = input(f"\n⚠️  This will DELETE ALL {initial_counts['postgresql_jobs']} jobs. Continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("❌ Operation cancelled by user")
            return
        
        # Clear existing jobs
        if not manager.clear_all_jobs():
            logger.error("✗ Failed to clear existing jobs")
            return
        
        # Process each PDF and create jobs
        created_jobs = []
        for pdf_file in pdf_files:
            logger.info(f"\n📋 Processing {pdf_file}...")
            
            # Extract text from PDF
            text = manager.extract_text_from_pdf(pdf_file)
            if not text:
                logger.error(f"✗ Failed to extract text from {pdf_file}")
                continue
            
            # Parse job description
            job_data = manager.parse_job_description(text, pdf_file)
            
            # Create job with embeddings
            job_id = await manager.create_job_with_embeddings(job_data)
            if job_id:
                created_jobs.append((job_id, job_data['title']))
                logger.info(f"✅ Successfully created job {job_id}: {job_data['title']}")
            else:
                logger.error(f"✗ Failed to create job from {pdf_file}")
        
        # Show final results
        final_counts = manager.get_job_counts()
        logger.info(f"\n📊 Final job counts: PostgreSQL={final_counts['postgresql_jobs']}, "
                   f"Neo4j nodes={final_counts['neo4j_job_nodes']}, "
                   f"Neo4j relationships={final_counts['neo4j_job_relationships']}")
        
        logger.info(f"\n🎉 Successfully created {len(created_jobs)} jobs:")
        for job_id, title in created_jobs:
            logger.info(f"   • Job {job_id}: {title}")
        
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
    finally:
        manager.close_connections()

if __name__ == "__main__":
    asyncio.run(main()) 