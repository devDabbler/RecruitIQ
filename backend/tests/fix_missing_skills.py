#!/usr/bin/env python3
"""
Script to fix missing skills by extracting them from parsed resume JSON.
This addresses the issue where skills are parsed but not saved to the database.
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Any

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.models.models import Candidate, Resume, CandidateSkill
from sqlalchemy.orm import Session
from sqlalchemy import text

def extract_skills_from_parsed_data(parsed_data: Dict[str, Any]) -> List[str]:
    """Extract skill names from parsed resume data."""
    skills = []
    
    if not parsed_data:
        return skills
    
    # Handle different skill formats
    if 'skills' in parsed_data and parsed_data['skills']:
        for skill in parsed_data['skills']:
            if isinstance(skill, dict):
                skill_name = skill.get('name', '')
            elif isinstance(skill, str):
                skill_name = skill
            else:
                continue
                
            if skill_name and skill_name.strip():
                skills.append(skill_name.strip())
    
    return skills

def extract_current_position_from_parsed_data(parsed_data: Dict[str, Any]) -> str:
    """Extract current position from parsed resume data."""
    if not parsed_data or 'experience' not in parsed_data:
        return ""
    
    experiences = parsed_data['experience']
    if not experiences:
        return ""
    
    # Get the most recent experience (first in the list)
    latest_exp = experiences[0]
    return latest_exp.get('title', '')

def fix_candidate_data(db: Session, candidate: Candidate) -> Dict[str, Any]:
    """Fix missing data for a specific candidate."""
    print(f"\nProcessing candidate: {candidate.first_name} {candidate.last_name} (ID: {candidate.id})")
    
    # Get the most recent resume for this candidate
    resume = db.query(Resume).filter(
        Resume.candidate_id == candidate.id
    ).order_by(Resume.created_at.desc()).first()
    
    if not resume:
        print(f"  No resume found for candidate {candidate.id}")
        return {"status": "no_resume", "skills_added": 0, "position_updated": False}
    
    if not resume.parsed_data:
        print(f"  No parsed data found in resume {resume.id}")
        return {"status": "no_parsed_data", "skills_added": 0, "position_updated": False}
    
    # Parse the JSON data
    try:
        if isinstance(resume.parsed_data, str):
            parsed_data = json.loads(resume.parsed_data)
        else:
            parsed_data = resume.parsed_data
    except Exception as e:
        print(f"  Error parsing resume data: {e}")
        return {"status": "parse_error", "skills_added": 0, "position_updated": False}
    
    # Extract skills
    skills = extract_skills_from_parsed_data(parsed_data)
    print(f"  Found {len(skills)} skills in parsed data")
    
    # Extract current position
    current_position = extract_current_position_from_parsed_data(parsed_data)
    print(f"  Current position: {current_position}")
    
    # Check existing skills
    existing_skills = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate.id
    ).all()
    existing_skill_names = [s.skill_name for s in existing_skills]
    print(f"  Existing skills in database: {len(existing_skill_names)}")
    
    # Add missing skills
    skills_added = 0
    for skill_name in skills:
        if skill_name not in existing_skill_names:
            try:
                new_skill = CandidateSkill(
                    candidate_id=candidate.id,
                    skill_name=skill_name
                )
                db.add(new_skill)
                skills_added += 1
                print(f"    Adding skill: {skill_name}")
            except Exception as e:
                print(f"    Error adding skill {skill_name}: {e}")
    
    # Update current position if missing
    position_updated = False
    if not candidate.current_position and current_position:
        try:
            candidate.current_position = current_position
            position_updated = True
            print(f"    Updated current position: {current_position}")
        except Exception as e:
            print(f"    Error updating position: {e}")
    
    # Commit changes
    try:
        db.commit()
        print(f"  Successfully committed changes")
    except Exception as e:
        db.rollback()
        print(f"  Error committing changes: {e}")
        return {"status": "commit_error", "skills_added": 0, "position_updated": False}
    
    return {
        "status": "success",
        "skills_added": skills_added,
        "position_updated": position_updated,
        "total_skills": len(skills),
        "current_position": current_position
    }

def main():
    """Main function to fix all candidates with missing data."""
    print("=== Fixing Missing Candidate Skills and Data ===")
    
    db = next(get_db())
    
    try:
        # Get all candidates
        candidates = db.query(Candidate).all()
        print(f"Found {len(candidates)} candidates")
        
        total_skills_added = 0
        total_positions_updated = 0
        results = []
        
        for candidate in candidates:
            result = fix_candidate_data(db, candidate)
            results.append({
                "candidate": f"{candidate.first_name} {candidate.last_name}",
                "result": result
            })
            
            if result["status"] == "success":
                total_skills_added += result["skills_added"]
                if result["position_updated"]:
                    total_positions_updated += 1
        
        # Print summary
        print(f"\n=== SUMMARY ===")
        print(f"Total candidates processed: {len(candidates)}")
        print(f"Total skills added: {total_skills_added}")
        print(f"Total positions updated: {total_positions_updated}")
        
        print(f"\n=== DETAILED RESULTS ===")
        for result in results:
            status = result["result"]["status"]
            candidate = result["candidate"]
            if status == "success":
                skills_added = result["result"]["skills_added"]
                position_updated = result["result"]["position_updated"]
                print(f"✓ {candidate}: Added {skills_added} skills, Position updated: {position_updated}")
            else:
                print(f"✗ {candidate}: {status}")
        
    except Exception as e:
        print(f"Error in main process: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main() 