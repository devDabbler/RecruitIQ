#!/usr/bin/env python3
"""
Script to fix malformed skills data in the database.
This script will:
1. Find candidates with malformed skills data
2. Parse and clean the skills data
3. Update the database with clean skill names
"""

import sys
import os
import json
import logging
from typing import List, Dict, Any

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.utils.database import get_db, SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_skill_data(skill_data: Any) -> str:
    """
    Clean and extract skill name from various formats.
    
    Args:
        skill_data: Raw skill data (string, dict, etc.)
        
    Returns:
        str: Clean skill name
    """
    if isinstance(skill_data, str):
        # Check if it looks like a dictionary string representation
        if skill_data.startswith("{'") or skill_data.startswith('{"'):
            try:
                # Try to parse as JSON or eval as dict
                if skill_data.startswith('{"'):
                    skill_dict = json.loads(skill_data)
                else:
                    skill_dict = eval(skill_data)  # Be careful with eval
                return skill_dict.get('name', str(skill_dict))
            except (json.JSONDecodeError, SyntaxError, ValueError, TypeError):
                # If parsing fails, return the original string
                return skill_data
        return skill_data
    elif isinstance(skill_data, dict):
        return skill_data.get('name', skill_data.get('skill_name', str(skill_data)))
    else:
        return str(skill_data)

def fix_candidate_skills_in_resumes(db: Session) -> int:
    """
    Fix skills in resume parsed_data.
    
    Args:
        db: Database session
        
    Returns:
        int: Number of resumes updated
    """
    updated_count = 0
    
    # Query all resumes with parsed_data using proper SQLAlchemy text()
    try:
        result = db.execute(
            text("SELECT id, candidate_id, parsed_data FROM resumes WHERE parsed_data IS NOT NULL")
        )
        resumes = result.fetchall()
        
        logger.info(f"Found {len(resumes)} resumes with parsed data to check")
        
        for resume in resumes:
            try:
                # Parse the resume data
                parsed_data_raw = resume.parsed_data
                if isinstance(parsed_data_raw, str):
                    parsed_data = json.loads(parsed_data_raw)
                else:
                    parsed_data = parsed_data_raw
                
                # Get skills from parsed data
                skills_data = parsed_data.get('skills', [])
                
                if skills_data:
                    # Clean the skills
                    clean_skills = []
                    original_malformed_count = 0
                    
                    for skill in skills_data:
                        try:
                            # Check if skill is malformed (contains dict-like strings)
                            if isinstance(skill, str) and ("'name':" in skill or '"name":' in skill):
                                original_malformed_count += 1
                                logger.debug(f"Found malformed skill: {skill}")
                            
                            clean_skill_name = clean_skill_data(skill)
                            if clean_skill_name and clean_skill_name.strip():
                                clean_skills.append(clean_skill_name.strip())
                        except Exception as e:
                            logger.warning(f"Error cleaning skill {skill} for resume {resume.id}: {str(e)}")
                            continue
                    
                    # Update the parsed data with clean skills if we found malformed data
                    if original_malformed_count > 0:
                        parsed_data['skills'] = clean_skills
                        
                        # Update the database using parameterized query
                        db.execute(
                            text("UPDATE resumes SET parsed_data = :parsed_data WHERE id = :resume_id"),
                            {"parsed_data": json.dumps(parsed_data), "resume_id": resume.id}
                        )
                        
                        updated_count += 1
                        logger.info(f"Fixed {original_malformed_count} malformed skills for resume {resume.id} (candidate {resume.candidate_id})")
                        logger.debug(f"Clean skills: {clean_skills}")
                        
            except Exception as e:
                logger.error(f"Error processing resume {resume.id}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error querying resumes: {str(e)}")
        return 0
    
    return updated_count

def main():
    """Main function to fix all candidate skills."""
    logger.info("Starting skills data cleanup...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Count total malformed skills before fixing
        logger.info("Scanning for malformed skills...")
        total_malformed_skills = 0
        
        result = db.execute(
            text("SELECT parsed_data FROM resumes WHERE parsed_data IS NOT NULL")
        )
        resumes = result.fetchall()
        
        logger.info(f"Checking {len(resumes)} resumes for malformed skills...")
        
        for resume in resumes:
            try:
                parsed_data_raw = resume.parsed_data
                if isinstance(parsed_data_raw, str):
                    parsed_data = json.loads(parsed_data_raw)
                else:
                    parsed_data = parsed_data_raw
                
                skills_data = parsed_data.get('skills', [])
                for skill in skills_data:
                    if isinstance(skill, str) and ("'name':" in skill or '"name":' in skill):
                        total_malformed_skills += 1
            except Exception as e:
                logger.debug(f"Error parsing resume data: {str(e)}")
                pass
        
        logger.info(f"Found {total_malformed_skills} malformed skills across all resumes")
        
        if total_malformed_skills == 0:
            logger.info("No malformed skills found. Nothing to fix!")
            return
        
        # Ask for confirmation
        print(f"\nFound {total_malformed_skills} malformed skills in the database.")
        print("This script will clean them up by extracting just the skill names.")
        confirmation = input("Do you want to proceed? (y/N): ").strip().lower()
        
        if confirmation not in ['y', 'yes']:
            logger.info("Operation cancelled by user.")
            return
        
        # Fix the skills
        logger.info("Starting cleanup process...")
        updated_count = fix_candidate_skills_in_resumes(db)
        
        # Commit all changes
        db.commit()
        
        logger.info(f"Skills cleanup completed successfully!")
        logger.info(f"Updated {updated_count} resumes with malformed skills.")
        logger.info(f"Total malformed skills fixed: {total_malformed_skills}")
        
    except Exception as e:
        logger.error(f"Error during skills cleanup: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main() 