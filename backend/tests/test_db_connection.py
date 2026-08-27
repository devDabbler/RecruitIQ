#!/usr/bin/env python3
"""
Simple test to check database connection.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.models.models import Candidate

def test_db_connection():
    """Test database connection."""
    try:
        db = next(get_db())
        print("✅ Database connection successful")
        
        # Test a simple query
        count = db.query(Candidate).count()
        print(f"✅ Found {count} candidates in database")
        
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_db_connection() 