import streamlit as st
import requests
import logging
import webbrowser
from streamlit import switch_page
from .resume_upload import fix_merged_text
from utils.ui_helpers import format_skills_list

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000" # Adjust if needed

def display_candidate_profile():
    # Create a navigation bar at the top
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 1, 1, 1])
    
    with nav_col1:
        if st.button("📊 Dashboard", key="profile_nav_dashboard"):
            if "view_candidate_id" in st.session_state:
                del st.session_state["view_candidate_id"]
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    with nav_col2:
        if st.button("👤 Candidates", key="profile_nav_candidates"):
            if "view_candidate_id" in st.session_state:
                del st.session_state["view_candidate_id"]
            st.session_state.current_page = "candidates"
            st.rerun()
    
    with nav_col3:
        if st.button("💼 Jobs", key="profile_nav_jobs"):
            if "view_candidate_id" in st.session_state:
                del st.session_state["view_candidate_id"]
            st.session_state.current_page = "jobs"
            st.rerun()
    
    with nav_col4:
        if st.button("🤖 Assistant", key="profile_nav_assistant"):
            if "view_candidate_id" in st.session_state:
                del st.session_state["view_candidate_id"]
            st.session_state.current_page = "assistant"
            st.rerun()
    
    with nav_col5:
        if st.button("🔎 Matching", key="profile_nav_matching"):
            if "view_candidate_id" in st.session_state:
                del st.session_state["view_candidate_id"]
            st.session_state.current_page = "candidate_matching"
            st.rerun()
    
    st.markdown("---")
    # st.title("Candidate Profile")  # Removed duplicate header
    
    # Get candidate ID from session state
    candidate_id = st.session_state.get("view_candidate_id")
    
    # Do NOT delete 'view_candidate_id' immediately. Only clear it if the user navigates away.
    if not candidate_id:
        # Remove candidate ID and simply return to show the candidates database inline
        st.session_state.pop("view_candidate_id", None)
        return
        
    # st.write(f"Fetching profile for Candidate ID: {candidate_id}")  # Commented out for production
    
    # All candidate profile data is now loaded from agentic backend endpoints.
    try:
        api_url = f"{BACKEND_URL}/api/candidates/{candidate_id}"
        logger.info(f"Requesting candidate data from: {api_url}")
        response = requests.get(api_url, timeout=30)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        if response.status_code == 200:
            candidate_data = response.json()
            logger.info(f"Successfully fetched data for candidate {candidate_id}")
            # Enhanced Candidate Profile with recruiter-focused UX
            # Use tabs for organization
            tabs = st.tabs(["Profile", "Work History", "Education", "Notes"])
            
            # ---- PROFILE TAB ----
            with tabs[0]:
                # Check if we have resume information
                has_resume = candidate_data.get('resume_id') is not None
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"## {candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}")
                    if candidate_data.get('headline'):
                        st.caption(candidate_data['headline'])
                with col2:
                    # Add a proper navigation button that works with the main app navigation
                    if st.button("Back to Candidates List"):
                        if "view_candidate_id" in st.session_state:
                            del st.session_state["view_candidate_id"]
                        st.session_state.current_page = "candidates"
                        st.rerun()
                    
                    # Add Download Resume button if resume_id exists
                    if candidate_data.get('resume_id'):
                        if st.button("📄 Download Resume", type="primary"):
                            try:
                                # Get resume preview URL from the backend
                                resume_id = candidate_data['resume_id']
                                api_url = f"{BACKEND_URL}/api/resume/{resume_id}/preview"
                                response = requests.get(api_url, timeout=30)
                                
                                if response.status_code == 200:
                                    url_data = response.json()
                                    # Open the URL in a new tab
                                    webbrowser.open_new_tab(url_data['url'])
                                    st.success("Resume download initiated.")
                                else:
                                    st.error(f"Failed to get resume download URL: {response.status_code}")
                            except Exception as e:
                                st.error(f"Error downloading resume: {str(e)}")
                                logger.error(f"Resume download error: {str(e)}")
                # Avatar/profile image if available
                if candidate_data.get('avatar_url'):
                    st.image(candidate_data['avatar_url'], width=120)
                st.write("")
                # Contact Info
                with st.expander("Contact Information", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Email:** {candidate_data.get('email', 'N/A')}")
                        st.write(f"**Phone:** {candidate_data.get('phone', 'N/A')}")
                    with c2:
                        st.write(f"**Location:** {candidate_data.get('location', 'N/A')}")
                # Status/Source
                with st.expander("Status & Source", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Status:** {candidate_data.get('status', 'N/A')}")
                    with c2:
                        st.write(f"**Source:** {candidate_data.get('source', 'N/A')}")
                        st.write(f"**Position Applied:** {candidate_data.get('position_applied', 'N/A')}")
                # Skills as badges
                if candidate_data.get('skills'):
                    st.markdown("**Skills**")
                    # Use safe formatting for skills
                    formatted_skills = format_skills_list(candidate_data['skills'])
                    if formatted_skills:
                        st.markdown(
                            " ".join([
                                f'<span style="background:#e0e7ff;color:#3730a3;border-radius:8px;padding:2px 10px;margin:2px;display:inline-block;font-size:10px">{skill}</span>'
                                for skill in formatted_skills
                            ]), unsafe_allow_html=True
                        )
                    else:
                        st.caption("No valid skills found.")
                else:
                    st.caption("No skills listed.")

            # ---- WORK HISTORY TAB ----
            with tabs[1]:
                st.markdown("### Work History")
                # Prefer parsed_data['experience'] if present, else fallback
                experience = []
                parsed_data = candidate_data.get('parsed_data', {})
                if parsed_data and 'experience' in parsed_data:
                    experience = parsed_data['experience']
                elif 'experience' in candidate_data:
                    experience = candidate_data['experience']
                if experience:
                    for exp in experience:
                        with st.expander(f"{exp.get('title', '-') or '-'} at {exp.get('company', '-') or '-'} ({exp.get('date_range', '-') or '-'})", expanded=False):
                            st.write(f"**Location:** {exp.get('location', '-')}")
                            if exp.get('description'):
                                # Enhanced bullet formatting for descriptions
                                description = fix_merged_text(exp['description'])
                                import re
                                
                                # Parse bullets from the formatted description
                                bullets = []
                                if '\n' in description:
                                    # Multi-line description - split by newlines (handle both single and double newlines)
                                    bullets = [line.strip() for line in re.split(r'\n+', description) if line.strip()]
                                elif any(marker in description for marker in ['•', '-', '*', '◦']):
                                    # Has bullet markers - split by them
                                    bullet_pattern = r'[•\-*◦]\s*(.+?)(?=(?:[•\-*◦])|$)'
                                    bullets = re.findall(bullet_pattern, description, re.DOTALL)
                                    bullets = [bullet.strip() for bullet in bullets if bullet.strip()]
                                else:
                                    # Single paragraph - split by sentences if long enough
                                    if len(description) > 100:
                                        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', description)
                                        bullets = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]
                                    else:
                                        bullets = [description]
                                
                                # Display bullets with enhanced formatting for better readability
                                if bullets and len(bullets) > 1:
                                    for bullet in bullets:
                                        # Remove existing bullet markers to avoid duplication
                                        cleaned_bullet = re.sub(r'^[•\-*◦]\s*', '', bullet)
                                        
                                        # Enhanced bullet styling
                                        bullet_style = f"""
                                            <div style='
                                                margin-bottom: 6px; 
                                                padding: 6px 10px; 
                                                line-height: 1.5;
                                                border-left: 2px solid #d1d5db;
                                                background-color: #f9fafb;
                                                border-radius: 3px;
                                                margin-left: 10px;
                                            '>
                                                <span style='color: #059669; font-weight: bold; margin-right: 6px;'>▸</span>
                                                <span style='color: #374151; font-size: 13px;'>{cleaned_bullet}</span>
                                            </div>
                                        """
                                        
                                        st.markdown(bullet_style, unsafe_allow_html=True)
                                else:
                                    # Single description or fallback
                                    st.markdown(f"""
                                        <div style='
                                            padding: 10px;
                                            background-color: #f9fafb;
                                            border-radius: 4px;
                                            border-left: 3px solid #059669;
                                            line-height: 1.5;
                                            color: #374151;
                                            font-size: 13px;
                                            margin-left: 10px;
                                        '>
                                            {description}
                                        </div>
                                    """, unsafe_allow_html=True)
                            # Achievements
                            if exp.get('achievements'):
                                st.markdown("**Achievements:**")
                                for ach in exp['achievements']:
                                    st.write(f"- {ach}")
                            # Technologies
                            if exp.get('technologies'):
                                st.markdown(f"**Technologies:** {', '.join(exp['technologies'])}")
                else:
                    st.info("No work history found.")

            # ---- EDUCATION TAB ----
            with tabs[2]:
                st.markdown("### Education")
                # Prefer parsed_data['education'] if present, else fallback
                education = []
                if parsed_data and 'education' in parsed_data:
                    education = parsed_data['education']
                elif 'education' in candidate_data:
                    education = candidate_data['education']
                if education:
                    for edu in education:
                        with st.expander(f"{edu.get('degree', '-') or '-'} at {edu.get('institution', '-') or '-'}", expanded=False):
                            st.write(f"**Location:** {edu.get('location', '-')}")
                            st.write(f"**Dates:** {edu.get('date_range', '-') or '-'}")
                            if edu.get('gpa'):
                                st.write(f"**GPA:** {edu['gpa']}")
                            if edu.get('description'):
                                st.markdown(f"> {edu['description']}")
                else:
                    st.info("No education history found.")

            # ---- NOTES TAB ----
            with tabs[3]:
                st.markdown("### Notes")
                notes = candidate_data.get('notes', '')
                if notes:
                    st.write(notes)
                else:
                    st.caption("No notes for this candidate.")

            # Optionally: Add more tabs for certifications, projects, etc. if present in candidate_data
            # with tabs[4]: ...

            # Debug: Show the full candidate_data JSON for troubleshooting
            with st.expander("Show Raw Candidate Data (Debug)", expanded=False):
                # st.json(candidate_data)  # Commented out for production
                st.write("Raw candidate data display disabled for production")
            
        else:
            # This case might not be reached due to raise_for_status
            st.error(f"Failed to fetch candidate data. Status code: {response.status_code}")
            logger.error(f"Failed to fetch candidate {candidate_id}. Status: {response.status_code}, Response: {response.text}")
            
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out fetching candidate {candidate_id}")
        st.error("Request timed out connecting to the backend.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            st.error(f"Candidate with ID '{candidate_id}' not found.")
            logger.warning(f"Candidate {candidate_id} not found (404).")
        else:
            st.error(f"HTTP error fetching candidate data: {e}")
            logger.error(f"HTTP error fetching candidate {candidate_id}: {e}", exc_info=True)
    except requests.exceptions.RequestException as e:
        st.error(f"Network error fetching candidate data: {e}")
        logger.error(f"Network error fetching candidate {candidate_id}: {e}", exc_info=True)
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        logger.error(f"Unexpected error displaying profile for {candidate_id}: {e}", exc_info=True)

# Run the function to display the profile
display_candidate_profile()
