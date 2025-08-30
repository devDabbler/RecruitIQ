import logging
from typing import Any, Dict, List, Optional

import requests
import urllib.parse
import streamlit as st

try:
    import httpx
except ImportError:
    httpx = None

from frontend.utils.ui_helpers import display_skills_badges

# Configuration
LOG_LEVEL = logging.INFO
NAV_ITEMS = [
    ("📊 Dashboard", "dashboard"),
    ("📄 Resume Upload", "resume_upload"),
    ("💼 Jobs", "jobs"),
    ("👥 Candidates", "candidates"),
    ("🤖 Assistant", "assistant"),
]
STATUS_COLORS = {
    "active": "#10b981",
    "screening": "#3b82f6",
    "interviewing": "#8b5cf6",
    "offered": "#f59e0b",
    "hired": "#059669",
    "rejected": "#ef4444",
    "withdrawn": "#6b7280",
    "on_hold": "#f97316",
}

# Setup logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def get_status_color(status: str) -> str:
    """Return a color based on candidate status."""
    return STATUS_COLORS.get(status.lower(), STATUS_COLORS["withdrawn"])


def fetch_candidate(api_url: str, candidate_id: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """Fetch candidate data synchronously using cached httpx client when available."""
    url = f"{api_url.rstrip('/')}/candidates/{candidate_id}"
    try:
        logger.info("Fetching candidate %s from %s", candidate_id, url)
        try:
            from frontend.utils.http_client import get_sync_client
            client = get_sync_client()
        except Exception:
            client = None

        if client and httpx:
            resp = client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        else:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Error fetching candidate %s: %s", candidate_id, e)
        return None


def render_nav() -> None:
    """Render the top navigation bar with unique keys per page."""
    cols = st.columns(len(NAV_ITEMS))
    for col, (label, page_name) in zip(cols, NAV_ITEMS):
        with col:
            key = f"nav_detail_{page_name}"
            if st.button(label, key=key):
                st.session_state.current_page = page_name
                st.rerun()
    st.markdown("---")


def render_basic_info(candidate: Dict[str, Any]) -> None:
    """Render the candidate's basic header information."""
    col1, col2 = st.columns([3, 1])
    name = f"{candidate.get('first_name','')} {candidate.get('last_name','')}".strip() or "Unknown Candidate"
    with col1:
        st.header(name)
        st.caption(candidate.get('headline', ''))
    with col2:
        status = candidate.get('status', '').upper()
        color = get_status_color(candidate.get('status', ''))
        st.markdown(
            f"<div style='background:{color};color:white;padding:6px 12px;"
            f"border-radius:20px;font-size:14px;text-align:center;'>{status}</div>",
            unsafe_allow_html=True,
        )


def render_profile(candidate: Dict[str, Any]) -> None:
    """Render the Profile tab."""
    st.subheader("Contact Information")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Email:**", candidate.get('email', '-'))
        st.write("**Phone:**", candidate.get('phone', '-'))
    with col2:
        st.write("**Location:**", candidate.get('location', '-'))
        st.write("**Source:**", candidate.get('source', '-'))

    st.subheader("Application Information")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Position Applied:**", candidate.get('position_applied', '-'))
        st.write("**Job ID:**", candidate.get('job_id', '-'))
    with col2:
        st.write("**Created:**", candidate.get('created_at', '-'))
        st.write("**Updated:**", candidate.get('updated_at', '-'))

    st.subheader("Current Position")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Title:**", candidate.get('current_position', '-'))
    with col2:
        st.write("**Company:**", candidate.get('current_company', '-'))

    if notes := candidate.get('notes'):
        st.subheader("Notes")
        st.info(notes)


def render_skills_experience(candidate: Dict[str, Any]) -> None:
    """Render the Skills & Experience tab."""
    st.subheader("Skills")
    skills = candidate.get('parsed_data', {}).get('skills', candidate.get('skills', []))
    display_skills_badges(skills, max_per_row=4, badge_style="default")
    st.markdown("---")

    st.subheader("Experience")
    experience = candidate.get('parsed_data', {}).get('experience', candidate.get('work_experience', []))
    if experience:
        for exp in experience:
            title = exp.get('title', 'Position')
            company = exp.get('company', 'Company')
            start = exp.get('start_date', '')
            end = exp.get('end_date', 'Present')
            date_range = f"{start} to {end}" if start else exp.get('date_range', '')
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{title} at {company}**")
            with col2:
                st.markdown(f"<span style='color:#666;'>{date_range}</span>", unsafe_allow_html=True)
            if loc := exp.get('location'):
                st.markdown(f"<span style='color:#666;'>📍 {loc}</span>", unsafe_allow_html=True)
            if desc := exp.get('description'):
                st.write(desc)
            st.markdown("---")
    else:
        st.info("No experience listed")

    st.subheader("Education")
    education = candidate.get('parsed_data', {}).get('education', candidate.get('education', []))
    if education:
        for edu in education:
            with st.expander(f"{edu.get('degree','Degree')} at {edu.get('institution','Institution')}"):
                st.write("**Location:**", edu.get('location', '-'))
                dates = f"{edu.get('start_date','-')} to {edu.get('end_date','Present')}"
                st.write("**Dates:**", dates)
                st.write("**GPA:**", edu.get('gpa', '-'))
                st.write("**Description:**", edu.get('description','-'))
    else:
        st.info("No education listed")

    st.subheader("Summary")
    if summary := candidate.get('parsed_data', {}).get('summary', candidate.get('summary', '')):
        st.write(summary)
    else:
        st.info("No summary available")


def render_interactions(candidate: Dict[str, Any]) -> None:
    """Render the Interactions tab."""
    st.subheader("Interactions")
    interactions = candidate.get('interactions', [])
    if interactions:
        for inter in interactions:
            date = inter.get('date', '-')
            typ = inter.get('interaction_type','Interaction')
            with st.expander(f"{typ} on {date}"):
                st.write("**Notes:**", inter.get('notes','-'))
                st.write("**Next Steps:**", inter.get('next_steps','-'))
                st.write("**Conducted By:**", inter.get('conducted_by','-'))
    else:
        st.info("No interactions recorded")

    st.subheader("Candidate Notes")
    notes = candidate.get('candidate_notes', [])
    if notes:
        for note in notes:
            st.markdown(f"**{note.get('created_at','-')}** by {note.get('created_by','-')}")
            st.markdown(f"> {note.get('content','-')}")
            st.markdown("---")
    else:
        st.info("No notes recorded")


def page() -> None:
    """Main entrypoint to render the candidate detail page."""
    render_nav()
    # st.title("Candidate Profile")  # Removed duplicate header

    # Retrieve candidate ID from query params or session state
    candidate_id_value = st.query_params.get("id")
    # `st.query_params.get()` returns a string or None, but older code expected a list.
    # Handle both possibilities safely.
    if isinstance(candidate_id_value, list):
        candidate_id = candidate_id_value[0]
    else:
        candidate_id = candidate_id_value
    
    # Fallback to session state if query params don't have the ID
    if not candidate_id:
        candidate_id = st.session_state.get("selected_candidate_id")
    
    # Debug information (commented out for production)
    # st.write(f"Debug: Query params candidate_id = {candidate_id_value}")
    # st.write(f"Debug: Session state selected_candidate_id = {st.session_state.get('selected_candidate_id')}")
    # st.write(f"Debug: Final candidate_id = {candidate_id}")
    
    if not candidate_id:
        st.error("No candidate ID provided. Please select a candidate first.")
        if st.button("Back to Candidates"):
            st.session_state.current_page = "candidates"
            st.query_params.clear()
            st.rerun()
        return

    # Prepare API URL
    api_url = st.session_state.get("api_url","http://localhost:8000")
    if not api_url.rstrip('/').endswith('/api'):
        api_url = api_url.rstrip('/') + '/api'

    # Fetch data
    with st.spinner("Loading candidate details..."):
        candidate = fetch_candidate(api_url, candidate_id)
    if not candidate:
        if not candidate_id or candidate_id == '0':
            st.error("No valid candidate selected. Please select a candidate from the list.")
        else:
            st.error(f"Candidate with ID '{candidate_id}' was not found. It may have been deleted or does not exist.")
        if st.button("Back to Candidates"):
            st.session_state.current_page = "candidates"
            st.query_params.clear()
            st.rerun()
        return

    # Header
    render_basic_info(candidate)

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Profile","Skills & Experience","Interactions"])
    with tab1:
        render_profile(candidate)
    with tab2:
        render_skills_experience(candidate)
    with tab3:
        render_interactions(candidate)

    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Edit Candidate"):
            st.session_state["edit_candidate_id"] = candidate_id
            st.rerun()
    with col2:
        if st.button("Back to Candidates"):
            st.session_state.current_page = "candidates"
            st.query_params.clear()
            st.rerun()
    with col3:
        # Check if candidate has any job applications
        if candidate.get("job_applications") and len(candidate.get("job_applications", [])) > 0:
            # Get the most recent application
            latest_application = candidate.get("job_applications")[0]
            job_id = latest_application.get("job_id")
            
            if st.button("View Applied Job"):
                try:
                    job_id_int = int(job_id)
                    st.session_state.current_page = "job_detail"
                    st.query_params['id'] = str(job_id_int)
                    st.query_params['view'] = "job_detail"
                    st.rerun()
                except (ValueError, TypeError):
                    st.warning("No valid job application found for this candidate.")
                    st.info("This candidate hasn't applied to any specific job yet.")
        elif candidate.get("job_id") and candidate.get("job_id") is not None:
            # Fallback to direct job_id if no applications but job_id exists
            if st.button("View Applied Job"):
                job_id = candidate.get("job_id")
                try:
                    job_id_int = int(job_id)
                    st.session_state.current_page = "job_detail"
                    st.query_params['id'] = str(job_id_int)
                    st.query_params['view'] = "job_detail"
                    st.rerun()
                except (ValueError, TypeError):
                    st.warning("No valid job application found for this candidate.")
                    st.info("This candidate hasn't applied to any specific job yet.")
        else:
            # Show info message when no applications exist
            st.info("No job applications found for this candidate.")
            st.caption("This candidate hasn't applied to any specific job yet.")

    # Resume Download and Preview
    if resume_id := candidate.get("resume_id"):
        st.markdown("---")
        st.subheader("Resume")
        
        # Import the document previewer utility
        try:
            from frontend.utils.doc_previewer import fetch_and_preview_resume
        except ImportError:
            st.error("Could not import document previewer utility. Please check if the required packages are installed.")
            if st.button("Try Legacy Download"):
                # Fallback to the old download method
                try:
                    download_resp = requests.get(f"{api_url.rstrip('/')}/resume/{resume_id}/preview")
                    download_resp.raise_for_status()
                    download_url = download_resp.json().get("url")
                    if download_url:
                        st.markdown(f"[⬇️ Download Resume]({download_url})", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error fetching download URL: {e}")
        else:
            # Use the new document previewer
            # Add a download option first
            try:
                download_resp = requests.get(f"{api_url.rstrip('/')}/resume/{resume_id}/preview")
                download_resp.raise_for_status()
                download_url = download_resp.json().get("url")
                if download_url:
                    st.markdown(f"[⬇️ Download Resume]({download_url})", unsafe_allow_html=True)
            except Exception as e:
                logger.warning(f"Could not get download URL: {e}")
            
            # Show the document preview
            fetch_and_preview_resume(resume_id, api_url, height=800)

    # Edit form
    if st.session_state.get("edit_candidate_id") == candidate_id:
        st.subheader("Edit Candidate")
        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            with col1:
                fn = st.text_input("First Name", value=candidate.get("first_name",""))
                email = st.text_input("Email", value=candidate.get("email",""))
                location = st.text_input("Location",value=candidate.get("location",""))
            with col2:
                ln = st.text_input("Last Name", value=candidate.get("last_name",""))
                phone = st.text_input("Phone", value=candidate.get("phone",""))
                headline = st.text_input("Headline", value=candidate.get("headline",""))
            status_opts = list(STATUS_COLORS.keys())
            status_idx = status_opts.index(candidate.get("status","active")) if candidate.get("status") in status_opts else 0
            status = st.selectbox("Status", options=status_opts, index=status_idx)
            notes = st.text_area("Notes", value=candidate.get("notes",""))
            if st.form_submit_button("Update Candidate"):
                data = {"first_name":fn,"last_name":ln,"email":email,
                        "phone":phone,"location":location,"headline":headline,
                        "status":status,"notes":notes}
                try:
                    res = requests.put(f"{api_url.rstrip('/')}/candidates/{candidate_id}",json=data)
                    res.raise_for_status()
                    st.success("Candidate updated.")
                    st.session_state.pop("edit_candidate_id",None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

    # Debug
    with st.expander("Show Raw Candidate Data (Debug)"):
        st.json(candidate)
        
    # Debug job applications
    with st.expander("Show Job Applications (Debug)"):
        if candidate.get("job_applications"):
            st.write(f"Found {len(candidate.get('job_applications'))} job applications:")
            for i, app in enumerate(candidate.get("job_applications")):
                st.write(f"Application {i+1}: Job ID {app.get('job_id')}, Status: {app.get('status')}")
        else:
            st.write("No job applications found")
