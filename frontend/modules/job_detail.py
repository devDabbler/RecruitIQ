import streamlit as st
import httpx
import asyncio
import logging
from typing import Dict, Any, List, Optional
import requests
from utils.ui_helpers import format_skills_list
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_job_async(api_url: str, job_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a job by ID from the API asynchronously"""
    try:
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/jobs/{job_id}"
        logger.info(f"Fetching job {job_id} from {endpoint}")
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            job = response.json()
            logger.info(f"Successfully fetched job {job_id}")
            return job
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {str(e)}")
        return None

def fetch_job(api_url: str, job_id: int) -> Optional[Dict[str, Any]]:
    """Synchronous wrapper for async job fetching (for Streamlit compatibility)"""
    return asyncio.run(fetch_job_async(api_url, job_id))

async def fetch_matching_candidates_async(api_url: str, job_id: int) -> List[Dict[str, Any]]:
    """Fetch candidates that match a job using the robust /search/match_candidates endpoint."""
    try:
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the endpoint properly
        endpoint = f"{api_url}/api/search/match_candidates"
        logger.info(f"Fetching matching candidates for job {job_id} via {endpoint}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json={"job_ids": [int(job_id)], "min_score": 30.0}
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug: Log the raw response
            logger.info(f"Raw match_candidates response type: {type(data)}, data: {str(data)[:200]}...")
            
            # Initialize candidates list
            candidates = []
            
            # Parse response according to its structure
            if isinstance(data, list):
                # Case 1: If response is already a flattened list of candidates (new format)
                if len(data) > 0 and isinstance(data[0], dict):
                    # Check if these look like candidate objects
                    if any(key in data[0] for key in ["id", "name", "score", "match_score", "email"]):
                        logger.info(f"Response is a flattened list of {len(data)} candidates")
                        candidates = data
                    # Case 2: Old nested format with job_id and candidates
                    else:
                        logger.info(f"Response is a list with {len(data)} job results")
                        for job_result in data:
                            logger.info(f"Processing job_result: {job_result.get('job_id', 'unknown')} looking for {job_id}")
                            if isinstance(job_result, dict) and int(job_result.get("job_id", -1)) == int(job_id):
                                job_candidates = job_result.get("candidates", [])
                                logger.info(f"Found {len(job_candidates)} candidates for job_id {job_id}")
                                if job_candidates:
                                    logger.info(f"Sample candidate: {str(job_candidates[0])[:300] if job_candidates else 'None'}")
                                    candidates = job_candidates
                                    break
                            else:
                                logger.info(f"Job result mismatch - got job_id {job_result.get('job_id')} expected {job_id}")
            # Case 3: If response is a dict with 'candidates' key
            elif isinstance(data, dict):
                logger.info(f"Response is a dict with keys: {list(data.keys())}")
                if "candidates" in data:
                    candidates = data["candidates"]
                    logger.info(f"Found {len(candidates)} candidates in 'candidates' key")
            
            logger.info(f"Before processing: candidates list has {len(candidates)} items")
            
            # Ensure all candidates have the required fields for rendering
            processed_candidates = []
            for i, candidate in enumerate(candidates):
                logger.info(f"Processing candidate {i+1}: {str(candidate)[:200]}")
                
                if not isinstance(candidate, dict):
                    logger.warning(f"Skipping non-dict candidate: {candidate}")
                    continue
                    
                # Check if candidate has some form of ID
                has_id = False
                for id_field in ["id", "candidate_id", "ID"]:
                    if id_field in candidate and candidate[id_field]:
                        has_id = True
                        # Ensure the main 'id' field exists
                        if id_field != "id":
                            candidate["id"] = candidate[id_field]
                        break
                        
                if not has_id:
                    logger.warning(f"Skipping candidate without ID: {candidate}")
                    continue
                
                # Ensure score is a number
                score = 0
                for score_field in ["match_score", "score", "adjusted_score"]:
                    if score_field in candidate:
                        try:
                            score = float(candidate[score_field])
                            candidate["match_score"] = score  # Standardize on match_score
                            logger.info(f"Candidate {candidate.get('id', 'unknown')} has match_score: {score}")
                            break
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid score format for {score_field}: {candidate[score_field]}")
                            pass
                
                # Set default name if missing
                if "name" not in candidate or not candidate["name"]:
                    candidate["name"] = "Unknown Candidate"
                
                logger.info(f"Adding candidate {candidate.get('id', 'unknown')} with score {candidate.get('match_score', 0)} to processed list")
                processed_candidates.append(candidate)
            
            # Sort by match score in descending order
            processed_candidates.sort(
                key=lambda c: float(c.get("match_score", 0)) 
                if isinstance(c.get("match_score"), (int, float, str)) else 0, 
                reverse=True
            )
            
            logger.info(f"Returning {len(processed_candidates)} processed candidates for job {job_id}")
            return processed_candidates
    except Exception as e:
        logger.error(f"Error fetching matching candidates for job {job_id}: {str(e)}")
        logger.exception("Exception details:")
        return []

def fetch_matching_candidates(api_url: str, job_id: int) -> List[Dict[str, Any]]:
    """Synchronous wrapper for async matching candidates fetching"""
    return asyncio.run(fetch_matching_candidates_async(api_url, job_id))

async def fetch_enhanced_matching_candidates_async(api_url: str, job_id: int, min_score: float = 20.0) -> List[Dict[str, Any]]:
    """Fetch candidates that match a job using the enhanced matching endpoint."""
    try:
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the enhanced matching endpoint
        endpoint = f"{api_url}/api/enhanced-matching/match-candidates"
        logger.info(f"Fetching enhanced matching candidates for job {job_id} via {endpoint}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json={"job_ids": [int(job_id)], "min_score": min_score}
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug: Log the raw response
            logger.info(f"Enhanced match_candidates response type: {type(data)}, data: {str(data)[:200]}...")
            
            # Extract candidates from the response
            candidates = data.get("candidates", []) if isinstance(data, dict) else []
            
            logger.info(f"Enhanced matching returned {len(candidates)} candidates for job {job_id}")
            
            # Process candidates to ensure they have all required fields
            processed_candidates = []
            for i, candidate in enumerate(candidates):
                logger.info(f"Processing enhanced candidate {i+1}: {str(candidate)[:200]}")
                
                if not isinstance(candidate, dict):
                    logger.warning(f"Skipping non-dict candidate: {candidate}")
                    continue
                    
                # Ensure the candidate has required fields
                if not candidate.get('id'):
                    logger.warning(f"Skipping candidate without ID: {candidate}")
                    continue
                
                # Ensure all score fields are present
                candidate.setdefault('match_score', 0)
                candidate.setdefault('skill_match_score', 0)
                candidate.setdefault('role_match_score', 0)
                candidate.setdefault('experience_match_score', 0)
                candidate.setdefault('match_explanation', 'No explanation available')
                
                # Set default name if missing
                if not candidate.get('name'):
                    candidate['name'] = "Unknown Candidate"
                
                processed_candidates.append(candidate)
            
            # Sort by match score in descending order
            processed_candidates.sort(
                key=lambda c: float(c.get("match_score", 0)), 
                reverse=True
            )
            
            logger.info(f"Returning {len(processed_candidates)} processed enhanced candidates for job {job_id}")
            return processed_candidates
            
    except Exception as e:
        logger.error(f"Error fetching enhanced matching candidates for job {job_id}: {str(e)}")
        logger.exception("Exception details:")
        return []

def fetch_enhanced_matching_candidates(api_url: str, job_id: int, min_score: float = 20.0) -> List[Dict[str, Any]]:
    """Synchronous wrapper for enhanced matching candidates."""
    return asyncio.run(fetch_enhanced_matching_candidates_async(api_url, job_id, min_score))

async def fetch_similar_jobs_async(api_url: str, job_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch similar jobs using the enhanced matching endpoint."""
    try:
        # Ensure api_url has the correct format - remove trailing slash
        api_url = api_url.rstrip('/')
        
        # Construct the similar jobs endpoint
        endpoint = f"{api_url}/api/enhanced-matching/similar-jobs"
        logger.info(f"Fetching similar jobs for job {job_id} via {endpoint}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json={"job_id": int(job_id), "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug: Log the raw response
            logger.info(f"Similar jobs response type: {type(data)}, data: {str(data)[:200]}...")
            
            # Extract similar jobs from the response
            similar_jobs = data.get("similar_jobs", []) if isinstance(data, dict) else []
            
            logger.info(f"Similar jobs returned {len(similar_jobs)} jobs for job {job_id}")
            
            # Process jobs to ensure they have all required fields
            processed_jobs = []
            for i, similar_job in enumerate(similar_jobs):
                logger.info(f"Processing similar job {i+1}: {str(similar_job)[:200]}")
                
                if not isinstance(similar_job, dict):
                    logger.warning(f"Skipping non-dict job: {similar_job}")
                    continue
                    
                # Ensure the job has required fields
                if not similar_job.get('id'):
                    logger.warning(f"Skipping job without ID: {similar_job}")
                    continue
                
                # Ensure all score fields are present
                similar_job.setdefault('similarity_score', 0)
                similar_job.setdefault('similarity_explanation', 'No explanation available')
                
                # Set default title if missing
                if not similar_job.get('title'):
                    similar_job['title'] = "Unknown Job"
                
                processed_jobs.append(similar_job)
            
            # Sort by similarity score in descending order
            processed_jobs.sort(
                key=lambda j: float(j.get("similarity_score", 0)), 
                reverse=True
            )
            
            logger.info(f"Returning {len(processed_jobs)} processed similar jobs for job {job_id}")
            return processed_jobs
            
    except Exception as e:
        logger.error(f"Error fetching similar jobs for job {job_id}: {str(e)}")
        logger.exception("Exception details:")
        return []

def fetch_similar_jobs(api_url: str, job_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Synchronous wrapper for similar jobs."""
    return asyncio.run(fetch_similar_jobs_async(api_url, job_id, limit))

def get_status_color(status: str) -> str:
    """Return a color based on job status"""
    status_colors = {
        "draft": "#6b7280",      # gray
        "open": "#10b981",       # green
        "on_hold": "#f97316",    # orange
        "filled": "#3b82f6",     # blue
        "closed": "#8b5cf6",     # purple
        "cancelled": "#ef4444"   # red
    }
    return status_colors.get(status.lower() if status else "", "#6b7280")

def format_salary(min_salary: Optional[int], max_salary: Optional[int]) -> str:
    """Format salary range for display"""
    if min_salary and max_salary:
        return f"${min_salary:,} - ${max_salary:,}"
    elif min_salary:
        return f"From ${min_salary:,}"
    elif max_salary:
        return f"Up to ${max_salary:,}"
    else:
        return "Not specified"

def render_job_detail(job: Dict[str, Any]) -> str:
    """Render a detailed job profile as HTML"""
    def fmt(val):
        return val if val not in [None, '', [], {}] else '-'
    
    # Format skills as badges safely
    skills_html = '-'
    if job.get('skills'):
        # Use safe formatting for job skills
        if isinstance(job['skills'], list):
            formatted_skills = format_skills_list(job['skills'])
        else:
            # Handle comma-separated skills string
            skills_list = [s.strip() for s in str(job['skills']).split(',') if s.strip()]
            formatted_skills = format_skills_list(skills_list)
        
        if formatted_skills:
            skills_html = " ".join([
                f'<span style="background:#e0f2fe;color:#0369a1;border-radius:8px;padding:2px 8px;margin:1px;display:inline-block;font-size:12px">{skill}</span>'
                for skill in formatted_skills
            ])
    
    # Format job type and location type
    job_type_display = {
        "full_time": "Full-time",
        "part_time": "Part-time",
        "contract": "Contract",
        "temporary": "Temporary",
        "internship": "Internship",
        "freelance": "Freelance"
    }.get(job.get('job_type', '').lower(), job.get('job_type', '-'))
    
    location_type_display = {
        "on_site": "On-site",
        "remote": "Remote",
        "hybrid": "Hybrid"
    }.get(job.get('location_type', '').lower(), job.get('location_type', '-'))
    
    experience_level_display = {
        "entry": "Entry Level",
        "mid": "Mid Level",
        "senior": "Senior Level",
        "lead": "Lead Level",
        "executive": "Executive Level"
    }.get(job.get('experience_level', '').lower(), job.get('experience_level', '-'))
    
    # Main job profile HTML
    html = f"""
    <div style="padding:24px;border-radius:12px;background:#ffffff;box-shadow:0 4px 6px rgba(0,0,0,0.1);margin-bottom:24px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <div>
                <h2 style="margin:0;color:#1e293b;font-size:28px;">{fmt(job.get('title'))}</h2>
                <div style="color:#64748b;font-size:16px;">{fmt(job.get('department'))}</div>
            </div>
            <div style="background:{get_status_color(job.get('status'))};color:white;padding:6px 12px;border-radius:20px;font-size:14px;">
                {fmt(job.get('status')).upper()}
            </div>
        </div>
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
            <div>
                <div style="margin-bottom:12px;">
                    <div style="font-weight:600;color:#475569;">Job Details</div>
                    <div style="margin-top:8px;">
                        <div><strong>Job Type:</strong> {job_type_display}</div>
                        <div><strong>Experience Level:</strong> {experience_level_display}</div>
                        <div><strong>Salary Range:</strong> {format_salary(job.get('min_salary'), job.get('max_salary'))}</div>
                    </div>
                </div>
                
                <div>
                    <div style="font-weight:600;color:#475569;">Location</div>
                    <div style="margin-top:8px;">
                        <div><strong>Location:</strong> {fmt(job.get('location'))}</div>
                        <div><strong>Work Type:</strong> {location_type_display}</div>
                    </div>
                </div>
            </div>
            
            <div>
                <div style="margin-bottom:12px;">
                    <div style="font-weight:600;color:#475569;">Hiring Information</div>
                    <div style="margin-top:8px;">
                        <div><strong>Hiring Manager:</strong> {fmt(job.get('hiring_manager'))}</div>
                        <div><strong>Recruiter:</strong> {fmt(job.get('recruiter'))}</div>
                        <div><strong>Application Deadline:</strong> {fmt(job.get('application_deadline'))}</div>
                    </div>
                </div>
                
                <div>
                    <div style="font-weight:600;color:#475569;">Metrics</div>
                    <div style="margin-top:8px;">
                        <div><strong>Views:</strong> {fmt(job.get('views'))}</div>
                        <div><strong>Applications:</strong> {fmt(job.get('applications'))}</div>
                        <div><strong>Posted:</strong> {fmt(job.get('created_at'))}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom:24px;">
            <div style="font-weight:600;color:#475569;margin-bottom:8px;">Required Skills</div>
            <div>{skills_html}</div>
        </div>
        
        <div style="margin-bottom:24px;">
            <div style="font-weight:600;color:#475569;margin-bottom:8px;">Job Overview</div>
            <div style="background:#f8fafc;padding:12px;border-radius:8px;white-space:pre-line;">{fmt(job.get('job_overview'))}</div>
        </div>
        
        <div>
            <div style="font-weight:600;color:#475569;margin-bottom:8px;">Required Qualifications</div>
            <div style="background:#f8fafc;padding:12px;border-radius:8px;white-space:pre-line;">{fmt(job.get('required_qualifications'))}</div>
        </div>
    </div>
    """
    return html

def render_candidate_card(candidate: Dict[str, Any]) -> str:
    """Render a candidate card with match score"""
    # Handle different possible field names and formats
    name = candidate.get('name', 'Unknown Candidate')
    
    # Handle possible email formats
    email = candidate.get('email', '-')
    if not email or email == '-':
        email = candidate.get('contact', '-')
    
    # Ensure match_score is a number and format it properly
    match_score = 0
    if 'match_score' in candidate:
        try:
            match_score = float(candidate['match_score'])
        except (ValueError, TypeError):
            match_score = 0
    elif 'score' in candidate:
        try:
            match_score = float(candidate['score'])
        except (ValueError, TypeError):
            match_score = 0
    elif 'adjusted_score' in candidate:
        try:
            match_score = float(candidate['adjusted_score'])
        except (ValueError, TypeError):
            match_score = 0
    
    # Format match score to integer if it's a whole number, otherwise 1 decimal place
    if match_score == int(match_score):
        match_score_display = f"{int(match_score)}"
    else:
        match_score_display = f"{match_score:.1f}"
    
    # Get candidate ID
    candidate_id = str(candidate.get('id', ''))
    
    # Get explanation if available
    explanation = candidate.get('match_explanation', 
                             candidate.get('explanation', 
                                          candidate.get('reason', '')))
    
    if explanation and len(explanation) > 150:
        explanation_preview = explanation[:147] + "..."
    else:
        explanation_preview = explanation
    
    explanation_html = f'<div style="color:#4b5563;font-size:12px;margin-top:8px;margin-bottom:4px;">{explanation_preview}</div>' if explanation else ''
    
    # Get position/title if available
    position = candidate.get('position', candidate.get('title', candidate.get('current_position', '')))
    position_html = f'<div style="color:#4b5563;font-size:13px;font-weight:500;">{position}</div>' if position else ''
    
    # Get skills if available
    skills = candidate.get('skills', [])
    skills_html = ''
    if skills and isinstance(skills, list) and len(skills) > 0:
        skills_badges = ' '.join([
            f'<span style="background:#e0f2fe;color:#0369a1;border-radius:8px;padding:2px 8px;margin:1px;display:inline-block;font-size:11px">{s}</span>'
            for s in skills[:5]  # Show at most 5 skills
        ])
        skills_html = f'<div style="margin-top:4px;">{skills_badges}</div>' if skills_badges else ''
    
    # Generate color based on match score
    if match_score >= 80:
        score_color = "#10b981"  # green
    elif match_score >= 60:
        score_color = "#3b82f6"  # blue
    elif match_score >= 40:
        score_color = "#f59e0b"  # amber
    else:
        score_color = "#6b7280"  # gray
    
    # Log the candidate data for debugging
    logger.info(f"Rendering candidate card: id={candidate_id}, name={name}, score={match_score}")
    
    return f"""
    <div style="border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:flex-start;">
        <div style="flex:1;">
            <div style="font-weight:600;font-size:16px;">{name}</div>
            <div style="color:#6b7280;font-size:14px;">{email}</div>
            {position_html}
            {skills_html}
            {explanation_html}
        </div>
        <div style="display:flex; flex-direction:column; align-items:flex-end; gap:10px;margin-left:12px;">
            <div style="background:{score_color}; color:white; padding:4px 10px; border-radius:16px; font-weight:600;text-align:center;">
                {match_score_display}% Match
            </div>
            <a href="?view=candidate_detail&id={candidate_id}" target="_self" style="text-decoration:none;">
                <button style="background:#3b82f6; color:white; border:none; padding:6px 12px; border-radius:6px; cursor:pointer;">
                    View Profile
                </button>
            </a>
        </div>
    </div>
    """

def render_enhanced_candidate_card_streamlit(candidate: Dict[str, Any], index: int):
    """Render an enhanced candidate card using native Streamlit components."""
    candidate_id = str(candidate.get('id', ''))
    name = candidate.get('name', 'Unknown Candidate')
    email = candidate.get('email', '')
    position = candidate.get('position', '')
    skills = candidate.get('skills', [])
    
    # Get match scores
    match_score = float(candidate.get('match_score', 0))
    skill_score = float(candidate.get('skill_match_score', 0))
    role_score = float(candidate.get('role_match_score', 0))
    experience_score = float(candidate.get('experience_match_score', 0))
    explanation = candidate.get('match_explanation', '')
    
    # Create a container for the candidate card
    with st.container():
        # Create columns for layout
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            # Candidate name and basic info
            st.markdown(f"**{name}**")
            if email and email != '-':
                st.caption(f"📧 {email}")
            if position:
                st.caption(f"💼 {position}")
            
            # Skills display
            if skills:
                formatted_skills = format_skills_list(skills)
                if formatted_skills:
                    skills_text = " • ".join(formatted_skills[:5])  # Show at most 5 skills
                    st.caption(f"🛠️ {skills_text}")
            
            # Component scores in a compact format
            if skill_score > 0 or role_score > 0 or experience_score > 0:
                st.caption("**Component Scores:**")
                score_cols = st.columns(3)
                with score_cols[0]:
                    st.caption(f"Skills: {skill_score:.0f}%")
                    st.progress(skill_score / 100)
                with score_cols[1]:
                    st.caption(f"Role: {role_score:.0f}%")
                    st.progress(role_score / 100)
                with score_cols[2]:
                    st.caption(f"Experience: {experience_score:.0f}%")
                    st.progress(experience_score / 100)
            
            # Match explanation
            if explanation:
                if len(explanation) > 150:
                    explanation = explanation[:147] + "..."
                st.caption(f"💡 {explanation}")
        
        with col2:
            # Match score badge
            if match_score >= 80:
                score_color = "🟢"
            elif match_score >= 60:
                score_color = "🔵"
            elif match_score >= 40:
                score_color = "🟡"
            else:
                score_color = "⚪"
            
            score_display = f"{int(match_score)}" if match_score == int(match_score) else f"{match_score:.1f}"
            st.metric("Match Score", f"{score_display}%", delta=None)
            st.progress(match_score / 100)
            st.markdown(f"{score_color}")
        
        with col3:
            # View profile button
            if st.button("View Profile", key=f"view_profile_{candidate_id}_{index}"):
                # Clear any existing view state
                st.session_state.pop("view_handled", None)
                # Set navigation parameters
                st.query_params.clear()
                st.query_params["view"] = "candidate_detail"
                st.query_params["id"] = candidate_id
                st.session_state.current_page = "candidate_detail"
                st.rerun()
        
        # Add separator
        st.markdown("---")

def page():
    """Job detail page with comprehensive debugging"""
    # COMPREHENSIVE DEBUGGING - Job Detail Page Entry
    logger.info("="*80)
    logger.info("JOB DETAIL PAGE CALLED")
    logger.info("="*80)
    logger.info(f"Timestamp: {pd.Timestamp.now()}")
    
    # Log all relevant session state
    logger.info("Session State at Job Detail Entry:")
    for key, value in st.session_state.items():
        if key.startswith(('current_page', 'selected_', 'view_', 'api_', 'job_')):
            logger.info(f"  {key}: {value}")
    
    # Log query parameters
    logger.info(f"Query Params: {dict(st.query_params)}")
    
    api_url = st.session_state.get("api_url", "http://localhost:8000")
    logger.info(f"API URL: {api_url}")
    
    # Get job ID from multiple sources with debugging
    job_id = None
    
    # Method 1: From session state
    if hasattr(st.session_state, 'selected_job_id') and st.session_state.selected_job_id:
        job_id = st.session_state.selected_job_id
        logger.info(f"Job ID found in session state: {job_id}")
    
    # Method 2: From query parameters
    elif st.query_params.get("id"):
        job_id = st.query_params.get("id")
        logger.info(f"Job ID found in query params: {job_id}")
        # Store in session state for consistency
        st.session_state.selected_job_id = str(job_id)
        logger.info("Stored job ID in session state")
    
    # Method 3: From deprecated session state key
    elif hasattr(st.session_state, 'view_job_id') and st.session_state.view_job_id:
        job_id = st.session_state.view_job_id
        logger.info(f"Job ID found in deprecated view_job_id: {job_id}")
    
    logger.info(f"FINAL JOB ID: {job_id} (type: {type(job_id)})")
    
    if not job_id:
        logger.error("NO JOB ID FOUND - Cannot display job details")
        st.error("❌ No job selected. Please select a job from the jobs page.")
        if st.button("Back to Jobs"):
            st.session_state.current_page = "jobs"
            st.query_params.clear()
            st.rerun()
        return

    try:
        # Convert to integer for API call
        job_id_int = int(job_id)
        logger.info(f"Job ID converted to integer: {job_id_int}")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid job ID format: {job_id} - {e}")
        
        # Check if this might be a candidate ID (UUID format)
        if len(job_id) == 36 and '-' in job_id:
            st.error(f"❌ Invalid job ID: {job_id}")
            st.warning("This appears to be a candidate ID, not a job ID.")
            st.info("Please navigate to the job detail page from the jobs list, not from a candidate profile.")
        else:
            st.error(f"❌ Invalid job ID: {job_id}")
        
        if st.button("Back to Jobs"):
            st.session_state.current_page = "jobs"
            st.query_params.clear()
            st.rerun()
        return

    # Show loading spinner while fetching job details
    with st.spinner(f"Loading job details for ID {job_id_int}..."):
        logger.info(f"Fetching job details from API for job_id={job_id_int}")
        
        # Fetch job details
        job = fetch_job(api_url, job_id_int)
        
        if job:
            logger.info(f"Successfully fetched job: {job.get('title', 'Unknown')} (ID: {job.get('id')})")
        else:
            logger.error(f"Failed to fetch job for ID: {job_id_int}")
    
    if not job:
        st.error(f"❌ Job not found with ID: {job_id_int}")
        logger.error(f"Job {job_id_int} not found - showing error message")
        
        # Provide navigation back to jobs
        if st.button("Back to Jobs"):
            logger.info("User clicked Back to Jobs from error state")
            st.session_state.current_page = "jobs"
            st.query_params.clear()
            st.rerun()
        return

    # Display job information with detailed logging
    logger.info("Displaying job information...")
    logger.info(f"Job title: {job.get('title', 'Unknown')}")
    logger.info(f"Job department: {job.get('department', 'Unknown')}")
    logger.info(f"Job status: {job.get('status', 'Unknown')}")
    
    # Instead of using complex HTML, use Streamlit components directly
    # Display basic job information
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(job.get('title', 'Job Title'))
        st.caption(job.get('department', ''))
    with col2:
        status = job.get('status', '').upper()
        status_color = get_status_color(job.get('status'))
        st.markdown(f"<div style='background:{status_color};color:white;padding:6px 12px;border-radius:20px;font-size:14px;text-align:center;'>{status}</div>", unsafe_allow_html=True)
    
    # Display job details in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Job Details", "Requirements & Skills", "Matching Candidates", "Similar Jobs"])
    
    with tab1:
        # Job Details
        st.subheader("Job Information")
        col1, col2 = st.columns(2)
        with col1:
            job_type_display = {
                "full_time": "Full-time",
                "part_time": "Part-time",
                "contract": "Contract",
                "temporary": "Temporary",
                "internship": "Internship",
                "freelance": "Freelance"
            }.get(job.get('job_type', '').lower(), job.get('job_type', '-'))
            
            experience_level_display = {
                "entry": "Entry Level",
                "mid": "Mid Level",
                "senior": "Senior Level",
                "lead": "Lead Level",
                "executive": "Executive Level"
            }.get(job.get('experience_level', '').lower(), job.get('experience_level', '-'))
            
            st.write(f"**Job Type:** {job_type_display}")
            st.write(f"**Experience Level:** {experience_level_display}")
            salary_range = format_salary(job.get('min_salary'), job.get('max_salary'))
            st.write(f"**Salary Range:** {salary_range}")
        
        with col2:
            location_type_display = {
                "on_site": "On-site",
                "remote": "Remote",
                "hybrid": "Hybrid"
            }.get(job.get('location_type', '').lower(), job.get('location_type', '-'))
            
            st.write(f"**Location:** {job.get('location', '-')}")
            st.write(f"**Work Type:** {location_type_display}")
            st.write(f"**Posted:** {job.get('created_at', '-')}")
        
        # Hiring Information
        st.subheader("Hiring Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Hiring Manager:** {job.get('hiring_manager', '-')}")
            st.write(f"**Recruiter:** {job.get('recruiter', '-')}")
        with col2:
            st.write(f"**Application Deadline:** {job.get('application_deadline', '-')}")
            st.write(f"**Start Date:** {job.get('start_date', '-')}")
        
        # Metrics
        st.subheader("Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Views", job.get('views', 0))
        with col2:
            st.metric("Applications", job.get('applications', 0))
        with col3:
            days_active = "N/A"
            if job.get('created_at'):
                try:
                    from datetime import datetime
                    created_date = datetime.fromisoformat(job.get('created_at').replace('Z', '+00:00'))
                    current_date = datetime.now()
                    days_active = (current_date - created_date).days
                except:
                    days_active = "N/A"
            st.metric("Days Active", days_active)
    
    with tab2:
        # Job Overview
        st.subheader("Job Overview")
        st.write(job.get('job_overview', 'No job overview provided.'))
        
        # Required Qualifications
        st.subheader("Required Qualifications")
        st.write(job.get('required_qualifications', 'No qualifications specified.'))
        
        # Skills
        st.subheader("Required Skills")
        if job.get('skills'):
            # Format skills safely before displaying
            job_skills = job.get('skills', [])
            if isinstance(job_skills, list):
                formatted_skills = format_skills_list(job_skills)
            else:
                # Handle comma-separated skills string
                skills_list = [s.strip() for s in str(job_skills).split(',') if s.strip()]
                formatted_skills = format_skills_list(skills_list)
            
            if formatted_skills:
                for skill in formatted_skills:
                    st.markdown(f"<span style='background:#e0f2fe;color:#0369a1;border-radius:8px;padding:4px 10px;margin:2px;display:inline-block;'>{skill}</span>", unsafe_allow_html=True)
            else:
                st.info("No valid skills found")
        else:
            st.info("No specific skills listed for this job")
    
    with tab3:
        # Enhanced Matching candidates section
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 20px; background-color: #f0f7ff; padding: 10px; border-radius: 5px; border-left: 4px solid #4361ee;">
            <div style="margin-right: 10px; font-size: 24px;">🤖</div>
            <div>
                <div style="font-weight: bold; margin-bottom: 5px;">AI-Powered Candidate Matching</div>
                <div style="font-size: 0.9em;">Advanced matching analyzes skills, experience, and role compatibility for precise candidate-job matching.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Match score threshold selector
        col1, col2 = st.columns([2, 1])
        with col1:
            min_match_score = st.slider(
                "Minimum Match Score (%)",
                min_value=0,
                max_value=100,
                value=20,
                step=5,
                help="Adjust the minimum match score to filter candidates"
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh Matches", key="refresh_matches"):
                st.session_state.refresh_matches = True
        
        try:
            with st.spinner("🤖 Finding great candidate matches for this role using advanced AI..."):
                # Debug: Log before making the request
                logger.info(f"Calling enhanced fetch_matching_candidates for job_id: {job_id_int}")
                matching_candidates = fetch_enhanced_matching_candidates(api_url, job_id_int, min_match_score)
                
                # Debug: Log the results
                logger.info(f"Enhanced matching received {type(matching_candidates)} from API")
                if matching_candidates is not None:
                    if isinstance(matching_candidates, list):
                        logger.info(f"Enhanced matching received {len(matching_candidates)} candidates from API")
                        if matching_candidates and len(matching_candidates) > 0:
                            logger.info(f"First enhanced candidate sample: {str(matching_candidates[0])[:200]}...")
                    else:
                        logger.warning(f"Unexpected type received: {type(matching_candidates)}")
        except Exception as e:
            logger.error(f"Error fetching enhanced matching candidates: {str(e)}")
            logger.exception("Detailed exception:")
            st.error("Could not load enhanced matching candidates for this job. The backend endpoint may be missing or there was a network error.")
            if st.button("Back to Jobs", key="back_from_error"):
                # Set flag in session state to indicate we're returning from job detail
                st.session_state.returning_from_job_detail = True
                st.session_state.current_page = "jobs"
                st.query_params.clear()
                st.rerun()
            st.stop()
        
        # Check if we have valid candidates
        logger.info(f"Validating enhanced candidates - matching_candidates is not None: {matching_candidates is not None}")
        logger.info(f"Validating enhanced candidates - is list: {isinstance(matching_candidates, list)}")
        
        has_valid_scores = False
        if isinstance(matching_candidates, list):
            logger.info(f"Validating enhanced candidates - length > 0: {len(matching_candidates) > 0}")
            if len(matching_candidates) > 0:
                logger.info(f"Validating enhanced candidates - first item is dict: {isinstance(matching_candidates[0], dict)}")
                
                # Helper function to safely get numeric score
                def safe_score(c):
                    score = c.get('match_score', 0)
                    try:
                        return float(score) if score is not None else 0
                    except (ValueError, TypeError):
                        return 0
                
                scores = [safe_score(c) for c in matching_candidates]
                logger.info(f"Validating enhanced candidates - scores: {scores}")
                logger.info(f"Validating enhanced candidates - any score >= {min_match_score}: {any(score >= min_match_score for score in scores)}")
                
                has_valid_scores = any(safe_score(c) >= min_match_score for c in matching_candidates)
        
        valid_candidates = (
            matching_candidates is not None and 
            isinstance(matching_candidates, list) and 
            len(matching_candidates) > 0 and
            isinstance(matching_candidates[0], dict) and
            has_valid_scores
        )
        
        logger.info(f"Final validation result: valid_candidates = {valid_candidates}")
        
        if not valid_candidates:
            st.info(f"🤖 No strong matches found for this role with minimum score of {min_match_score}%. Try adjusting the match threshold or adding more candidates.")
            
            # Show match score distribution if we have any candidates
            if matching_candidates and len(matching_candidates) > 0:
                scores = [c.get('match_score', 0) for c in matching_candidates if isinstance(c.get('match_score'), (int, float))]
                if scores:
                    st.write("**Match Score Distribution:**")
                    score_ranges = {
                        "80-100%": len([s for s in scores if s >= 80]),
                        "60-79%": len([s for s in scores if 60 <= s < 80]),
                        "40-59%": len([s for s in scores if 40 <= s < 60]),
                        "20-39%": len([s for s in scores if 20 <= s < 40]),
                        "0-19%": len([s for s in scores if s < 20])
                    }
                    
                    for range_name, count in score_ranges.items():
                        if count > 0:
                            st.write(f"• {range_name}: {count} candidates")
            
            if st.button("Back to Jobs", key="back_from_empty"):
                # Set flag in session state to indicate we're returning from job detail
                st.session_state.returning_from_job_detail = True
                st.session_state.current_page = "jobs"
                st.query_params.clear()
                st.rerun()
        else:
            # Filter candidates by minimum match score
            filtered_candidates = [c for c in matching_candidates if c.get('match_score', 0) >= min_match_score]
            
            # Show how many candidates were found
            st.markdown(f"""
                <div style='background:#e0f7fa;padding:16px;border-radius:8px;margin-bottom:16px;'>
                <b>🤖 Found {len(filtered_candidates)} candidates that match this role with scores ≥ {min_match_score}%:</b>
                </div>
            """, unsafe_allow_html=True)
            
            # Sort candidates by match score (highest first)
            sorted_candidates = sorted(
                filtered_candidates, 
                key=lambda c: float(c.get('match_score', 0)) if isinstance(c.get('match_score'), (int, float, str)) else 0,
                reverse=True
            )
            
            # Display match score statistics
            if len(sorted_candidates) > 1:
                scores = [c.get('match_score', 0) for c in sorted_candidates]
                avg_score = sum(scores) / len(scores)
                max_score = max(scores)
                min_score_actual = min(scores)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Average Match Score", f"{avg_score:.1f}%")
                with col2:
                    st.metric("Highest Score", f"{max_score:.1f}%")
                with col3:
                    st.metric("Lowest Score", f"{min_score_actual:.1f}%")
            
            # Process and display candidates using enhanced cards
            try:
                for i, candidate in enumerate(sorted_candidates):
                    logger.info(f"Processing enhanced candidate {i+1}/{len(sorted_candidates)}: {candidate.get('id', 'unknown_id')}")
                    try:
                        # Use the enhanced candidate card renderer
                        render_enhanced_candidate_card_streamlit(candidate, i)
                        
                    except Exception as card_error:
                        logger.error(f"Error rendering enhanced card for candidate {i+1}: {str(card_error)}")
                        logger.exception("Enhanced card rendering exception:")
                        
                        # Fallback: minimal info if card rendering fails
                        st.write(f"**{candidate.get('name', 'Unknown Candidate')}** - {candidate.get('match_score', 0)}% Match")
                        if st.button("View Profile", key=f"fallback_view_{candidate.get('id', '')}_{i}"):
                            # Clear any existing view state
                            st.session_state.pop("view_handled", None)
                            # Set navigation parameters
                            st.query_params.clear()
                            st.query_params["view"] = "candidate_detail"
                            st.query_params["id"] = str(candidate.get('id', ''))
                            st.session_state.current_page = "candidate_detail"
                            st.rerun()
                        st.markdown("---")
                        
            except Exception as display_error:
                logger.error(f"Error in enhanced candidate display loop: {str(display_error)}")
                logger.exception("Enhanced display loop exception:")
                st.error("There was an error displaying some candidate matches. Please try again later.")
    
    with tab4:
        # Similar Jobs section
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 20px; background-color: #f0f7ff; padding: 10px; border-radius: 5px; border-left: 4px solid #4361ee;">
            <div style="margin-right: 10px; font-size: 24px;">🔍</div>
            <div>
                <div style="font-weight: bold; margin-bottom: 5px;">Similar Jobs</div>
                <div style="font-size: 0.9em;">Find jobs similar to this one based on skills, requirements, and role characteristics.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Number of similar jobs to show
        col1, col2 = st.columns([2, 1])
        with col1:
            similar_jobs_limit = st.slider(
                "Number of Similar Jobs",
                min_value=1,
                max_value=10,
                value=5,
                step=1,
                help="How many similar jobs to display"
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh Similar Jobs", key="refresh_similar_jobs"):
                st.session_state.refresh_similar_jobs = True
        
        try:
            with st.spinner("🔍 Finding similar jobs..."):
                # Debug: Log before making the request
                logger.info(f"Calling fetch_similar_jobs for job_id: {job_id_int}")
                similar_jobs = fetch_similar_jobs(api_url, job_id_int, similar_jobs_limit)
                
                # Debug: Log the results
                logger.info(f"Similar jobs received {type(similar_jobs)} from API")
                if similar_jobs is not None:
                    if isinstance(similar_jobs, list):
                        logger.info(f"Similar jobs received {len(similar_jobs)} jobs from API")
                        if similar_jobs and len(similar_jobs) > 0:
                            logger.info(f"First similar job sample: {str(similar_jobs[0])[:200]}...")
                    else:
                        logger.warning(f"Unexpected type received: {type(similar_jobs)}")
        except Exception as e:
            logger.error(f"Error fetching similar jobs: {str(e)}")
            logger.exception("Detailed exception:")
            st.error("Could not load similar jobs for this job. The backend endpoint may be missing or there was a network error.")
            st.stop()
        
        # Check if we have valid similar jobs
        valid_similar_jobs = (
            similar_jobs is not None and 
            isinstance(similar_jobs, list) and 
            len(similar_jobs) > 0 and
            isinstance(similar_jobs[0], dict)
        )
        
        if not valid_similar_jobs:
            st.info("🔍 No similar jobs found for this role. This might be a unique position or there may not be enough job data for comparison.")
        else:
            # Show how many similar jobs were found
            st.markdown(f"""
                <div style='background:#e0f7fa;padding:16px;border-radius:8px;margin-bottom:16px;'>
                <b>🔍 Found {len(similar_jobs)} similar jobs:</b>
                </div>
            """, unsafe_allow_html=True)
            
            # Display similar jobs
            try:
                for i, similar_job in enumerate(similar_jobs):
                    logger.info(f"Processing similar job {i+1}/{len(similar_jobs)}: {similar_job.get('id', 'unknown_id')}")
                    try:
                        # Get job details
                        job_id = str(similar_job.get('id', ''))
                        title = similar_job.get('title', 'Unknown Job')
                        department = similar_job.get('department', '')
                        location = similar_job.get('location', '')
                        skills = similar_job.get('skills', [])
                        similarity_score = float(similar_job.get('similarity_score', 0))
                        explanation = similar_job.get('similarity_explanation', '')
                        
                        # Create a container for the similar job card
                        with st.container():
                            # Create columns for layout
                            col1, col2, col3 = st.columns([3, 1, 1])
                            
                            with col1:
                                # Job title and basic info
                                st.markdown(f"**{title}**")
                                if department:
                                    st.caption(f"🏢 {department}")
                                if location:
                                    st.caption(f"📍 {location}")
                                
                                # Skills display
                                if skills:
                                    formatted_skills = format_skills_list(skills)
                                    if formatted_skills:
                                        skills_text = " • ".join(formatted_skills[:5])  # Show at most 5 skills
                                        st.caption(f"🛠️ {skills_text}")
                                
                                # Similarity explanation
                                if explanation:
                                    if len(explanation) > 150:
                                        explanation = explanation[:147] + "..."
                                    st.caption(f"💡 {explanation}")
                            
                            with col2:
                                # Similarity score badge
                                if similarity_score >= 80:
                                    similarity_color = "🟢"
                                elif similarity_score >= 60:
                                    similarity_color = "🔵"
                                elif similarity_score >= 40:
                                    similarity_color = "🟡"
                                else:
                                    similarity_color = "⚪"
                                
                                score_display = f"{int(similarity_score)}" if similarity_score == int(similarity_score) else f"{similarity_score:.1f}"
                                st.metric("Similarity", f"{score_display}%", delta=None)
                                st.markdown(f"{similarity_color}")
                            
                            with col3:
                                # View job button
                                if st.button("View Job", key=f"view_job_{job_id}_{i}"):
                                    st.query_params.clear()
                                    st.query_params["view"] = "job_detail"
                                    st.query_params["id"] = job_id
                                    st.session_state.current_page = "job_detail"
                                    st.rerun()
                            
                            # Add separator
                            st.markdown("---")
                        
                    except Exception as job_error:
                        logger.error(f"Error rendering similar job {i+1}: {str(job_error)}")
                        logger.exception("Similar job rendering exception:")
                        
                        # Fallback: minimal info if rendering fails
                        st.write(f"**{similar_job.get('title', 'Unknown Job')}** - {similar_job.get('similarity_score', 0)}% Similar")
                        if st.button("View Job", key=f"fallback_view_job_{similar_job.get('id', '')}_{i}"):
                            st.query_params.clear()
                            st.query_params["view"] = "job_detail"
                            st.query_params["id"] = str(similar_job.get('id', ''))
                            st.session_state.current_page = "job_detail"
                            st.rerun()
                        st.markdown("---")
                        
            except Exception as display_error:
                logger.error(f"Error in similar jobs display loop: {str(display_error)}")
                logger.exception("Similar jobs display loop exception:")
                st.error("There was an error displaying some similar jobs. Please try again later.")
    
    # Action buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Edit Job"):
            st.session_state["edit_job_id"] = job_id
            st.rerun()
    with col2:
        if st.button("Back to Jobs"):
            # Set the current page in session state to navigate back to jobs
            st.session_state.current_page = "jobs"
            # Clear any query parameters
            st.query_params.clear()
            st.rerun()
    with col3:
        if job.get("status") == "open":
            if st.button("Close Job"):
                try:
                    response = requests.put(f"{api_url}/jobs/{job_id}", json={"status": "closed"})
                    if response.status_code == 200:
                        st.success("Job closed successfully!")
                        st.rerun()
                    else:
                        st.error(f"Failed to close job: {response.text}")
                except Exception as e:
                    st.error(f"Error closing job: {str(e)}")
    
    # Edit job form (conditionally displayed)
    if st.session_state.get("edit_job_id") == job_id:
        st.subheader("Edit Job")
        with st.form("edit_job_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Job Title", value=job.get("title", ""))
                department = st.text_input("Department", value=job.get("department", ""))
                location = st.text_input("Location", value=job.get("location", ""))
            with col2:
                status_options = ["draft", "open", "on_hold", "filled", "closed", "cancelled"]
                status = st.selectbox("Status", options=status_options, 
                                     index=status_options.index(job.get("status", "draft").lower()) if job.get("status") in status_options else 0)
                
                job_type_options = ["full_time", "part_time", "contract", "temporary", "internship", "freelance"]
                job_type = st.selectbox("Job Type", options=job_type_options,
                                       index=job_type_options.index(job.get("job_type", "full_time").lower()) if job.get("job_type") in job_type_options else 0)
                
                location_type_options = ["on_site", "remote", "hybrid"]
                location_type = st.selectbox("Location Type", options=location_type_options,
                                           index=location_type_options.index(job.get("location_type", "on_site").lower()) if job.get("location_type") in location_type_options else 0)
            
            col1, col2 = st.columns(2)
            with col1:
                min_salary = st.number_input("Minimum Salary", value=job.get("min_salary", 0), min_value=0)
            with col2:
                max_salary = st.number_input("Maximum Salary", value=job.get("max_salary", 0), min_value=0)
            
            # Skills as a comma-separated string
            current_skills = ", ".join(job.get("skills", []))
            skills_input = st.text_input("Skills (comma-separated)", value=current_skills)
            
            job_overview = st.text_area("Job Overview", value=job.get("job_overview", ""))
            required_qualifications = st.text_area("Required Qualifications", value=job.get("required_qualifications", ""))
            
            submitted = st.form_submit_button("Update Job")
            if submitted:
                # Prepare update data
                update_data = {
                    "title": title,
                    "department": department,
                    "location": location,
                    "status": status,
                    "job_type": job_type,
                    "location_type": location_type,
                    "min_salary": min_salary,
                    "max_salary": max_salary,
                    "job_overview": job_overview,
                    "required_qualifications": required_qualifications,
                    "skills": [s.strip() for s in skills_input.split(",")] if skills_input else []
                }
                
                # Send update request
                try:
                    response = requests.put(f"{api_url}/jobs/{job_id}", json=update_data)
                    if response.status_code == 200:
                        st.success("Job updated successfully!")
                        # Clear edit state and refresh
                        st.session_state.pop("edit_job_id", None)
                        st.rerun()
                    else:
                        st.error(f"Failed to update job: {response.text}")
                except Exception as e:
                    st.error(f"Error updating job: {str(e)}")
