from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from ..utils.database import get_db
from ..models.models import CandidatePitch, Candidate, Job

router = APIRouter(prefix="/pitches")
logger = logging.getLogger(__name__)

@router.post("/save")
async def save_candidate_pitch(
    title: str = Body(...),
    content: str = Body(...),
    user_id: str = Body(...),
    candidate_id: Optional[str] = Body(None),
    job_id: Optional[int] = Body(None),
    notes: Optional[str] = Body(None),
    tags: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    """
    Save a candidate pitch to the user's saved pitches.
    """
    try:
        # Create new pitch
        new_pitch = CandidatePitch(
            title=title,
            content=content,
            user_id=user_id,
            candidate_id=candidate_id,
            job_id=job_id,
            notes=notes,
            tags=tags
        )
        
        # Add to database
        db.add(new_pitch)
        db.commit()
        db.refresh(new_pitch)
        
        # Return the created pitch data
        return {
            "status": "success",
            "message": "Candidate pitch saved successfully",
            "pitch_id": new_pitch.id,
            "created_at": new_pitch.created_at
        }
    
    except Exception as e:
        logger.error(f"Error saving candidate pitch: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save candidate pitch")

@router.get("/user/{user_id}")
async def get_user_pitches(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all pitches saved by a specific user.
    """
    try:
        # Query all pitches for this user
        pitches = db.query(CandidatePitch).filter(CandidatePitch.user_id == user_id).all()
        
        # Format response
        result = []
        for pitch in pitches:
            pitch_data = {
                "id": pitch.id,
                "title": pitch.title,
                "content": pitch.content,
                "notes": pitch.notes,
                "tags": pitch.tags,
                "created_at": pitch.created_at,
                "updated_at": pitch.updated_at
            }
            
            # Add candidate information if available
            if pitch.candidate_id:
                candidate = db.query(Candidate).filter(Candidate.id == pitch.candidate_id).first()
                if candidate:
                    pitch_data["candidate"] = {
                        "id": candidate.id,
                        "name": f"{candidate.first_name} {candidate.last_name}",
                        "position": candidate.current_position,
                        "company": candidate.current_company
                    }
            
            # Add job information if available
            if pitch.job_id:
                job = db.query(Job).filter(Job.id == pitch.job_id).first()
                if job:
                    pitch_data["job"] = {
                        "id": job.id,
                        "title": job.title,
                        "department": job.department
                    }
            
            result.append(pitch_data)
        
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving user pitches: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve saved pitches")

@router.get("/{pitch_id}")
async def get_pitch_by_id(
    pitch_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific pitch by ID.
    """
    pitch = db.query(CandidatePitch).filter(CandidatePitch.id == pitch_id).first()
    
    if not pitch:
        raise HTTPException(status_code=404, detail="Pitch not found")
    
    return {
        "id": pitch.id,
        "title": pitch.title,
        "content": pitch.content,
        "notes": pitch.notes,
        "tags": pitch.tags,
        "user_id": pitch.user_id,
        "candidate_id": pitch.candidate_id,
        "job_id": pitch.job_id,
        "created_at": pitch.created_at,
        "updated_at": pitch.updated_at
    }

@router.delete("/{pitch_id}")
async def delete_pitch(
    pitch_id: str,
    user_id: str = Body(...),
    db: Session = Depends(get_db)
):
    """
    Delete a saved pitch.
    """
    # Get the pitch
    pitch = db.query(CandidatePitch).filter(CandidatePitch.id == pitch_id).first()
    
    # Check if pitch exists
    if not pitch:
        raise HTTPException(status_code=404, detail="Pitch not found")
    
    # Verify ownership
    if pitch.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this pitch")
    
    # Delete the pitch
    db.delete(pitch)
    db.commit()
    
    return {
        "status": "success",
        "message": "Pitch deleted successfully"
    }
