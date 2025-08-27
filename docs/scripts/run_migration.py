#!/usr/bin/env python3
"""
Simple script to run the database migration for candidate_pitches table.
"""

import os
import sys
from pathlib import Path

def main():
    """Run the database migration."""
    print("🔧 Running database migration for candidate_pitches table...")
    
    # Change to backend directory
    backend_dir = Path(__file__).parent / "backend"
    original_dir = os.getcwd()
    
    try:
        os.chdir(backend_dir)
        print(f"📁 Changed to directory: {backend_dir}")
        
        # Run the migration
        print("🚀 Running: alembic upgrade head")
        exit_code = os.system("alembic upgrade head")
        
        if exit_code == 0:
            print("✅ Migration completed successfully!")
            
            # Test the table
            print("🧪 Testing candidate_pitches table...")
            try:
                # Simple test using environment
                test_code = os.system('python -c "from sqlalchemy import create_engine, text; import os; engine = create_engine(os.getenv(\\"DATABASE_URL\\", \\"postgresql://admin:password@localhost:5432/ats_db\\")); conn = engine.connect(); result = conn.execute(text(\\"SELECT COUNT(*) FROM candidate_pitches\\")); print(f\\"✅ Table exists with {result.fetchone()[0]} records\\"); conn.close()"')
                
                if test_code == 0:
                    print("✅ candidate_pitches table is working correctly!")
                else:
                    print("⚠️  Table test failed, but migration might still be successful")
                    
            except Exception as e:
                print(f"⚠️  Could not test table: {e}")
                print("✅ Migration completed, but table test failed")
        else:
            print("❌ Migration failed!")
            print("💡 Try running manually: cd backend && alembic upgrade head")
            
    finally:
        os.chdir(original_dir)
        print(f"📁 Returned to directory: {original_dir}")

if __name__ == "__main__":
    main() 