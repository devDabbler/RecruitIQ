import streamlit as st
import httpx

async def fetch_jobs(api_url):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/jobs")
            response.raise_for_status()
            data = response.json()
            # Handle both paginated and non-paginated responses
            jobs = data.get("results", data) if isinstance(data, dict) else data
            return jobs
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")
        return None

def jobs_panel():
    st.subheader("📊 Hot Job Postings")
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    jobs = None
    with st.spinner("Loading jobs from backend..."):
        try:
            jobs = st.experimental_async(fetch_jobs)(api_url)
            if hasattr(jobs, "send"):
                jobs = st.run(jobs)
        except Exception as e:
            jobs = None
    if jobs is None:
        st.warning("Showing demo data. Backend jobs API unavailable.")
        jobs = [
            {"id": "job1", "title": "Senior Software Engineer", "applicants": "28", "views": "245", "days": "5"},
            {"id": "job2", "title": "Data Scientist", "applicants": "15", "views": "180", "days": "3"},
            {"id": "job3", "title": "Product Manager", "applicants": "20", "views": "210", "days": "7"},
        ]
    for i, job in enumerate(jobs):
        job_id = job.get('id', f"job_panel_{i}")
        with st.container(key=f"job_container_{job_id}"):
            st.markdown(f"**{job.get('title', 'Unknown Job')}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"👤 {job.get('applicants', job.get('num_applicants', '-'))}")
                st.caption("Applicants")
            with col2:
                st.caption(f"👁️ {job.get('views', job.get('num_views', '-'))}")
                st.caption("Views")
            with col3:
                st.caption(f"📅 {job.get('days', job.get('days_active', '-'))} days")
                st.caption("Active")
            st.divider()
