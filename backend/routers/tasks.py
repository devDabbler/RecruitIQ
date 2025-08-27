from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date
import uuid

# Initialize router
router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Not found"}},
)

# Define Task models
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str  # High, Medium, Low
    due_date: date
    due_time: Optional[str] = None
    category: Optional[str] = None
    recruiter_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_id: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: str
    completed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Mock database for now - would be replaced with real database in production
TASKS_DB = [
    {
        "id": str(uuid.uuid4()),
        "title": "Review resume for Software Engineer position",
        "description": "Review John Smith's resume for the Senior Software Engineer position",
        "priority": "High",
        "due_date": date.today(),
        "due_time": "14:00",
        "category": "Candidate Review",
        "recruiter_id": "user123",
        "job_id": "job456",
        "candidate_id": "cand789",
        "completed": False,
        "created_at": datetime.now(),
        "updated_at": None,
        "completed_at": None
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Schedule final interview with John Smith",
        "description": "Schedule final interview with John Smith for the Software Engineer position",
        "priority": "High",
        "due_date": date.today(),
        "due_time": "17:00",
        "category": "Interview Prep",
        "recruiter_id": "user123",
        "job_id": "job456",
        "candidate_id": "cand789",
        "completed": False,
        "created_at": datetime.now(),
        "updated_at": None,
        "completed_at": None
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Provide feedback on Marketing Manager candidates",
        "description": "Review and provide feedback on the current Marketing Manager candidates",
        "priority": "Medium",
        "due_date": date.today(),
        "due_time": "EOD",
        "category": "Candidate Review",
        "recruiter_id": "user123",
        "job_id": "job789",
        "candidate_id": None,
        "completed": False,
        "created_at": datetime.now(),
        "updated_at": None,
        "completed_at": None
    }
]

@router.get("/", response_model=List[Task])
async def get_tasks(
    completed: bool = Query(False, description="Filter by completion status"),
    priority: Optional[str] = Query(None, description="Filter by priority (High, Medium, Low)"),
    due_date: Optional[date] = Query(None, description="Filter by due date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    recruiter_id: Optional[str] = Query(None, description="Filter by recruiter ID")
):
    """
    Retrieve all tasks, with optional filtering.
    """
    # Apply filters
    filtered_tasks = TASKS_DB.copy()
    
    if completed is not None:
        filtered_tasks = [task for task in filtered_tasks if task["completed"] == completed]
    
    if priority:
        filtered_tasks = [task for task in filtered_tasks if task["priority"] == priority]
    
    if due_date:
        filtered_tasks = [task for task in filtered_tasks if task["due_date"] == due_date]
    
    if category:
        filtered_tasks = [task for task in filtered_tasks if task["category"] == category]
    
    if recruiter_id:
        filtered_tasks = [task for task in filtered_tasks if task["recruiter_id"] == recruiter_id]
    
    return filtered_tasks

@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str = Path(..., description="The ID of the task to retrieve")):
    """
    Retrieve a specific task by ID.
    """
    for task in TASKS_DB:
        if task["id"] == task_id:
            return task
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.post("/", response_model=Task, status_code=201)
async def create_task(task: TaskCreate):
    """
    Create a new task.
    """
    new_task = {
        "id": str(uuid.uuid4()),
        **task.dict(),
        "completed": False,
        "created_at": datetime.now(),
        "updated_at": None,
        "completed_at": None
    }
    
    TASKS_DB.append(new_task)
    return new_task

@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str = Path(..., description="The ID of the task to update"),
    task_update: TaskBase = None
):
    """
    Update an existing task.
    """
    for i, task in enumerate(TASKS_DB):
        if task["id"] == task_id:
            updated_task = {**task, **task_update.dict(exclude_unset=True), "updated_at": datetime.now()}
            TASKS_DB[i] = updated_task
            return updated_task
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}/complete", response_model=Task)
async def complete_task(task_id: str = Path(..., description="The ID of the task to mark as complete")):
    """
    Mark a task as completed.
    """
    for i, task in enumerate(TASKS_DB):
        if task["id"] == task_id:
            updated_task = {**task, "completed": True, "completed_at": datetime.now(), "updated_at": datetime.now()}
            TASKS_DB[i] = updated_task
            return updated_task
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str = Path(..., description="The ID of the task to delete")):
    """
    Delete a task.
    """
    for i, task in enumerate(TASKS_DB):
        if task["id"] == task_id:
            TASKS_DB.pop(i)
            return
    
    raise HTTPException(status_code=404, detail="Task not found")

@router.get("/job/{job_id}", response_model=List[Task])
async def get_tasks_for_job(job_id: str = Path(..., description="The job ID to get tasks for")):
    """
    Get all tasks related to a specific job.
    """
    return [task for task in TASKS_DB if task["job_id"] == job_id]

@router.get("/candidate/{candidate_id}", response_model=List[Task])
async def get_tasks_for_candidate(candidate_id: str = Path(..., description="The candidate ID to get tasks for")):
    """
    Get all tasks related to a specific candidate.
    """
    return [task for task in TASKS_DB if task["candidate_id"] == candidate_id] 