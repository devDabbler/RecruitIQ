#!/usr/bin/env python3
"""
Simple script to check candidate data in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.models.models import Candidate

def check_candidates():
    """Check candidate data in the database"""
    try:
        db = next(get_db())
        candidates = db.query(Candidate).limit(10).all()
        
        print(f"Found {len(candidates)} candidates in database")
        print("-" * 80)
        
        for i, c in enumerate(candidates):
            print(f"Candidate {i+1}:")
            print(f"  ID: {c.id}")
            print(f"  Name: {c.first_name or ''} {c.last_name or ''}".strip() or 'No name')
            print(f"  Email: {c.email or 'No email'}")
            print(f"  Current Position: {c.current_position or 'Not specified'}")
            print(f"  Current Company: {c.current_company or 'Not specified'}")
            print(f"  Location: {c.location or 'Not specified'}")
            print(f"  Experience Years: {c.experience_years or 'Not specified'}")
            print(f"  Has Skills: {len(c.skills) if c.skills else 0}")
            print(f"  Has Resumes: {len(c.resumes) if c.resumes else 0}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error checking candidates: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_candidates() 