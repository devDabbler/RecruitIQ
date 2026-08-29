"""Resume API Router
Handles resume parsing, storage, and retrieval endpoints
"""

import os
import logging
import uuid
import json
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, Response
from pydantic import BaseModel

from ..services.service_registry import provide_storage_service, provide_minio_storage_service, provide_resume_service
from backend.services.agent_framework.agent_factory import AgentFactory
from ..utils.resume_parsing import ResumeData
from backend.utils.auth import ROLE_ADMIN, get_optional_user
from backend.utils.database import get_db
from backend.utils.parse_quota import enforce_parse_quota
from backend.models.models import Job
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/resume", tags=["resume"])
logger = logging.getLogger(__name__)


def require_write_access_for_save(save_to_db: bool, current_user) -> None:
    """Guard the one write hiding inside an otherwise read-only endpoint.

    `/parse` is on the read-only allowlist in `utils/auth.py` because parsing a
    resume touches nothing — unless `save_to_db=true`, which a multipart form
    field the path-based gate cannot see. So the check lives here instead.
    """
    if not save_to_db:
        return
    if current_user is not None and current_user.role == ROLE_ADMIN:
        return
    raise HTTPException(
        status_code=403 if current_user is not None else 401,
        detail="Saving a parsed resume requires an administrator account.",
    )


class PreviewUrlResponse(BaseModel):
    """API response model for resume preview URL"""
    url: str
    content_type: str
    file_name: str
    file_id: str
    expires_in_seconds: int = 3600


class ResumeResponse(BaseModel):
    """API response model for resume parsing"""
    candidate_id: Optional[str] = None
    resume_id: Optional[int] = None
    file_id: Optional[str] = None
    personal_info: Optional[Dict[str, Any]] = None
    education: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[Dict[str, Any]]] = None
    parsed_data: Optional[Dict[str, Any]] = None
    military: Optional[List[Dict[str, Any]]] = None
    # Target-role analysis. Populated only when the caller supplied a job title;
    # the agent computed these all along, but until Phase 3c the router dropped
    # them and the fit scoring was invisible to the UI.
    job_fit_score: Optional[float] = None
    hiring_recommendation: Optional[Dict[str, Any]] = None
    market_alignment: Optional[Dict[str, Any]] = None
    quality_assessment: Optional[Dict[str, Any]] = None
    skill_suggestions: Optional[Dict[str, Any]] = None
    success: bool = True
    message: str = "Resume parsed successfully"


class ResumeConfirmRequest(BaseModel):
    """Request model for resume confirmation"""
    # Support both old format (resume_data) and new format (separate fields)
    resume_data: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = {"save_to_database": False, "create_candidate": False}
    
    # New format fields
    resume_id: Optional[int] = None
    personal_info: Optional[Dict[str, Any]] = None
    education: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[Dict[str, Any]]] = None
    military: Optional[List[Dict[str, Any]]] = None  # Changed from Dict to List to match database model


class ResumeConfirmResponse(BaseModel):
    """Response model for resume confirmation"""
    success: bool
    message: str
    candidate_id: Optional[str] = None
    resume_id: Optional[int] = None


@router.get("/{resume_id}/preview", response_model=PreviewUrlResponse)
async def get_resume_preview(
    resume_id: int,
    direct_download: bool = Query(False, description="If true, redirects directly to the file"),
    resume_service = Depends(provide_resume_service),
    minio_storage_service = Depends(provide_minio_storage_service)
):
    """Generate a pre-signed URL for previewing a resume file.
    
    If direct_download=True, redirects directly to the pre-signed URL.
    Otherwise, returns the URL as JSON.
    """
    try:
        # Get the resume from the database
        conn = None
        from backend.database.db_connection import get_postgres_connection
        try:
            conn = get_postgres_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT file_id, file_name, file_type FROM resumes WHERE id = %s", (resume_id,))
                row = cur.fetchone()
                
                if not row:
                    raise HTTPException(status_code=404, detail=f"Resume with ID {resume_id} not found")
                
                file_id_raw = row[0] if isinstance(row, tuple) else row['file_id']
                # Decode if file_id comes as memoryview/bytes
                # Normalize file_id to a clean UUID string (no spaces)
                try:
                    if isinstance(file_id_raw, memoryview):
                        raw_bytes = file_id_raw.tobytes()
                        # If it's 16 bytes, treat as UUID bytes
                        if len(raw_bytes) == 16:
                            file_id = str(uuid.UUID(bytes=raw_bytes))
                        else:
                            file_id = raw_bytes.decode(errors="ignore").strip()
                    elif isinstance(file_id_raw, bytes):
                        if len(file_id_raw) == 16:
                            file_id = str(uuid.UUID(bytes=file_id_raw))
                        else:
                            file_id = file_id_raw.decode(errors="ignore").strip()
                    else:
                        file_id = str(file_id_raw).strip()
                except Exception as norm_err:
                    logger.warning(f"Error normalizing file_id from DB: {norm_err}; raw value: {file_id_raw}")
                    file_id = str(file_id_raw).replace(' ', '')
                file_name = row[1] if isinstance(row, tuple) else row['file_name']
                file_type = row[2] if isinstance(row, tuple) else row['file_type']
                
                if not file_id:
                    raise HTTPException(status_code=404, detail=f"File ID not found for resume {resume_id}")
                
                # Check if file_name is None, which might indicate an incomplete record
                if not file_name:
                    logger.warning(f"Resume {resume_id} has file_id {file_id} but no file_name. This may indicate a corrupted record.")
                
        finally:
            if conn:
                conn.close()
        
        try:
            # Generate pre-signed URL for the resume file
            file_info = await minio_storage_service.get_document_presigned_url(file_id)
            
            # Return the URL or redirect
            if direct_download:
                return RedirectResponse(url=file_info["url"])
            
            return {
                "url": file_info["url"],
                "content_type": file_info["content_type"],
                "file_name": file_info["file_name"],
                "file_id": file_info["file_id"],
                "expires_in_seconds": 3600  # URL valid for 1 hour
            }
        except FileNotFoundError:
            # More user-friendly error when the physical file is missing
            logger.error(f"Physical file for resume {resume_id} (file_id: {file_id}) not found in MinIO storage")
            raise HTTPException(
                status_code=404, 
                detail=f"The resume file appears to be missing from storage. Please contact support and reference ID: {resume_id}."
            )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    except HTTPException:
        # Re-raise HTTP exceptions directly to preserve their status codes
        raise
    except Exception as e:
        logging.error(f"Error generating preview URL for resume {resume_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate preview URL: {str(e)}")


@router.post("/parse", response_model=ResumeResponse)
async def parse_resume(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    save_to_db: bool = Form(False),
    target_job_title: Optional[str] = Form(None),
    job_id: Optional[int] = Form(None),
    candidate_context: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_optional_user),
    _quota: None = Depends(enforce_parse_quota),
):
    """Parse a resume file and optionally save to database, now using Agentic Zero agent

    `job_id` names a real requisition and is the preferred way to ask for a fit
    score: the resume is then measured against the skills that job actually
    requires. `target_job_title` remains for roles that are not in the database,
    but a free-text title can only be scored against similar jobs and a static
    fallback list, which is a weaker claim. When both arrive, job_id wins.
    """
    require_write_access_for_save(save_to_db, current_user)

    # Resolved before the try below, which converts anything that escapes it
    # into a 500. A bad job_id is a client error and has to survive as one.
    resolved_job = None
    if job_id is not None:
        resolved_job = db.query(Job).filter(Job.id == job_id).first()
        if not resolved_job:
            # Deliberately not falling back to the free-text path. Silently
            # scoring against "roles like this one" while the caller believes it
            # asked about a specific opening is the exact failure this parameter
            # exists to remove.
            raise HTTPException(
                status_code=400,
                detail=f"No job with ID {job_id} exists to score against.",
            )

    try:
        # Check file extension
        _, file_extension = os.path.splitext(file.filename)
        supported_formats = [".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png"]
        if file_extension.lower() not in supported_formats:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
                }
            )
        # Use the agentic zero ResumeProcessingAgent
        resume_agent = AgentFactory.create_agent("resume")
        
        # Process job context if provided
        job_title = target_job_title
        job_data = None

        # A named requisition takes precedence over everything else: it is the
        # only input that lets the fit score reference real requirements.
        if resolved_job is not None:
            job_data = {
                "title": resolved_job.title,
                "department": resolved_job.department,
                "job_overview": resolved_job.job_overview,
                "required_qualifications": resolved_job.required_qualifications,
                "experience_level": resolved_job.experience_level,
                "skills": resolved_job.skills,
            }
            job_title = resolved_job.title
            logger.info(f"Scoring resume against job {job_id} ('{resolved_job.title}')")

        # Parse candidate_context JSON if provided. Skipped when a real job was
        # named, so a stale context blob cannot override the requisition.
        if candidate_context and resolved_job is None:
            try:
                context_data = json.loads(candidate_context)
                if isinstance(context_data, dict):
                    # Extract job title from context if not explicitly provided
                    if not job_title and 'job_title' in context_data:
                        job_title = context_data.get('job_title')
                    elif not job_title and 'target_job' in context_data and isinstance(context_data['target_job'], dict):
                        job_title = context_data['target_job'].get('title')
                    
                    # Log what we're doing
                    logger.info(f"Processing resume with job context - Title: {job_title}, Context: {candidate_context[:100]}...")
                    
                    # Store full job data for more detailed analysis
                    job_data = context_data.get('job_data', context_data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid candidate_context JSON: {candidate_context}")
        
        # Final check - log what we're using
        if job_title:
            logger.info(f"Will analyze resume against job title: '{job_title}'")
        else:
            logger.warning("No job title available for resume analysis - job fit cannot be determined")
                
        result = await resume_agent.process_resume(file, db=db, save_to_db=save_to_db, candidate_id=candidate_id, 
                                               target_job_title=job_title, job_data=job_data)
        
        # Convert to response model
        # Defensive: ensure resume_id is always present
        resume_id = result.get("resume_id")
        if resume_id is None:
            resume_id = -1  # fallback value
        response = ResumeResponse(
            candidate_id=candidate_id,
            resume_id=resume_id,
            file_id=result["file_id"],
            parsed_data=result.get("parsed_data"),
            personal_info=result.get("parsed_data", {}).get("personal_info") if isinstance(result.get("parsed_data"), dict) else None,
            education=result.get("parsed_data", {}).get("education") if isinstance(result.get("parsed_data"), dict) else None,
            experience=result.get("parsed_data", {}).get("experience") if isinstance(result.get("parsed_data"), dict) else None,
            skills=result.get("parsed_data", {}).get("skills") if isinstance(result.get("parsed_data"), dict) else None,
            military=result.get("parsed_data", {}).get("military") if isinstance(result.get("parsed_data"), dict) else None,
            job_fit_score=result.get("job_fit_score") if job_title else None,
            hiring_recommendation=result.get("hiring_recommendation") if job_title else None,
            market_alignment=result.get("market_alignment"),
            quality_assessment=result.get("quality_assessment"),
            skill_suggestions=result.get("skill_suggestions"),
            success=True,
            message="Resume parsed successfully"
        )
        
        # Debug logging for experience section
        logger.debug(f"API Response - parsed_data keys: {list(result.get('parsed_data', {}).keys()) if isinstance(result.get('parsed_data'), dict) else 'None'}")
        logger.debug(f"API Response - experience present: {bool(response.experience)}, experience count: {len(response.experience) if response.experience else 0}")
        if response.experience and len(response.experience) > 0:
            logger.debug(f"API Response - First experience item: {response.experience[0]}")
        else:
            logger.debug("API Response - No experience items found")
            
            # Check if experience data exists in the raw parsed_data
            experience_in_parsed = result.get("parsed_data", {}).get("experience") if isinstance(result.get("parsed_data"), dict) else None
            logger.debug(f"Raw parsed_data experience: {bool(experience_in_parsed)}, type: {type(experience_in_parsed)}, count: {len(experience_in_parsed) if experience_in_parsed else 0}")
        
        return response
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error parsing resume: {str(e)}"
            }
        )


@router.post("/parse-direct", response_model=ResumeResponse)
async def parse_resume_direct(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    save_to_db: bool = Form(False),
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service),
    current_user = Depends(get_optional_user),
    _quota: None = Depends(enforce_parse_quota),
):
    """Parse a resume file using direct resume service (no agent)"""
    require_write_access_for_save(save_to_db, current_user)
    try:
        # Check file extension
        _, file_extension = os.path.splitext(file.filename)
        supported_formats = [".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png"]
        if file_extension.lower() not in supported_formats:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
                }
            )
        
        # Use direct resume service parsing (no agent)
        result = await resume_service.parse_resume_upload_no_save(file, strategy='comprehensive')
        
        # Convert to response model
        resume_id = result.get("resume_id", -1)  # fallback value
        response = ResumeResponse(
            candidate_id=candidate_id,
            resume_id=resume_id,
            file_id=result.get("file_id"),
            parsed_data=result.get("parsed_data"),
            personal_info=result.get("parsed_data", {}).get("personal_info") if isinstance(result.get("parsed_data"), dict) else None,
            education=result.get("parsed_data", {}).get("education") if isinstance(result.get("parsed_data"), dict) else None,
            experience=result.get("parsed_data", {}).get("experience") if isinstance(result.get("parsed_data"), dict) else None,
            skills=result.get("parsed_data", {}).get("skills") if isinstance(result.get("parsed_data"), dict) else None,
            military=result.get("parsed_data", {}).get("military") if isinstance(result.get("parsed_data"), dict) else None,
            success=True,
            message="Resume parsed successfully using direct service"
        )
        
        return response
    except Exception as e:
        logger.error(f"Error parsing resume with direct service: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error parsing resume: {str(e)}"
            }
        )


class SaveCandidateResponse(BaseModel):
    """API response model for saving a reviewed parse as a candidate."""
    success: bool = True
    candidate_id: Optional[str] = None
    resume_id: Optional[int] = None
    message: str = "Candidate saved"


@router.post("/save-candidate", response_model=SaveCandidateResponse)
async def save_candidate_from_parse(
    file: UploadFile = File(...),
    parsed_data: str = Form(...),
    position_applied: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service),
):
    """Persist a reviewed parse: upsert the candidate, store the file, save the resume.

    Takes the parse the client already has instead of re-running the model, so a
    save is a few hundred milliseconds rather than another LLM round trip.

    Deliberately NOT in READ_ONLY_POST_PATHS: the app-wide `enforce_read_only`
    gate refuses anonymous callers (401) and the demo role (403) before this
    handler runs, so only an administrator can reach it.
    """
    import tempfile

    from sqlalchemy import text as sql_text

    try:
        data = json.loads(parsed_data)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        resume_model = ResumeData.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"parsed_data is not a valid parse payload: {e}")

    _, extension = os.path.splitext(file.filename or "")
    file_type = extension.lstrip(".").lower()
    supported_formats = ["pdf", "docx", "doc", "txt", "jpg", "jpeg", "png"]
    if file_type not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {extension}. Supported formats: {', '.join(supported_formats)}",
        )

    # Store the original file so the profile's resume list can preview it.
    content = await file.read()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        file_id = await resume_service.storage_service.store_document(
            file_path=tmp_path,
            file_name=file.filename,
            content_type=resume_service._get_content_type(file_type),
            metadata={},
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    try:
        resume_id = resume_service.save_resume(
            resume_data=resume_model,
            db_session=db,
            file_id=file_id,
            file_name=file.filename,
            file_type=file_type,
        )
    except Exception as e:
        logger.error(f"Saving candidate from parse failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save the candidate: {e}")

    row = db.execute(
        sql_text("SELECT candidate_id FROM resumes WHERE id = :id"), {"id": resume_id}
    ).fetchone()
    candidate_id = row[0] if row else None

    # The role the recruiter parsed against is the role they are considering
    # the person for; record it unless the candidate already has one.
    if candidate_id and position_applied and position_applied.strip():
        db.execute(
            sql_text(
                "UPDATE candidates SET position_applied = :position "
                "WHERE id = :id AND (position_applied IS NULL OR position_applied = '')"
            ),
            {"position": position_applied.strip(), "id": candidate_id},
        )
    db.commit()

    return SaveCandidateResponse(
        candidate_id=candidate_id,
        resume_id=resume_id,
        message="Candidate saved to the pipeline",
    )


@router.post("/confirm", response_model=ResumeConfirmResponse)
async def confirm_resume(
    request: ResumeConfirmRequest,
    db: Session = Depends(get_db),
    resume_service = Depends(provide_resume_service)
):
    """Confirm and save parsed resume data to database"""
    try:
        # Handle both old format and new format
        if request.resume_id:
            # New format: resume_id provided separately
            resume_id = request.resume_id
            confirmed_data = {}
            
            # Build confirmed_data from individual fields
            if request.personal_info:
                confirmed_data['personal_info'] = request.personal_info
                logger.info(f"Personal info type: {type(request.personal_info)}, data: {request.personal_info}")
            if request.education:
                confirmed_data['education'] = request.education
                logger.info(f"Education type: {type(request.education)}, length: {len(request.education)}")
            if request.experience:
                confirmed_data['experience'] = request.experience
                logger.info(f"Experience type: {type(request.experience)}, length: {len(request.experience)}")
            if request.skills:
                confirmed_data['skills'] = request.skills
                logger.info(f"Skills type: {type(request.skills)}, length: {len(request.skills)}")
            if request.military:
                confirmed_data['military'] = request.military
                logger.info(f"Military type: {type(request.military)}, data: {request.military}")
                
            logger.info(f"Using new format - resume_id: {resume_id}")
            logger.info(f"Confirmed data structure: {list(confirmed_data.keys())}")
            logger.debug(f"Full confirmed data: {confirmed_data}")
        else:
            # Old format: extract resume_id from resume_data
            if not request.resume_data:
                raise HTTPException(status_code=400, detail="Either resume_id or resume_data must be provided")
            
            resume_id = request.resume_data.get('resume_id')
            confirmed_data = request.resume_data
            logger.info(f"Using old format - resume_id: {resume_id}")
        
        # If resume_id is missing, create a new resume record from the confirmed data
        if not resume_id:
            logger.info("resume_id not provided – creating a new resume entry from confirmed data")
            try:
                # Convert the confirmed_data dict to a ResumeData model for save_resume()
                from backend.utils.resume_parsing.models.resume_schema import ResumeData
                resume_model = ResumeData.model_validate(confirmed_data) if isinstance(confirmed_data, dict) else ResumeData.model_validate(dict(confirmed_data))

                # Persist the resume and obtain a new ID
                # Pass through file_id if present so storage reference is maintained
                file_id_param = confirmed_data.get('file_id') if isinstance(confirmed_data, dict) else None
                resume_id = resume_service.save_resume(resume_model, db, file_id=file_id_param)
                logger.info(f"Created new resume with id {resume_id} from confirmed data")
            except Exception as create_err:
                logger.error(f"Failed to create resume from confirmed data: {create_err}", exc_info=True)
                raise HTTPException(status_code=500, detail="Unable to create resume from confirmed data")
        
        # Get settings from request
        settings = request.settings or {}
        save_to_database = settings.get("save_to_database", False)
        create_candidate = settings.get("create_candidate", False)
        
        # Confirm and update the resume data
        candidate_id = resume_service.confirm_resume_data(resume_id, confirmed_data, db, save_to_database, create_candidate)
        if candidate_id is None:
            raise HTTPException(status_code=404, detail=f"Resume with ID {resume_id} not found")
        
        return ResumeConfirmResponse(
            success=True,
            message="Resume confirmed and saved successfully",
            resume_id=resume_id,
            candidate_id=candidate_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming resume: {str(e)}", exc_info=True)
        # Log additional request information for debugging
        logger.error(f"Request data: resume_id={request.resume_id}, has_resume_data={bool(request.resume_data)}, military={bool(request.military)}")
        
        # Check for validation errors
        if hasattr(e, 'errors'):
            logger.error(f"Validation errors: {e.errors()}")
            
        raise HTTPException(
            status_code=500,
            detail=f"Error confirming resume: {str(e)}"
        )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: int, db: Session = Depends(get_db), resume_service = Depends(provide_resume_service)):
    """Retrieve a parsed resume by ID"""
    try:
        # Get the resume from database
        resume_data = await resume_service.get_resume(db, resume_id)

        if not resume_data:
            # get_resume() returns None both for "no such row" and for "the row
            # is there but its parsed_data will not load". Those want different
            # answers: a 404 on a resume the Candidate Detail screen just linked
            # to reads as a broken link rather than as bad stored data.
            from backend.models.models import Resume as ResumeRow

            exists = db.query(ResumeRow.id).filter(ResumeRow.id == resume_id).first()
            if exists:
                logger.error(
                    "Resume %s exists but its parsed_data could not be loaded", resume_id
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Resume {resume_id} is stored but its parsed data is unreadable",
                )
            raise HTTPException(status_code=404, detail=f"Resume with ID {resume_id} not found")

        # Convert to response model
        response = ResumeResponse(
            resume_id=resume_id,
            success=True,
            message="Resume retrieved successfully"
        )
        
        # Add resume data to response
        if resume_data.personal_info:
            response.personal_info = resume_data.personal_info.dict()
        
        if resume_data.education:
            response.education = [edu.dict() for edu in resume_data.education]
        
        if resume_data.experience:
            response.experience = [exp.dict() for exp in resume_data.experience]
        
        if resume_data.skills:
            response.skills = [skill.dict() for skill in resume_data.skills]
        
        if resume_data.military:
            response.military = [mil.dict() for mil in resume_data.military]
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving resume {resume_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving resume: {str(e)}")


# Registered as two routes rather than api_route(methods=["GET", "HEAD"]).
# FastAPI derives one operationId from whichever method it pops off that set
# first and then gives it to both operations, so the id collided *and* changed
# between processes with Python's hash seed — which made openapi.json
# non-reproducible and broke the CI drift check before it was even written.
@router.get("/{resume_id}/view", operation_id="view_resume_pdf")
@router.head("/{resume_id}/view", operation_id="head_resume_pdf")
async def view_resume_pdf(
    resume_id: int,
    request: Request,
    minio_storage_service = Depends(provide_minio_storage_service)
):
    """Stream a resume file directly for viewing with PDF.js.
    
    This endpoint retrieves the resume file from storage and streams it directly to the client,
    allowing it to be viewed in a PDF.js viewer without cross-origin restrictions.
    """
    try:
        # Get the resume from the database
        conn = None
        from backend.database.db_connection import get_postgres_connection
        try:
            conn = get_postgres_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT file_id, file_name, file_type FROM resumes WHERE id = %s", (resume_id,))
                row = cur.fetchone()
                
                if not row:
                    raise HTTPException(status_code=404, detail=f"Resume with ID {resume_id} not found")
                
                file_id_raw = row[0] if isinstance(row, tuple) else row['file_id']
                # Normalize file_id to a clean UUID string (no spaces)
                try:
                    if isinstance(file_id_raw, memoryview):
                        raw_bytes = file_id_raw.tobytes()
                        # If it's 16 bytes, treat as UUID bytes
                        if len(raw_bytes) == 16:
                            file_id = str(uuid.UUID(bytes=raw_bytes))
                        else:
                            file_id = raw_bytes.decode(errors="ignore").strip()
                    elif isinstance(file_id_raw, bytes):
                        if len(file_id_raw) == 16:
                            file_id = str(uuid.UUID(bytes=file_id_raw))
                        else:
                            file_id = file_id_raw.decode(errors="ignore").strip()
                    else:
                        file_id = str(file_id_raw).strip()
                except Exception as norm_err:
                    logger.warning(f"Error normalizing file_id from DB: {norm_err}; raw value: {file_id_raw}")
                    file_id = str(file_id_raw).replace(' ', '')
                
                if not file_id:
                    raise HTTPException(status_code=404, detail=f"File ID not found for resume {resume_id}")
                
        finally:
            if conn:
                conn.close()
        
        try:
            # For HEAD requests, we only need to verify the file exists, not return content
            if request.method == "HEAD":
                # Just check if the file exists
                await minio_storage_service.get_document_info(file_id)
                # Return an empty response with 200 status code
                return Response(status_code=200)
            else:
                # For GET requests, stream the file content
                file_stream, file_info = await minio_storage_service.get_document_stream(file_id)
                
                # Return the file as a streaming response
                return StreamingResponse(
                    content=file_stream,
                    media_type=file_info["content_type"],
                    headers={
                        "Content-Disposition": f"inline; filename=\"resume_{resume_id}.pdf\""
                    }
                )
        except FileNotFoundError:
            logger.error(f"Physical file for resume {resume_id} (file_id: {file_id}) not found in MinIO storage")
            raise HTTPException(
                status_code=404, 
                detail=f"The resume file appears to be missing from storage. Please contact support and reference ID: {resume_id}."
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions directly to preserve their status codes
        raise
    except Exception as e:
        logging.error(f"Error streaming resume {resume_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stream resume: {str(e)}")


# Test endpoint
@router.get("/test", tags=["debug"])
def test_resume_endpoint():
    """Test endpoint for resume router"""
    return {"status": "ok", "message": "Resume router is working"}
