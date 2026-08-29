import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug("[candidates.py] Importing candidates router...")
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, or_
from typing import List, Optional, Dict, Any
import json
import tempfile
import os
from datetime import datetime
import re

from ..utils.database import get_db
from ..models.candidate import (
    CandidateCreate, 
    CandidateUpdate, 
    CandidateResponse, 
    CandidateSearchResponse,
    CandidateStatus
)
from ..models.models import Candidate, CandidateSkill, Resume
from ..services.service_registry import provide_resume_service
from ..crud.candidate_crud import get_candidate as crud_get_candidate
from ..utils.performance import async_timed

router = APIRouter(prefix="/candidates")


# Response models for the routes that used to return bare dicts. Declared here
# rather than in models/candidate.py because they describe this router's
# envelopes, not the candidate domain.
class MessageResponse(BaseModel):
    """A plain acknowledgement."""
    message: str


class CandidateResumeSummary(BaseModel):
    id: int
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    created_at: Optional[datetime] = None


class CandidateResumesResponse(BaseModel):
    candidate_id: str
    resumes: List[CandidateResumeSummary]


class ResumeUploadResponse(BaseModel):
    message: str
    resume_id: int
    candidate_id: Optional[str] = None


class ParsedResumeSaveResponse(BaseModel):
    message: str
    resume_id: int
    candidate_id: str
    candidate_updated: bool

def format_candidate_skills(candidate, parsed_data=None):
    """Format candidate skills safely, handling various data structures.

    The relationship is `Candidate.skills` (models.py), not `candidate_skills`.
    This read the latter, so `hasattr` was always False and the branch never ran
    once: every candidate whose skills live only in the candidate_skills table --
    anyone added without a parsed resume -- reported no skills at all, on both
    the list and the detail route. The `skills_breakdown` endpoint reads the
    correct attribute, which is why the dashboard's numbers disagreed with the
    profiles they were supposedly summarising.
    """
    related = getattr(candidate, 'skills', None)
    if related:
        try:
            # Rows carry .skill_name; some callers hand in an already-flattened
            # list of strings. Accept both rather than silently returning [].
            skills = [
                s if isinstance(s, str) else s.skill_name
                for s in related
                if (s if isinstance(s, str) else getattr(s, 'skill_name', None))
            ]
            if skills:
                return skills
        except (AttributeError, TypeError) as e:
            logging.warning(f"Error accessing candidate skills: {str(e)}")

    # Fall back to parsed data if relationship is not available
    if parsed_data and 'skills' in parsed_data:
        skills_data = parsed_data['skills']
        if isinstance(skills_data, list):
            # Extract skill names as strings regardless of input format
            skills = []
            for skill in skills_data:
                if skill:  # Skip empty/None values
                    if isinstance(skill, dict):
                        skill_name = skill.get('name') or skill.get('skill_name')
                        if skill_name:
                            skills.append(str(skill_name))
                    else:
                        skills.append(str(skill))
            return skills
    
    return []

def enhance_experience_with_bullet_points(experience_list):
    """Enhance experience entries with bullet point metadata for better analysis."""
    if not experience_list or not isinstance(experience_list, list):
        return experience_list
    
    enhanced_experience = []
    for exp in experience_list:
        if isinstance(exp, dict):
            # Create a copy to avoid modifying the original
            enhanced_exp = exp.copy()
            
            # Get description for analysis
            description = exp.get('description', '')
            
            # Parse bullet points using the same logic as the Experience model
            bullets = []
            if isinstance(description, list):
                bullets = [item.strip() for item in description if item.strip()]
            elif description:
                if '\n' in description:
                    # Multi-line description - split by newlines (handle both single and double newlines)
                    lines = [line.strip() for line in re.split(r'\n+', description) if line.strip()]
                    bullets = lines
                elif any(marker in description for marker in ['•', '-', '*', '◦']):
                    # Has bullet markers - split by them
                    bullets = re.split(r'[•\-*◦]\s*', description)
                    bullets = [bullet.strip() for bullet in bullets if bullet.strip()]
                else:
                    # Single paragraph - split by sentences
                    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', description)
                    bullets = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]
            
            # Add bullet point metadata
            enhanced_exp['bullet_points'] = bullets
            enhanced_exp['bullet_count'] = len(bullets)
            enhanced_experience.append(enhanced_exp)
        else:
            enhanced_experience.append(exp)
    
    return enhanced_experience

@router.post("/", response_model=CandidateResponse)
async def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Create a new candidate."""
    # Check if candidate with the same email already exists
    existing_candidate = db.query(Candidate).filter(
        Candidate.email == candidate.email
    ).first()
    
    if existing_candidate:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate with email {candidate.email} already exists"
        )
    
    # Create new candidate
    db_candidate = Candidate(
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        headline=candidate.headline,
        source=candidate.source.value if candidate.source else None,
        status=candidate.status.value if isinstance(candidate.status, CandidateStatus) else candidate.status,
        position_applied=candidate.position_applied,
        job_id=candidate.job_id,
        notes=candidate.notes
    )
    
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    return db_candidate

@router.get("/skills_breakdown", response_model=Dict[str, int])
def get_skills_breakdown(db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)):
    """
    Get a breakdown/count of all skills across all candidates.
    Returns a dict: {"Python": 5, "SQL": 3, ...}
    """
    from collections import Counter
    skill_counts = Counter()
    candidates = db.query(Candidate).all()
    for candidate in candidates:
        if hasattr(candidate, 'skills') and candidate.skills:
            for skill in candidate.skills:
                if skill.skill_name:
                    skill_counts[skill.skill_name] += 1
    return dict(skill_counts)


# Must stay below every literal path in this router: FastAPI matches routes in
# registration order, so a "/{candidate_id}" declared first swallows
# "/skills_breakdown" and answers 404 for it.
@router.get("/{candidate_id}", response_model=CandidateResponse)
@async_timed
async def get_candidate_by_id(
    candidate_id: str,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Get a candidate by ID with populated skills and parsed resume data."""
    try:
        # Query candidate with eager loading of skills if available
        db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not db_candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate with ID {candidate_id} not found"
            )
        
        # Convert to dictionary
        candidate_dict = db_candidate.__dict__.copy()
        # Remove SQLAlchemy internal state
        candidate_dict.pop('_sa_instance_state', None)
        
        # Get the most recent resume for this candidate
        # Get most recent resume that has an associated file stored (file_id is not null)
        resume = (
            db.query(Resume)
            .filter(Resume.candidate_id == candidate_id, Resume.file_id.isnot(None))
            .order_by(Resume.created_at.desc())
            .first()
        )
        # Include resume id for frontend download button
        candidate_dict['resume_id'] = getattr(resume, 'id', None) if resume else None
        
        # Get job applications for this candidate
        from ..models.models import JobApplication
        job_applications = (
            db.query(JobApplication)
            .filter(JobApplication.candidate_id == candidate_id)
            .order_by(JobApplication.applied_at.desc())
            .all()
        )
        
        # Convert job applications to dictionaries
        candidate_dict['job_applications'] = []
        for app in job_applications:
            app_dict = {
                'id': app.id,
                'job_id': app.job_id,
                'status': app.status,
                'applied_at': app.applied_at.isoformat() if app.applied_at else None,
                'cover_letter': app.cover_letter,
                'source': app.source,
                'notes': app.notes
            }
            candidate_dict['job_applications'].append(app_dict)
        
        parsed_data = None
        if resume and resume.parsed_data:
            try:
                if isinstance(resume.parsed_data, str):
                    parsed_data = json.loads(resume.parsed_data)
                else:
                    parsed_data = resume.parsed_data
            except (json.JSONDecodeError, TypeError) as e:
                logging.warning(f"Error parsing resume data for candidate {candidate_id}: {str(e)}")
        
        # Format skills safely
        candidate_dict['skills'] = format_candidate_skills(db_candidate, parsed_data)
        
        # Add parsed data if available
        if parsed_data:
            # Enhance experience entries with bullet point metadata
            if 'experience' in parsed_data:
                parsed_data['experience'] = enhance_experience_with_bullet_points(parsed_data['experience'])
            
            candidate_dict['parsed_data'] = parsed_data
            
            # Update candidate info from parsed data if fields are empty
            personal_info = parsed_data.get('personal_info', {})
            
            if not candidate_dict.get('location') and personal_info.get('location'):
                candidate_dict['location'] = personal_info.get('location')
            
            if not candidate_dict.get('phone') and personal_info.get('phone'):
                candidate_dict['phone'] = personal_info.get('phone')
            
            # Update current position and company from most recent experience
            if (not candidate_dict.get('current_position') or not candidate_dict.get('current_company')) and parsed_data.get('experience'):
                # Get the most recent experience entry
                experience_list = parsed_data.get('experience', [])
                if experience_list:
                    try:
                        # Sort by end_date, putting 'Present' entries first
                        recent_exp = sorted(experience_list, 
                                          key=lambda x: (x.get('end_date') != 'Present', x.get('end_date') or '9999'), 
                                          reverse=False)
                        if recent_exp:
                            if not candidate_dict.get('current_position'):
                                candidate_dict['current_position'] = recent_exp[0].get('title')
                            if not candidate_dict.get('current_company'):
                                candidate_dict['current_company'] = recent_exp[0].get('company')
                    except Exception as e:
                        logging.warning(f"Error processing experience for candidate {candidate_id}: {str(e)}")
            
            # Ensure headline/summary is populated
            if not candidate_dict.get('headline') and parsed_data.get('summary'):
                summary = parsed_data.get('summary')
                if isinstance(summary, str):
                    headline = summary.split('\n')[0][:100]
                    if len(headline) < len(summary):
                        headline += '...'
                    candidate_dict['headline'] = headline
        
        # Ensure status has a default value if None
        if candidate_dict.get('status') is None:
            candidate_dict['status'] = 'active'
        
        # Handle None values for required fields
        if candidate_dict.get('first_name') is None:
            candidate_dict['first_name'] = ""
        if candidate_dict.get('last_name') is None:
            candidate_dict['last_name'] = ""
            
        # Handle empty email strings
        if candidate_dict.get('email') == '':
            candidate_dict['email'] = None
        
        # Ensure required fields have defaults
        candidate_dict.setdefault('created_at', datetime.utcnow())
        candidate_dict.setdefault('updated_at', datetime.utcnow())
        
        return CandidateResponse(**candidate_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving candidate {candidate_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while retrieving candidate: {str(e)}"
        )


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: str,
    candidate_update: CandidateUpdate,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Update an existing candidate."""
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not db_candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Update the fields that are provided
    update_data = candidate_update.dict(exclude_unset=True)
    
    # Convert Enum to string value if present
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].value
    
    if "source" in update_data and update_data["source"]:
        update_data["source"] = update_data["source"].value
    
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
    
    db.commit()
    db.refresh(db_candidate)
    
    return db_candidate

@router.delete("/{candidate_id}", response_model=MessageResponse)
async def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Delete a candidate and all related records avoiding problematic ORM relationships."""
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy import text
    
    try:
        # Check candidate exists using raw SQL to avoid loading relationships
        result = db.execute(text("SELECT id FROM candidates WHERE id = :candidate_id"), 
                          {"candidate_id": candidate_id})
        if not result.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Candidate with ID {candidate_id} not found"
            )

        logging.info(f"Starting deletion of candidate {candidate_id}")

        # Delete essential records with individual error handling to prevent transaction abort
        essential_operations = [
            ("DELETE FROM resumes WHERE candidate_id = :candidate_id", "resumes"),
            ("DELETE FROM candidate_skills WHERE candidate_id = :candidate_id", "skills"),
            ("DELETE FROM candidates WHERE id = :candidate_id", "candidate")
        ]
        
        for sql, description in essential_operations:
            try:
                result = db.execute(text(sql), {"candidate_id": candidate_id})
                logging.info(f"Deleted {result.rowcount} {description} for candidate {candidate_id}")
            except Exception as e:
                logging.warning(f"Failed to delete {description}: {str(e)}")
                # If any essential operation fails, rollback and restart transaction
                db.rollback()
                logging.info(f"Restarting transaction after {description} failure...")
                
                # Re-run successful operations in new transaction
                for retry_sql, retry_desc in essential_operations:
                    if retry_desc == description:
                        break  # Skip the one that failed and continue with remaining
                    try:
                        result = db.execute(text(retry_sql), {"candidate_id": candidate_id})
                        logging.info(f"Re-deleted {result.rowcount} {retry_desc} for candidate {candidate_id}")
                    except Exception as retry_e:
                        logging.warning(f"Retry failed for {retry_desc}: {str(retry_e)}")
                
                # Try the failed operation again (might work in new transaction)
                try:
                    result = db.execute(text(sql), {"candidate_id": candidate_id})
                    logging.info(f"Deleted {result.rowcount} {description} for candidate {candidate_id} (retry)")
                except Exception as retry_e:
                    logging.error(f"{description} deletion failed again: {str(retry_e)}")
                    if description == "candidate":  # Critical failure
                        raise HTTPException(status_code=500, detail=f"Failed to delete candidate: {str(retry_e)}")
        
        try:
            db.commit()
            logging.info(f"Successfully deleted candidate {candidate_id} (main transaction)")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to commit deletion: {str(e)}")
        
        # Optional cleanup in separate transaction (won't affect main deletion)
        try:
            result = db.execute(text("DELETE FROM candidate_pitches WHERE candidate_id = :candidate_id"),
                              {"candidate_id": candidate_id})
            db.commit()
            logging.info(f"Cleaned up {result.rowcount} pitches for candidate {candidate_id}")
        except Exception as e:
            db.rollback()
            logging.info(f"Pitch cleanup failed (table may not exist): {str(e)}")
        
        return {"message": f"Candidate with ID {candidate_id} and all related data deleted successfully"}
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except SQLAlchemyError as e:
        logging.error(f"Database error during deletion of candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error during deletion: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error during deletion of candidate {candidate_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/", response_model=CandidateSearchResponse)
def search_candidates(
    keyword: Optional[str] = None,
    status: Optional[CandidateStatus] = None,
    position: Optional[str] = None,
    skills: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Search for candidates with various filters."""
    try:
        logging.info(f"Searching candidates with filters: keyword={keyword}, status={status}, position={position}, skills={skills}")
        
        # Start with a simpler query - just get candidates first
        query = db.query(Candidate)
        
        # Apply filters
        if keyword:
            # Name, email, *and* the fields a recruiter actually searches by.
            # This used to cover first_name/last_name/email only, so the one
            # query that matters most -- "who knows Python" -- returned nothing
            # on a fully populated database while the UI offered to search by
            # skill and position.
            term = f"%{keyword}%"
            # EXISTS rather than a join: joining candidate_skills multiplies a
            # candidate by their skill count, which would both duplicate rows
            # and inflate the `total` used for pagination.
            has_skill = (
                db.query(CandidateSkill)
                .filter(
                    CandidateSkill.candidate_id == Candidate.id,
                    CandidateSkill.skill_name.ilike(term),
                )
                .exists()
            )
            query = query.filter(
                or_(
                    Candidate.first_name.ilike(term),
                    Candidate.last_name.ilike(term),
                    Candidate.email.ilike(term),
                    Candidate.headline.ilike(term),
                    Candidate.position_applied.ilike(term),
                    Candidate.current_position.ilike(term),
                    Candidate.current_company.ilike(term),
                    Candidate.location.ilike(term),
                    has_skill,
                )
            )
        
        if status:
            query = query.filter(Candidate.status == status.value)
        
        if position:
            query = query.filter(Candidate.position_applied.ilike(f"%{position}%"))
        
        if skills:
            # This should be implemented to filter by skills when skills model is available
            # For now, we'll just handle it as a keyword search in any text fields
            skill_list = [s.strip() for s in skills.split(',')]
            for skill in skill_list:
                query = query.filter(Candidate.headline.ilike(f"%{skill}%") | 
                                   Candidate.notes.ilike(f"%{skill}%"))
        
        # Apply sorting
        if hasattr(Candidate, sort_by):
            sort_column = getattr(Candidate, sort_by)
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        else:
            # Default to sort by id if attribute doesn't exist
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(Candidate.id))
            else:
                query = query.order_by(asc(Candidate.id))
        
        # Count total results before pagination
        total_count = query.count()
        logging.info(f"Found {total_count} candidates matching criteria")
        
        # Apply pagination
        offset = (page - 1) * page_size
        candidates = query.offset(offset).limit(page_size).all()
        
        # Convert candidates to response model format
        results = []
        for candidate in candidates:
            try:
                # Convert SQLAlchemy model to dictionary
                candidate_dict = candidate.__dict__.copy()
                # Remove SQLAlchemy internal state
                candidate_dict.pop('_sa_instance_state', None)
                
                # Handle skills safely using the new formatting function
                parsed_data = None
                try:
                    # Get parsed data if available - use a separate query to avoid N+1 problem
                    resume = db.query(Resume).filter(
                        Resume.candidate_id == candidate.id
                    ).order_by(Resume.created_at.desc()).first()
                    
                    if resume and resume.parsed_data:
                        if isinstance(resume.parsed_data, str):
                            parsed_data = json.loads(resume.parsed_data)
                        else:
                            parsed_data = resume.parsed_data
                except Exception as e:
                    logging.warning(f"Error getting parsed data for candidate {candidate.id}: {str(e)}")
                
                candidate_dict['skills'] = format_candidate_skills(candidate, parsed_data)
                
                # If location is missing on the candidate record, try to populate from parsed resume data
                try:
                    if (
                        not candidate_dict.get('location') or 
                        str(candidate_dict.get('location')).strip() in ['', '-', 'None']
                    ) and parsed_data and isinstance(parsed_data, dict):
                        personal_info = parsed_data.get('personal_info') or {}
                        loc = personal_info.get('location')
                        if loc:
                            candidate_dict['location'] = loc
                except Exception as e:
                    logging.warning(f"Error enriching location for candidate {candidate.id}: {str(e)}")

                # Ensure status has a default value if None
                if candidate_dict.get('status') is None:
                    candidate_dict['status'] = 'active'
                
                # Handle None values for required fields
                if candidate_dict.get('first_name') is None:
                    candidate_dict['first_name'] = ""
                if candidate_dict.get('last_name') is None:
                    candidate_dict['last_name'] = ""
                    
                # Handle empty email strings
                if candidate_dict.get('email') == '':
                    candidate_dict['email'] = None
                
                # Ensure required fields have defaults
                candidate_dict.setdefault('created_at', datetime.utcnow())
                candidate_dict.setdefault('updated_at', datetime.utcnow())
                
                # Add to results
                results.append(CandidateResponse(**candidate_dict))
                
            except Exception as e:
                logging.error(f"Error processing candidate {candidate.id}: {str(e)}")
                continue
        
        # Return the response
        return CandidateSearchResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            results=results
        )
    
    except Exception as e:
        logging.error(f"Error searching candidates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while searching candidates: {str(e)}"
        )


@router.post("/{candidate_id}/upload-resume", response_model=ResumeUploadResponse)
async def upload_candidate_resume(
    candidate_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Upload a resume for an existing candidate."""
    # Check if candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Validate file type
    file_type = file.filename.split(".")[-1].lower()
    if file_type not in ["pdf", "docx", "doc"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and Word documents are supported"
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        # Process the resume
        candidate_data = {
            "id": candidate.id,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "email": candidate.email,
            "phone": candidate.phone
        }
        
        resume = await resume_service.process_resume(
            db=db,
            file_path=temp_file_path,
            file_name=file.filename,
            file_type=file_type,
            candidate_data=candidate_data
        )
        
        return {
            "message": "Resume uploaded and processed successfully",
            "resume_id": resume.id,
            "candidate_id": resume.candidate_id
        }
    
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)

@router.get("/{candidate_id}/resumes", response_model=CandidateResumesResponse)
async def get_candidate_resumes(
    candidate_id: str,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Get all resumes for a candidate."""
    # Check if candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Get resumes
    resumes = db.query(Resume).filter(Resume.candidate_id == candidate_id).all()
    
    return {
        "candidate_id": candidate_id,
        "resumes": [
            {
                "id": resume.id,
                "file_name": resume.file_name,
                "file_type": resume.file_type,
                "created_at": resume.created_at
            }
            for resume in resumes
        ]
    }

@router.post("/{candidate_id}/parsed-resume", response_model=ParsedResumeSaveResponse)
async def save_parsed_resume_data(
    candidate_id: str,
    parsed_data: Dict[str, Any],
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Save parsed resume data for a candidate."""
    # Check if candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Get the most recent resume for this candidate
    resume = db.query(Resume).filter(
        Resume.candidate_id == candidate_id
    ).order_by(Resume.created_at.desc()).first()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail=f"No resume found for candidate with ID {candidate_id}"
        )
    
    # Extract the parsed_data from the request if it's nested
    actual_parsed_data = parsed_data.get("parsed_data", parsed_data)
    
    # Update the resume with parsed data
    resume.parsed_data = json.dumps(actual_parsed_data)
    
    # Update candidate information if available
    personal_info = actual_parsed_data.get("personal_info", {})
    
    # Only update empty fields
    update_needed = False
    
    if not candidate.phone and personal_info.get("phone"):
        candidate.phone = personal_info.get("phone")
        update_needed = True
    
    if not candidate.location and personal_info.get("location"):
        candidate.location = personal_info.get("location")
        update_needed = True
    
    # Extract skills if available
    if "skills" in actual_parsed_data and actual_parsed_data["skills"] and not candidate.skills:
        # `candidate.skills` is a relationship to CandidateSkill rows. This used
        # to assign `",".join(...)` to it, which SQLAlchemy raises on at flush --
        # so confirming a resume for a candidate with no skills yet was a 500.
        for skill_name in actual_parsed_data["skills"]:
            name = skill_name.get("name") if isinstance(skill_name, dict) else skill_name
            if name:
                candidate.skills.append(CandidateSkill(skill_name=str(name)))
        update_needed = True
    
    # Extract experience if available
    if "experience" in actual_parsed_data and actual_parsed_data["experience"]:
        # Update most recent job title and company if empty
        most_recent_exp = actual_parsed_data["experience"][0]
        if not candidate.current_position and most_recent_exp.get("title"):
            candidate.current_position = most_recent_exp.get("title")
            update_needed = True
        
        if not candidate.current_company and most_recent_exp.get("company"):
            candidate.current_company = most_recent_exp.get("company")
            update_needed = True
    
    # Save changes
    db.commit()
    
    return {
        "message": "Parsed resume data saved successfully",
        "resume_id": resume.id,
        "candidate_id": candidate_id,
        "candidate_updated": update_needed
    }
