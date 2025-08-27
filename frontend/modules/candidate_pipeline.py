import streamlit as st
import httpx
from components.candidate_stages import candidate_stages_panel

async def fetch_all_candidates(api_url):
    """Fetch all candidates from the backend"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/candidates?limit=100")
            response.raise_for_status()
            data = response.json()
            candidates = data.get("results", data) if isinstance(data, dict) else data
            return candidates
    except Exception as e:
        st.error(f"Error fetching candidates: {str(e)}")
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

async def fetch_jobs(api_url):
    """Fetch all jobs from the backend"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/jobs")
            response.raise_for_status()
            data = response.json()
            jobs = data.get("results", data) if isinstance(data, dict) else data
            return jobs
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")
        return None

def page():
    """Candidate pipeline view page"""
    # st.title("Candidate Pipeline Overview")  # Removed duplicate header
    st.markdown("### Track candidates across all stages of the recruitment process")
    
    # Get API URL from session state
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    
    # Fetch all jobs
    jobs = None
    with st.spinner("Loading jobs..."):
        try:
            jobs = st.experimental_async(fetch_jobs)(api_url)
            if hasattr(jobs, "send"):
                jobs = st.run(jobs)
        except Exception as e:
            jobs = None
    
    if jobs is None:
        st.warning("Showing demo data. Backend jobs API unavailable.")
        jobs = [
            {"id": 1, "title": "Senior Software Engineer"},
            {"id": 2, "title": "Data Scientist"},
            {"id": 3, "title": "Product Manager"},
        ]
    
    # Add option to view all candidates or filter by job
    job_options = ["All Jobs"] + [f"{job.get('title')} (ID: {job.get('id')})" for job in jobs]
    selected_job = st.selectbox("Filter by Job", job_options)
    
    # Fetch candidates based on selection
    candidates = None
    
    if selected_job == "All Jobs":
        with st.spinner("Loading all candidates..."):
            try:
                candidates = st.experimental_async(fetch_all_candidates)(api_url)
                if hasattr(candidates, "send"):
                    candidates = st.run(candidates)
            except Exception as e:
                candidates = None
    else:
        # Extract job_id from the selection string
        import re
        job_id_match = re.search(r'ID: (\d+)', selected_job)
        if job_id_match:
            job_id = int(job_id_match.group(1))
            with st.spinner(f"Loading candidates for job {job_id}..."):
                try:
                    candidates = st.experimental_async(fetch_job_candidates)(api_url, job_id)
                    if hasattr(candidates, "send"):
                        candidates = st.run(candidates)
                except Exception as e:
                    candidates = None
    
    # If backend failed, use demo data
    if candidates is None:
        st.warning("Showing demo data. Backend candidates API unavailable.")
        # Create demo data with stage information
        candidates = [
            {"name": "Alex Thompson", "position": "Full Stack Developer", "matches": "92%", "stage": "New Application"},
            {"name": "Priya Patel", "position": "Data Engineer", "matches": "88%", "stage": "Recruiter Screen"},
            {"name": "James Wilson", "position": "Product Manager", "matches": "85%", "stage": "Interview 2"},
            {"name": "Linda Martinez", "position": "Marketing Specialist", "matches": "78%", "stage": "New Application"},
            {"name": "Michael Johnson", "position": "UX Designer", "matches": "90%", "stage": "Shortlisted"},
            {"name": "Sophia Rodriguez", "position": "Business Analyst", "matches": "82%", "stage": "Interview 1"},
            {"name": "Raj Patel", "position": "DevOps Engineer", "matches": "86%", "stage": "Final Interview"},
            {"name": "Emily Wilson", "position": "Frontend Developer", "matches": "89%", "stage": "Recruiter Screen"},
            {"name": "David Kim", "position": "Data Scientist", "matches": "91%", "stage": "Offer Stage"},
            {"name": "Sarah Miller", "position": "QA Engineer", "matches": "79%", "stage": "Resume Screening"},
            {"name": "Carlos Garcia", "position": "Backend Developer", "matches": "83%", "stage": "Background Check"},
            {"name": "Tina Chen", "position": "System Administrator", "matches": "75%", "stage": "Interview 3"}
        ]
    
    # Display the candidate pipeline visualization using our component
    candidate_stages_panel(candidates) 