# frontend/modules/candidate_matching.py
import streamlit as st
import pandas as pd
import httpx
import asyncio
import logging
import os
from typing import Dict, List
from .resume_upload import fix_merged_text
from utils.ui_helpers import display_skills_badges, format_skills_list
import requests

# Robust logger setup for production job actions
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "production_job_action.log"))
logger = logging.getLogger("production_job_action")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(log_path, mode='a')
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
logger.propagate = False  # Prevent double logging if root logger is configured elsewhere
logger.info("Loaded candidate_matching.py and logger initialized.")

# Constants
MAX_PAGE_SIZE = 100  # Match backend validation limit

# Setup enhanced logging for button debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('candidate_matching_debug.log')
    ]
)
logger = logging.getLogger('candidate_matching_buttons')

def page():
    """Candidate-to-Job Matching page content (recruiter-focused, agentic endpoints only)"""
    # st.title("🔍 Intelligent Candidate Matching")  # Removed duplicate header
    
    # Add AI Agent indicator
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px; background-color: #f0f7ff; padding: 10px; border-radius: 5px; border-left: 4px solid #4361ee;">
        <div style="margin-right: 10px; font-size: 24px;">🤖</div>
        <div>
            <div style="font-weight: bold; margin-bottom: 5px;">AI-Powered Matching</div>
            <div style="font-size: 0.9em;">This module uses advanced AI to analyze skills, experience, and qualifications for precise candidate-job matching.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(
        """
        Find the best candidates for your jobs, or the best jobs for your candidates. Powered by advanced agentic AI for recruiters.
        """
    )
    tab1, tab2, tab3 = st.tabs(["Jobs → Candidates", "Candidate → Jobs", "Batch Matching"])
    with tab1:
        job_to_candidates()
    with tab2:
        candidate_to_jobs()
    with tab3:
        batch_matching()

async def fetch_jobs_async() -> List[Dict]:
    """Fetch jobs from the API asynchronously"""
    try:
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/jobs/"
        logger.info(f"Fetching jobs from {endpoint}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            data = response.json()
            
            # Check if data is a dictionary with a 'results' field (paginated response)
            if isinstance(data, dict) and "results" in data:
                jobs = data["results"]
                if isinstance(jobs, list):
                    logger.info(f"Successfully fetched {len(jobs)} jobs from API")
                    return jobs
                else:
                    logger.warning(f"Malformed job results: {jobs}")
                    return []
            # Ensure the result is always a list for downstream logic
            elif isinstance(data, dict):
                logger.warning(f"Unexpected response format: {data}")
                return [data]
            else:
                return data
    except Exception as e:
        logger.error(f"Error fetching jobs: {str(e)}", exc_info=True)
        return []

async def fetch_candidates_async() -> List[Dict]:
    """Fetch candidates from the API asynchronously"""
    try:
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/candidates/"
        logger.info(f"Starting paginated fetch for candidates from {endpoint}")
        
        all_candidates = []
        page = 1
        total_candidates = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {"page": page, "page_size": MAX_PAGE_SIZE}
                try:
                    logger.info(f"Fetching page {page} with params: {params}")
                    response = await client.get(endpoint, params=params)
                    response.raise_for_status() # Raise exception for 4xx or 5xx errors
                    data = response.json()
                    
                    # --- Adapt based on actual API response structure --- 
                    # Assuming the response is a dict like: 
                    # {"items": [...], "total": N, "page": P, "size": S}
                    # Adjust keys ('items', 'total') if needed
                    current_page_candidates = data.get("results", []) 
                    if not isinstance(current_page_candidates, list):
                        logger.error(f"Expected 'results' to be a list, but got {type(current_page_candidates)}. Response: {data}")
                        break # Stop if format is wrong
                        
                    all_candidates.extend(current_page_candidates)
                    
                    # Get total count only on the first page
                    if page == 1:
                        total_candidates = data.get("total", 0)
                        if not isinstance(total_candidates, int):
                            logger.warning(f"Could not determine total candidate count from response: {data}")
                            total_candidates = len(current_page_candidates) # Fallback for single page
                    
                    logger.info(f"Fetched {len(current_page_candidates)} candidates from page {page}. Total fetched so far: {len(all_candidates)}. Overall total: {total_candidates}")
                    
                    # Check if we've fetched all candidates
                    if not current_page_candidates or len(all_candidates) >= total_candidates:
                        logger.info("Finished fetching all candidates.")
                        break
                    
                    page += 1 # Move to the next page
                    
                except httpx.HTTPStatusError as exc:
                    logger.error(f"HTTP Status error on page {page}: Status {exc.response.status_code} for {exc.request.url!r}. Response: {exc.response.text}")
                    break # Stop pagination on error
                except httpx.RequestError as exc:
                    logger.error(f"HTTP Request error on page {page}: {exc}")
                    break # Stop pagination on error
                except Exception as e:
                    logger.error(f"Unexpected error fetching candidates on page {page}: {type(e).__name__} - {e}")
                    break # Stop pagination on error
        
        logger.info(f"Finished pagination. Total candidates retrieved: {len(all_candidates)}")
        return all_candidates
    
    except Exception as e:
        logger.error(f"Error fetching candidates: {str(e)}")
        return []

async def match_candidates_for_jobs_async(job_ids: List[int]) -> List[Dict]:
    """Find candidates that match the given jobs"""
    try:
        # Ensure job_ids are integers
        job_ids_int = [int(job_id) for job_id in job_ids if job_id]
        
        if not job_ids_int:
            logger.warning("No valid job IDs provided for matching")
            return []
        
        logger.info(f"Sending payload to match_candidates_for_jobs: job_ids={job_ids_int} (type: {type(job_ids_int)})")
        print("DEBUG match_candidates_for_jobs_async payload:", {"job_ids": job_ids_int, "min_score": 30.0})
        
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/search/match_candidates"
        logger.info(f"Matching candidates via {endpoint}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint, 
                json={"job_ids": job_ids_int, "min_score": 30.0}
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug log the response structure
            logger.info(f"Match candidates API response: {data}")
            
            # Handle different response formats
            if isinstance(data, dict):
                # Check if this is a single job result with candidates
                if "job_id" in data and "candidates" in data:
                    logger.info(f"Detected single job result format with {len(data.get('candidates', []))} candidates")
                    return [data]
                # Check if this is a wrapper with results
                elif "results" in data:
                    logger.info(f"Detected results wrapper format")
                    return data["results"] if isinstance(data["results"], list) else [data["results"]]
                # Other dict format
                else:
                    logger.info(f"Detected unknown dict format, using as is")
                    return [data]
            elif isinstance(data, list):
                logger.info(f"Detected list format with {len(data)} items")
                return data
            else:
                logger.warning(f"Unexpected response type: {type(data)}")
                return []
    except Exception as e:
        logger.error(f"Error matching candidates to jobs: {str(e)}")
        return []

async def match_jobs_for_candidate_async(candidate_id: str) -> List[Dict]:
    """Find jobs that match the given candidate"""
    try:
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/search/match_jobs"
        logger.info(f"Matching jobs for candidate {candidate_id} via {endpoint}")
        
        # Ensure the candidate_id is passed as a string
        candidate_id_str = str(candidate_id)
        payload = {"candidate_id": candidate_id_str, "min_score": 10.0}  # Lower min_score for stricter matching algorithm
        logger.info(f"DEBUG: Sending payload: {payload}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint, 
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"DEBUG: Received response from API: {data}")
            return data
    except Exception as e:
        logger.error(f"Error matching jobs to candidate: {str(e)}")
        return []

async def generate_match_report_async(job_id: int, candidate_id: str) -> Dict:
    """Generate a detailed match report between a job and candidate"""
    try:
        api_url = st.session_state.get("api_url", "http://localhost:8000")
        
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/search/match_report"
        logger.info(f"🔍 Generating match report for job {job_id} and candidate {candidate_id} via {endpoint}")
        
        # Ensure candidate_id is a string
        candidate_id_str = str(candidate_id)
        payload = {"job_id": job_id, "candidate_id": candidate_id_str}
        
        logger.info(f"📤 Sending payload: {payload}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased timeout
            response = await client.post(
                endpoint, 
                json=payload
            )
            
            logger.info(f"📬 Response status: {response.status_code}")
            
            if response.status_code == 404:
                error_msg = "Analysis service endpoint not found - feature may not be implemented"
                logger.error(f"❌ {error_msg}")
                return {"match_score": 0, "explanation": f"Service Error: {error_msg}"}
            elif response.status_code == 500:
                error_text = response.text
                error_msg = f"Backend server error: {error_text[:200]}..."
                logger.error(f"❌ {error_msg}")
                return {"match_score": 0, "explanation": f"Server Error: Backend processing failed"}
            elif response.status_code != 200:
                error_text = response.text
                error_msg = f"API returned {response.status_code}: {error_text[:200]}..."
                logger.error(f"❌ {error_msg}")
                return {"match_score": 0, "explanation": f"API Error: {error_msg}"}
            
            try:
                data = response.json()
                logger.info(f"✅ Successfully received match report data")
                return data
            except Exception as json_err:
                logger.error(f"❌ Failed to parse JSON response: {json_err}")
                return {"match_score": 0, "explanation": f"Data Error: Invalid response format"}
            
    except httpx.TimeoutException:
        error_msg = "Request timed out - analysis is taking too long"
        logger.error(f"⏱️ {error_msg}")
        return {"match_score": 0, "explanation": f"Timeout Error: {error_msg}"}
    except httpx.ConnectError:
        error_msg = "Cannot connect to backend server - check if server is running"
        logger.error(f"🔌 {error_msg}")
        return {"match_score": 0, "explanation": f"Connection Error: {error_msg}"}
    except Exception as e:
        error_msg = f"Unexpected error during analysis: {str(e)}"
        logger.error(f"💥 {error_msg}")
        return {"match_score": 0, "explanation": f"System Error: {error_msg}"}

def job_to_candidates():
    """Interface for matching jobs to candidates"""
    st.subheader("Find Best Candidates for Jobs")
    
    # Fetch available jobs
    with st.spinner("Loading available jobs..."):
        jobs = fetch_jobs()
    
    # Remove redundant check since fetch_jobs_async already handles this
    if not jobs:
        st.warning("No jobs found. Please create some jobs first.")
        return
    
    # Defensive: filter out jobs missing 'id' or 'title' and log malformed jobs
    valid_jobs = []
    for job in jobs:
        if not isinstance(job, dict) or 'id' not in job or 'title' not in job:
            logger.warning(f"Malformed job entry: {job}")
            continue
        valid_jobs.append(job)

    if not valid_jobs:
        st.warning("No valid jobs found. Please check job data format.")
        return

    job_options = {f"{job['id']} - {job['title']}": job['id'] for job in valid_jobs}
    
    # Job selection
    selected_job_keys = st.multiselect(
        "Select jobs to find candidates for:",
        options=list(job_options.keys()),
        default=[list(job_options.keys())[0]] if job_options else None
    )
    
    selected_job_ids = [job_options[key] for key in selected_job_keys]

    # Ensure all job IDs are integers
    selected_job_ids = [int(jid) for jid in selected_job_ids if isinstance(jid, (int, str)) and str(jid).isdigit()]

    # Prevent empty selection
    if not selected_job_ids:
        st.warning("Please select at least one job.")
        return
    
    # Minimum match threshold - lower default to show more results
    min_match_score = st.slider(
        "Minimum match score (%)", 
        min_value=0, 
        max_value=100, 
        value=5,  # Lower default to show more candidates
        step=5,
        key="basic_job_to_candidates_min_score"
    )
    
    # Fetch and display matches
    if selected_job_ids and st.button("Find Matching Candidates"):
        with st.spinner("Finding best candidates for selected jobs..."):
            results = asyncio.run(match_candidates_for_jobs_async(selected_job_ids))
            logger.info(f"Got matching results: {results}")
            
        if not results:
            st.warning("No matching candidates found or there was an error retrieving matches.")
        else:
            # Check if results is a flat list of candidates (flattened response)
            # or a list of job results (structured response)
            if results and isinstance(results, list) and results and isinstance(results[0], dict) and "match_score" in results[0]:
                # Flattened response - direct list of candidates
                logger.info(f"Detected flattened response format with {len(results)} candidates")
                candidates = results
                
                # Filter by minimum match score
                candidates = [c for c in candidates if c.get("match_score", 0) >= min_match_score]
                logger.info(f"After filtering by min score {min_match_score}%, have {len(candidates)} candidates")
                
                # Get job details from the selected jobs
                job_title = "Selected Job"
                for job in jobs:
                    if job['id'] == selected_job_ids[0]:  # Use the first selected job for the title
                        job_title = job['title']
                        break
                
                st.markdown(f"### Results for: {job_title}")
                
                if not candidates:
                    st.info(f"No candidates with match score >= {min_match_score}% found for this job.")
                else:
                    # Sort candidates by match score (highest first)
                    candidates = sorted(candidates, key=lambda x: x.get("match_score", 0), reverse=True)
                    
                    # Display candidates
                    display_candidate_results(candidates, selected_job_ids[0], min_match_score)
            else:
                # Original structured response format
                # Display results for each job
                logger.info(f"Detected structured response format with {len(results)} job results")
                for job_result in results:
                    if not isinstance(job_result, dict):
                        logger.error(f"Unexpected job_result type: {type(job_result)} - value: {job_result}")
                        st.warning(f"Warning: Unexpected result type from backend. Skipping entry: {job_result}")
                        continue
                    
                    job_id = job_result.get("job_id")
                    job_title = job_result.get("job_title")
                    # Check both 'candidates' and 'results' fields for backward compatibility
                    candidates = job_result.get("candidates", [])
                    if not candidates:
                        candidates = job_result.get("results", [])
                    
                    logger.info(f"Processing job {job_id} ({job_title}) with {len(candidates)} candidates")
                    
                    # Filter by minimum match score
                    candidates = [c for c in candidates if c.get("match_score", 0) >= min_match_score]
                    logger.info(f"After filtering by min score {min_match_score}%, have {len(candidates)} candidates")
                    
                    st.markdown(f"### Results for: {job_title}")
                    
                    if not candidates:
                        st.info(f"No candidates with match score >= {min_match_score}% found for this job.")
                        continue
                    
                    # Display candidates
                    display_candidate_results(candidates, job_id, min_match_score)

def display_candidate_results(candidates, job_id, min_match_score):
    """Display candidate results in expandable sections"""
    # Add debug expander to show raw data
    with st.expander("Debug: Raw Candidate Data", expanded=False):
        # st.json(candidates)  # Commented out for production
        st.write("Raw candidate data display disabled for production")
    
    # Check if we have any candidates to display
    if not candidates:
        st.warning("No candidates to display after filtering.")
        return
    
    # Create expandable sections for each candidate
    for i, candidate in enumerate(candidates):
        # Get match score with fallback
        match_score = candidate.get('match_score', 0)
        
        # Get candidate name with fallbacks
        name = candidate.get('name')
        if not name:
            # Try to construct from first_name and last_name if available
            first_name = candidate.get('first_name', '')
            last_name = candidate.get('last_name', '')
            if first_name or last_name:
                name = f"{first_name} {last_name}".strip()
            else:
                name = f"Candidate {i+1}"
        
        with st.expander(
            f"#{i+1}: {name} - Match: {match_score:.1f}%",
            expanded=i == 0  # Expand first result by default
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Candidate header with status
                st.markdown(f"### {name}")
                if candidate.get('headline'):
                    st.caption(candidate.get('headline'))
                
                # Contact information
                st.markdown("#### Contact Information")
                contact_col1, contact_col2 = st.columns(2)
                with contact_col1:
                    st.markdown(f"📧 {candidate.get('email', 'N/A')}")
                    st.markdown(f"📱 {candidate.get('phone', 'N/A')}")
                with contact_col2:
                    st.markdown(f"📍 {candidate.get('location', 'N/A')}")
                    if candidate.get('experience_years'):
                        st.markdown(f"⏳ {candidate.get('experience_years')} years experience")
                
                # Current position
                if candidate.get('position') or candidate.get('current_company'):
                    st.markdown("#### Current Position")
                    st.markdown(f"💼 {candidate.get('position', 'N/A')}")
                    st.markdown(f"🏢 {candidate.get('current_company', 'N/A')}")
                
                # Education
                if candidate.get('education'):
                    st.markdown("#### Education")
                    education = candidate.get('education', [])
                    if isinstance(education, list):
                        for edu in education:
                            if isinstance(edu, dict):
                                degree = edu.get('degree', 'Degree')
                                institution = edu.get('institution', 'Institution')
                                grad_year = edu.get('year', '')
                                st.markdown(f"🎓 **{degree}** - {institution} {f'({grad_year})' if grad_year else ''}")
                            else:
                                st.markdown(f"🎓 {edu}")
                    else:
                        st.markdown(f"🎓 {education}")
                
                # Work Experience
                if candidate.get('experience'):
                    st.markdown("#### Work Experience")
                    experience = candidate.get('experience', [])
                    for exp in experience:
                        if isinstance(exp, dict):
                            title = exp.get('title', 'Title')
                            company = exp.get('company', 'Company')
                            duration = exp.get('duration', '')
                            description = fix_merged_text(exp.get('description', ''))
                            
                            st.markdown(f"**{title}** at **{company}** {f'({duration})' if duration else ''}")
                            if description:
                                st.markdown(description)
                            st.markdown("---")
                        else:
                            st.markdown(f"• {exp}")
                            st.markdown("---")
                
                # Skills
                if candidate.get('skills'):
                    st.markdown("#### Skills")
                    skills = candidate.get('skills', [])
                    # Use the safe skills display function
                    display_skills_badges(skills, max_per_row=4, badge_style="default")
                
                # Match explanation
                if candidate.get('match_explanation'):
                    st.markdown("#### Match Analysis")
                    st.info(candidate.get('match_explanation', 'No explanation provided'))
            
            with col2:
                # Match score with color
                score_color = "#10b981" if match_score >= 80 else "#f59e0b" if match_score >= 60 else "#ef4444"
                st.markdown(f"""
                <div style='background:{score_color};color:white;padding:12px;border-radius:8px;text-align:center;margin-bottom:16px;'>
                    <div style='font-size:24px;font-weight:600;'>{match_score:.1f}%</div>
                    <div style='font-size:14px;'>Match Score</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                st.button(
                    "View Full Profile", 
                    key=f"view_profile_{candidate.get('id', '')}_{job_id}",
                    help="View the candidate's complete profile"
                )
                
                st.button(
                    "Generate Match Report", 
                    key=f"match_report_{candidate.get('id', '')}_{job_id}",
                    help="Generate a detailed AI analysis of this match"
                )

def candidate_to_jobs():
    """Interface for matching a candidate to jobs"""
    st.subheader("Find Best Jobs for a Candidate")
    
    # Fetch available candidates
    with st.spinner("Loading candidates..."):
        candidates = fetch_candidates()
    
    if not candidates:
        st.warning("No candidates found. Please add some candidates first.")
        return

    # Create enhanced candidate selection UI
    st.markdown("### Select a Candidate")
    
    # Process candidates into a more structured format
    processed_candidates = []
    for c in candidates:
        # Get name using multiple possible fields
        name = c.get('name', '')
        if not name or name.strip() == '':
            first = c.get('first_name', '').strip()
            last = c.get('last_name', '').strip()
            if first or last:
                name = f"{first} {last}".strip()
            else:
                name = c.get('email', f"Candidate {str(c['id'])[:8]}")
        
        # Extract other candidate information
        candidate_info = {
            'id': c.get('id'),
            'name': name,
            'email': c.get('email', 'No email provided'),
            'position': c.get('current_position', c.get('position', 'Position not specified')),
            'company': c.get('current_company', c.get('company', '')),
            'skills': c.get('skills', []),
            'experience_years': c.get('experience_years', c.get('years_experience', 'Not specified')),
            'location': c.get('location', 'Location not specified'),
            'phone': c.get('phone', 'Not provided')
        }
        processed_candidates.append(candidate_info)
    
    # Create a filter for easier candidate finding
    search_term = st.text_input("Search candidates by name, skills, or position:", 
                                key="basic_candidate_search",
                                placeholder="Type to filter candidates...")
    
    # Filter candidates based on search term
    if search_term:
        filtered_candidates = []
        for c in processed_candidates:
            # Format skills safely for search
            safe_skills = format_skills_list(c.get('skills', []))
            if (search_term.lower() in c['name'].lower() or 
                search_term.lower() in c['position'].lower() or
                search_term.lower() in c['email'].lower() or
                any(search_term.lower() in skill.lower() for skill in safe_skills)):
                filtered_candidates.append(c)
        display_candidates = filtered_candidates
    else:
        display_candidates = processed_candidates
    
    # Show how many candidates match the filter
    if search_term:
        st.caption(f"Showing {len(display_candidates)} of {len(processed_candidates)} candidates")
    
    # Display candidates with card-based UI
    selected_candidate_id = None
    
    if not display_candidates:
        st.warning("No candidates found matching your search criteria.")
    else:
        # Use a container to style the selection area
        with st.container():
            st.markdown("#### Available Candidates")
            
            # Use grid layout for candidate cards
            # We'll show 2 candidates per row in a responsive layout
            for i in range(0, len(display_candidates), 2):
                col1, col2 = st.columns(2)
                
                # First candidate in this row
                with col1:
                    if i < len(display_candidates):
                        candidate = display_candidates[i]
                        
                        # Safely handle None values and create comprehensive candidate cards
                        name = candidate['name'] or "Unknown Candidate"
                        position = candidate['position'] if candidate['position'] != 'Position not specified' else "Position not specified"
                        location = candidate['location'] if candidate['location'] not in ['Location not specified', 'None', None] else "Remote/Flexible"
                        company = candidate.get('company', '')
                        experience_years = candidate.get('experience_years', 'Not specified')
                        email = candidate.get('email', 'Not provided')
                        
                        # Format skills for display
                        skills = candidate.get('skills', [])
                        skills_display = ""
                        if skills and len(skills) > 0:
                            skill_list = skills[:3]  # Show first 3 skills
                            skills_text = ", ".join(skill_list)
                            if len(skills) > 3:
                                skills_text += f" +{len(skills) - 3} more"
                            skills_display = f"<p><strong>Top Skills:</strong> {skills_text}</p>"
                        
                        # Create a comprehensive card-like UI for each candidate
                        with st.container():
                            st.markdown(f"""
                            <div style="border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:12px; background:#f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <h4 style="margin-top:0; margin-bottom:8px; color:#2c3e50;">{name}</h4>
                                <p style="margin:4px 0;"><strong>Position:</strong> {position}</p>
                                {f'<p style="margin:4px 0;"><strong>Company:</strong> {company}</p>' if company else ''}
                                <p style="margin:4px 0;"><strong>Location:</strong> {location}</p>
                                <p style="margin:4px 0;"><strong>Experience:</strong> {experience_years} years</p>
                                {skills_display}
                                <p style="margin:4px 0; font-size:12px; color:#666;">📧 {email}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Add a select button for each candidate
                            if st.button(f"Select {name.split()[0]}", key=f"select_candidate_{candidate['id']}"):
                                selected_candidate_id = candidate['id']
                                st.session_state.selected_candidate_id = selected_candidate_id
                                st.rerun()  # Force page refresh to show selection
                
                # Second candidate in this row
                with col2:
                    if i + 1 < len(display_candidates):
                        candidate = display_candidates[i + 1]
                        
                        # Safely handle None values and create comprehensive candidate cards
                        name = candidate['name'] or "Unknown Candidate"
                        position = candidate['position'] if candidate['position'] != 'Position not specified' else "Position not specified"
                        location = candidate['location'] if candidate['location'] not in ['Location not specified', 'None', None] else "Remote/Flexible"
                        company = candidate.get('company', '')
                        experience_years = candidate.get('experience_years', 'Not specified')
                        email = candidate.get('email', 'Not provided')
                        
                        # Format skills for display
                        skills = candidate.get('skills', [])
                        skills_display = ""
                        if skills and len(skills) > 0:
                            skill_list = skills[:3]  # Show first 3 skills
                            skills_text = ", ".join(skill_list)
                            if len(skills) > 3:
                                skills_text += f" +{len(skills) - 3} more"
                            skills_display = f"<p><strong>Top Skills:</strong> {skills_text}</p>"
                        
                        # Create a comprehensive card-like UI for each candidate
                        with st.container():
                            st.markdown(f"""
                            <div style="border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:12px; background:#f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <h4 style="margin-top:0; margin-bottom:8px; color:#2c3e50;">{name}</h4>
                                <p style="margin:4px 0;"><strong>Position:</strong> {position}</p>
                                {f'<p style="margin:4px 0;"><strong>Company:</strong> {company}</p>' if company else ''}
                                <p style="margin:4px 0;"><strong>Location:</strong> {location}</p>
                                <p style="margin:4px 0;"><strong>Experience:</strong> {experience_years} years</p>
                                {skills_display}
                                <p style="margin:4px 0; font-size:12px; color:#666;">📧 {email}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Add a select button for each candidate
                            if st.button(f"Select {name.split()[0]}", key=f"select_candidate_{candidate['id']}"):
                                selected_candidate_id = candidate['id']
                                st.session_state.selected_candidate_id = selected_candidate_id
                                st.rerun()  # Force page refresh to show selection
    
    # Show selection status
    if 'selected_candidate_id' in st.session_state:
        selected_candidate_id = st.session_state.selected_candidate_id
        # Find the selected candidate data
        selected_candidate_data = next((c for c in processed_candidates if c['id'] == selected_candidate_id), None)
        
        if selected_candidate_data:
            st.success(f"✅ **Selected:** {selected_candidate_data['name']} (ID: {selected_candidate_id})")
        else:
            st.warning(f"⚠️ Selected candidate ID {selected_candidate_id} not found in current list")
    else:
        st.info("👆 **Please select a candidate above to continue**")
        
    # If a candidate is selected, use the one from session state
    if 'selected_candidate_id' in st.session_state:
        selected_candidate_id = st.session_state.selected_candidate_id
        
        # Find the selected candidate data
        selected_candidate_data = next((c for c in processed_candidates if c['id'] == selected_candidate_id), None)
        
        if selected_candidate_data:
            # Display detailed information for the selected candidate
            st.markdown("---")
            st.subheader("Selected Candidate Details")
            
            # Create a nice layout for the candidate details
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"### {selected_candidate_data['name']}")
                
                # Handle position display
                position = selected_candidate_data['position']
                if position == 'Position not specified':
                    position = "Position not specified"
                st.markdown(f"**Position:** {position}")
                
                # Handle company display
                company = selected_candidate_data.get('company', '')
                if company and company.strip():
                    st.markdown(f"**Company:** {company}")
                
                # Handle location display
                location = selected_candidate_data['location']
                if location in ['Location not specified', 'None', None]:
                    location = "Remote/Flexible"
                st.markdown(f"**Location:** {location}")
                
                # Handle experience display
                experience = selected_candidate_data['experience_years']
                if experience == 'Not specified':
                    experience = "Experience not specified"
                st.markdown(f"**Experience:** {experience}")
            
            with col2:
                # Create a card-like UI for contact information
                st.markdown("**Contact Information:**")
                
                # Handle email display
                email = selected_candidate_data['email']
                if email == 'No email provided':
                    email = "Email not provided"
                st.markdown(f"📧 {email}")
                
                # Handle phone display
                phone = selected_candidate_data['phone']
                if phone == 'Not provided':
                    phone = "Phone not provided"
                st.markdown(f"📱 {phone}")
            
            # Display skills in a nicer format
            skills = selected_candidate_data.get('skills', [])
            if skills and len(skills) > 0:
                st.markdown("**Skills:**")
                # Use the safe skills display function
                display_skills_badges(skills, max_per_row=3, badge_style="compact")
            else:
                st.markdown("**Skills:** No skills listed")
            
            # Show the minimum score slider only when a candidate is selected
            st.markdown("---")
            min_match_score = st.slider(
                "Minimum match score (%)", 
                min_value=0, 
                max_value=100, 
                value=15,  # Lower default for stricter matching algorithm
                step=5,
                key="basic_candidate_to_jobs_min_score"
            )
            
            # Fetch and display matches
            # Check if we already have results for this candidate in session state
            results_key = f"job_matches_{selected_candidate_id}"
            
            if st.button("Find Matching Jobs"):
                with st.spinner("Finding best jobs for selected candidate..."):
                    try:
                        results = asyncio.run(match_jobs_for_candidate_async(selected_candidate_id))
                        # Save results to session state to persist across reruns
                        st.session_state[results_key] = results
                        logger.info(f"SAVED MATCHING RESULTS to session state: {results_key}")
                    except Exception as e:
                        st.error(f"Error calling match_jobs_for_candidate_async: {str(e)}")
                        results = {}
                        st.session_state[results_key] = {}
            
            # Check for existing results in session state
            elif results_key in st.session_state:
                results = st.session_state[results_key]
                logger.info(f"LOADED EXISTING RESULTS from session state: {results_key}")
            else:
                results = {}
                
            if not results:
                if results_key not in st.session_state:
                    st.info("👆 Click 'Find Matching Jobs' to see available positions for this candidate")
                else:
                    st.warning("No matching jobs found or there was an error retrieving matches.")
            else:
                # Display results
                jobs = results.get("results", [])
                
                # Filter by minimum match score
                jobs = [j for j in jobs if j.get("match_score", 0) >= min_match_score]
                
                if not jobs:
                    st.info(f"No jobs with match score >= {min_match_score}% found for this candidate.")
                else:
                    st.markdown(f"### {len(jobs)} Matching Jobs Found")
                    
                    # Create expandable sections for each job
                    for i, job in enumerate(jobs):
                        # Handle None values for better display
                        job_title = job.get('title', 'Job Title Not Specified')
                        department = job.get('department', 'Department not specified')
                        location = job.get('location')
                        if location in ['Not specified', 'None', None, '']:
                            location = 'Remote/Flexible'
                        
                        match_score = job.get('match_score', 0)
                        
                        # Color coding for match score
                        if match_score >= 80:
                            score_color = "#10b981"  # Green for excellent matches
                            score_label = "Excellent Match"
                        elif match_score >= 60:
                            score_color = "#3b82f6"  # Blue for good matches  
                            score_label = "Good Match"
                        elif match_score >= 40:
                            score_color = "#f59e0b"  # Orange for moderate matches
                            score_label = "Moderate Match"
                        else:
                            score_color = "#ef4444"  # Red for poor matches
                            score_label = "Poor Match"
                        
                        with st.expander(
                            f"#{i+1}: {job_title} - Match: {match_score:.1f}% ({score_label})",
                            expanded=i == 0  # Expand first result by default
                        ):
                            # Enhanced job card layout
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                # Job header with enhanced styling
                                st.markdown(f"""
                                <div style='background:{score_color};color:white;padding:12px;border-radius:8px;margin-bottom:16px;'>
                                    <h3 style='margin:0;color:white;'>{job_title}</h3>
                                    <p style='margin:4px 0;color:white;opacity:0.9;'>{department} • {location}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Job description preview
                                description = job.get('description', '')
                                if description:
                                    desc_preview = description[:200] + "..." if len(description) > 200 else description
                                    st.markdown(f"**Description:** {desc_preview}")
                                
                                # Display required skills with badges
                                skills = job.get('skills', [])
                                if skills:
                                    st.markdown("**Required Skills:**")
                                    # Create skill badges
                                    skills_html = ""
                                    for skill in skills[:8]:  # Show first 8 skills
                                        skills_html += f'<span style="background:#e2e8f0;color:#1e293b;padding:4px 8px;border-radius:12px;margin:2px;display:inline-block;font-size:12px;">{skill}</span> '
                                    if len(skills) > 8:
                                        skills_html += f'<span style="background:#cbd5e1;color:#475569;padding:4px 8px;border-radius:12px;margin:2px;display:inline-block;font-size:12px;">+{len(skills)-8} more</span>'
                                    st.markdown(skills_html, unsafe_allow_html=True)
                                
                                # Match explanation with better formatting
                                explanation = job.get('match_explanation', 'No explanation provided')
                                st.markdown("**Match Analysis:**")
                                st.markdown(f"""
                                <div style='background:#f8f9fa;padding:12px;border-radius:6px;border-left:4px solid {score_color};'>
                                    <p style='margin:0;'>{explanation}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            with col2:
                                # Enhanced match score display
                                st.markdown(f"""
                                <div style='background:{score_color};color:white;padding:16px;border-radius:8px;text-align:center;margin-bottom:16px;'>
                                    <div style='font-size:24px;font-weight:600;'>{match_score:.1f}%</div>
                                    <div style='font-size:14px;'>{score_label}</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Component scores if available
                                if any(job.get(key) for key in ['skill_match_score', 'role_match_score', 'experience_match_score']):
                                    st.markdown("**Score Breakdown:**")
                                    
                                    if job.get('role_match_score'):
                                        role_score = job.get('role_match_score', 0)
                                        st.markdown(f"Role: {role_score:.1f}%")
                                        st.progress(role_score/100)
                                    
                                    if job.get('skill_match_score'):
                                        skill_score = job.get('skill_match_score', 0)
                                        st.markdown(f"Skills: {skill_score:.1f}%")
                                        st.progress(skill_score/100)
                                    
                                    if job.get('experience_match_score'):
                                        exp_score = job.get('experience_match_score', 0)
                                        st.markdown(f"Experience: {exp_score:.1f}%")
                                        st.progress(exp_score/100)
                                
                                # Action buttons
                                st.markdown("**Actions:**")
                                
                                # Initialize analysis state
                                # Action Buttons for Job Application
                                st.markdown("#### Take Action on This Job")
                                
                                job_id = job.get('id')
                                action_key = f"{selected_candidate_id}_{job_id}"
                                
                                # Safety check: ensure we have a valid candidate ID
                                if not selected_candidate_id:
                                    st.error("❌ No candidate selected. Please select a candidate first.")
                                    continue
                                
                                # DEBUG: Check if we reach the button section
                                logger.info(f"REACHED BUTTON SECTION for job_id={job_id}, candidate_id={selected_candidate_id}")
                                logger.info(f"Action key: {action_key}")
                                
                                # Create action button layout
                                job_action_col1, job_action_col2, job_action_col3 = st.columns(3)
                                
                                # DEBUG: Check button state before creating buttons
                                button_states = {}
                                for key, value in st.session_state.items():
                                    if f"job_{job_id}" in str(key) or f"view_job_details_{job_id}" in str(key):
                                        button_states[key] = value
                                
                                if button_states:
                                    logger.info(f"EXISTING BUTTON STATES: {button_states}")
                                
                                with job_action_col1:
                                    # Apply to Job button with comprehensive debugging
                                    logger.info(f"CREATING APPLY BUTTON: apply_job_{job_id}")
                                    if st.button("✅ Apply to Job", 
                                                key=f"apply_job_{job_id}", 
                                                type="primary",
                                                help="Submit application for this job"):
                                        
                                        # COMPREHENSIVE DEBUGGING - Apply Button
                                        logger.info("="*80)
                                        logger.info("APPLY TO JOB BUTTON CLICKED")
                                        logger.info("="*80)
                                        logger.info(f"Timestamp: {pd.Timestamp.now()}")
                                        logger.info(f"Job ID: {job_id}")
                                        logger.info(f"Job Title: {job.get('title', 'Unknown')}")
                                        logger.info(f"Selected Candidate ID: {selected_candidate_id}")
                                        logger.info(f"Action Key: {action_key}")
                                        
                                        # Log session state before action
                                        logger.info("Session State Before Apply:")
                                        for key, value in st.session_state.items():
                                            if key.startswith(('current_page', 'api_', 'job_', 'candidate_')):
                                                logger.info(f"  {key}: {value}")
                                        
                                        # Log query parameters
                                        logger.info(f"Query Params: {dict(st.query_params)}")
                                        
                                        with st.spinner("Submitting job application..."):
                                            try:
                                                # Make API call to submit application
                                                api_url = st.session_state.get("api_url", "http://localhost:8000")
                                                request_url = f"{api_url}/api/jobs/{job_id}/apply"
                                                request_payload = {
                                                    "candidate_id": str(selected_candidate_id),
                                                    "source": "candidate_matching"
                                                }
                                                
                                                # Enhanced debugging for API call
                                                logger.info("API CALL DETAILS:")
                                                logger.info(f"  Request URL: {request_url}")
                                                logger.info(f"  Request Method: POST")
                                                logger.info(f"  Request Payload: {request_payload}")
                                                logger.info(f"  Timeout: 10 seconds")
                                                
                                                # Make the request
                                                response = requests.post(
                                                    request_url,
                                                    json=request_payload,
                                                    timeout=10
                                                )
                                                
                                                # Log detailed response
                                                logger.info("API RESPONSE DETAILS:")
                                                logger.info(f"  Response Status: {response.status_code}")
                                                logger.info(f"  Response Headers: {dict(response.headers)}")
                                                logger.info(f"  Response Text: {response.text}")
                                                logger.info(f"  Response Size: {len(response.text)} chars")
                                                
                                                if response.status_code == 200:
                                                    st.success(f"✅ Application submitted for {job.get('title')} role!")
                                                    st.info("📋 **Next Steps:**\n- Wait for employer response\n- Prepare for potential screening\n- Check your applications in the Candidate Pipeline")
                                                    
                                                    # Update session state for UI consistency
                                                    if 'job_applications' not in st.session_state:
                                                        st.session_state['job_applications'] = {}
                                                    st.session_state['job_applications'][action_key] = {
                                                        'action': 'applied',
                                                        'job_id': job_id,
                                                        'job_title': job.get('title'),
                                                        'candidate_id': selected_candidate_id,
                                                        'timestamp': pd.Timestamp.now()
                                                    }
                                                    
                                                    logger.info("SUCCESS: Application submitted successfully")
                                                    logger.info(f"Updated session state: job_applications[{action_key}]")
                                                    
                                                elif response.status_code == 400 and "Already applied" in response.text:
                                                    st.warning("⚠️ You have already applied to this job!")
                                                    logger.warning("User already applied to this job")
                                                elif response.status_code == 404:
                                                    st.error("❌ Job or candidate not found. Please refresh and try again.")
                                                    logger.error("404 - Job or candidate not found")
                                                else:
                                                    st.error(f"❌ Failed to submit application (Status {response.status_code}): {response.text}")
                                                    st.error(f"🔗 Request URL: {request_url}")
                                                    logger.error(f"API Error: Status {response.status_code}, Response: {response.text}")
                                                    
                                            except requests.exceptions.ConnectionError as e:
                                                error_msg = f"Connection error: {e}"
                                                logger.error(error_msg)
                                                st.error("❌ Cannot connect to backend server!")
                                                st.error("💡 **Solution:** Make sure the backend is running:")
                                                st.code("cd backend && python start_backend.py")
                                                st.error(f"🔗 Expected backend URL: {api_url}")
                                            except requests.exceptions.RequestException as e:
                                                error_msg = f"API request failed: {e}"
                                                logger.error(error_msg)
                                                st.error(f"❌ Failed to submit application: {str(e)}")
                                            except Exception as e:
                                                error_msg = f"Exception during apply: {e}"
                                                logger.error(error_msg)
                                                logger.exception("Full exception traceback:")
                                                st.error(f"❌ Failed to submit application: {str(e)}")
                                                
                                        logger.info("="*80)
                                        logger.info("APPLY TO JOB BUTTON COMPLETED")
                                        logger.info("="*80)
                                
                                with job_action_col2:
                                    # Save for Later button with comprehensive debugging
                                    logger.info(f"CREATING SAVE BUTTON: save_job_{job_id}")
                                    if st.button("💾 Save for Later", 
                                                key=f"save_job_{job_id}",
                                                help="Save this job to review later"):
                                        
                                        # COMPREHENSIVE DEBUGGING - Save Button
                                        logger.info("="*80)
                                        logger.info("SAVE FOR LATER BUTTON CLICKED")
                                        logger.info("="*80)
                                        logger.info(f"Timestamp: {pd.Timestamp.now()}")
                                        logger.info(f"Job ID: {job_id}")
                                        logger.info(f"Job Title: {job.get('title', 'Unknown')}")
                                        logger.info(f"Selected Candidate ID: {selected_candidate_id}")
                                        logger.info(f"Action Key: {action_key}")
                                        
                                        # Log session state before action
                                        logger.info("Session State Before Save:")
                                        for key, value in st.session_state.items():
                                            if key.startswith(('current_page', 'api_', 'job_', 'candidate_', 'saved_')):
                                                logger.info(f"  {key}: {value}")
                                        
                                        with st.spinner("Saving job..."):
                                            try:
                                                # Make API call to save job
                                                api_url = st.session_state.get("api_url", "http://localhost:8000")
                                                request_url = f"{api_url}/api/jobs/{job_id}/save"
                                                request_payload = {
                                                    "candidate_id": str(selected_candidate_id),
                                                    "notes": f"Saved from candidate matching on {pd.Timestamp.now().strftime('%Y-%m-%d')}"
                                                }
                                                
                                                # Enhanced debugging for API call
                                                logger.info("SAVE API CALL DETAILS:")
                                                logger.info(f"  Request URL: {request_url}")
                                                logger.info(f"  Request Method: POST")
                                                logger.info(f"  Request Payload: {request_payload}")
                                                logger.info(f"  Timeout: 10 seconds")
                                                
                                                response = requests.post(
                                                    request_url,
                                                    json=request_payload,
                                                    timeout=10
                                                )
                                                
                                                # Log detailed response
                                                logger.info("SAVE API RESPONSE DETAILS:")
                                                logger.info(f"  Response Status: {response.status_code}")
                                                logger.info(f"  Response Headers: {dict(response.headers)}")
                                                logger.info(f"  Response Text: {response.text}")
                                                logger.info(f"  Response Size: {len(response.text)} chars")
                                                
                                                if response.status_code == 200:
                                                    st.success(f"💾 {job.get('title')} saved to your job list!")
                                                    st.info("📌 **Job saved!** You can find it in your saved jobs list.")
                                                    
                                                    # Update session state for UI consistency
                                                    if 'saved_jobs' not in st.session_state:
                                                        st.session_state['saved_jobs'] = {}
                                                    st.session_state['saved_jobs'][action_key] = {
                                                        'action': 'saved',
                                                        'job_id': job_id,
                                                        'job_title': job.get('title'),
                                                        'candidate_id': selected_candidate_id,
                                                        'timestamp': pd.Timestamp.now()
                                                    }
                                                    
                                                    logger.info("SUCCESS: Job saved successfully")
                                                    logger.info(f"Updated session state: saved_jobs[{action_key}]")
                                                    
                                                    # Optional: Show navigation to saved jobs
                                                    if st.button("View Saved Jobs", key=f"view_saved_{job_id}"):
                                                        logger.info("View Saved Jobs button clicked - navigating to jobs page")
                                                        st.session_state.current_page = "jobs"
                                                        st.query_params.clear()
                                                        st.query_params["view"] = "saved"
                                                        st.rerun()
                                                        
                                                elif response.status_code == 404:
                                                    st.error("❌ Job or candidate not found. Please refresh and try again.")
                                                    logger.error("404 - Job or candidate not found")
                                                else:
                                                    st.error(f"❌ Failed to save job (Status {response.status_code}): {response.text}")
                                                    st.error(f"🔗 Request URL: {request_url}")
                                                    logger.error(f"Save API Error: Status {response.status_code}, Response: {response.text}")
                                                    
                                            except requests.exceptions.ConnectionError as e:
                                                error_msg = f"Save connection error: {e}"
                                                logger.error(error_msg)
                                                st.error("❌ Cannot connect to backend server!")
                                                st.error("💡 **Solution:** Make sure the backend is running:")
                                                st.code("cd backend && python start_backend.py")
                                                st.error(f"🔗 Expected backend URL: {api_url}")
                                            except requests.exceptions.RequestException as e:
                                                error_msg = f"Save API request failed: {e}"
                                                logger.error(error_msg)
                                                st.error(f"❌ Failed to save job: {str(e)}")
                                            except Exception as e:
                                                error_msg = f"Exception during save: {e}"
                                                logger.error(error_msg)
                                                logger.exception("Full save exception traceback:")
                                                st.error(f"❌ Failed to save job: {str(e)}")
                                                
                                        logger.info("="*80)
                                        logger.info("SAVE FOR LATER BUTTON COMPLETED")
                                        logger.info("="*80)
                                
                                with job_action_col3:
                                    # View Job Details button with comprehensive debugging
                                    logger.info(f"CREATING VIEW DETAILS BUTTON: view_job_details_{job_id}_{selected_candidate_id}")
                                    if st.button("📄 View Job Details", 
                                                key=f"view_job_details_{job_id}_{selected_candidate_id}",
                                                help="See full job description and requirements"):
                                        
                                        # COMPREHENSIVE DEBUGGING - View Details Button
                                        logger.info("="*80)
                                        logger.info("VIEW JOB DETAILS BUTTON CLICKED")
                                        logger.info("="*80)
                                        logger.info(f"Timestamp: {pd.Timestamp.now()}")
                                        logger.info(f"Job ID: {job_id}")
                                        logger.info(f"Job Title: {job.get('title', 'Unknown')}")
                                        logger.info(f"Selected Candidate ID: {selected_candidate_id}")
                                        logger.info(f"Button Key: view_job_details_{job_id}_{selected_candidate_id}")
                                        
                                        # Log current navigation state
                                        logger.info("BEFORE NAVIGATION - Session State:")
                                        for key, value in st.session_state.items():
                                            if key.startswith(('current_page', 'selected_', 'view_', 'api_', 'pending_')):
                                                logger.info(f"  {key}: {value}")
                                        
                                        logger.info(f"BEFORE NAVIGATION - Query Params: {dict(st.query_params)}")
                                        
                                        # Clear any existing view_handled flag
                                        if "view_handled" in st.session_state:
                                            logger.info("Clearing existing view_handled flag")
                                            del st.session_state["view_handled"]
                                        
                                        # DUAL NAVIGATION APPROACH: Query Params + Session State Fallback
                                        logger.info("Setting navigation parameters (dual approach)...")
                                        
                                        # Method 1: Set session state (always works)
                                        st.session_state.current_page = "job_detail"
                                        st.session_state.selected_job_id = str(job_id)
                                        
                                        # Method 2: Set pending navigation (fallback)
                                        st.session_state.pending_navigation_page = "job_detail"
                                        st.session_state.pending_navigation_id = str(job_id)
                                        
                                        # Method 3: Set query parameters (traditional)
                                        logger.info("Clearing and setting query parameters...")
                                        try:
                                            st.query_params.clear()
                                            st.query_params["view"] = "job_detail"
                                            st.query_params["id"] = str(job_id)
                                            logger.info("Query parameters set successfully")
                                        except Exception as e:
                                            logger.warning(f"Failed to set query parameters: {e}")
                                            logger.info("Will rely on session state navigation instead")
                                        
                                        # Log navigation state after changes
                                        logger.info("AFTER NAVIGATION SETUP - Session State:")
                                        for key, value in st.session_state.items():
                                            if key.startswith(('current_page', 'selected_', 'view_', 'api_', 'pending_')):
                                                logger.info(f"  {key}: {value}")
                                        
                                        logger.info(f"AFTER NAVIGATION SETUP - Query Params: {dict(st.query_params)}")
                                        
                                        # Show immediate feedback
                                        st.success(f"🔍 Navigating to job details for {job.get('title', 'Unknown Job')}...")
                                        
                                        # Force navigation
                                        logger.info("Calling st.rerun() to force navigation...")
                                        st.rerun()
                                        
                                        logger.info("="*80)
                                        logger.info("VIEW JOB DETAILS BUTTON COMPLETED")
                                        logger.info("="*80)

                            # Show current action status if any
                            if 'job_applications' in st.session_state and action_key in st.session_state['job_applications']:
                                app_info = st.session_state['job_applications'][action_key]
                                timestamp = app_info['timestamp'].strftime("%Y-%m-%d %H:%M")
                                st.success(f"✅ **Status:** Applied on {timestamp}")
                                logger.info(f"Displaying application status for {action_key}")
                            
                            elif 'saved_jobs' in st.session_state and action_key in st.session_state['saved_jobs']:
                                save_info = st.session_state['saved_jobs'][action_key]
                                timestamp = save_info['timestamp'].strftime("%Y-%m-%d %H:%M")
                                st.info(f"💾 **Status:** Saved on {timestamp}")
                                logger.info(f"Displaying saved status for {action_key}")

def batch_matching():
    """Batch matching interface using agentic endpoint (if supported)."""
    st.subheader("Batch Matching (Agentic)")
    st.markdown("""
    Use this tool to discover optimal matches across your jobs and candidates. All matching leverages advanced agentic intelligence for recruiter efficiency.
    """)
    st.info("Contact your admin if batch matching at scale is required. This feature will be enabled when backend support is available.")
    st.warning("Batch matching is currently not available in this build. Please use the Jobs→Candidates or Candidate→Jobs tabs.")
    # The following code block was incorrectly indented and caused an error. If needed, re-integrate into logic:
    # sample_data = {
    #     "Candidate": [f"Candidate {j}" for j in range(1, 6)],
    #     "Match Score": [95 - j*5 for j in range(1, 6)],
    #     "Skills Match": ["Python, AWS, React", "Python, Docker", "AWS, React", "Python", "JavaScript"]
    # }
    # st.dataframe(sample_data)

# Helper function to render a match card
def render_match_card(match_data):
    match_score = match_data.get("match_score", 0)
    
    # Color coding based on match score
    if match_score >= 80:
        color = "#4CAF50"  # Green for strong matches
    elif match_score >= 60:
        color = "#2196F3"  # Blue for good matches
    elif match_score >= 40:
        color = "#FF9800"  # Orange for moderate matches
    else:
        color = "#F44336"  # Red for weak matches
    
    # Get candidate information
    name = match_data.get('name', 'Unknown')
    email = match_data.get('email', 'N/A')
    phone = match_data.get('phone', 'N/A')
    location = match_data.get('location', 'N/A')
    position = match_data.get('position', 'N/A')
    company = match_data.get('current_company', 'N/A')
    experience_years = match_data.get('experience_years', 'N/A')
    education = match_data.get('education', 'N/A')
    headline = match_data.get('headline', '')
    
    # Format skills if available
    skills = match_data.get('skills', [])
    skills_display = ""
    if skills:
        skills_str = ", ".join(skills[:5])
        if len(skills) > 5:
            skills_str += "..."
        skills_display = f"<div class='card-section'><b>Skills:</b> {skills_str}</div>"
    
    # Format experience if available
    experience = match_data.get('experience', [])
    experience_display = ""
    if experience and len(experience) > 0:
        exp_item = experience[0]  # Show most recent experience
        exp_role = fix_merged_text(exp_item.get('title', 'N/A'))
        exp_company = fix_merged_text(exp_item.get('company', 'N/A'))
        exp_duration = fix_merged_text(exp_item.get('duration', 'N/A'))
        experience_display = f"<div class='card-section'><b>Recent Experience:</b> {exp_role} at {exp_company}, {exp_duration}</div>"
    
    # Format match explanation
    match_explanation = match_data.get('match_explanation', 'No match explanation available')
    
    # Create HTML for the card with more comprehensive styling
    html = f"""
    <style>
        .candidate-card {{
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        .score-badge {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: {color};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: bold;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        .card-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .card-subtitle {{
            font-size: 14px;
            color: #666;
        }}
        .card-section {{
            margin-bottom: 12px;
            font-size: 14px;
        }}
        .contact-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
        }}
        .divider {{
            border-top: 1px solid #eee;
            margin: 15px 0;
        }}
        .match-explanation {{
            font-size: 14px;
            color: #444;
            background: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
        }}
    </style>
    
    <div class="candidate-card">
        <div class="card-header">
            <div class="score-badge">
                {int(match_score)}%
            </div>
            <div>
                <div class="card-title">{name}</div>
                {f'<div class="card-subtitle">{headline}</div>' if headline else ''}
                <div class="card-subtitle">{position} {f'at {company}' if company != 'N/A' else ''}</div>
            </div>
        </div>
        
        <div class="contact-grid">
            <div class="card-section"><b>📧 Email:</b> {email}</div>
            <div class="card-section"><b>📱 Phone:</b> {phone}</div>
            <div class="card-section"><b>📍 Location:</b> {location}</div>
            <div class="card-section"><b>⏳ Experience:</b> {experience_years}</div>
        </div>
        
        {f'<div class="card-section"><b>🎓 Education:</b> {education}</div>' if education != 'N/A' else ''}
        {skills_display}
        {experience_display}
        
        <div class="divider"></div>
        
        <div class="match-explanation">
            <b>Match Analysis:</b> {match_explanation}
        </div>
    </div>
    """
    return html

@st.cache_data(ttl=60)
def fetch_jobs() -> List[Dict]:
    """Synchronous wrapper for async job fetching"""
    # Temporarily disable cache to ensure we get fresh data
    fetch_jobs.clear()
    result = asyncio.run(fetch_jobs_async())
    logger.info(f"fetch_jobs returned {len(result)} jobs")
    return result

@st.cache_data(ttl=60)
def fetch_candidates() -> List[Dict]:
    """Synchronous wrapper for async candidate fetching"""
    return asyncio.run(fetch_candidates_async())

