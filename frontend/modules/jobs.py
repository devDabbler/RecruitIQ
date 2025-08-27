# frontend/modules/jobs.py
import streamlit as st
import pandas as pd
from datetime import datetime
from .jobs_ui import display_active_jobs

def page():
    """Jobs page content"""
    # Check if we're returning from job detail and explicitly reset the layout
    if st.session_state.get('returning_from_job_detail', False):
        # Force the layout to reset using more aggressive CSS
        st.markdown("""
        <style>
        body {
            width: 100% !important;
        }
        .main .block-container {
            max-width: 95% !important;
            width: 95% !important;
            padding: 1rem !important;
            margin: 0 auto !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Clear the flag so it doesn't persist
        del st.session_state['returning_from_job_detail']
    
    # All job management, creation, and analytics now use agentic backend endpoints.
    st.subheader("Jobs Management")
    tab1, tab2, tab3 = st.tabs(["Active Jobs", "Create Job", "Job Analytics"])
    with tab1:
        display_active_jobs()
    with tab2:
        create_job()
    with tab3:
        job_analytics()


def display_job_details(job):
    """Display detailed information for a selected job"""
    st.write("### Job Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Title:** {job['title']}")
        st.write(f"**Department:** {job['department']}")
        st.write(f"**Location:** {job['location']}")
        st.write(f"**Status:** {job['status']}")
    
    with col2:
        st.write(f"**Job ID:** {job['id']}")
        st.write(f"**Posted Date:** {job['posted_date']}")
        st.write(f"**Applicants:** {job['applicants']}")
        st.write(f"**Shortlisted:** {job['shortlisted']}")
    
    # Job actions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Edit Job"):
            st.write("Edit job functionality will be implemented here")
    with col2:
        if st.button("Close Job"):
            st.write("Close job functionality will be implemented here")
    with col3:
        if st.button("View Candidates"):
            st.write("View candidates functionality will be implemented here")

def create_job():
    """Create a new job posting"""
    st.subheader("Create New Job")
    
    # Form for job creation
    with st.form("job_creation_form"):
        # Basic job details
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Job Title")
            department = st.selectbox(
                "Department",
                ["Engineering", "Product", "Marketing", "Sales", "HR", "Finance", "Operations"]
            )
            employment_type = st.selectbox(
                "Employment Type",
                ["Full-time", "Part-time", "Contract", "Temporary", "Internship"]
            )
        
        with col2:
            location = st.text_input("Location")
            remote = st.selectbox(
                "Remote Work",
                ["On-site", "Remote", "Hybrid"]
            )
            experience_level = st.selectbox(
                "Experience Level",
                ["Entry", "Mid", "Senior", "Executive"]
            )
        
        # Salary range
        col1, col2 = st.columns(2)
        with col1:
            min_salary = st.number_input("Minimum Salary", min_value=0, value=50000)
        with col2:
            max_salary = st.number_input("Maximum Salary", min_value=0, value=100000)
        
        # Detailed job information
        st.write("### Job Details")
        job_overview = st.text_area("Job Overview")
        required_qualifications = st.text_area("Required Qualifications")
        
        # Submit button
        submitted = st.form_submit_button("Create Job")
        
        if submitted:
            import requests
            api_url = st.session_state.get("api_url", "http://localhost:8000/api")
            # Map user-friendly values to backend enums
            job_type_map = {
                "Full-time": "full_time",
                "Part-time": "part_time",
                "Contract": "contract",
                "Temporary": "temporary",
                "Internship": "internship",
                "Freelance": "freelance"
            }
            location_type_map = {
                "On-site": "on_site",
                "Remote": "remote",
                "Hybrid": "hybrid"
            }
            experience_level_map = {
                "Entry": "entry",
                "Mid": "mid",
                "Senior": "senior",
                "Lead": "lead",
                "Executive": "executive"
            }
            job_data = {
                "title": title,
                "department": department,
                "job_overview": job_overview,
                "required_qualifications": required_qualifications,
                "location": location,
                "location_type": location_type_map.get(remote, "on_site"),
                "job_type": job_type_map.get(employment_type, "full_time"),
                "experience_level": experience_level_map.get(experience_level, "entry"),
                "min_salary": min_salary,
                "max_salary": max_salary,
                "status": "draft",  # Default to draft
                "hiring_manager": None,
                "recruiter": None,
                "application_deadline": None,
                "start_date": None,
                "job_metadata": {},
                "skills": []
            }
            try:
                response = requests.post(f"{api_url}/jobs", json=job_data, timeout=10)
                if response.status_code == 201:
                    st.success(f"Job '{title}' created successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to create job (status {response.status_code}): {response.text}")
            except Exception as e:
                st.error(f"Error creating job: {str(e)}")

def job_analytics():
    """Display analytics for jobs"""
    st.subheader("Job Analytics")
    
    # Mock data for demonstration
    
    # Time to fill metrics
    st.write("### Time to Fill (Days)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Engineering", "45", "-5")
    with col2:
        st.metric("Product", "38", "-2")
    with col3:
        st.metric("Marketing", "30", "+3")
    with col4:
        st.metric("Overall", "38", "-3")
    
    # Application sources
    st.write("### Application Sources")
    source_data = {
        "source": ["LinkedIn", "Company Website", "Indeed", "Referral", "Other"],
        "value": [45, 30, 15, 8, 2]
    }
    
    source_df = pd.DataFrame(source_data)
    st.bar_chart(source_df, x="source", y="value")
    
    # Applicant funnel
    st.write("### Applicant Funnel")
    funnel_data = {
        "stage": ["Applications", "Screening", "Interview", "Offer", "Hired"],
        "count": [150, 75, 30, 12, 8]
    }
    
    funnel_df = pd.DataFrame(funnel_data)
    st.bar_chart(funnel_df, x="stage", y="count")
