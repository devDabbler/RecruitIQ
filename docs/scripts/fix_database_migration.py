#!/usr/bin/env python3
"""
Script to apply database migrations and fix the candidate_pitches table issue.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migrations():
    """Run Alembic migrations to create the candidate_pitches table."""
    try:
        # Change to backend directory
        backend_dir = Path(__file__).parent / "backend"
        os.chdir(backend_dir)
        
        logger.info("Running Alembic migration to create candidate_pitches table...")
        
        # Run alembic upgrade using poetry
        result = subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=False,
            cwd=backend_dir
        )
        
        if result.returncode == 0:
            logger.info("✅ Database migration completed successfully!")
            logger.info(f"Migration output: {result.stdout}")
        else:
            logger.error(f"❌ Migration failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            logger.error(f"Stdout: {result.stdout}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error running migrations: {str(e)}")
        return False

def test_candidate_pitches_table():
    """Test if the candidate_pitches table was created successfully."""
    try:
        # Import database components
        sys.path.append(str(Path(__file__).parent))
        sys.path.append(str(Path(__file__).parent / "backend"))
        
        try:
            from backend.utils.database import get_db
            from sqlalchemy import text
            import psycopg2
        except ImportError:
            # Fallback - try direct connection
            import psycopg2
            from sqlalchemy import create_engine, text
            
            # Use environment variables or default connection
            DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/ats_db")
            engine = create_engine(DATABASE_URL)
            
            def get_db():
                return engine.connect()
        
        logger.info("Testing candidate_pitches table...")
        
        # Try to get database connection
        try:
            db = next(get_db())
        except:
            # Fallback connection
            db = get_db()
        
        # Try to query the table
        result = db.execute(text("SELECT COUNT(*) FROM candidate_pitches")).fetchone()
        count = result[0] if result else 0
        
        logger.info(f"✅ candidate_pitches table exists and contains {count} records")
        
        # Test table structure
        result = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'candidate_pitches'
            ORDER BY ordinal_position
        """)).fetchall()
        
        logger.info("Table structure:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]}")
        
        # Close connection if it's not a generator
        if hasattr(db, 'close'):
            db.close()
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing candidate_pitches table: {str(e)}")
        return False

def main():
    """Main function to run the database fix."""
    logger.info("🔧 Starting database migration for candidate_pitches table...")
    
    # Step 1: Run migrations
    if not run_migrations():
        logger.error("❌ Failed to run migrations. Exiting.")
        sys.exit(1)
    
    # Step 2: Test the table
    if not test_candidate_pitches_table():
        logger.error("❌ Failed to verify candidate_pitches table. Exiting.")
        sys.exit(1)
    
    logger.info("🎉 Database migration completed successfully!")
    logger.info("✅ The candidate_pitches table has been created and is ready to use.")
    logger.info("✅ You can now use the candidate pitch functionality without errors.")

if __name__ == "__main__":
    main() 