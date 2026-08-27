#!/usr/bin/env python3
"""
Database schema verification script.
Checks if all required tables and columns exist for the AI assistant to work properly.
"""

import logging
import sys
from sqlalchemy import text, inspect
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_database_schema():
    """Verify that all required database tables and columns exist."""
    
    try:
        # Import database connection
        from backend.utils.database import engine, get_db
        from backend.models.models import Base, Candidate, Resume, CandidateSkill, Job
        
        print("🔍 Verifying Database Schema...")
        print("=" * 50)
        
        # Create a session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Get inspector
        inspector = inspect(engine)
        
        # Get all table names
        all_tables = inspector.get_table_names()
        print(f"📋 Found {len(all_tables)} tables in database:")
        for table in sorted(all_tables):
            print(f"   - {table}")
        print()
        
        # Required tables for AI assistant functionality
        required_tables = [
            "candidates",
            "resumes", 
            "candidate_skills",
            "jobs",
            "skills"
        ]
        
        missing_tables = []
        existing_tables = []
        
        for table in required_tables:
            if table in all_tables:
                existing_tables.append(table)
                print(f"✅ Table '{table}' exists")
            else:
                missing_tables.append(table)
                print(f"❌ Table '{table}' is missing")
        
        print()
        
        # Check columns for existing tables
        table_columns = {}
        for table in existing_tables:
            columns = inspector.get_columns(table)
            column_names = [col['name'] for col in columns]
            table_columns[table] = column_names
            print(f"📊 Table '{table}' has {len(columns)} columns:")
            for col in columns:
                print(f"   - {col['name']} ({col['type']})")
            print()
        
        # Verify specific columns for AI assistant functionality
        print("🔍 Verifying Required Columns...")
        print("=" * 50)
        
        column_issues = []
        
        # Check candidates table columns
        if "candidates" in table_columns:
            required_candidate_columns = ["id", "first_name", "last_name", "email"]
            for col in required_candidate_columns:
                if col in table_columns["candidates"]:
                    print(f"✅ candidates.{col} exists")
                else:
                    print(f"❌ candidates.{col} is missing")
                    column_issues.append(f"candidates.{col}")
        
        # Check resumes table columns
        if "resumes" in table_columns:
            required_resume_columns = ["id", "candidate_id", "parsed_content", "parsed_data"]
            for col in required_resume_columns:
                if col in table_columns["resumes"]:
                    print(f"✅ resumes.{col} exists")
                else:
                    print(f"❌ resumes.{col} is missing")
                    column_issues.append(f"resumes.{col}")
        
        # Check candidate_skills table columns
        if "candidate_skills" in table_columns:
            required_skill_columns = ["id", "candidate_id", "skill_name"]
            for col in required_skill_columns:
                if col in table_columns["candidate_skills"]:
                    print(f"✅ candidate_skills.{col} exists")
                else:
                    print(f"❌ candidate_skills.{col} is missing")
                    column_issues.append(f"candidate_skills.{col}")
        
        # Check jobs table columns
        if "jobs" in table_columns:
            required_job_columns = ["id", "title", "department"]
            for col in required_job_columns:
                if col in table_columns["jobs"]:
                    print(f"✅ jobs.{col} exists")
                else:
                    print(f"❌ jobs.{col} is missing")
                    column_issues.append(f"jobs.{col}")
        
        print()
        
        # Test basic queries
        print("🧪 Testing Basic Queries...")
        print("=" * 50)
        
        query_issues = []
        
        # Test candidate count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM candidates")).fetchone()
            candidate_count = result[0] if result else 0
            print(f"✅ Candidate count query successful: {candidate_count} candidates")
        except Exception as e:
            print(f"❌ Candidate count query failed: {e}")
            query_issues.append(f"Candidate count: {e}")
        
        # Test resume count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM resumes")).fetchone()
            resume_count = result[0] if result else 0
            print(f"✅ Resume count query successful: {resume_count} resumes")
        except Exception as e:
            print(f"❌ Resume count query failed: {e}")
            query_issues.append(f"Resume count: {e}")
        
        # Test candidate skills count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM candidate_skills")).fetchone()
            skill_count = result[0] if result else 0
            print(f"✅ Candidate skills count query successful: {skill_count} skill records")
        except Exception as e:
            print(f"❌ Candidate skills count query failed: {e}")
            query_issues.append(f"Candidate skills count: {e}")
        
        # Test job count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM jobs")).fetchone()
            job_count = result[0] if result else 0
            print(f"✅ Job count query successful: {job_count} jobs")
        except Exception as e:
            print(f"❌ Job count query failed: {e}")
            query_issues.append(f"Job count: {e}")
        
        # Test candidate search query
        try:
            result = db.execute(text("""
                SELECT c.id, c.first_name, c.last_name 
                FROM candidates c 
                LIMIT 5
            """)).fetchall()
            print(f"✅ Candidate search query successful: {len(result)} results")
        except Exception as e:
            print(f"❌ Candidate search query failed: {e}")
            query_issues.append(f"Candidate search: {e}")
        
        # Test resume join query
        try:
            result = db.execute(text("""
                SELECT c.id, c.first_name, c.last_name, r.parsed_content 
                FROM candidates c 
                LEFT JOIN resumes r ON c.id = r.candidate_id 
                LIMIT 3
            """)).fetchall()
            print(f"✅ Resume join query successful: {len(result)} results")
        except Exception as e:
            print(f"❌ Resume join query failed: {e}")
            query_issues.append(f"Resume join: {e}")
        
        # Test candidate skills join query
        try:
            result = db.execute(text("""
                SELECT c.id, c.first_name, c.last_name, cs.skill_name 
                FROM candidates c 
                LEFT JOIN candidate_skills cs ON c.id = cs.candidate_id 
                LIMIT 3
            """)).fetchall()
            print(f"✅ Candidate skills join query successful: {len(result)} results")
        except Exception as e:
            print(f"❌ Candidate skills join query failed: {e}")
            query_issues.append(f"Candidate skills join: {e}")
        
        print()
        
        # Generate summary
        print("📊 SCHEMA VERIFICATION SUMMARY")
        print("=" * 50)
        
        if not missing_tables and not column_issues and not query_issues:
            print("🎉 EXCELLENT! All database schema requirements are met.")
            print("   The AI assistant should work properly with the database.")
        else:
            print("⚠️  ISSUES FOUND:")
            
            if missing_tables:
                print(f"   Missing tables: {', '.join(missing_tables)}")
            
            if column_issues:
                print(f"   Missing columns: {', '.join(column_issues)}")
            
            if query_issues:
                print(f"   Query issues: {len(query_issues)} problems")
                for issue in query_issues:
                    print(f"     - {issue}")
            
            print("\n🔧 RECOMMENDATIONS:")
            if missing_tables:
                print("   1. Run database migrations to create missing tables")
                print("   2. Check alembic migration files")
            
            if column_issues:
                print("   3. Update database schema to add missing columns")
                print("   4. Check model definitions in models.py")
            
            if query_issues:
                print("   5. Fix database connection or permission issues")
                print("   6. Check database user permissions")
        
        # Close database session
        db.close()
        
        return {
            "missing_tables": missing_tables,
            "column_issues": column_issues,
            "query_issues": query_issues,
            "all_ok": not missing_tables and not column_issues and not query_issues
        }
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        logger.error(f"Database verification error: {e}", exc_info=True)
        return {
            "error": str(e),
            "all_ok": False
        }

if __name__ == "__main__":
    result = verify_database_schema()
    
    if result.get("all_ok"):
        print("\n✅ Database schema verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Database schema verification found issues!")
        sys.exit(1) 