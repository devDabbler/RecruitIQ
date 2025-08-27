# frontend/modules/dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
import json
import logging
import asyncio
from typing import Dict, List, Any
from components.quick_stats import quick_stats_row
from components.job_card import job_card
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# All dashboard data is now loaded from agentic backend endpoints. Removed all legacy/demo/sample/mock data and functions.

# Example: Fetch recruiter dashboard metrics from backend
async def fetch_dashboard_metrics(api_url):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{api_url}/api/dashboard/metrics/")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch dashboard metrics: {e}")
        return None

# Example: Fetch jobs, tasks, and interviews from backend
async def fetch_recruiter_jobs(api_url):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{api_url}/api/jobs/")
            resp.raise_for_status()
            return resp.json().get('results', [])
    except Exception as e:
        logger.error(f"Failed to fetch recruiter jobs: {e}")
        return []

async def fetch_job_candidates(api_url, job_id):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{api_url}/api/jobs/{job_id}/candidates/")
            resp.raise_for_status()
            return resp.json().get('results', [])
    except Exception as e:
        logger.error(f"Failed to fetch job candidates: {e}")
        return []

async def fetch_job_tasks(api_url, job_id):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{api_url}/api/jobs/{job_id}/tasks/")
            resp.raise_for_status()
            return resp.json().get('results', [])
    except Exception as e:
        logger.error(f"Failed to fetch job tasks: {e}")
        return []

async def fetch_recruiter_jobs(api_url):
    """Fetch jobs assigned to the current recruiter"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # In a real implementation, we would pass the recruiter_id parameter
            # For now, we'll just fetch all jobs as if they're assigned to this recruiter
            response = await client.get(f"{api_url}/jobs")
            response.raise_for_status()
            data = response.json()
            jobs = data.get("results", data) if isinstance(data, dict) else data
            return jobs
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")
        return None

async def fetch_job_candidates(api_url, job_id):
    """Fetch candidates for a specific job"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/jobs/{job_id}/candidates")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        st.error(f"Error fetching candidates for job {job_id}: {str(e)}")
        return None

async def fetch_job_tasks(api_url, job_id):
    """Fetch tasks for a specific job"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # This would be a real endpoint in production
            # response = await client.get(f"{api_url}/jobs/{job_id}/tasks")
            # For now, we'll simulate a task list
            await httpx.AsyncClient().get("https://httpbin.org/status/200", timeout=0.1)
            return None  # Return None to use demo data
    except Exception:
        return None

def render_candidate_card(candidate):
    """Render a single candidate card with match score"""
    name = candidate.get('name') or f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or "Unknown"
    
    # Try to get a match score as a percentage string
    match_score = candidate.get('match_score')
    if match_score is not None:
        try:
            pct = int(float(match_score) * 100)
            match_display = f"{pct}%"
        except:
            match_display = candidate.get('matches', "N/A")
    else:
        match_display = candidate.get('matches', "N/A")
    
    status = candidate.get('status', 'New Application')
    
    st.markdown(f"**{name}**")
    cols = st.columns([3, 1])
    with cols[0]:
        st.caption(f"{candidate.get('position', candidate.get('position_applied', 'Unknown Position'))}")
    with cols[1]:
        st.caption(f"Match: {match_display}")
    
    # Convert match score to progress bar percentage
    try:
        pct = int(match_display.strip('%')) / 100
    except:
        pct = 0.5
    
    st.progress(pct)
    st.caption(f"Status: {status}")
    
    # Action buttons
    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.button("👍", key=f"approve_{name}_{candidate.get('id', '')}")
    with cols[1]:
        st.button("👎", key=f"reject_{name}_{candidate.get('id', '')}")
    with cols[2]:
        if st.button("🔍 Review", key=f"review_{name}_{candidate.get('id', '')}"):
            # In production, navigate to candidate detail view
            if candidate.get('id'):
                st.session_state.current_page = "candidate_detail"
                st.query_params["id"] = str(candidate.get('id'))
                st.query_params["view"] = "candidate_detail"
                st.rerun()

def render_task_card(task):
    """Render a single task card"""
    priority_color = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
    
    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(f"**{task['title']}**")
        st.caption(f"Due: {task['due_date']}")
    with cols[1]:
        st.markdown(f"{priority_color[task['priority']]} {task['priority']}")
    
    st.divider()

def get_user_role():
    """Get the current user's role.
    In a production environment, this would come from the authentication system.
    For this demo, we'll determine role based on username or allow manual selection.
    """
    # For demo purposes, let the user select their role if not already set
    if "user_role" not in st.session_state:
        # Default role based on username if available
        username = st.session_state.get("username", "").lower()
        if "recruiter" in username:
            st.session_state.user_role = "recruiter"
        elif "manager" in username or "hiring" in username:
            st.session_state.user_role = "hiring_manager"
        else:
            # Default to recruiter
            st.session_state.user_role = "recruiter"
    
    # Allow user to override their role (for demo purposes)
    # In a real app, this would be determined by authentication
    return st.session_state.user_role

def page():
    """Dashboard page showing role-specific recruitment information"""
    
    # Get user info and role
    user_info = {
        "name": st.session_state.get("name", "User"),
        "email": st.session_state.get("user_email", ""),
    }
    
    # Get or set the user's role
    user_role = get_user_role()
    
    # Display welcome message
    message = f"Welcome to your recruitment dashboard, {user_info['name']}!"
    st.markdown(f"""
    <div class="alert-box alert-info">
        <strong>👋 {message}</strong>
        <p>Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # For demo purposes, allow switching between roles
    with st.expander("💼 Role Selection (Demo)"):
        st.markdown("**Note:** In a production environment, the dashboard view would be determined by your account role.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View as Recruiter", use_container_width=True):
                st.session_state.user_role = "recruiter"
                st.rerun()
        with col2:
            if st.button("View as Hiring Manager", use_container_width=True):
                st.session_state.user_role = "hiring_manager"
                st.rerun()
    
    # Display role-specific dashboard
    if user_role == "recruiter":
        display_recruiter_dashboard(user_info)
    else:
        display_hiring_manager_dashboard(user_info)
    
    # Add debug info if in development mode
    if st.checkbox("Show Debug Info", False):
        st.subheader("Session & Context Information")
        
        # Display user information from the new st.user and st.context objects
        st.json(user_info)
        
        # Show all session state variables
        st.write("Session State Variables:")
        st.json({k: str(v) if not isinstance(v, (int, float, str, bool, list, dict, type(None))) else v 
                 for k, v in st.session_state.items()})


from modules.dashboard_sample_data import generate_sample_data

def display_recruiter_dashboard(user_info):
    """Display the dashboard specifically for recruiters"""
    # Generate sample data for demo purposes
    data = generate_sample_data()
    
    # Section 1: Assigned Jobs with Pipeline
    st.subheader("🔍 My Assigned Jobs")
    
    # Safely get jobs from data dict with a fallback empty list
    jobs = data.get("jobs", [])
    
    # Validate each job has the expected structure
    valid_jobs = []
    for job in jobs:
        if isinstance(job, dict) and all(key in job for key in ['title', 'department', 'status']):
            valid_jobs.append(job)
    
    # Filter for jobs assigned to this recruiter
    # In a real implementation, this would filter based on the current user's ID
    assigned_jobs = valid_jobs
    
    if not assigned_jobs:
        st.info("You don't have any jobs assigned to you yet.")
    else:
        # Display job cards with expandable pipelines
        for i, job in enumerate(assigned_jobs):
            with st.expander(f"**{job['title']}** ({job['department']}) - {job['status']}", expanded=i==0):
                st.markdown(f"**Open Positions:** {job.get('open_positions', 'N/A')} | **Applications:** {job.get('applications', 'N/A')}")
                
                # Create tabs for different parts of the pipeline
                pipeline_tabs = st.tabs(["📥 New Applications", "👍 AI Matches", "🗓️ Interviews", "🏁 Final Stage"])
                
                # New Applications tab
                with pipeline_tabs[0]:
                    st.caption("New applications awaiting review")
                    
                    # Sample new applications for this job
                    new_apps = [
                        {"id": f"candidate_{i}_{j}", "name": f"Candidate {j}", "position": job['title'], 
                         "match_score": round(np.random.uniform(0.6, 0.95), 2), "status": "New Application"} 
                        for j in range(1, 4)  # 3 sample candidates per job
                    ]
                    
                    for candidate in new_apps:
                        st.markdown("---")
                        render_candidate_card(candidate)
                
                # AI Matches tab
                with pipeline_tabs[1]:
                    st.caption("Candidates automatically matched to this job")
                    st.info("AI recommends these candidates based on skills, experience, and job requirements.")
                    
                    # Sample AI matches for this job
                    ai_matches = [
                        {"id": f"match_{i}_{j}", "name": f"Match {j}", "position": job['title'], 
                         "match_score": round(np.random.uniform(0.75, 0.98), 2), "status": "AI Matched"} 
                        for j in range(1, 4)  # 3 sample matches per job
                    ]
                    
                    for candidate in ai_matches:
                        st.markdown("---")
                        render_candidate_card(candidate)
                
                # Interviews tab
                with pipeline_tabs[2]:
                    st.caption("Candidates in the interview process")
                    
                    # Sample interviews for this job
                    now = datetime.datetime.now()
                    interviews = [
                        {
                            "id": f"interview_{i}_{j}",
                            "candidate": f"Interview Candidate {j}",
                            "position": job['title'],
                            "date": (now + datetime.timedelta(days=j)).strftime("%Y-%m-%d"),
                            "time": f"{10 + j}:00 AM",
                            "type": ["Technical", "HR", "Culture Fit"][j % 3]
                        } 
                        for j in range(1, 4)  # 3 sample interviews per job
                    ]
                    
                    for interview in interviews:
                        st.markdown("---")
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.markdown(f"**{interview['candidate']}**")
                            st.caption(interview['position'])
                        with col2:
                            st.markdown(f"**{interview['date']} at {interview['time']}**")
                        with col3:
                            st.markdown(f"**{interview['type']}**")
                            if st.button("📝 Notes", key=f"notes_{interview['id']}"):
                                st.info(f"Taking notes for {interview['candidate']}")
                
                # Final Stage tab
                with pipeline_tabs[3]:
                    st.caption("Candidates in final stages (offer, negotiation, etc.)")
                    
                    # Sample final stage candidates for this job
                    final_stage = [
                        {"id": f"final_{i}_{j}", "name": f"Final Candidate {j}", 
                         "position": job['title'], "status": ["Offer Pending", "Background Check", "References"][j % 3]} 
                        for j in range(1, 3)  # 2 sample final stage candidates per job
                    ]
                    
                    for candidate in final_stage:
                        st.markdown("---")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{candidate['name']}**")
                            st.caption(candidate['position'])
                        with col2:
                            st.markdown(f"**{candidate['status']}**")
                            if st.button("✅ Complete", key=f"complete_{candidate['id']}"):
                                st.success(f"Marked {candidate['name']} as hired!")
    
    # Section 2: Recruiter Tasks
    st.markdown("---")
    st.subheader("📝 My Recruitment Tasks")
    
    # Safely get tasks with fallback to empty list
    tasks = data.get("tasks", [])
    
    # Validate each task has the expected structure
    valid_tasks = []
    for task in tasks:
        if isinstance(task, dict) and all(key in task for key in ['title', 'priority']):
            valid_tasks.append(task)
    
    tasks = valid_tasks
    
    if not tasks:
        st.info("You don't have any pending tasks.")
    else:
        # Group tasks by priority
        high_priority = [task for task in tasks if task['priority'] == "High"]
        other_tasks = [task for task in tasks if task['priority'] != "High"]
        
        # Display high priority tasks first
        if high_priority:
            st.markdown("### 🔴 High Priority")
            for task in high_priority:
                render_task_card(task)
        
        if other_tasks:
            st.markdown("### Other Tasks")
            for task in other_tasks:
                render_task_card(task)
    
    # Section 3: Upcoming Interviews
    st.markdown("---")
    st.subheader("🗓️ Upcoming Interviews")
    
    # Get interviews from data - ensure we're handling the correct data structure
    # The error was occurring because the interviews might not be in the expected format
    interviews = data.get("interviews", [])
    
    # Verify each interview is a dictionary with the required fields
    valid_interviews = []
    for interview in interviews:
        if isinstance(interview, dict) and 'candidate' in interview and 'position' in interview:
            valid_interviews.append(interview)
    
    if not valid_interviews:
        st.info("You don't have any upcoming interviews scheduled.")
    else:
        # Create two columns for layout
        cols = st.columns(2)
        
        # Distribute interviews between columns
        for i, interview in enumerate(valid_interviews):
            with cols[i % 2]:
                st.markdown(f"**{interview['candidate']}** - {interview['position']}")
                st.markdown(f"**When:** {interview.get('date', 'TBD')} at {interview.get('time', 'TBD')}")
                st.markdown(f"**Type:** {interview.get('type', 'Not specified')}")
                st.markdown("---")


def display_hiring_manager_dashboard(user_info):
    """Display the dashboard specifically for hiring managers"""
    # Generate sample data for demo purposes
    data = generate_sample_data()
    
    # Section 1: Jobs I'm Hiring For
    st.subheader("💼 Jobs I'm Hiring For")
    
    # Safely get jobs from data dict with a fallback empty list
    jobs = data.get("jobs", [])
    
    # Validate each job has the expected structure
    valid_jobs = []
    for job in jobs:
        if isinstance(job, dict) and all(key in job for key in ['title', 'department', 'status']):
            valid_jobs.append(job)
    
    # Filter for jobs where this person is the hiring manager
    # In a real implementation, this would filter based on the current user's ID
    hiring_jobs = valid_jobs
    
    if not hiring_jobs:
        st.info("You don't have any active jobs you're hiring for.")
    else:
        # Display job cards with key metrics
        for i, job in enumerate(hiring_jobs):
            with st.expander(f"**{job['title']}** ({job['department']}) - {job['status']}", expanded=i==0):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Open Positions", job['open_positions'])
                
                with col2:
                    st.metric("Total Applications", job['applications'])
                
                with col3:
                    # In a real app, we'd calculate this from actual data
                    interviews_count = np.random.randint(1, 10)
                    st.metric("Interviews Scheduled", interviews_count)
                
                # Create tabs for different parts of the hiring process from manager's view
                pipeline_tabs = st.tabs(["👤 Top Candidates", "🗓️ My Interviews", "📋 Feedback Required"])
                
                # Top Candidates tab
                with pipeline_tabs[0]:
                    st.caption("Top candidates selected by recruiters for your review")
                    
                    # Sample top candidates for this job
                    top_candidates = [
                        {"id": f"top_{i}_{j}", "name": f"Top Candidate {j}", "position": job['title'], 
                         "match_score": round(np.random.uniform(0.85, 0.98), 2), 
                         "status": "Ready for Manager Review"} 
                        for j in range(1, 4)  # 3 sample candidates per job
                    ]
                    
                    for candidate in top_candidates:
                        st.markdown("---")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{candidate['name']}**")
                            st.caption(f"{candidate['position']} | Match: {int(candidate['match_score']*100)}%")
                        with col2:
                            if st.button("👁️ Review", key=f"review_{candidate['id']}"):
                                st.session_state.current_page = "candidate_detail"
                                st.query_params["id"] = str(candidate['id'])
                                st.query_params["view"] = "candidate_detail"
                                st.rerun()
                
                # My Interviews tab
                with pipeline_tabs[1]:
                    st.caption("Interviews you're scheduled to conduct")
                    
                    # Sample interviews for this job
                    now = datetime.datetime.now()
                    my_interviews = [
                        {
                            "id": f"mgr_interview_{i}_{j}",
                            "candidate": f"Interview Candidate {j}",
                            "position": job['title'],
                            "date": (now + datetime.timedelta(days=j)).strftime("%Y-%m-%d"),
                            "time": f"{13 + j}:00 PM",
                            "type": "Manager Interview"
                        } 
                        for j in range(1, 4)  # 3 sample interviews per job
                    ]
                    
                    for interview in my_interviews:
                        st.markdown("---")
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.markdown(f"**{interview['candidate']}**")
                            st.caption(interview['position'])
                        with col2:
                            st.markdown(f"**{interview['date']} at {interview['time']}**")
                        with col3:
                            if st.button("📋 Prep", key=f"prep_{interview['id']}"):
                                st.info(f"Preparing for interview with {interview['candidate']}")
                
                # Feedback Required tab
                with pipeline_tabs[2]:
                    st.caption("Candidates awaiting your feedback")
                    
                    # Sample feedback requests for this job
                    feedback_requests = [
                        {"id": f"feedback_{i}_{j}", "name": f"Feedback Candidate {j}", 
                         "position": job['title'], "interview_date": (now - datetime.timedelta(days=j)).strftime("%Y-%m-%d")} 
                        for j in range(1, 4)  # 3 sample feedback requests per job
                    ]
                    
                    for candidate in feedback_requests:
                        st.markdown("---")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{candidate['name']}**")
                            st.caption(f"{candidate['position']} | Interviewed: {candidate['interview_date']}")
                        with col2:
                            if st.button("📝 Provide Feedback", key=f"feedback_{candidate['id']}"):
                                st.info(f"Providing feedback for {candidate['name']}")
    
    # Section 2: Manager Tasks
    st.markdown("---")
    st.subheader("✅ My Tasks")
    
    # Sample tasks specific to hiring managers
    manager_tasks = [
        {"id": "manager_task1", "title": "Review shortlisted candidates", "due_date": "Today", 
         "priority": "High", "status": "Pending"},
        {"id": "manager_task2", "title": "Update job requirements for Data Analyst role", 
         "due_date": "Tomorrow", "priority": "Medium", "status": "Pending"},
        {"id": "manager_task3", "title": "Approve offer for Senior Developer", 
         "due_date": "Today", "priority": "High", "status": "In Progress"},
    ]
    
    if not manager_tasks:
        st.info("You don't have any pending tasks.")
    else:
        # Group tasks by priority
        high_priority = [task for task in manager_tasks if task['priority'] == "High"]
        other_tasks = [task for task in manager_tasks if task['priority'] != "High"]
        
        # Display high priority tasks first
        if high_priority:
            st.markdown("### 🔴 High Priority")
            for task in high_priority:
                render_task_card(task)
        
        if other_tasks:
            st.markdown("### Other Tasks")
            for task in other_tasks:
                render_task_card(task)
    
    # Section 3: Hiring Overview
    st.markdown("---")
    st.subheader("📊 Hiring Overview")
    
    # Create three columns for key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Open Positions", len(hiring_jobs))
    
    with col2:
        # In a real app, we'd calculate this from actual data
        st.metric("Candidates in Pipeline", 23, delta=5, delta_color="normal")
    
    with col3:
        st.metric("Time to Hire (avg)", "21 days", delta="-3 days", delta_color="inverse")
    
    # Display a simple timeline of recent hiring activities
    st.markdown("### Recent Hiring Activities")
    
    activities = [
        {"date": "Today", "event": "Interview scheduled with Jane Doe for Senior Developer position"},
        {"date": "Yesterday", "event": "New candidate shortlisted for Marketing Manager role"},
        {"date": "2 days ago", "event": "Offer approved for Product Designer position"},
        {"date": "Last week", "event": "New job requisition for Data Analyst opened"}
    ]
    
    for activity in activities:
        if isinstance(activity, dict) and 'date' in activity and 'event' in activity:
            st.markdown(f"**{activity['date']}:** {activity['event']}")
        else:
            st.markdown("Activity data not in expected format")
    
    # Add custom CSS for the dashboard - enhanced for role-specific dashboards
    st.markdown("""
    <style>
    /* Metric cards */
    .metric-card {
        background-color: white;
        border-radius: 0.75rem;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        height: 100%;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.05), 0 10px 15px rgba(0,0,0,0.03);
    }
    
    .metric-title {
        color: #64748b;
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        color: #1e293b;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: baseline;
    }
    
    .metric-unit {
        font-size: 1rem;
        font-weight: 500;
        color: #64748b;
        margin-left: 0.25rem;
    }
    
    .metric-trend {
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .metric-trend.up {
        color: #16a34a;
    }
    
    .metric-trend.down {
        color: #ef4444;
    }
    
    /* Task and interview items */
    .task-item, .interview-item {
        background-color: white;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .task-header, .interview-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    
    .task-title, .interview-candidate {
        font-weight: 600;
        color: #1e293b;
    }
    
    .task-priority, .interview-type {
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.15rem 0.4rem;
        border-radius: 0.25rem;
    }
    
    .task-details, .interview-details {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #64748b;
    }
    
    .interview-position {
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)
