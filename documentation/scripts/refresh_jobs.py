#!/usr/bin/env python3
"""
Job Database Refresh Script
Clears all existing jobs and creates new ones from PDF job descriptions
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Optional

# Database connections
import psycopg2
import psycopg2.errors
from neo4j import GraphDatabase

# PDF processing
try:
    import PyPDF2
except ImportError:
    print("Installing PyPDF2...")
    os.system("pip install PyPDF2")
    import PyPDF2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000"
POSTGRESQL_CONFIG = {
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': int(os.environ.get('PG_PORT', '5432')),
    'database': os.environ.get('PG_DATABASE', 'ats_db'),
    'user': os.environ.get('PG_USER', 'admin'),
    'password': os.environ.get('PG_PASSWORD', '')
}

NEO4J_CONFIG = {
    'uri': os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.environ.get('NEO4J_USER', 'neo4j'),
    'password': os.environ.get('NEO4J_PASSWORD', ''),
    'database': os.environ.get('NEO4J_DATABASE', 'neo4j')
}

class JobRefreshManager:
    def __init__(self):
        self.pg_conn = None
        self.neo4j_driver = None
    
    def connect_databases(self) -> bool:
        """Connect to PostgreSQL and Neo4j"""
        try:
            self.pg_conn = psycopg2.connect(**POSTGRESQL_CONFIG)
            self.pg_conn.autocommit = False
            logger.info("✓ Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"✗ PostgreSQL connection failed: {str(e)}")
            return False
        
        try:
            self.neo4j_driver = GraphDatabase.driver(
                NEO4J_CONFIG['uri'],
                auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
            )
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                result = session.run("RETURN 1")
                result.single()
            logger.info("✓ Connected to Neo4j")
        except Exception as e:
            logger.error(f"✗ Neo4j connection failed: {str(e)}")
            return False
        
        return True
    
    def check_api_status(self) -> bool:
        """Check if backend API is running"""
        try:
            response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
            if response.status_code == 200:
                logger.info("✓ Backend API is running")
                return True
        except:
            pass
        
        logger.error("✗ Backend API not accessible")
        logger.info("💡 Start the backend: cd backend && python -m uvicorn main:app --reload --port 8000")
        return False
    
    def get_job_counts(self) -> Dict[str, int]:
        """Get current job counts"""
        counts = {'postgresql_jobs': 0, 'neo4j_job_nodes': 0}
        
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            counts['postgresql_jobs'] = cursor.fetchone()[0]
            cursor.close()
        except Exception as e:
            logger.error(f"Error getting PostgreSQL count: {str(e)}")
        
        try:
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                result = session.run("MATCH (j:Job) RETURN count(j) as count")
                counts['neo4j_job_nodes'] = result.single()["count"]
        except Exception as e:
            logger.error(f"Error getting Neo4j count: {str(e)}")
        
        return counts
    
    def clear_all_jobs(self) -> bool:
        """Clear all jobs from both databases"""
        logger.info("🗑️ Clearing all jobs...")
        
        # Clear PostgreSQL
        try:
            cursor = self.pg_conn.cursor()
            
            # Try to delete from candidate_pitches if it exists
            pitches_deleted = 0
            try:
                cursor.execute("DELETE FROM candidate_pitches WHERE job_id IS NOT NULL")
                pitches_deleted = cursor.rowcount
                logger.info(f"✓ Deleted {pitches_deleted} candidate pitches")
            except psycopg2.errors.UndefinedTable:
                logger.info("- Table candidate_pitches doesn't exist, skipping...")
                self.pg_conn.rollback()  # Reset transaction after error
            
            # Delete jobs
            cursor.execute("DELETE FROM jobs")
            jobs_deleted = cursor.rowcount
            logger.info(f"✓ Deleted {jobs_deleted} jobs from PostgreSQL")
            
            self.pg_conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"✗ PostgreSQL cleanup failed: {str(e)}")
            self.pg_conn.rollback()
            return False
        
        # Clear Neo4j
        try:
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                result = session.run("MATCH (j:Job)-[r]->() DELETE r RETURN count(r) as deleted")
                rel_deleted = result.single()["deleted"]
                result = session.run("MATCH (j:Job) DELETE j RETURN count(j) as deleted")
                job_deleted = result.single()["deleted"]
                logger.info(f"✓ Deleted {job_deleted} job nodes and {rel_deleted} relationships from Neo4j")
        except Exception as e:
            logger.error(f"✗ Neo4j cleanup failed: {str(e)}")
            return False
        
        return True
    
    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        logger.info(f"📄 Extracting text from {pdf_path}")
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                logger.info(f"✓ Extracted {len(text)} characters")
                return text.strip()
        except Exception as e:
            logger.error(f"✗ PDF extraction failed: {str(e)}")
            return ""
    
    def create_job_data(self, text: str, filename: str) -> Dict[str, Any]:
        """Create job data structure from PDF content"""
        if 'software_development' in filename.lower():
            return {
                'title': 'Software Development Engineer',
                'department': 'Engineering',
                'location': 'Seattle, WA',
                'location_type': 'hybrid',
                'job_type': 'full_time',
                'experience_level': 'senior',
                'status': 'open',
                'job_overview': 'We are seeking a highly skilled Software Development Engineer to join our dynamic engineering team. You will be responsible for designing, developing, and maintaining scalable software solutions that serve millions of users worldwide.',
                'required_qualifications': 'Bachelor\'s degree in Computer Science or related field. 5+ years of experience in software development. Strong proficiency in Python, Java, and modern web technologies. Experience with cloud platforms (AWS preferred).',
                'skills': ['Python', 'Java', 'JavaScript', 'AWS', 'Docker', 'Kubernetes', 'REST APIs', 'Microservices', 'SQL', 'Git'],
                'min_salary': 120000,
                'max_salary': 200000
            }
        elif 'data_scientist' in filename.lower():
            return {
                'title': 'Data Scientist',
                'department': 'Data Science',
                'location': 'New York, NY',
                'location_type': 'hybrid',
                'job_type': 'full_time',
                'experience_level': 'mid',
                'status': 'open',
                'job_overview': 'Join our data science team to extract insights from complex datasets and build predictive models that drive business decisions. You will work with cross-functional teams to identify opportunities.',
                'required_qualifications': 'Master\'s degree in Data Science, Statistics, Mathematics, or related field. 3+ years of experience in data analysis and machine learning. Proficiency in Python or R.',
                'skills': ['Python', 'R', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn', 'TensorFlow', 'Tableau'],
                'min_salary': 90000,
                'max_salary': 160000
            }
        else:
            return {
                'title': 'General Position',
                'department': 'General',
                'location': 'Remote',
                'location_type': 'remote',
                'job_type': 'full_time',
                'experience_level': 'mid',
                'status': 'open',
                'job_overview': 'Extracted from PDF content.',
                'required_qualifications': 'See job description for details.',
                'skills': ['Communication', 'Teamwork'],
                'min_salary': 70000,
                'max_salary': 120000
            }
    
    def create_job_via_api(self, job_data: Dict[str, Any]) -> Optional[int]:
        """Create job using REST API"""
        logger.info(f"💼 Creating job: {job_data['title']}")
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/jobs/",
                json=job_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 201:
                job_response = response.json()
                job_id = job_response.get('id')
                logger.info(f"✅ Created job {job_id}: {job_data['title']}")
                return job_id
            else:
                logger.error(f"✗ API failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"✗ Error creating job: {str(e)}")
            return None
    
    def close_connections(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.neo4j_driver:
            self.neo4j_driver.close()

def main():
    """Main execution function"""
    logger.info("🚀 Starting job database refresh...")
    
    pdf_files = ["software_development_engineer.pdf", "data_scientist_job_description.pdf"]
    
    # Check PDF files exist
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            logger.error(f"✗ PDF file not found: {pdf_file}")
            return
    
    manager = JobRefreshManager()
    
    try:
        # Check API and connect to databases
        if not manager.check_api_status():
            return
        
        if not manager.connect_databases():
            return
        
        # Show current state
        initial_counts = manager.get_job_counts()
        logger.info(f"📊 Current jobs: PostgreSQL={initial_counts['postgresql_jobs']}, Neo4j={initial_counts['neo4j_job_nodes']}")
        
        # Confirm deletion
        response = input(f"\n⚠️ This will DELETE ALL {initial_counts['postgresql_jobs']} jobs. Continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("❌ Cancelled by user")
            return
        
        # Clear existing jobs
        if not manager.clear_all_jobs():
            logger.error("✗ Failed to clear jobs")
            return
        
        # Process PDFs and create jobs
        created_jobs = []
        for pdf_file in pdf_files:
            logger.info(f"\n📋 Processing {pdf_file}...")
            
            # Extract text
            text = manager.extract_pdf_text(pdf_file)
            
            # Create job data
            job_data = manager.create_job_data(text, pdf_file)
            
            # Create job via API
            job_id = manager.create_job_via_api(job_data)
            if job_id:
                created_jobs.append((job_id, job_data['title']))
        
        # Show results
        final_counts = manager.get_job_counts()
        logger.info(f"\n📊 Final jobs: PostgreSQL={final_counts['postgresql_jobs']}, Neo4j={final_counts['neo4j_job_nodes']}")
        
        logger.info(f"\n🎉 Successfully created {len(created_jobs)} jobs:")
        for job_id, title in created_jobs:
            logger.info(f"   • Job {job_id}: {title}")
        
        logger.info("\n📝 Next steps:")
        logger.info("   1. Check frontend to verify jobs display correctly")
        logger.info("   2. Test candidate matching against new jobs")
        logger.info("   3. Verify embeddings and Neo4j relationships")
        
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
    finally:
        manager.close_connections()

if __name__ == "__main__":
    main() 