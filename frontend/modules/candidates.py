# frontend/modules/candidates.py
import streamlit as st
import json
import os
import datetime
import logging
import requests
import time
from typing import Dict, Any, List, Optional
from functools import lru_cache
from .resume_upload import fix_merged_text
from frontend.utils.ui_helpers import display_skills_badges, format_skills_list, clean_display_text

# Set up frontend logging (don't add file handlers at import time)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def page():
    """Candidates page content"""
    # --- Sidebar API URL config ---
    if 'api_url' not in st.session_state:
        st.session_state['api_url'] = 'http://localhost:8000'
    st.session_state['api_url'] = st.sidebar.text_input('API Base URL', value=st.session_state['api_url'])
    logger.info("Rendering candidates page")
    
    # All candidate UI, data, and actions now use agentic backend endpoints.
    tab1, tab2, tab3 = st.tabs(["Candidates Database", "Upload Resume", "Search Candidates"])
    with tab1:
        display_candidates_database()
    with tab2:
        upload_resume()
    with tab3:
        search_candidates()

@st.cache_data(ttl=60)  # Cache data for 1 minute only
def fetch_candidates(api_url: str) -> List[Dict]:
    """Fetch candidates synchronously using a cached httpx client where available."""
    try:
        logger.info(f"Fetching candidates synchronously. API URL: {api_url}")
        base_url = api_url.rstrip('/')
        endpoint = f"{base_url}/api/candidates/"

        # Try to use cached sync client
        try:
            from frontend.utils.http_client import get_sync_client
            client = get_sync_client()
        except Exception:
            client = None

        if client is None:
            # Fallback to requests
            resp = requests.get(endpoint, params={"page_size": 50}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        else:
            resp = client.get(endpoint, params={"page_size": 50}, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, dict) and 'results' in data:
            candidates = data['results']
        elif isinstance(data, list):
            candidates = data
        else:
            logger.warning(f"Unexpected data format received: {type(data)}")
            candidates = []

        for c in candidates:
            c.setdefault("id", "-")
            c.setdefault("first_name", "")
            c.setdefault("last_name", "")
            c.setdefault("email", "-")
            c.setdefault("phone", "-")
            c.setdefault("location", "-")
            c.setdefault("position_applied", "-")
            c.setdefault("status", "-")
            c.setdefault("source", "-")
            c.setdefault("created_at", "-")

        return candidates
    except Exception as e:
        logger.error(f"Error fetching candidates: {e}")
        raise

# Function to clear the candidate cache when a new candidate is added
def clear_candidate_cache():
    """Clear the candidate cache to force a refresh"""
    fetch_candidates.clear()

# Import cache manager for better cache management
from frontend.utils.cache_manager import cache_manager

def display_candidates_database():
    """Display the list of candidates in the database"""
    logger.debug("Rendering candidates database")
    st.subheader("Candidates Database")
    
    # Add a search box to filter candidates by name
    search_query = st.text_input("Search candidates by name", key="candidate_search")
    
    # Check if we just added a candidate and need to refresh
    if st.session_state.get("candidate_added", False):
        clear_candidate_cache()
        st.session_state.candidate_added = False
    
    with st.spinner("Loading candidates from database..."):
        try:
            candidates = fetch_candidates(st.session_state['api_url'])
            
            # Handle different response types
            if not isinstance(candidates, list):
                if isinstance(candidates, dict) and 'results' in candidates:
                    candidates = candidates['results']
                else:
                    st.error("Invalid data structure received from API. Please check your backend endpoint and response format.")
                    logger.error(f"Invalid candidates data: {candidates}")
                    return
            
            if len(candidates) == 0:
                st.info("No candidates found in the database.")
                st.markdown("**Troubleshooting Tips:**")
                st.markdown("- Check if the backend is running properly")
                st.markdown("- Verify the API URL in the sidebar")
                st.markdown("- Check backend logs for any errors")
                return
            
            # Filter candidates by search query if provided
            if search_query:
                filtered_candidates = []
                for cand in candidates:
                    name = f"{cand.get('first_name', '')} {cand.get('last_name', '')}".lower()
                    if search_query.lower() in name:
                        filtered_candidates.append(cand)
                candidates = filtered_candidates
                st.write(f"Found {len(candidates)} candidates matching '{search_query}'")
            else:
                pass  # st.write(f"Rendering {len(candidates)} candidates...")  # Commented out for production
            
            # If no candidates match the search, show a message
            if len(candidates) == 0:
                st.info(f"No candidates found matching '{search_query}'. Try a different search term.")
                return
            
            # Display each candidate in a card format using Streamlit components
            for idx, cand in enumerate(candidates):
                candidate_id = cand.get("id")
                key_suffix = candidate_id if candidate_id and candidate_id != '-' else idx
                
                with st.container():
                    # Create a card-like container with a border
                    st.markdown("---")
                    
                    # Header row with name and status
                    col1, col2, col3 = st.columns([6, 3, 1])
                    with col1:
                        # Handle empty names gracefully
                        first_name = cand.get('first_name', '').strip()
                        last_name = cand.get('last_name', '').strip()
                        full_name = f"{first_name} {last_name}".strip()
                        if not full_name:
                            full_name = f"Candidate {candidate_id[:8]}" if candidate_id else "Unknown Candidate"
                        st.subheader(full_name)
                        
                        # Display current job title directly under name
                        if cand.get('current_position'):
                            st.caption(f"🏢 {cand.get('current_position')}")
                        elif cand.get('headline'):
                            st.caption(cand.get('headline'))
                    
                    with col2:
                        status = cand.get('status', '').upper()
                        status_color = get_status_color(cand.get('status'))
                        st.markdown(
                            f"<div style='background:{status_color};color:white;padding:4px 12px;"
                            f"border-radius:20px;font-size:13px;font-weight:500;text-align:center;'>"
                            f"{status}</div>",
                            unsafe_allow_html=True
                        )
                    
                    with col3:
                        if st.button("🗑️", key=f'delete_{key_suffix}'):
                            st.session_state[f'delete_confirm_{key_suffix}'] = True
                            st.rerun()
                    
                    # Main content columns
                    info_col1, info_col2 = st.columns(2)
                    
                    with info_col1:
                        st.markdown("##### Contact Information")
                        st.write(f"📧 {cand.get('email', '-')}")
                        st.write(f"📱 {cand.get('phone', '-')}")
                        st.write(f"📍 {cand.get('location', '-')}")
                    
                    with info_col2:
                        st.markdown("##### Application Details")
                        
                        
                        st.write(f"💼 Applied For: {cand.get('position_applied', '-')}")
                        st.write(f"📅 Applied: {cand.get('created_at', '-')}")
                        # st.write(f"🔍 Source: {cand.get('source', '-')}")  # Commented out for production
                    
                    # Skills section
                    if cand.get('skills'):
                        st.markdown("##### Skills")
                        # Format skills safely before displaying
                        formatted_skills = format_skills_list(cand['skills'])
                        if formatted_skills:
                            # Use the safe skills display function with formatted skills
                            display_skills_badges(formatted_skills, max_per_row=4, badge_style="compact")
                        else:
                            st.caption("No valid skills found.")
                    
                    # Actions row
                    actions_col1, actions_col2, actions_col3 = st.columns(3)
                    
                    with actions_col1:
                        if st.button("👁️ View Details", key=f'view_{key_suffix}'):
                            # Navigate to candidate detail page using query params
                            st.session_state.current_page = "candidate_detail"
                            st.query_params["id"] = str(candidate_id)
                            st.query_params["view"] = "candidate_detail"
                            st.rerun()
                    
                    with actions_col2:
                        if st.button("✏️ Edit", key=f'edit_{key_suffix}'):
                            st.session_state['edit_candidate_id'] = candidate_id
                            st.rerun()
                    
                    with actions_col3:
                        # Handle delete confirmation dialog
                        if st.session_state.get(f'delete_confirm_{key_suffix}', False):
                            # Use the same name logic as above
                            first_name = cand.get('first_name', '').strip()
                            last_name = cand.get('last_name', '').strip()
                            full_name = f"{first_name} {last_name}".strip()
                            if not full_name:
                                full_name = f"Candidate {candidate_id[:8]}" if candidate_id else "Unknown Candidate"
                            st.warning(f"Are you sure you want to delete {full_name}?")
                            del_col1, del_col2 = st.columns(2)
                            with del_col1:
                                if st.button("Yes, Delete", key=f'confirm_delete_{key_suffix}'):
                                    delete_result = delete_candidate_api(candidate_id)
                                    if delete_result:
                                        st.success("Candidate deleted successfully!")
                                        clear_candidate_cache()
                                        st.session_state[f'delete_confirm_{key_suffix}'] = False
                                        st.rerun()
                            with del_col2:
                                if st.button("Cancel", key=f'cancel_delete_{key_suffix}'):
                                    st.session_state[f'delete_confirm_{key_suffix}'] = False
                                    st.rerun()
        
        except Exception as e:
            st.error(f"Error loading candidates: {str(e)}")
            logger.error(f"Error in display_candidates_database: {str(e)}", exc_info=True)
            
            # Provide troubleshooting guidance
            st.markdown("**Troubleshooting Steps:**")
            st.markdown("1. **Check Backend Connection**: Ensure the backend is running")
            st.markdown("2. **Verify API URL**: Check the API URL in the sidebar")
            st.markdown("3. **Check Network**: Ensure you can access the backend URL")
            st.markdown("4. **Review Logs**: Check both frontend and backend logs for errors")
            
            if st.button("🔄 Retry Loading Candidates"):
                clear_candidate_cache()
                st.rerun()

def render_candidate_card(cand):
    """Render a candidate card with all available details"""
    def fmt(val):
        return val if val not in [None, '', [], {}] else '-'
    
    # Format skills as badges safely using ui_helpers
    skills_html = '-'
    if cand.get('skills'):
        # Use the safe formatting function from ui_helpers
        formatted_skills = format_skills_list(cand['skills'])
        if formatted_skills:
            skills_html = " ".join([
                f'<span style="background:#e0e7ff;color:#3730a3;border-radius:8px;padding:0.5rem 0.75rem;margin:2px;display:inline-block;font-size:12px;font-weight:500">{skill}</span>'
                for skill in formatted_skills
            ])
    
    # Format interactions
    interactions_html = ''
    if cand.get('interactions'):
        for inter in cand['interactions']:
            interactions_html += f"""
            <div style="background:#f8fafc;padding:8px 12px;border-radius:6px;margin-bottom:8px;">
                <div style="font-weight:600;color:#4338ca">{fmt(inter.get('interaction_type'))}</div>
                <div style="color:#64748b;font-size:12px;">{fmt(inter.get('date'))}</div>
                <div style="margin-top:4px">{fmt(inter.get('notes'))}</div>
                <div style="margin-top:4px;font-style:italic;color:#475569">Next: {fmt(inter.get('next_steps'))}</div>
            </div>
            """
    
    # Format notes
    notes_html = ''
    if cand.get('candidate_notes'):
        for note in cand['candidate_notes']:
            notes_html += f"""
            <div style="background:#f1f5f9;padding:8px 12px;border-radius:6px;margin-bottom:8px;">
                <div style="color:#1e293b">{fmt(note.get('content'))}</div>
                <div style="font-size:11px;color:#64748b;margin-top:4px">By {fmt(note.get('created_by'))}</div>
            </div>
            """
    
    # Get status color
    status_color = get_status_color(cand.get('status'))
    
    # Main candidate card HTML
    return f"""
    <div style="padding:20px;margin-bottom:20px;border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <div>
                <div style="font-size:20px;font-weight:600;color:#1e293b;">{
                    ((first_name := cand.get('first_name', '').strip()) + ' ' + (last_name := cand.get('last_name', '').strip())).strip() 
                    or f"Candidate {cand.get('id', '')[:8]}" if cand.get('id') else 'Unknown Candidate'
                }</div>
                {f"<div style='color:#1e40af;font-size:15px;margin-top:4px;'>🏢 {fmt(cand.get('current_position'))}</div>" if cand.get('current_position') else f"<div style='color:#64748b;font-size:14px;margin-top:4px;'>{fmt(cand.get('headline'))}</div>"}
            </div>
            <div style="background:{status_color};color:white;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:500;">
                {fmt(cand.get('status')).upper()}
            </div>
        </div>
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
            <div>
                <div style="margin-bottom:12px;">
                    <div style="font-weight:600;color:#475569;font-size:13px;">Contact Information</div>
                    <div style="margin-top:8px;color:#475569;">
                        <div>📧 {fmt(cand.get('email'))}</div>
                        <div>📱 {fmt(cand.get('phone'))}</div>
                        <div>📍 {fmt(cand.get('location'))}</div>
                    </div>
                </div>
            </div>
            
            <div>
                <div style="margin-bottom:12px;">
                    <div style="font-weight:600;color:#475569;font-size:13px;">Application Details</div>
                    <div style="margin-top:8px;color:#475569;">
                        
                        <div>💼 Applied For: {fmt(cand.get('position_applied'))}</div>
                        <div>📅 Applied: {fmt(cand.get('created_at'))}</div>
                        <div>🔍 Source: {fmt(cand.get('source'))}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom:16px;">
            <div style="font-weight:600;color:#475569;font-size:13px;margin-bottom:8px;">Skills</div>
            <div>{skills_html}</div>
        </div>
        
        <details style="margin-top:12px;">
            <summary style="cursor:pointer;font-weight:500;color:#3730a3;font-size:13px;">Show Interactions & Notes</summary>
            <div style="margin-top:12px;">
                <div style="font-weight:600;color:#475569;font-size:13px;margin-bottom:8px;">Recent Interactions</div>
                <div>{interactions_html or '<div style="color:#94a3b8;font-style:italic;">No interactions recorded</div>'}</div>
                <div style="font-weight:600;color:#475569;font-size:13px;margin:16px 0 8px 0;">Notes</div>
                <div>{notes_html or '<div style="color:#94a3b8;font-style:italic;">No notes recorded</div>'}</div>
            </div>
        </details>
    </div>
    """


def render_candidate_row(row):
    # Render a candidate row with user-friendly labels and HTML for skills
    html = f"""
    <div style='padding:8px 0;border-bottom:1px solid #eee;'>
        <b>Name:</b> {row.get('Name','-')}<br>
        <b>Email:</b> {row.get('Email','-')}<br>
        <b>Position:</b> {row.get('Position','-')}<br>
        <b>Status:</b> {row.get('Status','-')}<br>
        <b>Source:</b> {row.get('Source','-')}<br>
        <b>Last Contact:</b> {row.get('Last Contact','-')}<br>
        <b>Skills:</b> {row.get('Skills','-')}
    </div>
    """
    return html

def delete_candidate_api(candidate_id):
    api_url = st.session_state.get("api_url", "http://localhost:8000")
    try:
        try:
            from frontend.utils.http_client import get_sync_client
            client = get_sync_client()
        except Exception:
            client = None

        if client is None:
            resp = requests.delete(f"{api_url}/api/candidates/{candidate_id}", timeout=30)
        else:
            resp = client.delete(f"{api_url}/api/candidates/{candidate_id}", timeout=30.0)

        status = getattr(resp, 'status_code', None) or (resp.status if hasattr(resp, 'status') else None)
        if status == 200:
            return True
        elif status == 404:
            st.error("Candidate not found - may have already been deleted")
            return False
        elif status == 500:
            try:
                error_detail = resp.json().get('detail', 'Internal server error')
                st.error(f"Server error deleting candidate: {error_detail}")
            except Exception:
                st.error(f"Server error deleting candidate: {getattr(resp, 'text', str(resp))}")
            return False
        else:
            st.error(f"Failed to delete candidate (HTTP {status}): {getattr(resp, 'text', str(resp))}")
            return False
    except requests.exceptions.Timeout:
        st.error("Request timed out - candidate deletion may still be in progress")
        return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to server - please check if the backend is running")
        return False
    except Exception as e:
        st.error(f"Unexpected error deleting candidate: {str(e)}")
        return False


def upload_resume():
    """Upload and parse a resume"""
    logger.info("Rendering resume upload form")
    st.subheader("Upload Resume")
    
    # Initialize session state variables if they don't exist
    if "parsed_resume_data" not in st.session_state:
        st.session_state.parsed_resume_data = None
    if "resume_parsed" not in st.session_state:
        st.session_state.resume_parsed = False
    if "resume_file" not in st.session_state:
        st.session_state.resume_file = None
    if "candidate_added" not in st.session_state:
        st.session_state.candidate_added = False
    
    # Split the function - a cacheable part for API calls and processing
    # and a non-cacheable part for UI updates
    @st.cache_data(ttl=60)  # Cache parsed resume data for 1 minute
    def call_parse_resume_api(file_name, file_content, file_type, api_url):
        """Call the resume parsing API with caching - no UI elements here"""
        try:
            logger.info(f"Calling resume parsing API at: {api_url}/api/resume/parse")
            
            # Create multipart form data
            files = {"file": (file_name, file_content, file_type)}
            
            response = requests.post(f"{api_url}/api/resume/parse", files=files, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            
            # Check for duplicate resume
            if result.get("duplicate"):
                logger.warning(f"Duplicate resume detected: {file_name}")
                return {"duplicate": True, "duplicate_info": result.get("duplicate_info"), "message": result.get("message")}
            
            logger.info(f"Successfully parsed resume: {file_name}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise Exception(f"Failed to parse resume: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing resume: {e}")
            raise
            
            # Add retry mechanism for backend connection
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Sending POST request to API (attempt {attempt+1}/{max_retries})...")
                    
                    response = requests.post(
                        f"{api_url}/api/resume/parse",
                        files=files,
                        timeout=60  # Increased timeout for larger files
                    )
                    
                    # If successful, break out of retry loop
                    if response.status_code == 200:
                        break
                    
                    logger.warning(f"Attempt {attempt+1} failed with status code {response.status_code}")
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    logger.warning(f"Connection error on attempt {attempt+1}: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        raise
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                parsed_data = result.get("parsed_data", {})
                
                # Set file_id if present
                if 'file_id' not in parsed_data and 'file_id' in result:
                    parsed_data['file_id'] = result['file_id']
                    
                return {
                    "success": True,
                    "data": parsed_data,
                    "missing_sections": get_missing_sections(parsed_data)
                }
            else:
                logger.error(f"Error parsing resume: {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.exception(f"Error processing resume: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # Helper function to determine missing sections - no UI elements
    def get_missing_sections(parsed_data):
        missing_sections = []
        if not parsed_data.get('skills', []):
            missing_sections.append("Skills")
        if not parsed_data.get('education', []):
            missing_sections.append("Education")
        if not parsed_data.get('experience', []):
            missing_sections.append("Experience")
        return missing_sections
    
    # The non-cached wrapper function that handles UI elements
    def parse_resume_file(uploaded_file):
        """Parse a resume file and update the UI"""
        try:
            # Create a hash of the file content to use as a cache key
            file_content = uploaded_file.getvalue()
            
            # Don't log the full file info - this slows things down for large files
            file_size = len(file_content)
            api_url = st.session_state.get("api_url", "http://localhost:8000")
            
            # Show status message in UI
            st.info(f"Processing resume: {uploaded_file.name} ({file_size/1024:.1f} KB)")
            
            # Call the cached function for API processing without UI elements
            result = call_parse_resume_api(
                uploaded_file.name, 
                file_content, 
                uploaded_file.type, 
                api_url
            )
            
            if result["success"]:
                parsed_data = result["data"]
                missing_sections = result["missing_sections"]
                
                # Process results without excessive UI updates - combine messages
                messages = []
                if missing_sections:
                    messages.append(f"Resume processed, but you may need to manually enter: {', '.join(missing_sections)}")
                else:
                    messages.append("Resume processed successfully!")
                    
                # Try to extract name from filename if not found in parsed data
                if parsed_data.get('personal_info', {}).get('name') in [None, "", "Unknown"]:
                    # Try to extract name from filename (assuming format like "FirstName LastName Resume.pdf")
                    filename = uploaded_file.name
                    name_part = filename.split(" Resume")[0] if " Resume" in filename else filename.split(".")[0]
                    
                    # Only use if it looks like a name (not just "resume" or similar)
                    if name_part.lower() not in ["resume", "cv", "curriculum"]:
                        logger.info(f"Extracted name from filename: {name_part}")
                        if 'personal_info' not in parsed_data:
                            parsed_data['personal_info'] = {}
                        parsed_data['personal_info']['name'] = name_part
                        messages.append(f"Used filename to determine candidate name: {name_part}")
                
                # Show all messages at once rather than multiple UI calls
                st.success("\n\n".join(messages))
                
                # Ensure resume_id is propagated from backend result if present
                if 'resume_id' not in parsed_data and 'resume_id' in result:
                    parsed_data['resume_id'] = result['resume_id']
                return parsed_data
            else:
                st.error(f"Error parsing resume: {result['error']}")
                return {}
            
        except Exception as e:
            st.error(f"Error processing resume: {str(e)}")
            logger.exception(f"Error in parse_resume_file: {str(e)}")
            return {}
    
    # File upload
    uploaded_file = st.file_uploader("Choose a resume file", type=["pdf", "docx"])
    
    # Handle file change separately from UI rendering
    if uploaded_file is not None and uploaded_file != st.session_state.resume_file:
        logger.info(f"New file uploaded: {uploaded_file.name}")
        st.session_state.resume_file = uploaded_file
        st.session_state.resume_parsed = False
        st.session_state.parsed_resume_data = None
        st.rerun()

    # Always show these if a file is uploaded
    if uploaded_file is not None:
        # Display file details
        st.write(f"Filename: {uploaded_file.name}")
        st.write(f"File size: {uploaded_file.size} bytes")

        parse_checkbox = st.checkbox("Parse resume to extract information", value=True)
        
        if parse_checkbox and st.button("Parse Resume"):
            logger.info("Parse Resume button clicked")
            
            # Use a placeholder to show status instead of multiple st.info/success calls
            status_placeholder = st.empty()
            status_placeholder.info("Starting resume parsing process...")
            
            with st.spinner("Parsing resume..."):
                logger.debug("Calling parse_resume_file function")
                parsed_data = parse_resume_file(uploaded_file)
                logger.debug(f"Returned from parse_resume_file, got data: {bool(parsed_data)}")
                
                if parsed_data:
                    st.session_state.parsed_resume_data = parsed_data
                    st.session_state.resume_parsed = True
                    status_placeholder.success("[SUCCESS] Resume parsed successfully!")
                    logger.info("Resume parsed successfully, updating UI")
                    st.rerun()
                else:
                    status_placeholder.error("[ERROR] Failed to parse resume. Please try again or upload a different file.")
                    logger.warning("Resume parsing returned empty data")
    
    # Display form if file is uploaded
    if uploaded_file is not None:
        # Extract values from parsed data if available
        personal_info = {}
        if st.session_state.parsed_resume_data:
            personal_info = st.session_state.parsed_resume_data.get("personal_info", {})
            
        # Extract name parts if present
        first_name = ""
        last_name = ""
        if personal_info.get("name"):
            name_parts = personal_info.get("name", "").split()
            if name_parts:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Form for candidate information
        with st.form("candidate_form"):
            st.write("### Basic Candidate Information")
            
            col1, col2 = st.columns(2)
            with col1:
                first_name_input = st.text_input("First Name", value=first_name)
                email_input = st.text_input("Email", value=personal_info.get("email", ""))
                position_input = st.text_input("Position Applied For")
            
            with col2:
                last_name_input = st.text_input("Last Name", value=last_name)
                phone_input = st.text_input("Phone", value=personal_info.get("phone", ""))
                source_input = st.selectbox(
                    "Source", 
                    ["LinkedIn", "Indeed", "Company Website", "Referral", "Job Board", "Other"]
                )
            
            submitted = st.form_submit_button("Submit")
            
            if submitted:
                with st.spinner("Creating candidate record..."):
                    try:
                        api_url = st.session_state.get("api_url", "http://localhost:8000")
                        
                        # Create candidate in the database using the API
                        candidate_data = {
                            "first_name": first_name_input,
                            "last_name": last_name_input,
                            "email": email_input,
                            "phone": phone_input,
                            "position_applied": position_input,
                            "source": source_input,
                            "status": "active"
                        }
                        
                        # Create a placeholder for status updates to reduce UI redraws
                        status_placeholder = st.empty()
                        
                        # Create candidate in API
                        candidate_response = requests.post(
                            f"{api_url}/candidates",
                            json=candidate_data,
                            timeout=10
                        )
                        
                        if candidate_response.status_code in [200, 201]:
                            candidate_id = candidate_response.json().get("id")
                            status_placeholder.success(f"Candidate created successfully with ID: {candidate_id}")
                            
                            # Now upload the resume for this candidate
                            resume_response = requests.post(
                                f"{api_url}/api/candidates/{candidate_id}/upload-resume",
                                files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                                timeout=30
                            )
                            
                            if resume_response.status_code in [200, 201]:
                                status_placeholder.success("Resume uploaded and linked to candidate.")
                                
                                # If we parsed the resume, also save the structured data
                                if st.session_state.parsed_resume_data:
                                    parsed_data_response = requests.post(
                                        f"{api_url}/api/candidates/{candidate_id}/parsed-resume",
                                        json={"parsed_data": st.session_state.parsed_resume_data},
                                        timeout=10
                                    )
                                    
                                    if parsed_data_response.status_code in [200, 201]:
                                        status_placeholder.success("Parsed resume data saved.")
                                    else:
                                        status_placeholder.warning(f"Warning: Structured resume data not saved: {parsed_data_response.text}")
                            else:
                                status_placeholder.error(f"Error uploading resume: {resume_response.text}")
                        else:
                            status_placeholder.error(f"Error creating candidate: {candidate_response.text}")
                    except Exception as e:
                        st.error(f"Error creating candidate: {str(e)}")
        
        # Show parsed information if available
        if st.session_state.parsed_resume_data:
            display_parsed_resume(st.session_state.parsed_resume_data)

@st.cache_data(ttl=60)
def get_formatted_resume_data(parsed_data):
    """Prepare resume data for display with caching to avoid reprocessing"""
    # Process any data transformations needed for display
    # This offloads processing from the UI rendering
    formatted_data = {
        "personal_info": parsed_data.get("personal_info", {}),
        "summary": parsed_data.get("summary", ""),
        "skills": parsed_data.get("skills", []),
        "education": parsed_data.get("education", []),
        "experience": parsed_data.get("experience", [])
    }
    return formatted_data

def display_parsed_resume(parsed_data):
    """Display the parsed resume data."""
    # Use cached data processing
    formatted_data = get_formatted_resume_data(parsed_data)
    
    # Personal Information
    st.write("### Personal Information")
    personal_info = parsed_data.get("personal_info", {})
    
    if not personal_info or all(value is None or value == "" for value in personal_info.values()):
        st.write("No personal information extracted. Please fill in the details below.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {personal_info.get('name', 'Not found')}")
            st.write(f"**Email:** {personal_info.get('email', 'Not found')}")
        with col2:
            st.write(f"**Phone:** {personal_info.get('phone', 'Not found')}")
            st.write(f"**Location:** {personal_info.get('location', 'Not found')}")
    
    # Summary
    st.write("### Summary")
    summary = parsed_data.get("summary", "")
    if summary:
        st.write(summary)
    else:
        st.write("No summary extracted. Please provide a brief professional summary below.")
    
    # Skills
    st.write("### Skills")
    skills = parsed_data.get("skills", [])
    if skills:
        # Create a grid layout for skills
        cols = st.columns(3)
        for i, skill in enumerate(skills):
            cols[i % 3].write(f"- {skill}")
    else:
        st.write("No skills extracted. Please add relevant skills below.")
    
    # Education
    st.write("### Education")
    education = parsed_data.get("education", [])
    if education:
        for edu in education:
            # Enhanced display for education with fixed date handling
            degree = edu.get('degree', 'Degree')
            institution = edu.get('institution', 'Institution')
            location = edu.get('location', '')
            
            st.write(f"**{degree}**")
            st.write(f"{institution}{', ' + location if location else ''}")
            
            # Use date_range if available, otherwise build from start/end dates
            date_range = edu.get('date_range')
            if not date_range and (edu.get('start_date') or edu.get('end_date')):
                start = edu.get('start_date', '')
                end = edu.get('end_date', '')
                if start or end:
                    date_range = f"{start} - {end}"
            
            if date_range:
                st.write(f"*{date_range}*")
            else:
                st.write("*Date range not specified*")
                
            if edu.get('gpa'):
                st.write(f"GPA: {edu.get('gpa')}")
            if edu.get('description'):
                st.write(edu.get('description'))
            st.write("---")
    else:
        st.write("No education history extracted. Please add education details below.")
    
    # Experience
    st.write("### Work Experience")
    experience = parsed_data.get("experience", [])
    if experience:
        for exp in experience:
            # Enhanced display for work experience
            title = exp.get('title', 'Position')
            company = exp.get('company', 'Company')
            location = exp.get('location', '')
            
            # Format job title and company with better handling
            st.write(f"**{title}** at *{company}*{' - ' + location if location else ''}")
            
            # Use date_range if available, otherwise build from start/end dates
            date_range = exp.get('date_range')
            if not date_range and (exp.get('start_date') or exp.get('end_date')):
                start = exp.get('start_date', '')
                end = exp.get('end_date', 'Present')
                if start or end:
                    date_range = f"{start} - {end}" 
            
            if date_range:
                st.write(f"*{date_range}*")
            else:
                st.write("*Date range not specified*")
                
            if exp.get('description'):
                st.write(fix_merged_text(exp.get('description')))
            
            # Display achievements if any
            achievements = exp.get('achievements', [])
            if achievements:
                st.write("**Achievements:**")
                for achievement in achievements:
                    st.write(f"- {achievement}")
            
            # Display technologies if any
            technologies = exp.get('technologies', [])
            if technologies:
                st.write("**Technologies used:**")
                tech_cols = st.columns(3)
                for i, tech in enumerate(technologies):
                    tech_cols[i % 3].write(f"- {tech}")
            
            st.write("---")
    else:
        st.write("No work experience extracted. Please add relevant work experience below.")
        
    # Allow for manual edits and saving
    st.write("### Save Parsed Resume")
    st.write("Review the extracted information and save it to the database.")
    
    # Form for saving the parsed resume
    with st.form("resume_validation_form"):
        # Instructions
        st.write("Click the button below to save this parsed resume to the database.")
        
        # Add a hidden field to store the file_id
        file_id = parsed_data.get("file_id", "")
        
        save_button = st.form_submit_button("Save Parsed Resume", help="Save the parsed resume data to the database")
        
        if save_button:
            try:
                # Prepare the request to the confirmation endpoint
                api_url = st.session_state.get("api_url", "http://localhost:8000")
                
                # Log the request details
                logger.info(f"Sending resume confirmation request to {api_url}/resumes/confirm")
                logger.debug(f"Resume data keys: {list(parsed_data.keys())}")
                
                # Ensure the parsed data has all required fields for the ResumeData model
                # Convert skills from strings to Skill objects
                formatted_skills = []
                if "skills" in parsed_data and isinstance(parsed_data["skills"], list):
                    for skill in parsed_data["skills"]:
                        if isinstance(skill, str):
                            formatted_skills.append({"name": skill, "category": "General"})
                        else:
                            # Already in correct format
                            formatted_skills.append(skill)
                
                # Ensure all required fields are present
                formatted_resume_data = {
                    "file_id": parsed_data.get("file_id", ""),
                    "file_name": parsed_data.get("file_name", "resume.pdf"),
                    "content_type": parsed_data.get("content_type", "application/pdf"),
                    "full_text": parsed_data.get("full_text", ""),
                    "sections": parsed_data.get("sections", []),
                    "personal_info": parsed_data.get("personal_info", {}),
                    "summary": parsed_data.get("summary", ""),
                    "skills": formatted_skills,
                    "education": parsed_data.get("education", []),
                    "experience": parsed_data.get("experience", []),
                    "projects": parsed_data.get("projects", []),
                    "certifications": parsed_data.get("certifications", []),
                    "languages": parsed_data.get("languages", []),
                    "raw_entities": parsed_data.get("raw_entities", {}),
                    "embeddings": parsed_data.get("embeddings", {}),
                    "metadata": parsed_data.get("metadata", {})
                }
                
                # If sections is missing, create a minimal set of sections
                if not formatted_resume_data["sections"]:
                    formatted_resume_data["sections"] = [
                        {
                            "title": "Summary",
                            "content": formatted_resume_data["summary"],
                            "markdown_content": formatted_resume_data["summary"],
                            "confidence": 1.0
                        }
                    ]
                
                # If full_text is missing, create it from available data
                if not formatted_resume_data["full_text"]:
                    full_text = []
                    if formatted_resume_data["personal_info"].get("name"):
                        full_text.append(formatted_resume_data["personal_info"]["name"])
                    if formatted_resume_data["summary"]:
                        full_text.append(formatted_resume_data["summary"])
                    for exp in formatted_resume_data["experience"]:
                        full_text.append(f"{exp.get('company', '')}: {fix_merged_text(exp.get('description', ''))}")
                    formatted_resume_data["full_text"] = "\n\n".join(full_text)
                
                # Create the request payload with the expected structure
                # The backend expects settings and request at the top level
                request_payload = {
                    "resume_data": formatted_resume_data,
                    "user_edits": None  # No edits for now
                }
                
                # Make the API call
                with st.spinner("Saving resume data to database..."):
                    # Log all possible endpoint formats for debugging
                    endpoint1 = f"{api_url}/resumes/confirm"
                    endpoint2 = f"{api_url.rstrip('/api')}/api/resumes/confirm"
                    endpoint3 = "http://localhost:8000/api/resumes/confirm"
                    
                    logger.info(f"Trying endpoints: {endpoint1}, {endpoint2}, {endpoint3}")
                    
                    # Structure the payload correctly for the FastAPI endpoint
                    # The backend expects a ResumeConfirmationFullRequest object
                    # Prepare the request with settings at the root level
                    request_body = {
                        "settings": {
                            "save_to_database": False,
                            "create_candidate": False
                        },
                        "resume_data": formatted_resume_data,
                        "user_edits": None
                    }
                    
                    # Try all possible endpoint formats
                    for endpoint in [endpoint3, endpoint1, endpoint2]:
                        try:
                            logger.info(f"Attempting request to: {endpoint}")
                            # Send the request with settings at root level
                            response = requests.post(
                                "http://localhost:8000/api/resumes/confirm",
                                json=request_body,
                                timeout=30
                            )
                            # Log the response for debugging
                            logger.info(f"Response from {endpoint}: {response.status_code}")
                            logger.debug(f"Response content: {response.text}")
                            
                            # If successful, break the loop
                            if response.status_code in [200, 201, 202]:
                                logger.info(f"Successful response from {endpoint}")
                                break
                        except Exception as e:
                            logger.error(f"Error calling {endpoint}: {str(e)}")
                    
                    # If we didn't get a successful response, try one more time with the exact endpoint
                    if not response.status_code in [200, 201, 202]:
                        logger.warning("All endpoints failed, trying exact registered endpoint")
                        try:
                            # Send the full_request nested
                            response = requests.post(
                                "http://localhost:8000/api/resumes/confirm",
                                json=request_body,
                                timeout=30
                            )
                        except Exception as e:
                            logger.error(f"Final attempt failed: {str(e)}")
                
                # Handle the response
                if response.status_code in [200, 201]:
                    result = response.json()
                    if result.get("success"):
                        st.success("✅ Resume successfully saved to the database!")
                        # Show only the button after success, not the form
                        show_upload_another = True
                        # Set flag to indicate a candidate was added
                        st.session_state.candidate_added = True
                        # Clear the candidates cache to force a refresh
                        clear_candidate_cache()
                        logger.info("Cleared candidate cache after successful resume save")
                    else:
                        st.error(f"Error saving resume: {result.get('message')}")
                        logger.error(f"API returned error: {result}")
                        show_upload_another = False
                else:
                    st.error(f"Error saving resume: {response.text}")
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    show_upload_another = False

                # The Upload Another Resume button will be shown outside of this try/except block
            except Exception as e:
                st.error(f"Error saving resume: {str(e)}")
                logger.exception("Exception while saving resume:")
                show_upload_another = False
        
    # Show upload another button outside of the form context
    # Important: This must be properly outside the st.form() context
    if 'show_upload_another' in locals() and show_upload_another:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("Upload Another Resume"):
                st.session_state.resume_parsed = False
                st.session_state.parsed_resume_data = None
                st.session_state.resume_file = None
                # Keep the candidate_added flag to ensure list refreshes
                # when returning to the candidates list
                st.rerun()

def search_candidates():
    """Search for candidates based on various criteria"""
    st.subheader("Search Candidates")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        keyword = st.text_input("Search by keyword")
    
    with col2:
        position = st.selectbox(
            "Position",
            ["Any", "Software Engineer", "Data Scientist", "Product Manager", "Designer"]
        )
    
    with col3:
        status = st.selectbox(
            "Status",
            ["Any", "Active", "Interviewing", "Hired", "Rejected"]
        )
    
    # Skills multi-select
    skills = st.multiselect(
        "Required Skills",
        ["Python", "Java", "JavaScript", "React", "Angular", "Vue", "SQL", "NoSQL", 
         "AWS", "Azure", "GCP", "Machine Learning", "Data Analysis", "UX Design"]
    )
    
    # Search button
    if st.button("Search"):
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        params = {}
        if keyword:
            params["keyword"] = keyword
        if position and position != "Any":
            params["position"] = position
        if status and status != "Any":
            params["status"] = status
        if skills:
            params["skills"] = ",".join(skills)
        with st.spinner("Searching candidates..."):
            try:
                # Use cached sync client when available
                try:
                    from frontend.utils.http_client import get_sync_client
                    client = get_sync_client()
                except Exception:
                    client = None

                endpoint = f"{api_url.rstrip('/')}/candidates"
                if client is None:
                    resp = requests.get(endpoint, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                else:
                    resp = client.get(endpoint, params=params, timeout=10.0)
                    resp.raise_for_status()
                    data = resp.json()

                candidates = data.get("results") if isinstance(data, dict) else data if isinstance(data, list) else None
                if not isinstance(candidates, list):
                    st.error("Invalid data structure received from API.")
                    logger.error(f"Invalid candidates data: {data}")
                    return

                st.write("### Search Results")
                if len(candidates) == 0:
                    st.info("No candidates match the search criteria.")
                    return

                for c in candidates:
                    c.setdefault("name", "-")
                    c.setdefault("position", "-")
                    c.setdefault("skills", "-")
                    c.setdefault("status", "-")

                # Lazy import pandas only when needed
                import pandas as pd
                df = pd.DataFrame(candidates)
                st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True
                )
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to search candidates: {str(e)}")
                logger.error(f"Error searching candidates: {str(e)}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")
                logger.error(f"Unexpected error: {str(e)}")

def get_status_color(status: str) -> str:
    """Return a color based on candidate status"""
    status_colors = {
        "active": "#10b981",      # green
        "screening": "#3b82f6",   # blue
        "interviewing": "#8b5cf6", # purple
        "offered": "#f59e0b",     # amber
        "hired": "#059669",       # emerald
        "rejected": "#ef4444",    # red
        "withdrawn": "#6b7280",   # gray
        "on_hold": "#f97316"      # orange
    }
    return status_colors.get(status.lower() if status else "", "#6b7280")
