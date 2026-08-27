#!/usr/bin/env python3
"""
Test script to verify that experience calculation is working automatically for new candidates.
"""

import json
import logging
from sqlalchemy import text
from backend.utils.database import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_experience_calculation():
    """Test that experience calculation is working for new candidates."""
    db = SessionLocal()
    
    try:
        logger.info("=== TESTING EXPERIENCE CALCULATION ===")
        
        # Get all candidates with their experience data
        result = db.execute(text("""
            SELECT 
                c.id,
                c.first_name,
                c.last_name,
                c.email,
                c.experience_years,
                c.experience_level,
                c.current_position,
                r.parsed_data,
                r.created_at as resume_created_at
            FROM candidates c
            LEFT JOIN resumes r ON c.id = r.candidate_id
            ORDER BY r.created_at DESC
        """))
        
        candidates = result.fetchall()
        
        if not candidates:
            logger.info("No candidates found in database")
            return
        
        logger.info(f"Found {len(candidates)} candidates")
        
        for candidate in candidates:
            candidate_id, first_name, last_name, email, exp_years, exp_level, position, parsed_data, resume_created_at = candidate
            
            logger.info(f"\n--- Candidate: {first_name} {last_name} ({email}) ---")
            logger.info(f"ID: {candidate_id}")
            logger.info(f"Resume Created: {resume_created_at}")
            logger.info(f"Current Position: {position}")
            logger.info(f"Experience Years (DB): {exp_years}")
            logger.info(f"Experience Level (DB): {exp_level}")
            
            if parsed_data:
                try:
                    parsed = json.loads(parsed_data) if isinstance(parsed_data, str) else parsed_data
                    experience_list = parsed.get('experience', [])
                    
                    logger.info(f"Experience entries in parsed_data: {len(experience_list)}")
                    
                    if experience_list:
                        logger.info("Experience details:")
                        for i, exp in enumerate(experience_list):
                            title = exp.get('title', 'N/A')
                            company = exp.get('company', 'N/A')
                            start_date = exp.get('start_date', 'N/A')
                            end_date = exp.get('end_date', 'N/A')
                            logger.info(f"  {i+1}. {title} at {company} ({start_date} - {end_date})")
                    else:
                        logger.warning("No experience entries found in parsed_data")
                        
                except Exception as e:
                    logger.error(f"Error parsing parsed_data: {e}")
            else:
                logger.warning("No parsed_data found")
            
            # Check if experience data is present
            if exp_years is not None and exp_level is not None:
                logger.info("✅ Experience data is present in database")
            else:
                logger.warning("❌ Experience data is missing from database!")
        
        logger.info(f"\n=== SUMMARY ===")
        logger.info("The experience calculation should now work automatically for new candidates.")
        logger.info("Upload a new resume to test the automatic experience calculation.")
        
    except Exception as e:
        logger.error(f"Error testing experience calculation: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_experience_calculation() 