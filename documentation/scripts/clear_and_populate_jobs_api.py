#!/usr/bin/env python3
"""
Alternative script to clear ALL jobs and repopulate using the REST API.
This approach ensures proper validation and processing through the API endpoints.
"""

import os
import sys
import json
import logging
import asyncio
import requests
from pathlib import Path
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000"
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

class JobAPIManager:
    """Manages job operations using the REST API and direct database access for cleanup"""
    
    def __init__(self):
        self.pg_conn = None
        self.neo4j_driver = None
    
    def connect_databases(self) -> bool:
        """Connect to databases for cleanup operations"""
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
        
        return True
    
    def check_api_status(self) -> bool:
        """Check if the backend API is running"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✓ Backend API is running")
                return True
            else:
                logger.error(f"✗ Backend API returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to connect to backend API: {str(e)}")
            logger.info("💡 Make sure to start the backend server first:")
            logger.info("   cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000")
            return False
    
    def get_job_counts(self) -> Dict[str, int]:
        """Get current job counts"""
        counts = {'api_jobs': 0, 'postgresql_jobs': 0, 'neo4j_job_nodes': 0}
        
        # API count
        try:
            response = requests.get(f"{API_BASE_URL}/api/jobs")
            if response.status_code == 200:
                jobs = response.json()
                counts['api_jobs'] = len(jobs)
        except Exception as e:
            logger.error(f"Error getting API job count: {str(e)}")
        
        # PostgreSQL count
        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            counts['postgresql_jobs'] = cursor.fetchone()[0]
            cursor.close()
        except Exception as e:
            logger.error(f"Error getting PostgreSQL job count: {str(e)}")
        
        # Neo4j count
        try:
            with self.neo4j_driver.session(database=NEO4J_CONFIG['database']) as session:
                result = session.run("MATCH (j:Job) RETURN count(j) as count")
                counts['neo4j_job_nodes'] = result.single()["count"]
        except Exception as e:
            logger.error(f"Error getting Neo4j job count: {str(e)}")
        
        return counts
    
    def clear_all_jobs(self) -> bool:
        """Clear all jobs from both databases"""
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
        
        # Enhanced job parsing based on PDF content and filename
        job_data = {
            'title': 'Software Engineer',
            'department': 'Engineering',
            'location': 'San Francisco, CA',
            'location_type': 'hybrid',
            'job_type': 'full_time',
            'experience_level': 'mid_level',
            'status': 'open',
            'job_overview': '',
            'required_qualifications': '',
            'skills': [],
            'min_salary': 80000,
            'max_salary': 150000
        }
        
        # Customize based on filename
        if 'software_development' in filename.lower():
            job_data.update({
                'title': 'Software Development Engineer',
                'department': 'Engineering',
                'location': 'Seattle, WA',
                'experience_level': 'senior_level',
                'skills': ['Python', 'Java', 'JavaScript', 'AWS', 'Docker', 'Kubernetes', 'REST APIs', 'Microservices', 'SQL', 'Git'],
                'min_salary': 120000,
                'max_salary': 200000,
                'job_overview': 'We are seeking a highly skilled Software Development Engineer to join our dynamic engineering team. You will be responsible for designing, developing, and maintaining scalable software solutions that serve millions of users worldwide.',
                'required_qualifications': 'Bachelor\'s degree in Computer Science or related field. 5+ years of experience in software development. Strong proficiency in Python, Java, and modern web technologies. Experience with cloud platforms (AWS preferred). Knowledge of containerization and microservices architecture.'
            })
        elif 'data_scientist' in filename.lower():
            job_data.update({
                'title': 'Data Scientist',
                'department': 'Data Science',
                'location': 'New York, NY',
                'experience_level': 'mid_level',
                'skills': ['Python', 'R', 'Machine Learning', 'SQL', 'Statistics', 'Pandas', 'NumPy', 'Scikit-learn', 'TensorFlow', 'Tableau'],
                'min_salary': 90000,
                'max_salary': 160000,
                'job_overview': 'Join our data science team to extract insights from complex datasets and build predictive models that drive business decisions. You will work with cross-functional teams to identify opportunities and implement data-driven solutions.',
                'required_qualifications': 'Master\'s degree in Data Science, Statistics, Mathematics, or related field. 3+ years of experience in data analysis and machine learning. Proficiency in Python or R. Experience with SQL and data visualization tools. Strong statistical and analytical skills.'
            })
        
        # Enhance with actual PDF content if available
        if len(text) > 100:
            # Look for specific patterns in the text
            if 'machine learning' in text.lower() or 'data science' in text.lower():
                job_data['skills'].extend(['Deep Learning', 'PyTorch', 'Apache Spark'])
            if 'aws' in text.lower() or 'cloud' in text.lower():
                job_data['skills'].extend(['AWS', 'Cloud Computing'])
            if 'api' in text.lower():
                job_data['skills'].extend(['API Development', 'RESTful Services'])
        
        # Remove duplicates from skills
        job_data['skills'] = list(set(job_data['skills']))
        
        logger.info(f"✓ Parsed job: {job_data['title']} with {len(job_data['skills'])} skills")
        return job_data
    
    def create_job_via_api(self, job_data: Dict[str, Any]) -> Optional[int]:
        """Create a job using the REST API"""
        logger.info(f"💼 Creating job via API: {job_data['title']}")
        
        try:
            # Prepare the job payload
            payload = {
                'title': job_data['title'],
                'department': job_data['department'],
                'job_overview': job_data['job_overview'],
                'required_qualifications': job_data['required_qualifications'],
                'location': job_data['location'],
                'location_type': job_data['location_type'],
                'job_type': job_data['job_type'],
                'experience_level': job_data['experience_level'],
                'min_salary': job_data.get('min_salary'),
                'max_salary': job_data.get('max_salary'),
                'status': job_data['status'],
                'skills': job_data['skills']
            }
            
            # Make API request
            response = requests.post(
                f"{API_BASE_URL}/api/jobs/",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 201:
                job_response = response.json()
                job_id = job_response.get('id')
                logger.info(f"✅ Successfully created job {job_id} via API")
                return job_id
            else:
                logger.error(f"✗ API request failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"✗ Error creating job via API: {str(e)}")
            return None
    
    def close_connections(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("✓ Closed PostgreSQL connection")
        
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("✓ Closed Neo4j connection")

def main():
    """Main function to orchestrate the job clearing and population"""
    logger.info("🚀 Starting job database refresh via API...")
    
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
    
    # Initialize manager
    manager = JobAPIManager()
    
    try:
        # Check API status
        if not manager.check_api_status():
            return
        
        # Connect to databases
        if not manager.connect_databases():
            logger.error("✗ Failed to connect to databases")
            return
        
        # Show current counts
        initial_counts = manager.get_job_counts()
        logger.info(f"📊 Current job counts: API={initial_counts['api_jobs']}, "
                   f"PostgreSQL={initial_counts['postgresql_jobs']}, "
                   f"Neo4j={initial_counts['neo4j_job_nodes']}")
        
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
            
            # Parse job description
            job_data = manager.parse_job_description(text, pdf_file)
            
            # Create job via API
            job_id = manager.create_job_via_api(job_data)
            if job_id:
                created_jobs.append((job_id, job_data['title']))
                logger.info(f"✅ Successfully created job {job_id}: {job_data['title']}")
            else:
                logger.error(f"✗ Failed to create job from {pdf_file}")
        
        # Show final results
        final_counts = manager.get_job_counts()
        logger.info(f"\n📊 Final job counts: API={final_counts['api_jobs']}, "
                   f"PostgreSQL={final_counts['postgresql_jobs']}, "
                   f"Neo4j={final_counts['neo4j_job_nodes']}")
        
        logger.info(f"\n🎉 Successfully created {len(created_jobs)} jobs:")
        for job_id, title in created_jobs:
            logger.info(f"   • Job {job_id}: {title}")
        
        logger.info("\n📝 Next steps:")
        logger.info("   1. Check the frontend to verify the jobs are displayed correctly")
        logger.info("   2. Test candidate matching against these new jobs")
        logger.info("   3. Verify embeddings and Neo4j relationships are working")
        
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
    finally:
        manager.close_connections()

if __name__ == "__main__":
    main() 