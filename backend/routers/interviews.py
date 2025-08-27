from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date, time, timedelta
import uuid

# Initialize router
router = APIRouter(
    prefix="/interviews",
    tags=["interviews"],
    responses={404: {"description": "Not found"}},
)

# Define Interview models
class InterviewBase(BaseModel):
    candidate_id: str
    job_id: str
    date: date
    time: time
    stage: str  # Initial Screening, Technical, Culture Fit, Final Round
    duration: str
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    interviewers: List[str] = []

class InterviewCreate(InterviewBase):
    pass

class InterviewUpdate(BaseModel):
    date: Optional[date] = None
    time: Optional[time] = None
    stage: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    interviewers: Optional[List[str]] = None

class Interview(InterviewBase):
    id: str
    candidate_name: str
    position: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed: bool = False
    feedback: Optional[str] = None
    status: Optional[str] = None  # Scheduled, Completed, Canceled, No-show

    class Config:
        from_attributes = True

# Mock database for now - would be replaced with real database in production
today = datetime.now()
INTERVIEWS_DB = [
    {
        "id": str(uuid.uuid4()),
        "candidate_id": "cand123",
        "candidate_name": "Emma Johnson",
        "job_id": "job456",
        "position": "Senior Data Scientist",
        "date": today.date(),
        "time": today.time().replace(hour=11, minute=30),
        "stage": "Technical",
        "duration": "1 hour",
        "location": "Virtual",
        "meeting_link": "https://meet.example.com/interview-1",
        "notes": "Focus on Python, SQL, and machine learning experience.",
        "interviewers": ["John Smith", "Maria Garcia"],
        "created_at": today - timedelta(days=2),
        "updated_at": None,
        "completed": False,
        "feedback": None,
        "status": "Scheduled"
    },
    {
        "id": str(uuid.uuid4()),
        "candidate_id": "cand456",
        "candidate_name": "Michael Chen",
        "job_id": "job789",
        "position": "Frontend Developer",
        "date": today.date(),
        "time": today.time().replace(hour=15, minute=0),
        "stage": "Final",
        "duration": "1.5 hours",
        "location": "Virtual",
        "meeting_link": "https://meet.example.com/interview-2",
        "notes": "Review portfolio and React experience. Discuss senior role possibilities.",
        "interviewers": ["Sarah Lee", "Robert Johnson"],
        "created_at": today - timedelta(days=3),
        "updated_at": None,
        "completed": False,
        "feedback": None,
        "status": "Scheduled"
    },
    {
        "id": str(uuid.uuid4()),
        "candidate_id": "cand789",
        "candidate_name": "Sophia Rodriguez",
        "job_id": "job123",
        "position": "UX Designer",
        "date": (today + timedelta(days=1)).date(),
        "time": today.time().replace(hour=10, minute=0),
        "stage": "Portfolio Review",
        "duration": "1 hour",
        "location": "In-person",
        "meeting_link": None,
        "notes": "Ask about experience with design systems and user research.",
        "interviewers": ["John Smith"],
        "created_at": today - timedelta(days=1),
        "updated_at": None,
        "completed": False,
        "feedback": None,
        "status": "Scheduled"
    }
]

@router.get("/", response_model=List[Interview])
async def get_interviews(
    date_from: Optional[date] = Query(None, description="Filter by start date"),
    date_to: Optional[date] = Query(None, description="Filter by end date"),
    stage: Optional[str] = Query(None, description="Filter by interview stage"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    completed: Optional[bool] = Query(None, description="Filter by completion status")
):
    """
    Retrieve all interviews, with optional filtering.
    """
    # Apply filters
    filtered_interviews = INTERVIEWS_DB.copy()
    
    if date_from:
        filtered_interviews = [i for i in filtered_interviews if i["date"] >= date_from]
    
    if date_to:
        filtered_interviews = [i for i in filtered_interviews if i["date"] <= date_to]
    
    if stage:
        filtered_interviews = [i for i in filtered_interviews if i["stage"] == stage]
    
    if job_id:
        filtered_interviews = [i for i in filtered_interviews if i["job_id"] == job_id]
    
    if candidate_id:
        filtered_interviews = [i for i in filtered_interviews if i["candidate_id"] == candidate_id]
    
    if completed is not None:
        filtered_interviews = [i for i in filtered_interviews if i["completed"] == completed]
    
    return filtered_interviews

@router.get("/{interview_id}", response_model=Interview)
async def get_interview(interview_id: str = Path(..., description="The ID of the interview to retrieve")):
    """
    Retrieve a specific interview by ID.
    """
    for interview in INTERVIEWS_DB:
        if interview["id"] == interview_id:
            return interview
    
    raise HTTPException(status_code=404, detail="Interview not found")

@router.post("/", response_model=Interview, status_code=201)
async def create_interview(interview: InterviewCreate):
    """
    Schedule a new interview.
    """
    # In a real implementation, we would validate the candidate and job IDs
    # and fetch their names from the database
    
    new_interview = {
        "id": str(uuid.uuid4()),
        **interview.dict(),
        "candidate_name": "Demo Candidate",  # Would be fetched from DB in real implementation
        "position": "Demo Position",  # Would be fetched from DB in real implementation
        "created_at": datetime.now(),
        "updated_at": None,
        "completed": False,
        "feedback": None,
        "status": "Scheduled"
    }
    
    INTERVIEWS_DB.append(new_interview)
    return new_interview

@router.put("/{interview_id}", response_model=Interview)
async def update_interview(
    interview_id: str = Path(..., description="The ID of the interview to update"),
    interview_update: InterviewUpdate = None
):
    """
    Update an existing interview.
    """
    for i, interview in enumerate(INTERVIEWS_DB):
        if interview["id"] == interview_id:
            # Get non-None values from the update
            update_data = {k: v for k, v in interview_update.dict().items() if v is not None}
            updated_interview = {**interview, **update_data, "updated_at": datetime.now()}
            INTERVIEWS_DB[i] = updated_interview
            return updated_interview
    
    raise HTTPException(status_code=404, detail="Interview not found")

@router.patch("/{interview_id}/complete", response_model=Interview)
async def complete_interview(
    interview_id: str = Path(..., description="The ID of the interview to mark as complete"),
    feedback: Optional[str] = None,
    status: str = "Completed"
):
    """
    Mark an interview as completed and provide feedback.
    """
    for i, interview in enumerate(INTERVIEWS_DB):
        if interview["id"] == interview_id:
            updated_interview = {
                **interview,
                "completed": True,
                "feedback": feedback,
                "status": status,
                "updated_at": datetime.now()
            }
            INTERVIEWS_DB[i] = updated_interview
            return updated_interview
    
    raise HTTPException(status_code=404, detail="Interview not found")

@router.delete("/{interview_id}", status_code=204)
async def delete_interview(interview_id: str = Path(..., description="The ID of the interview to delete")):
    """
    Delete an interview.
    """
    for i, interview in enumerate(INTERVIEWS_DB):
        if interview["id"] == interview_id:
            INTERVIEWS_DB.pop(i)
            return
    
    raise HTTPException(status_code=404, detail="Interview not found")

@router.get("/candidate/{candidate_id}", response_model=List[Interview])
async def get_interviews_for_candidate(candidate_id: str = Path(..., description="The candidate ID to get interviews for")):
    """
    Get all interviews for a specific candidate.
    """
    return [interview for interview in INTERVIEWS_DB if interview["candidate_id"] == candidate_id]

@router.get("/job/{job_id}", response_model=List[Interview])
async def get_interviews_for_job(job_id: str = Path(..., description="The job ID to get interviews for")):
    """
    Get all interviews for a specific job.
    """
    return [interview for interview in INTERVIEWS_DB if interview["job_id"] == job_id] 