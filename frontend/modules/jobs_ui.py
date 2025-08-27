import streamlit as st
import pandas as pd
import requests
from .job_utils import delete_job_api
from functools import lru_cache

def fetch_jobs(api_url: str):
    try:
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/jobs/"
        
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("results", []) if isinstance(data, dict) else []
        return jobs
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")
        return []

def display_active_jobs():
    st.subheader("Active Jobs")
    api_url = st.session_state.get("api_url", "http://localhost:8000")
    
    with st.spinner("Loading jobs from database..."):
        jobs = fetch_jobs(api_url)
        if not isinstance(jobs, list):
            st.error("Invalid data structure received from API.")
            return
        if len(jobs) == 0:
            st.info("No jobs found in the database.")
            return
        # st.write(f"Rendering {len(jobs)} jobs...")  # Commented out for production
        for idx, job in enumerate(jobs):
            col1, col2, col3 = st.columns([1, 10, 2])
            with col1:
                delete_key = f'delete_confirm_{job.get("id", idx)}'
                if st.session_state.get(delete_key):
                    st.warning(f"Are you sure you want to delete job '{job.get('title', 'this job')}'?")
                    yes, no = st.columns(2)
                    with yes:
                        if st.button('Yes', key=f'yes_{job.get("id", idx)}'):
                            success, msg = delete_job_api(job.get('id'))
                            if success:
                                st.success(msg)
                                st.session_state.pop(delete_key)
                                st.rerun()
                            else:
                                st.error(msg)
                    with no:
                        if st.button('No', key=f'no_{job.get("id", idx)}'):
                            st.session_state.pop(delete_key)
                            st.rerun()
                else:
                    if st.button('🗑️', key=f'del_{job.get("id", idx)}', help='Delete job'):
                        st.session_state[delete_key] = True
            with col2:
                st.markdown(render_job_card(job), unsafe_allow_html=True)
            with col3:
                if st.button("View Details", key=f"view_job_{job.get('id', idx)}"):
                    st.session_state.current_page = "job_detail"
                    st.session_state["view_job_id"] = job.get('id')
                    st.rerun()

def render_job_card(job):
    # Render job details as a card with proper Streamlit navigation
    return f"""
    <div style='border:1px solid #e0e0e0; border-radius:8px; padding:12px; margin-bottom:12px;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <b>{job.get('title', 'Job')}</b> <br>
                <b>Department:</b> {job.get('department', '-')}, <b>Location:</b> {job.get('location', '-')}, <b>Status:</b> {job.get('status', '-')}<br>
                <b>Posted:</b> {job.get('posted_date', '-')}, <b>Applicants:</b> {job.get('applicants', 0)}, <b>Shortlisted:</b> {job.get('shortlisted', 0)}
            </div>
        </div>
    </div>
    """
