#!/usr/bin/env python
"""
Backfill Current Positions Script

This script updates all existing candidates' current_position and current_company fields
by analyzing their most recent work experience from saved resume data.
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# Add the project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database.db_connection import get_postgres_connection

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_most_recent_position(experiences: List[Dict[str, Any]]) -> tuple:
    """
    Determine the most recent position from a list of work experiences.
    
    Args:
        experiences: List of experience dictionaries
        
    Returns:
        Tuple of (job_title, company_name)
    """
    most_recent_job = None
    most_recent_company = None
    most_recent_end_date = None
    
    for exp in experiences:
        # Extract fields safely
        title = exp.get('title')
        company = exp.get('company')
        end_date = exp.get('end_date')
        
        # If end_date is None/empty, it's likely a current position
        is_current = not end_date
        
        # Logic to identify the most recent position:
        # 1. Current positions (no end date) take priority
        # 2. Otherwise, compare end dates to find the most recent
        if is_current:
            # Current position takes precedence
            most_recent_job = title
            most_recent_company = company
            break  # Exit the loop as we found a current position
        elif end_date and (most_recent_end_date is None or end_date > most_recent_end_date):
            # This has a more recent end date
            most_recent_job = title
            most_recent_company = company
            most_recent_end_date = end_date
    
    return most_recent_job, most_recent_company


async def backfill_current_positions():
    """Update all existing candidates with their most recent job titles from resume data."""
    conn = None
    try:
        logger.info("Starting backfill of current positions...")
        conn = get_postgres_connection()
        
        with conn.cursor() as cur:
            # Get all candidates with their resumes
            cur.execute("""
                SELECT c.id, r.parsed_data
                FROM candidates c
                LEFT JOIN resumes r ON c.id = r.candidate_id
                WHERE r.parsed_data IS NOT NULL
            """)
            
            candidates_updated = 0
            candidates_skipped = 0
            
            for row in cur.fetchall():
                candidate_id = row['id'] if isinstance(row, dict) else row[0]
                parsed_data = row['parsed_data'] if isinstance(row, dict) else row[1]
                
                if not parsed_data:
                    logger.info(f"Skipping candidate {candidate_id} - no resume data")
                    candidates_skipped += 1
                    continue
                
                try:
                    # Extract experience data directly from JSON
                    experiences = parsed_data.get('experience', [])
                    
                    if experiences:
                        logger.info(f"Found {len(experiences)} experiences for candidate {candidate_id}")
                        most_recent_job, most_recent_company = get_most_recent_position(experiences)
                        
                        if most_recent_job:
                            # Update the candidate record
                            with conn.cursor() as update_cur:
                                update_cur.execute(
                                    """UPDATE candidates 
                                       SET current_position = %s, current_company = %s, updated_at = NOW()
                                       WHERE id = %s""",
                                    (most_recent_job, most_recent_company, candidate_id)
                                )
                            
                            logger.info(f"Updated candidate {candidate_id} with position: {most_recent_job} at {most_recent_company}")
                            candidates_updated += 1
                        else:
                            logger.info(f"No job title found in experiences for candidate {candidate_id}")
                            candidates_skipped += 1
                    else:
                        logger.info(f"No work experience found for candidate {candidate_id}")
                        candidates_skipped += 1
                
                except Exception as e:
                    logger.error(f"Error processing candidate {candidate_id}: {str(e)}")
                    candidates_skipped += 1
            
            conn.commit()
            logger.info(f"Backfill complete: {candidates_updated} candidates updated, {candidates_skipped} skipped")
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error during backfill: {str(e)}")
    
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    asyncio.run(backfill_current_positions())
    print("Backfill of current positions complete!")
