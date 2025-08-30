# frontend/modules/assistant.py
import streamlit as st
import logging

logger = logging.getLogger(__name__)
from datetime import datetime
import re
import ast
import pyperclip
import requests
import json
import os
import time
import logging
import uuid
from typing import List, Dict, Any

from frontend.utils.ui_helpers import fix_merged_text, sanitize_html

# Configure logging (do not add file handlers at import time)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_backend_url() -> str:
    """Resolve the backend URL dynamically from session state with a sensible default.

    This keeps the frontend dynamic and avoids hardcoding backend endpoints.
    """
    try:
        if 'api_url' in st.session_state and st.session_state['api_url']:
            return st.session_state['api_url'].rstrip('/')
    except Exception:
        pass
    return "http://localhost:8000"

@st.cache_data(ttl=300)
def fetch_active_jobs():
    """Fetch active jobs from the ATS for the dropdown"""
    try:
        backend = get_backend_url()
        url = f"{backend}/api/jobs/"
        params = {
            "page_size": 100,  # Get up to 100 jobs
            "sort_by": "created_at",
            "sort_order": "desc"
        }
        logger.info(f"Fetching jobs from: {url} with params: {params}")

        response = requests.get(url, params=params, timeout=10)
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            logger.info(f"Full response data: {data}")
            
            # Try different possible keys for jobs data
            jobs = []
            if isinstance(data, dict):
                if 'results' in data:
                    jobs = data['results']
                    logger.info(f"Found jobs in 'results' key: {len(jobs)}")
                elif 'jobs' in data:
                    jobs = data['jobs']
                    logger.info(f"Found jobs in 'jobs' key: {len(jobs)}")
                elif 'data' in data:
                    jobs = data['data']
                    logger.info(f"Found jobs in 'data' key: {len(jobs)}")
                else:
                    logger.warning(f"No jobs found in expected keys. Available keys: {list(data.keys())}")
            
            logger.info(f"Fetched {len(jobs)} jobs from ATS")
            if jobs:
                logger.info(f"First job sample: {jobs[0] if jobs else 'None'}")
            return jobs
        else:
            logger.error(f"Failed to fetch jobs: HTTP {response.status_code}")
            try:
                error_text = response.text
                logger.error(f"Error response: {error_text}")
            except:
                logger.error("Could not read error response")
            return []
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}", exc_info=True)
        return []

# -----------------------------------------------------------------------------
# Navigation helpers
# -----------------------------------------------------------------------------

def navigate_to_candidate_detail(candidate_id: str, log_label: str = "Navigation") -> None:
    """Navigate to candidate_detail page and trigger rerun.

    This centralizes navigation logic, ensuring consistent behaviour and
    providing debug logs whenever a UI element requests navigation.
    """
    logger.info("%s clicked for candidate %s", log_label, candidate_id)
    logger.info(
        "Before nav: current_page=%s, query_params=%s",
        st.session_state.get("current_page"),
        dict(st.query_params),
    )
    st.session_state.current_page = "candidate_detail"
    st.query_params["id"] = candidate_id
    st.query_params["view"] = "candidate_detail"
    logger.info(
        "After nav: current_page=%s, query_params=%s",
        st.session_state.get("current_page"),
        dict(st.query_params),
    )

def initialize_chat_history():
    """Initialize the chat history tracking system"""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = []
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None
    # Initialize conversation context for enhanced intent detection
    if "conversation_context" not in st.session_state:
        st.session_state.conversation_context = {}
    
    # Initialize agent settings (always enabled)
    # Agent mode is always on by default in the unified workflow
    if "show_agent_reasoning" not in st.session_state:
        st.session_state.show_agent_reasoning = True
    if "agent_processing_strategy" not in st.session_state:
        st.session_state.agent_processing_strategy = "comprehensive_fallback"
    
    # Initialize the current session ID if it doesn't exist
    if "current_session_id" not in st.session_state:
        # Create a new session ID using timestamp
        st.session_state.current_session_id = f"session_{int(time.time())}"
        # Add entry to chat sessions list
        st.session_state.chat_sessions.append({
            "id": st.session_state.current_session_id,
            "name": f"Chat {len(st.session_state.chat_sessions) + 1}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "preview": "New conversation"
        })
    
    # Initialize the messages for the current session if they don't exist
    session_key = f"messages_{st.session_state.current_session_id}"
    if session_key not in st.session_state:
        st.session_state[session_key] = [
            {"role": "assistant", "content": "Hello! I'm your AI recruiting assistant. How can I help you today?"}
        ]
    
    # Make sure messages points to the current session
    st.session_state.messages = st.session_state[session_key]

def update_chat_preview():
    """Update the preview text for the current chat session"""
    if len(st.session_state.chat_sessions) > 0 and "messages" in st.session_state and len(st.session_state.messages) > 1:
        # Find the current session in the list
        for i, session in enumerate(st.session_state.chat_sessions):
            if session["id"] == st.session_state.current_session_id:
                # Get the first user message as preview
                user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
                if user_messages:
                    preview = user_messages[0]["content"]
                    # Truncate if too long
                    if len(preview) > 40:
                        preview = preview[:37] + "..."
                    st.session_state.chat_sessions[i]["preview"] = preview
                break

def clear_chat():
    """Clear the current chat conversation and start a new one"""
    # Initialize welcome message
    welcome_message = {"role": "assistant", "content": "Hello! I'm your AI recruiting assistant. How can I help you today?"}
    
    # Reset all conversation state
    if "messages" in st.session_state:
        st.session_state.messages = [welcome_message]
    if "chat_history" in st.session_state:
        st.session_state.chat_history = [welcome_message]
    if "conversation_context" in st.session_state:
        st.session_state.conversation_context = {}
    
    # Reset chat sessions metadata and create a new session
    if "chat_sessions" in st.session_state:
        # Create a new session ID
        new_session_id = f"session_{int(time.time())}"
        # Add to chat sessions list
        st.session_state.chat_sessions.append({
            "id": new_session_id,
            "name": f"Chat {len(st.session_state.chat_sessions) + 1}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "preview": "New conversation"
        })
        # Set as current session
        st.session_state.current_session_id = new_session_id
        # Initialize messages for this session
        st.session_state[f"messages_{new_session_id}"] = [welcome_message]
        st.session_state.messages = st.session_state[f"messages_{new_session_id}"]
    
    logging.info("FRONTEND: Chat cleared and all conversation state reset")
    
    # Log that chat was cleared
    logger.info("Chat cleared and new conversation started")

def page():
    """Assistant chat interface using the new Streamlit 1.45.0 features."""
    # st.title("AI Assistant")  # Removed duplicate header
    
    # Add AI Agent indicator
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px; background-color: #f0f7ff; padding: 10px; border-radius: 5px; border-left: 4px solid #4361ee;">
        <div style="margin-right: 10px; font-size: 24px;">🤖</div>
        <div>
            <div style="font-weight: bold; margin-bottom: 5px;">Enhanced AI Agent Mode</div>
            <div style="font-size: 0.9em;">This assistant uses advanced AI to provide comprehensive, contextual responses to your recruiting questions.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("Get help with job descriptions, interview questions, candidate evaluation, and more.")
    initialize_chat_history()
    
    # --- AI Agent Settings (Unified Workflow) ---
    with st.sidebar:
        st.markdown("### 🤖 AI Agent Settings (Always Enabled)")
        st.markdown("**Agentic Features:**")
        st.markdown("- Context-aware error recovery")
        st.markdown("- Intelligent data enhancement")
        st.markdown("- Market alignment analysis")
        st.markdown("- Quality scoring & feedback")
        st.markdown("- Batch processing support")
        
        # Agent configuration options (always available)
        st.markdown("#### Agent Configuration")
        show_reasoning = st.checkbox(
            "Show Agent Reasoning",
            value=st.session_state.show_agent_reasoning,
            help="Display the agent's decision-making process and analysis",
            key="sidebar_show_agent_reasoning"
        )
        st.session_state.show_agent_reasoning = show_reasoning
        processing_strategy = st.selectbox(
            "Processing Strategy",
            options=["comprehensive_fallback", "comprehensive_only", "section_by_section"],
            index=0 if st.session_state.agent_processing_strategy == "comprehensive_fallback" else 
                  1 if st.session_state.agent_processing_strategy == "comprehensive_only" else 2,
            help="Choose how the agent should process resumes",
            key="sidebar_processing_strategy"
        )
        st.session_state.agent_processing_strategy = processing_strategy
        strategy_explanations = {
            "comprehensive_fallback": "Try comprehensive parsing first, fall back to section-by-section if needed",
            "comprehensive_only": "Only use comprehensive parsing (faster but less resilient)",
            "section_by_section": "Parse each section individually (slower but more thorough)"
        }
        st.caption(strategy_explanations[processing_strategy])
    
    # --- Resume Processing Section ---
    with st.expander("📄 Quick Resume Screening & Job Fit Analysis", expanded=False):
        st.markdown("### 🎯 Pre-Screening Resume Analysis")
        st.markdown("""
        **Purpose**: Quickly evaluate newly sourced candidates before adding them to your ATS database.
        
        **What you'll get**:
        - ✅ **Job Fit Score**: How well the candidate matches your target role
        - 📊 **Skills Analysis**: Matching skills vs. missing skills for the position
        - 🏆 **Quality Assessment**: Resume clarity, impact, and professionalism scores
        - 💡 **Hiring Recommendation**: Should you proceed with this candidate?
        - 📈 **Market Insights**: Salary expectations and skill gap analysis
        """)
        st.markdown("---")

        # File uploader (single file for robust workflow)
        uploaded_file = st.file_uploader(
            "Upload Resume for Screening",
            type=['pdf', 'docx', 'doc', 'txt'],
            accept_multiple_files=False,
            help="Upload a candidate resume you want to quickly evaluate",
            key="assistant_resume_uploader"
        )

        # Job selection from ATS
        st.markdown("**Select Job from ATS:**")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Refresh Jobs", help="Refresh the jobs list from ATS"):
                st.rerun()
        active_jobs = fetch_active_jobs()
        job_options = ["Select a job..."]
        job_map = {}
        if active_jobs:
            for job in active_jobs:
                job_title = job.get('title', 'Unknown Title')
                department = job.get('department', '')
                location = job.get('location', '')
                display_parts = [job_title]
                if department:
                    display_parts.append(f"({department})")
                if location:
                    display_parts.append(f"- {location}")
                display_text = " ".join(display_parts)
                job_options.append(display_text)
                job_map[display_text] = job
        else:
            job_options = ["No jobs available - Please add jobs to your ATS first"]
        selected_job_display = st.selectbox(
            "Choose the job to assess candidates against:",
            options=job_options,
            help="Select a job from your ATS to evaluate candidate fit" if active_jobs else "No jobs available",
            disabled=not active_jobs
        )
        selected_job = None
        target_job_title = None
        if active_jobs and selected_job_display != "Select a job..." and selected_job_display in job_map:
            selected_job = job_map[selected_job_display]
            target_job_title = selected_job.get('title', '')
            st.info(f"💼 **Selected Job:** {selected_job.get('title', 'N/A')} | {selected_job.get('department', 'N/A')} | {selected_job.get('location', 'N/A')}")

        # Session state vars for robust workflow
        if "assistant_parsed_data" not in st.session_state:
            st.session_state["assistant_parsed_data"] = None
        if "assistant_save_status" not in st.session_state:
            st.session_state["assistant_save_status"] = None
        if "assistant_saved_candidate_id" not in st.session_state:
            st.session_state["assistant_saved_candidate_id"] = None
        if "assistant_uploaded_file_info" not in st.session_state:
            st.session_state["assistant_uploaded_file_info"] = None

        # Handle new upload
        if uploaded_file is not None:
            current_file_name = uploaded_file.name
            if (
                st.session_state.assistant_uploaded_file_info is None or
                st.session_state.assistant_uploaded_file_info.get("name") != current_file_name
            ):
                st.session_state.assistant_uploaded_file_info = {"name": uploaded_file.name, "type": uploaded_file.type}
                st.session_state.assistant_parsed_data = None
                st.session_state.assistant_save_status = None
                st.session_state.assistant_saved_candidate_id = None

            st.write("Selected file:", current_file_name)

            # Show Parse button if not already parsed/saved
            if st.session_state.assistant_parsed_data is None and st.session_state.assistant_save_status is None:
                parse_button_text = "🤖 Analyze Resume Fit"
                if st.button(parse_button_text, type="primary", disabled=not (uploaded_file and selected_job)):
                    with st.spinner("🤖 Processing resume with AI agent..."):
                        try:
                            # First ensure job data is synced to Neo4j
                            try:
                                job_id = selected_job.get('id') if selected_job else None
                                sync_response = None
                                if job_id:
                                    sync_url = f"{get_backend_url()}/api/jobs/sync-to-neo4j"
                                    sync_response = requests.post(
                                        sync_url,
                                        json={"job_ids": [job_id]},
                                        timeout=30
                                    )
                                
                                if sync_response and sync_response.status_code == 200:
                                    logger.info(f"Job successfully synced to Neo4j: {sync_response.json()}")
                                elif sync_response:
                                    logger.warning(f"Job sync warning: {sync_response.text}")
                                else:
                                    logger.warning("No job ID available for sync")
                            except requests.exceptions.Timeout:
                                logger.warning("Job sync timed out, continuing with analysis")
                            except Exception as e:
                                logger.warning(f"Job sync error: {e}, continuing with analysis")
                            
                            # Continue with analysis regardless of sync status
                                
                            # Now process the resume with the agent
                            files = {"files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                            task_details = {"target_job_title": target_job_title, "job_data": selected_job}
                            agent_task_url = f"{get_backend_url()}/api/assistant/agent-task"
                            response = requests.post(
                                agent_task_url,
                                files=files,
                                data={
                                    "agent_name": "ResumeProcessingAgent",
                                    "task_details_json": json.dumps(task_details)
                                },
                                timeout=180
                            )
                            response.raise_for_status()
                            result = response.json()
                            
                            # Debug logging
                            logger.info(f"Frontend received response: {result}")
                            logger.info(f"Response status: {result.get('status')}")
                            logger.info(f"Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                            
                            # Additional debugging (commented out for production)
                            # st.write(f"🔍 Debug: Response status = {result.get('status')}")
                            # st.write(f"🔍 Debug: Response keys = {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                            
                            # Handle async task processing
                            if result.get("status") == "processing" and "task_id" in result:
                                task_id = result["task_id"]
                                st.info(f"🔄 Task started with ID: {task_id}")
                                
                                # Poll for task completion with progress indicator
                                max_attempts = 60  # 5 minutes with 5-second intervals
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                # Start a non-blocking background poller to monitor task status
                                status_url = f"{get_backend_url()}/api/assistant/task-status/{task_id}"
                                try:
                                    from frontend.utils.assistant_poller import start_task_poller
                                    # The poller will populate `st.session_state['assistant_parsed_data']` when done
                                    start_task_poller(task_id=task_id, status_url=status_url, result_key="assistant_parsed_data", interval=5.0, max_attempts=max_attempts)
                                    st.info("🔄 Background processing started. This page will update when processing completes.")
                                    # Show a lightweight status area that reflects the current known status
                                    polling_status = st.session_state.get(f"assistant_task_status_{task_id}", "processing")
                                    st.write(f"Task status: {polling_status}")
                                    # Keep an indeterminate progress bar to indicate background work
                                    progress_bar.progress(0.5)
                                    # Don't block — let Streamlit rerun update UI when session_state changes
                                except Exception as e:
                                    logger.exception("Failed to start background poller")
                                    st.error("Failed to start background poller. Falling back to direct polling.")
                                    # Fallback: small blocking loop (short) to check once or twice
                                    try:
                                        status_response = requests.get(status_url, timeout=30)
                                        if status_response.status_code == 200:
                                            task_result = status_response.json()
                                            if task_result.get("status") == "completed":
                                                result = task_result.get("result", {})
                                                st.session_state.assistant_parsed_data = result
                                                st.success("✅ Processing completed!")
                                            else:
                                                st.info(f"Task status: {task_result.get('status')}")
                                        else:
                                            st.warning("Could not retrieve task status from backend")
                                    except Exception as e:
                                        logger.warning(f"Fallback status check failed: {e}")
                            
                            if result.get("status") == "success":
                                # Store the complete agent response so that all analysis fields (job fit score, 
                                # hiring recommendation, quality assessment, etc.) are available to the UI.
                                parsed_full = result.copy()
                                # If the agent nested raw resume data under the 'data' key, merge those keys
                                # into the top-level dictionary for convenient access when rendering.
                                if isinstance(result.get("data"), dict):
                                    parsed_full.update(result["data"])
                                st.session_state.assistant_parsed_data = parsed_full
                                
                                # Show success message
                                st.success("✅ Resume analysis completed successfully!")
                                # st.write("Processing results...")  # Commented out for production
                            else:
                                # Debug: Show the actual response for troubleshooting
                                logger.error(f"Agent processing failed. Full response: {result}")
                                st.error(f"Agent processing failed: {result.get('message', 'Unknown error')}")
                                
                                # Show debug info without nested expander
                                if st.checkbox("Show debug response details", False):
                                    # st.json(result)  # Commented out for production
                                    st.write("Debug response details disabled for production")
                                
                                # If the error is related to Neo4j, try to provide a helpful message
                                error_msg = result.get("message", "").lower()
                                if "neo4j" in error_msg or "graph" in error_msg or "vector" in error_msg or "embedding" in error_msg:
                                    st.warning("⚠️ **Database Synchronization Issue:** Try running the job sync script to ensure all jobs are properly synchronized to the graph database.")
                        except Exception as e:
                            logger.error(f"Error during agent processing: {e}", exc_info=True)
                            st.error(f"Agent processing failed: {str(e)}")

        # Review and confirm UI
        parsed_data = st.session_state.get("assistant_parsed_data")
        save_status = st.session_state.get("assistant_save_status")
        
        # Debug logging of parsed data structure
        if parsed_data:
            logger.info(f"Parsed data structure keys: {list(parsed_data.keys() if isinstance(parsed_data, dict) else [])}")
            logger.info(f"Job fit score present: {'job_fit_score' in parsed_data}")
            logger.info(f"Hiring recommendation present: {'hiring_recommendation' in parsed_data}")
            logger.info(f"Market alignment present: {'market_alignment' in parsed_data}")
            logger.info(f"Quality assessment present: {'quality_assessment' in parsed_data}")
            logger.info(f"Parsed data sample: {str(parsed_data)[:1000]}...")
        if parsed_data and save_status is None:
            st.header("Job Fit Analysis Results")
            st.success("✅ Resume successfully analyzed! Review the job fit assessment below.")
            
            # Display job fit analysis components
            if 'hiring_recommendation' in parsed_data or 'quality_assessment' in parsed_data or 'market_alignment' in parsed_data or 'skill_suggestions' in parsed_data:
                # Display enhanced job fit analysis
                display_hiring_recommendation(parsed_data)
                
                # Display market alignment analysis
                if 'market_alignment' in parsed_data and parsed_data.get('market_alignment') is not None:
                    display_market_alignment_analysis(parsed_data.get('market_alignment', {}))
                
                # Display quality assessment
                if 'quality_assessment' in parsed_data and parsed_data.get('quality_assessment') is not None:
                    display_quality_assessment(parsed_data.get('quality_assessment', {}))
                
                # Display skill suggestions
                if 'skill_suggestions' in parsed_data and parsed_data.get('skill_suggestions') is not None:
                    display_skill_suggestions(parsed_data.get('skill_suggestions', {}))
                    
                st.markdown("---")
                # --- Download / Save Report ---
                report_json = json.dumps(parsed_data, indent=2, default=str)
                st.download_button(
                    label="📥 Download Analysis Report (JSON)",
                    data=report_json,
                    file_name=f"{parsed_data.get('resume_id', 'resume')}_analysis.json",
                    mime="application/json"
                )
            
            # Show job match score
            if 'job_fit_score' in parsed_data:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.metric("Job Fit Score", f"{parsed_data['job_fit_score']}/10")
                with col2:
                    job_title = selected_job.get('title', 'selected') if selected_job else 'selected'
                    st.markdown(f"*How well this candidate matches the {job_title} role*")
            
            # After job fit analysis, show resume content as a separate section
            st.markdown("## Resume Content Preview")
            # Use a toggle instead of an expander to avoid nesting issues
            show_resume_content = st.checkbox("Show parsed resume content", False)
            
            # Only display resume content if the checkbox is checked
            if show_resume_content:
                from frontend.modules.resume_upload import display_personal_info, display_skills, display_experience, display_education, display_military
                # Disable debug expanders to avoid nesting within the assistant expander
                display_personal_info(parsed_data.get("personal_info", {}), debug_expanders=False)
                summary = parsed_data.get("summary")
                if summary:
                    st.subheader("📝 Summary")
                    st.markdown(summary)
                    st.divider()
                display_skills(parsed_data.get("skills", []))
                display_experience(parsed_data.get("experience", []), debug_expanders=False)
                display_education(parsed_data.get("education", []))
                display_military(parsed_data.get("military", []))
            # Other sections
            other_sections = parsed_data.get("other_sections")
            if other_sections and isinstance(other_sections, dict):
                for section_title, section_content in other_sections.items():
                    st.subheader(f"📄 {section_title.replace('_', ' ').title()}")
                    if isinstance(section_content, list):
                        for item in section_content:
                            if isinstance(item, dict):
                                details = [f"**{k.replace('_', ' ').title()}:** {v}" for k, v in item.items() if v]
                                st.markdown("- " + ", ".join(details))
                            else:
                                st.markdown(f"- {item}")
                    elif isinstance(section_content, str):
                        st.markdown(section_content)
                    st.divider()
            st.divider()
            # --- Editable fields for user confirmation ---
            st.subheader("Confirm/Edit Key Details")
            with st.form("assistant_confirm_form"):
                personal_info = parsed_data.get("personal_info", {})
                default_first_name = personal_info.get("first_name", "")
                default_last_name = personal_info.get("last_name", "")
                if not default_first_name and not default_last_name and personal_info.get("name"):
                    name_parts = personal_info["name"].strip().split(maxsplit=1)
                    default_first_name = name_parts[0]
                    default_last_name = name_parts[1] if len(name_parts) > 1 else ""
                first_name = st.text_input("First Name*", value=default_first_name)
                last_name = st.text_input("Last Name", value=default_last_name)
                email = st.text_input("Email*", value=personal_info.get("email", ""))
                submitted = st.form_submit_button("Confirm and Save Candidate")
                if submitted:
                    if not first_name or not email:
                        st.warning("First Name and Email are required.")
                    else:
                        with st.spinner("Saving candidate..."):
                            personal_info["first_name"] = first_name
                            personal_info["last_name"] = last_name
                            personal_info["email"] = email
                            parsed_data["personal_info"] = personal_info
                            original_filename = st.session_state.assistant_uploaded_file_info.get("name") if st.session_state.assistant_uploaded_file_info else "unknown"
                            try:
                                payload = {
                                    "resume_data": parsed_data,
                                    "settings": {"save_to_database": False, "create_candidate": False, "filename": original_filename}
                                }
                                confirm_url = f"{get_backend_url()}/api/resume/confirm"
                                response = requests.post(confirm_url, json=payload, timeout=180)
                                response.raise_for_status()
                                save_response = response.json()
                                if save_response.get("success"):
                                    st.session_state.assistant_save_status = "success"
                                    st.session_state.assistant_saved_candidate_id = save_response.get("candidate_id")
                                    st.session_state.assistant_parsed_data = None
                                    st.success("Candidate saved successfully!")
                                    st.rerun()
                                else:
                                    error_msg = save_response.get("message", "Unknown error during save.")
                                    st.error(f"Failed to save candidate: {error_msg}")
                                    st.session_state.assistant_save_status = "error"
                            except requests.exceptions.Timeout:
                                st.error("Saving request timed out. Please try again.")
                                st.session_state.assistant_save_status = "error"
                            except requests.exceptions.RequestException as e:
                                st.error(f"Network error during save: {e}")
                                st.session_state.assistant_save_status = "error"
                            except Exception as e:
                                st.error(f"An unexpected error occurred during save: {e}")
                                st.session_state.assistant_save_status = "error"
        # Post-save options
        if save_status == "success":
            st.success("Candidate saved successfully!")
            saved_candidate_id = st.session_state.get("assistant_saved_candidate_id")
            if saved_candidate_id:
                st.info(f"Candidate ID: {saved_candidate_id}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("View Candidate Profile", key="assistant_view_profile_btn"):
                    if saved_candidate_id:
                        st.query_params["id"] = saved_candidate_id
                        st.session_state.pop("view_handled", None)
                        st.rerun()
                    else:
                        st.warning("Cannot navigate, saved Candidate ID is missing.")
            with col2:
                if st.button("Upload Another Resume", key="assistant_upload_another_btn"):
                    st.session_state.assistant_uploaded_file_info = None
                    st.session_state.assistant_parsed_data = None
                    st.session_state.assistant_save_status = None
                    st.session_state.assistant_saved_candidate_id = None
                    st.rerun()
        elif save_status == "error":
            st.error("There was an issue saving the candidate. Please review the details and try again, or check the backend logs.")
            if st.button("Try Again / Clear Form", key="assistant_clear_form_btn"):
                st.session_state.assistant_save_status = None
                # Keep parsed_data so the form is still populated
        
    
    # Display any stored results (outside the expander to avoid nesting)
    if "processing_results" in st.session_state and st.session_state.processing_results is not None:
        display_processing_results(st.session_state.processing_results)
    
    # Debug info (outside the expander to avoid nesting) - COMMENTED OUT FOR PRODUCTION
    # with st.expander("🔧 Debug Info", expanded=False):
    #     st.write(f"Backend URL: {BACKEND_URL}")
    #     active_jobs = fetch_active_jobs()  # Get fresh data for debug
    #     st.write(f"Jobs fetched: {len(active_jobs) if active_jobs else 0}")
    #     if active_jobs:
    #         st.write(f"Sample job keys: {list(active_jobs[0].keys()) if active_jobs else 'None'}")
    #         st.json(active_jobs[0] if active_jobs else {})
    
    # --- Recruiter-Focused Info Panel ---
    with st.container():
        st.markdown(f"""
        <div style="background-color: #e0f2fe; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #0288d1;">
            <h3 style="color: #01579b; margin-top: 0;">🤖 <b>Unified AI Recruiting Assistant</b>: Your All-in-One Talent Intelligence Hub</h3>
            <p style="font-size: 1.1rem; color: #334155;">
                <b>Purpose:</b> Empower recruiters to make smarter, faster, and more personalized hiring decisions. Leverage advanced AI to:
                <ul>
                    <li><b>Research</b> candidates, companies, and markets instantly</li>
                    <li><b>Create compelling pitches</b> for top talent</li>
                    <li><b>Answer travel, commute, and relocation questions</b> for candidates (cost, neighborhoods, quality of life, commute trade-offs)</li>
                    <li><b>Analyze salaries</b> and market compensation</li>
                    <li><b>Assess skills</b> and suggest upskilling paths</li>
                    <li><b>Learn about technologies, tools, or industries</b> on demand</li>
                    <li><b>Advanced resume processing</b> with quality scoring and market analysis</li>
                </ul>
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Add a clear button in the main UI area
    col1, col2 = st.columns([5, 1])
    with col1:
        st.write("Get AI assistance with your recruiting tasks.")
    with col2:
        if st.button("🗑️ New Chat", type="primary", help="Clear current chat and start a new conversation"):
            # Direct reset approach
            st.session_state.chat_history = [{"role": "assistant", "content": "Hello! I'm your AI recruiting assistant. How can I help you today?"}]
            st.session_state.conversation_context = {}
            st.rerun()
    

    
    # Also add a button in the sidebar for additional visibility
    st.sidebar.markdown("### Chat Controls")
    if st.sidebar.button("🗑️ Clear Chat", help="Start a new conversation"):
        # Direct reset approach
        st.session_state.chat_history = [{"role": "assistant", "content": "Hello! I'm your recruiting assistant. How can I help you today?"}]
        st.session_state.conversation_context = {}
        st.rerun()
    # Recruiter email style controls
    st.sidebar.markdown("### ✉️ Recruiter Email Style")
    tone_option = st.sidebar.selectbox(
        "Tone",
        options=["professional", "warm", "enthusiastic", "direct", "playful"],
        index=0,
        help="Controls the tone of generated recruiter outreach emails"
    )
    creativity_option = st.sidebar.select_slider(
        "Creativity",
        options=["low", "medium", "high"],
        value="medium",
        help="Higher creativity yields catchier phrasing; lower is more conservative"
    )
    subject_count = st.sidebar.slider(
        "Subject line options",
        min_value=1,
        max_value=5,
        value=3,
        help="How many subject line options to generate"
    )
    # Persist into conversation_context so backend can consume immediately
    ctx = st.session_state.get("conversation_context", {})
    style_ctx = ctx.get("recruiter_email_style", {}) if isinstance(ctx, dict) else {}
    style_ctx.update({
        "tone": tone_option,
        "creativity": creativity_option,
        "subject_line_count": subject_count,
    })
    if isinstance(ctx, dict):
        ctx["recruiter_email_style"] = style_ctx
        st.session_state.conversation_context = ctx
    
    # Initialize chat history in session state if it doesn't exist
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Hello! I'm your recruiting assistant. How can I help you today?"},
            {"role": "user", "content": "I need help drafting a job description for a Senior Python Developer."},
            {"role": "assistant", "content": "I'd be happy to help you draft a job description for a Senior Python Developer position. Here are some key elements to include:\n\n1. **Company Overview**: Brief description of your company and culture\n2. **Role Description**: What the Senior Python Developer will be responsible for\n3. **Required Skills**: Technical skills and experience needed (Python, frameworks, etc.)\n4. **Nice-to-Have Skills**: Preferred but not required skills\n5. **Experience Level**: Years of experience and type of background preferred\n6. **Education Requirements**: Degree requirements or equivalents\n7. **Benefits & Perks**: What makes your company attractive\n\nWould you like me to create a draft based on these elements?"},
            {"role": "user", "content": "Yes, please create a draft. We're a fintech company focusing on payment processing."},
            {"role": "assistant", "content": "**Job Description: Senior Python Developer**\n\n**About Us:**\nOur company is a leading fintech organization specializing in innovative payment processing solutions. We combine cutting-edge technology with financial expertise to deliver secure, efficient, and user-friendly payment systems for businesses of all sizes. We have a collaborative, fast-paced culture where creative problem-solving and continuous learning are valued.\n\n**Role Description:**\nWe are seeking a Senior Python Developer to join our engineering team. In this role, you will design, develop, and maintain our core payment processing systems. You'll work closely with product managers, data scientists, and other developers to build scalable, secure, and high-performance applications. You'll have the opportunity to mentor junior developers and contribute to architectural decisions.\n\n**Key Responsibilities:**\n- Develop and maintain robust, scalable payment processing systems using Python\n- Design and implement APIs for internal and external consumption\n- Optimize application performance and ensure high availability\n- Contribute to architectural decisions and technical strategy\n- Mentor junior developers and perform code reviews\n- Collaborate with cross-functional teams to define requirements and deliver solutions\n- Implement security best practices in all developed systems\n\n**Required Skills and Experience:**\n- 5+ years of professional software development experience\n- 3+ years of experience with Python development\n- Strong experience with RESTful API design and implementation\n- Proficiency with SQL databases (PostgreSQL preferred)\n- Experience with asynchronous programming in Python\n- Knowledge of payment systems or financial technology (desirable)\n- Understanding of security best practices in financial applications\n- Experience with containerization (Docker) and cloud platforms (AWS preferred)\n- Strong problem-solving and debugging skills\n\n**Nice-to-Have Skills:**\n- Experience with FastAPI or Django Rest Framework\n- Knowledge of message queuing systems (RabbitMQ, Kafka)\n- Familiarity with microservices architecture\n- Experience with Redis or other caching mechanisms\n- Understanding of PCI DSS compliance\n- Experience with CI/CD pipelines\n\n**Education:**\n- Bachelor's degree in Computer Science, Software Engineering, or related field (or equivalent practical experience)\n\n**Benefits & Perks:**\n- Competitive salary and equity package\n- Comprehensive health, dental, and vision insurance\n- 401(k) matching program\n- Flexible work arrangements with remote options\n- Continuous learning budget for courses and conferences\n- Regular team events and activities\n- Modern office with all necessary amenities\n\nWe are an equal opportunity employer and value diversity. All employment decisions are made without regard to race, color, religion, sex, national origin, age, disability, or any other protected characteristic.\n\nWould you like me to make any adjustments to this draft?"}
        ]
    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            # Render previously saved messages as markdown for better readability
            if isinstance(message.get("content"), str):
                try:
                    # Try to extract embedded JSON even if wrapped (e.g., 'json (...)' or code fences)
                    maybe_json = _maybe_parse_json_object(message["content"])  # may return dict or None
                    if isinstance(maybe_json, dict):
                        # If this is a market research report, render it nicely
                        if maybe_json.get("response_type") == "market_research":
                            report_payload = maybe_json.get("response") if isinstance(maybe_json.get("response"), dict) else maybe_json
                            display_market_research_report(report_payload)
                        elif maybe_json.get("response_type") == "recruiter_outreach_email":
                            # Display recruiter outreach email properly
                            role = maybe_json.get("role", "the position")
                            email_body = maybe_json.get("email_body") or maybe_json.get("email_content", "")
                            subject_lines = maybe_json.get("subject_lines", [])
                            st.markdown(f"### 📧 Recruiter Outreach Email for {role}")
                            if subject_lines:
                                st.markdown("**Subject line options:**")
                                for s in subject_lines:
                                    st.markdown(f"- {s}")
                            if email_body:
                                st.markdown("```")
                                st.markdown(email_body)
                                st.markdown("```")
                            else:
                                st.error("Email content not generated properly")
                        elif maybe_json.get("report_type"):
                            display_market_research_report(maybe_json)
                        else:
                            _render_dict_as_markdown(maybe_json)
                    else:
                        formatted_content = format_ai_response(message["content"])
                        st.markdown(formatted_content, unsafe_allow_html=True)
                except Exception:
                    st.markdown(fix_merged_text(message["content"]))
            else:
                # Non-string content (e.g., dicts) may come from older messages
                content = message.get("content")
                try:
                    if isinstance(content, dict):
                        # Prefer rich rendering for market research payloads
                        if content.get("response_type") == "market_research" or content.get("report_type"):
                            payload = content.get("response") if isinstance(content.get("response"), dict) else content
                            display_market_research_report(payload)
                        elif content.get("response_type") == "recruiter_outreach_email":
                            # Display recruiter outreach email properly
                            role = content.get("role", "the position")
                            email_body = content.get("email_body") or content.get("email_content", "")
                            subject_lines = content.get("subject_lines", [])
                            st.markdown(f"### 📧 Recruiter Outreach Email for {role}")
                            if subject_lines:
                                st.markdown("**Subject line options:**")
                                for s in subject_lines:
                                    st.markdown(f"- {s}")
                            if email_body:
                                st.markdown("```")
                                st.markdown(email_body)
                                st.markdown("```")
                            else:
                                st.error("Email content not generated properly")
                        else:
                            _render_dict_as_markdown(content)
                    else:
                        st.write(content)
                except Exception:
                    st.write(content)

    # Use the new chat_input with icons feature
    if prompt := st.chat_input("Type your message here...", key="assistant_chat_input"):
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Show assistant typing indicator and process response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    data = generate_response(prompt)
                except Exception as e:
                    logger.exception("Error generating response")
                    st.error("Sorry, I ran into an unexpected error. Please try again.")
                    # Store a compact error string in chat history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"Error: {str(e)}"
                    })
                    raise

            # Handle structured responses
            try:
                # If backend returns a dict
                if isinstance(data, dict):
                    # Candidate search results flow
                    if data.get("candidate_details"):
                        display_enhanced_candidate_results(data)
                        # Save a compact summary to chat history
                        count = len(data.get("candidate_details", []))
                        summary = data.get("response") or f"Found {count} candidate(s)."
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": str(summary)
                        })
                        return

                    # Market research report flow
                    if data.get("response_type") == "market_research":
                        report_payload = data.get("response") if isinstance(data.get("response"), dict) else data
                        display_market_research_report(report_payload)
                        # Save compact string to history
                        title = (report_payload.get("report_type") or "Market Research").replace("_", " ").title() if isinstance(report_payload, dict) else "Market Research"
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"[Generated {title} report]"
                        })
                        return

                    # Recruiter outreach email flow
                    if data.get("response_type") == "recruiter_outreach_email":
                        role = data.get("role", "the position")
                        email_body = data.get("email_body") or data.get("email_content", "")
                        subject_lines = data.get("subject_lines", [])
                        st.markdown(f"### 📧 Recruiter Outreach Email for {role}")
                        if subject_lines:
                            st.markdown("**Subject line options:**")
                            for s in subject_lines:
                                st.markdown(f"- {s}")
                        if email_body:
                            st.markdown("```")
                            st.markdown(email_body)
                            st.markdown("```")
                            # Save to chat history
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": data  # Store the full structured response
                            })
                        else:
                            st.error("Email content not generated properly")
                        return

                    # Generic dict with text response
                    if "response" in data and isinstance(data["response"], str):
                        text = data["response"]
                        # Try JSON detection first
                        try:
                            jd = _maybe_parse_json_object(text)
                            if isinstance(jd, dict):
                                if jd.get("report_type") or jd.get("response_type") == "market_research":
                                    report_payload = jd.get("response") if isinstance(jd.get("response"), dict) else jd
                                    display_market_research_report(report_payload)
                                elif jd.get("response_type") == "recruiter_outreach_email":
                                    # Handle recruiter outreach email in nested JSON
                                    role = jd.get("role", "the position")
                                    email_body = jd.get("email_body") or jd.get("email_content", "")
                                    subject_lines = jd.get("subject_lines", [])
                                    st.markdown(f"### 📧 Recruiter Outreach Email for {role}")
                                    if subject_lines:
                                        st.markdown("**Subject line options:**")
                                        for s in subject_lines:
                                            st.markdown(f"- {s}")
                                    if email_body:
                                        st.markdown("```")
                                        st.markdown(email_body)
                                        st.markdown("```")
                                    else:
                                        st.error("Email content not generated properly")
                                else:
                                    _render_dict_as_markdown(jd)
                            else:
                                formatted_text = format_ai_response(text)
                                st.markdown(formatted_text, unsafe_allow_html=True)
                        except Exception:
                            formatted_text = format_ai_response(text)
                            st.markdown(formatted_text, unsafe_allow_html=True)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": str(text)
                        })
                        return

                    # If dict looks like a direct report object (has report_type), render as market research
                    if data.get("report_type"):
                        display_market_research_report(data)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"[Generated {data.get('report_type', 'Market Research').replace('_',' ').title()} report]"
                        })
                        return

                    # Fallback: render generic dicts nicely
                    _render_dict_as_markdown(data)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": json.dumps(data)
                    })
                    return

                # If backend returned a string
                if isinstance(data, str):
                    # Try to detect embedded JSON report or generic JSON payloads
                    try:
                        jd = _maybe_parse_json_object(data)
                        if isinstance(jd, dict):
                            if jd.get("report_type") or jd.get("response_type") == "market_research":
                                report_payload = jd.get("response") if isinstance(jd.get("response"), dict) else jd
                                display_market_research_report(report_payload)
                            elif jd.get("response_type") == "recruiter_outreach_email":
                                # Handle recruiter outreach email in string response
                                role = jd.get("role", "the position")
                                email_content = jd.get("email_content", "")
                                st.markdown(f"### 📧 Recruiter Outreach Email for {role}")
                                if email_content:
                                    st.markdown("```")
                                    st.markdown(email_content)
                                    st.markdown("```")
                                else:
                                    st.error("Email content not generated properly")
                            else:
                                _render_dict_as_markdown(jd)
                        else:
                            formatted_text = format_ai_response(data)
                            st.markdown(formatted_text, unsafe_allow_html=True)
                    except Exception:
                        formatted_text = format_ai_response(data)
                        st.markdown(formatted_text, unsafe_allow_html=True)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": str(data)
                    })
                    return

                # Unknown type fallback
                formatted_text = format_ai_response(str(data))
                st.markdown(formatted_text, unsafe_allow_html=True)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": str(data)
                })
            except Exception as e:
                logger.exception("Error rendering assistant response")
                st.error("I couldn't render the response properly. Showing raw content below.")
                st.code(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data))
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": (json.dumps(data) if isinstance(data, (dict, list)) else str(data))
                })

def format_ai_response(text: str) -> str:
    """
    Format AI response text for better readability and presentation.
    
    Args:
        text: Raw AI response text
        
    Returns:
        Formatted HTML string for better display
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Apply basic text fixes first
    text = fix_merged_text(text)
    
    import re
    
    # Split by double newlines to get logical blocks
    blocks = text.split('\n\n')
    formatted_blocks = []
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = block.split('\n')
        
        # Check if it's a header (single line starting with #)
        if len(lines) == 1 and lines[0].startswith('#'):
            line = lines[0]
            if line.startswith('### '):
                header_text = sanitize_html(line[4:].strip())
                formatted_blocks.append(f'<h3 style="color: #1e40af; margin-top: 1.5rem; margin-bottom: 0.5rem; font-weight: 600;">{header_text}</h3>')
            elif line.startswith('## '):
                header_text = sanitize_html(line[3:].strip())
                formatted_blocks.append(f'<h4 style="color: #1e40af; margin-top: 1.2rem; margin-bottom: 0.5rem; font-weight: 600;">{header_text}</h4>')
            elif line.startswith('# '):
                header_text = sanitize_html(line[2:].strip())
                formatted_blocks.append(f'<h5 style="color: #1e40af; margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600;">{header_text}</h5>')
            continue
        
        # Check if it's a bullet list (all lines start with -, *, or •)
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if non_empty_lines and all(line.startswith(('- ', '* ', '• ')) for line in non_empty_lines):
            list_items = []
            for line in non_empty_lines:
                item_text = line[2:].strip()
                # Apply inline formatting
                item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
                item_text = re.sub(r'`([^`]+)`', r'<code style="background-color: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.9em;">\1</code>', item_text)
                list_items.append(f'<li style="margin: 0.3rem 0; line-height: 1.5;">{item_text}</li>')
            formatted_blocks.append(f'<ul style="margin: 0.8rem 0; padding-left: 1.5rem; color: #374151;">{"".join(list_items)}</ul>')
            continue
        
        # Check if it's a numbered list (all lines start with number.)
        if non_empty_lines and all(re.match(r'^\d+\.\s', line) for line in non_empty_lines):
            list_items = []
            for line in non_empty_lines:
                item_text = re.sub(r'^\d+\.\s', '', line).strip()
                # Apply inline formatting
                item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
                item_text = re.sub(r'`([^`]+)`', r'<code style="background-color: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.9em;">\1</code>', item_text)
                list_items.append(f'<li style="margin: 0.3rem 0; line-height: 1.5;">{item_text}</li>')
            formatted_blocks.append(f'<ol style="margin: 0.8rem 0; padding-left: 1.5rem; color: #374151;">{"".join(list_items)}</ol>')
            continue
        
        # Regular paragraph - join all lines
        para_text = ' '.join(line.strip() for line in lines if line.strip())
        if para_text:
            # Apply inline formatting
            para_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', para_text)
            para_text = re.sub(r'`([^`]+)`', r'<code style="background-color: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.9em;">\1</code>', para_text)
            formatted_blocks.append(f'<p style="margin: 0.8rem 0; line-height: 1.6; color: #374151;">{para_text}</p>')
    
    # Join all formatted content
    formatted_content = ''.join(formatted_blocks)
    
    # Wrap in a container for consistent styling
    return f'''
    <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 100%; overflow-wrap: break-word;">
        {formatted_content}
    </div>
    '''

def _maybe_parse_json_object(text: str):
    """
    Best-effort extraction of a JSON object from a text blob.
    Handles cases like:
    - ```json { ... } ```
    - json({...}) or JSON: {...}
    - Plain leading/trailing prose around { ... }

    Returns a dict if parsing succeeds, else None.
    """
    if not isinstance(text, str):
        return None
    s = text.strip()
    # Handle inline code-style wrappers using single backticks and normalize smart quotes
    if (s.startswith("`") and s.endswith("`")) or s.startswith("`json"):
        s = s.strip("`")
    # Normalize curly quotes to straight quotes to improve JSON parsing resilience
    s = (s
         .replace("\u201c", '"').replace("\u201d", '"')
         .replace("\u2018", "'").replace("\u2019", "'")
         .replace("“", '"').replace("”", '"')
         .replace("‘", "'").replace("’", "'"))
    # Remove code fences
    if s.startswith("```"):
        # Strip first fence line
        s = "\n".join(s.splitlines()[1:])
        # Strip trailing fence if present
        if s.rstrip().endswith("```"):
            s = "\n".join(s.rstrip().splitlines()[:-1])
        s = s.strip()
    # Remove leading 'json' or 'JSON:' wrappers
    lower = s.lower()
    if lower.startswith("json(") and s.endswith(")"):
        s = s[5:-1].strip()
    elif lower.startswith("json "):
        s = s[5:].strip()
    elif lower.startswith("json:"):
        s = s[5:].strip()
    elif lower.startswith("json"):
        s = s[4:].strip()

    # If it already starts with '{', try direct loads
    try:
        if s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                # Try Python-literal style (single quotes) safely
                try:
                    candidate = ast.literal_eval(s)
                    if isinstance(candidate, dict):
                        logger.debug("_maybe_parse_json_object: parsed python-literal dict at start")
                        return candidate
                except Exception:
                    pass
    except Exception:
        pass

    # Attempt to find the first balanced {...} block
    start = s.find("{")
    if start == -1:
        return None
    stack = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == '{':
            stack += 1
        elif ch == '}':
            stack -= 1
            if stack == 0:
                candidate = s[start:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    # Try Python-literal style (single quotes) safely
                    try:
                        py_obj = ast.literal_eval(candidate)
                        if isinstance(py_obj, dict):
                            logger.debug("_maybe_parse_json_object: parsed python-literal dict from balanced braces")
                            return py_obj
                    except Exception:
                        return None
    return None

def _format_key_label(k: Any) -> str:
    """Format dict keys into human-friendly labels:
    - Replace underscores with spaces
    - Insert spaces between camelCase/PascalCase boundaries
    - Collapse multiple spaces and title-case
    """
    try:
        s = str(k).strip()
        s = s.replace('_', ' ')
        # Insert spaces before capital letters that follow a lowercase/digit, e.g., 'ActivePostings' -> 'Active Postings'
        s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', s)
        # Handle acronym followed by capital+lower, e.g., 'APIResponse' -> 'API Response'
        s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        return sanitize_html(s.title())
    except Exception:
        return sanitize_html(str(k))

def _render_dict_as_markdown(data: Any, level: int = 0):
    """Render arbitrary dict/list payloads as readable markdown instead of JSON.
    - Dict: prints section header per nested dict, and bullets for key-values
    - List: prints bullets; nested dicts render recursively
    """
    indent = ""  # Streamlit markdown ignores leading spaces for bullets; keep flat
    def fmt_key(k: Any) -> str:
        return _format_key_label(k)
    def fmt_val(v: Any) -> str:
        if isinstance(v, (dict, list)):
            return None
        try:
            return sanitize_html(str(v))
        except Exception:
            return str(v)

    lines: list[str] = []
    try:
        if isinstance(data, dict):
            # Separate simple pairs from nested sections
            simple_items = []
            nested_items = []
            for k, v in data.items():
                (nested_items if isinstance(v, (dict, list)) else simple_items).append((k, v))

            # Simple K/V as bullets
            for k, v in simple_items:
                val = fmt_val(v)
                if val not in (None, "", "None"):
                    lines.append(f"- **{fmt_key(k)}:** {val}")

            # Nested sections
            for k, v in nested_items:
                lines.append("")
                lines.append(f"#### {fmt_key(k)}")
                nested_md = _collect_markdown(v)
                if nested_md:
                    lines.append(nested_md)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append("-")
                    nested_md = _collect_markdown(item)
                    if nested_md:
                        lines.append(nested_md)
                else:
                    val = fmt_val(item)
                    if val not in (None, "", "None"):
                        lines.append(f"- {val}")
        else:
            lines.append(sanitize_html(str(data)))
    except Exception:
        # Fallback to code if anything goes wrong
        st.code(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data))
        return

    md = "\n".join([ln for ln in lines if ln is not None])
    if md.strip():
        st.markdown(md)
    else:
        st.code(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data))

def _collect_markdown(value: Any) -> str:
    """Helper that collects markdown text recursively for dict/list values."""
    buf: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                buf.append(f"- **{_format_key_label(k)}:**")
                nested = _collect_markdown(v)
                if nested:
                    buf.append(nested)
            else:
                buf.append(f"- **{_format_key_label(k)}:** {sanitize_html(str(v))}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                nested = _collect_markdown(item)
                if nested:
                    buf.append(nested)
            else:
                buf.append(f"- {sanitize_html(str(item))}")
    else:
        buf.append(sanitize_html(str(value)))
    return "\n".join(buf)

def display_market_research_report(report: Dict[str, Any]):
    """Render market research/intelligence reports in chat.

    Expected dynamic payload from backend (examples):
      - City viability snapshot: {
          status, report_type, role, city, seniority, time_range, analysis, sources, timestamp
        }
      - Other report types may include different keys; we render dynamically.
    """
    try:
        # Header
        role = report.get("role")
        city = report.get("city")
        report_type = report.get("report_type", "Market Research").replace("_", " ").title()
        seniority = report.get("seniority")
        time_range = report.get("time_range")
        ts = report.get("timestamp")

        header_bits = []
        if role: header_bits.append(f"Role: <b>{sanitize_html(role)}</b>")
        if city: header_bits.append(f"City: <b>{sanitize_html(city)}</b>")
        if seniority: header_bits.append(f"Seniority: <b>{sanitize_html(seniority)}</b>")
        if time_range: header_bits.append(f"Time Range: <b>{sanitize_html(time_range)}</b>")

        st.markdown(
            f"""
            <div style="padding:12px;border-left:4px solid #1d4ed8;background:#eff6ff;border-radius:6px;margin-bottom:8px;">
                <div style="font-weight:700;color:#1e3a8a;">📊 {sanitize_html(report_type)}</div>
                <div style="font-size:0.9rem;color:#334155;">{' • '.join(header_bits)}</div>
                {f'<div style="font-size:0.8rem;color:#64748b;margin-top:4px;">Generated: {sanitize_html(ts)}</div>' if ts else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Analysis can be string or dict
        analysis = report.get("analysis")
        if isinstance(analysis, str) and analysis.strip():
            st.markdown(analysis)
        elif isinstance(analysis, dict):
            # Show known helpful sections first if present
            prioritized = [
                "summary", "overview", "demand_supply", "salary_benchmarks",
                "top_companies", "talent_pools", "remote_viability",
                "sourcing_channels", "risk_factors", "actions"
            ]
            shown = set()
            for key in prioritized:
                if key in analysis and analysis[key]:
                    _display_generic_section(key, analysis[key])
                    shown.add(key)
            # Render any remaining sections dynamically
            for key, val in analysis.items():
                if key in shown:
                    continue
                _display_generic_section(key, val)

        # Sources (if any)
        sources = report.get("sources")
        if isinstance(sources, list) and sources:
            with st.expander("Sources", expanded=False):
                for idx, src in enumerate(sources, start=1):
                    if isinstance(src, dict):
                        title = src.get("title") or f"Source {idx}"
                        link = src.get("link") or src.get("url")
                        snippet = src.get("snippet") or src.get("summary")
                        if link:
                            st.markdown(f"- [{sanitize_html(title)}]({link})")
                        else:
                            st.markdown(f"- {sanitize_html(title)}")
                        if snippet:
                            st.caption(snippet)
                    else:
                        st.markdown(f"- {sanitize_html(str(src))}")

    except Exception as e:
        logger.error(f"Error rendering market research report: {e}")
        st.code(json.dumps(report, indent=2), language="json")

def _display_generic_section(title_key: str, content: Any):
    """Helper to render any section with a nice heading and dynamic content."""
    title = title_key.replace("_", " ").title()
    st.markdown(f"#### {title}")
    if isinstance(content, str):
        st.markdown(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                st.json(item)
            else:
                st.markdown(f"- {item}")
    elif isinstance(content, dict):
        # Try to present key metrics cleanly
        simple = True
        for v in content.values():
            if isinstance(v, (dict, list)):
                simple = False
                break
        if simple:
            # Render as bullet list of key: value
            for k, v in content.items():
                st.markdown(f"- **{k.replace('_',' ').title()}:** {v}")
        else:
            # Nested structure - fallback to JSON for clarity
            st.json(content)

# ... (rest of the code remains the same)
        
        # Display parsed data
        if 'parsed_data' in data:
            display_parsed_resume_data(data['parsed_data'])
        else:
            # Fallback to individual fields
            parsed_data = {
                'personal_info': data.get('personal_info'),
                'education': data.get('education'),
                'experience': data.get('experience'),
                'skills': data.get('skills'),
                'military': data.get('military')
            }
            display_parsed_resume_data(parsed_data)
    else:
        st.error(data.get('message', 'Resume parsing failed'))

def display_parsed_resume_data(parsed_data):
    """Display the parsed resume data in a structured format"""
    
    if not parsed_data:
        st.warning("No parsed data available")
        return
    
    # Personal Information
    if parsed_data.get('personal_info'):
        st.markdown("#### Personal Information")
        personal = parsed_data['personal_info']
        
        col1, col2 = st.columns(2)
        with col1:
            if personal.get('name'):
                st.markdown(f"**Name:** {personal['name']}")
            if personal.get('email'):
                st.markdown(f"**Email:** {personal['email']}")
            if personal.get('phone'):
                st.markdown(f"**Phone:** {personal['phone']}")
        with col2:
            if personal.get('location'):
                st.markdown(f"**Location:** {personal['location']}")
            if personal.get('linkedin'):
                st.markdown(f"**LinkedIn:** {personal['linkedin']}")
    
    # Experience
    if parsed_data.get('experience'):
        st.markdown("#### Experience")
        for exp in parsed_data['experience']:
            st.markdown(f"**{exp.get('title', '-') or '-'} at {exp.get('company', '-') or '-'}**")
            if exp.get('date_range'):
                st.markdown(f"*{exp['date_range']}*")
            if exp.get('description'):
                st.markdown(exp['description'])
            if exp.get('location'):
                st.markdown(f"Location: {exp['location']}")
            st.markdown("---")
    
    # Education
    if parsed_data.get('education'):
        st.markdown("#### Education")
        for edu in parsed_data['education']:
            st.markdown(f"**{edu.get('degree', '-') or '-'} at {edu.get('institution', '-') or '-'}**")
            if edu.get('graduation_date'):
                st.markdown(f"*Graduated: {edu['graduation_date']}*")
    
    # Skills
    if parsed_data.get('skills'):
        st.markdown("#### Skills")
        skills_list = []
        for skill in parsed_data['skills']:
            if isinstance(skill, dict):
                skills_list.append(skill.get('name', str(skill)))
            else:
                skills_list.append(str(skill))
        
        if skills_list:
            st.markdown(", ".join(skills_list))
    
    # Certifications
    if parsed_data.get('certifications'):
        st.markdown("#### Certifications")
        for cert in parsed_data['certifications']:
            st.markdown(f"- {cert}")
    
    # Summary
    if parsed_data.get('summary'):
        st.markdown("#### Summary")
        st.markdown(parsed_data['summary'])

def generate_response(prompt: str):
    """
    Generate an AI response using the agentic backend assistant endpoint.
    Returns the full response data to allow for enhanced display of candidate results.
    """
    return call_backend_assistant(prompt)

def display_enhanced_candidate_results(response_data):
    """
    Display candidate search results with enhanced formatting, interactive links, and stack ranking.
    
    Args:
        response_data: Dictionary containing response text and candidate details
    """
    response_text = response_data.get("response", "")
    candidate_details = response_data.get("candidate_details", [])
    
    # Display the main response text with smart JSON detection
    try:
        jd = _maybe_parse_json_object(response_text) if isinstance(response_text, str) else None
        if isinstance(jd, dict) and (jd.get("report_type") or jd.get("response_type") == "market_research"):
            report_payload = jd.get("response") if isinstance(jd.get("response"), dict) else jd
            display_market_research_report(report_payload)
        else:
            st.markdown(fix_merged_text(response_text))
    except Exception:
        st.markdown(fix_merged_text(response_text))
    logger.info("Candidate section: received %d candidates", len(candidate_details))
    
    # If we have candidate details, display them in an enhanced format
    if candidate_details:
        st.markdown("---")
        st.markdown("### Interactive Candidate Matches")
        
        # Sort candidates by match score (stack ranking)
        if candidate_details and 'match_score' in candidate_details[0]:
            candidate_details.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        # Display candidates in a more interactive format
        for i, candidate in enumerate(candidate_details, 1):
            match_score = candidate.get('match_score', 0)
            score_color = "🟢" if match_score >= 80 else "🟡" if match_score >= 70 else "🔴"
            
            # Simple candidate header (HTML card temporarily removed to test button clicks)
            st.markdown(f"**{score_color} {candidate['name']}** • {candidate.get('position', 'Position not specified')} ({match_score}% match)")
            
            # Create columns for action buttons
            col1, col2, col3, col4 = st.columns(4)
                
            with col1:
                    # Quick View button - opens candidate detail in new tab
                    candidate_key = str(candidate.get('id', i))
                    logger.info("Rendering card %d with key %s", i, candidate_key)
                    logger.debug("Session state keys snapshot: %s", list(st.session_state.keys())[:20])
                    st.button(
                        "👁️ Quick View",
                        key=f"quick_view_{candidate_key}",
                        on_click=navigate_to_candidate_detail,
                        args=(candidate_key,),
                        kwargs={"log_label": "Quick View"},
                    )
                
            with col2:
                    # View Full Profile button
                    if st.button("📋 Full Profile", key=f"full_profile_{candidate_key}"):
                        # Navigate to candidate detail page using query params (matching working pattern)
                        st.session_state.current_page = "candidate_detail"
                        st.query_params["id"] = candidate_key
                        st.query_params["view"] = "candidate_detail"
                        st.rerun()
                
            with col3:
                    # Contact button
                    if st.button("📧 Contact", key=f"contact_{candidate_key}"):
                        st.info(f"Contact functionality for {candidate['name']} would be implemented here")
                
            with col4:
                    # Expandable details
                    with st.expander("🔍 Details", expanded=False):
                        # Display skills if available
                        if candidate.get('skills'):
                            st.markdown("**🛠️ Key Skills:**")
                            skills = candidate['skills'][:8]  # Show first 8 skills
                            if len(candidate['skills']) > 8:
                                skills.append(f"... and {len(candidate['skills']) - 8} more")
                            
                            # Create skill badges
                            for skill in skills:
                                st.markdown(f"<div style='background-color: #e3f2fd; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; margin: 2px; display: inline-block;'>{skill}</div>", unsafe_allow_html=True)
                        
                        # Display additional context if available
                        if candidate.get('current_company') or candidate.get('location'):
                            st.markdown("**📍 Additional Info:**")
                            info_parts = []
                            if candidate.get('current_company'):
                                info_parts.append(f"Company: {candidate['current_company']}")
                            if candidate.get('location'):
                                info_parts.append(f"Location: {candidate['location']}")
                            st.write(" • ".join(info_parts))
                
        st.markdown("---")
        
        # Add summary statistics
        st.markdown("### 📊 Match Summary")
        total_candidates = len(candidate_details)
        high_matches = len([c for c in candidate_details if c.get('match_score', 0) >= 80])
        good_matches = len([c for c in candidate_details if 70 <= c.get('match_score', 0) < 80])
        basic_matches = len([c for c in candidate_details if c.get('match_score', 0) < 70])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Matches", total_candidates)
        with col2:
            st.metric("Excellent (80%+)", high_matches, delta=f"{high_matches/total_candidates*100:.1f}%" if total_candidates > 0 else 0)
        with col3:
            st.metric("Good (70-79%)", good_matches, delta=f"{good_matches/total_candidates*100:.1f}%" if total_candidates > 0 else 0)
        with col4:
            st.metric("Basic (<70%)", basic_matches, delta=f"{basic_matches/total_candidates*100:.1f}%" if total_candidates > 0 else 0)
        

        
        # Add action buttons
        st.markdown("### 🚀 Quick Actions")
        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        
        with action_col1:
            if st.button("📋 Export List", key="export_list", use_container_width=True):
                st.info("Export functionality would be implemented here")
        
        with action_col2:
            if st.button("📧 Contact Top Matches", key="contact_top", use_container_width=True):
                st.info("Bulk contact functionality would be implemented here")
        
        with action_col3:
            if st.button("📊 Create Report", key="create_report", use_container_width=True):
                st.info("Report generation would be implemented here")
        
        with action_col4:
            if st.button("🔍 Refine Search", key="refine_search", use_container_width=True):
                st.info("Search refinement would be implemented here")

def is_candidate_pitch(text):
    """
    Detect if text appears to be a candidate pitch.
    
    Args:
        text: The response text to analyze (can be string or dict)
        
    Returns:
        bool: True if text is likely a candidate pitch, False otherwise
    """
    # Ensure text is always a string
    if isinstance(text, dict):
        text = text.get('content', '')
    else:
        text = str(text)
    # Check for typical patterns in candidate pitches
    pitch_keywords = [
        "candidate pitch", "candidate profile", "candidate summary",
        "professional summary", "pitch for", "candidate overview"
    ]
    has_pitch_keyword = any(keyword in text.lower() for keyword in pitch_keywords)
    # Check for structural elements common in pitches
    has_pitch_structure = (
        ("skills" in text.lower() or "experience" in text.lower()) and
        ("background" in text.lower() or "profile" in text.lower()) and
        len(text.split()) > 50  # Reasonable length for a pitch
    )
    return has_pitch_keyword or has_pitch_structure

def save_candidate_pitch(pitch_content, user_id=None, candidate_id=None, job_id=None):
    """
    Save a candidate pitch to the user's account.
    
    Args:
        pitch_content: The pitch text to save
        user_id: The ID of the user saving the pitch
        candidate_id: Optional ID of the associated candidate
        job_id: Optional ID of the associated job
        
    Returns:
        dict: Result of the save operation
    """
    try:
        # Default to testuser if no user_id is provided
        if not user_id and "username" in st.session_state:
            user_id = st.session_state.username
        elif not user_id:
            user_id = "testuser"  # Fallback for demo
        
        # Show a form to gather additional information
        with st.form(key="save_pitch_form"):
            title = st.text_input("Title for this pitch", value="Candidate Pitch")
            notes = st.text_area("Additional notes", placeholder="Add any notes about this pitch...")
            tags = st.text_input("Tags (comma separated)", placeholder="e.g., technical, senior-level, remote")
            
            submit_pressed = st.form_submit_button("Save Pitch")
            
            if submit_pressed:
                # Call the backend API to save the pitch
                api_url = "http://localhost:8000/pitches/save"
                
                payload = {
                    "title": title,
                    "content": pitch_content,
                    "user_id": user_id,
                    "notes": notes,
                    "tags": tags,
                    "candidate_id": candidate_id,
                    "job_id": job_id
                }
                
                response = requests.post(api_url, json=payload)
                
                if response.status_code == 200:
                    st.success(" Pitch saved successfully! You can view it in the Communications tab.")
                    return {"success": True, "message": "Pitch saved successfully"}
                else:
                    st.error(f"Failed to save pitch: {response.text}")
                    return {"success": False, "message": f"Error: {response.text}"}
        
        return {"success": False, "message": "Form not submitted"}
    
    except Exception as e:
        st.error(f"Error saving pitch: {str(e)}")
        return {"success": False, "message": f"Exception: {str(e)}"}

def call_backend_assistant(message):
    """
    Call the backend assistant API to get responses for database queries and other server-side data.
    Includes conversation context for enhanced intent detection.
    """
    try:
        # Prepare the data to send to the API
        api_url = "http://localhost:8000/api/assistant/chat"
        
        # Using the global state for enhanced context tracking
        conversation_history = []
        for msg in st.session_state.chat_history:
            # Convert to format expected by backend
            conversation_history.append({
                "sender": "user" if msg["role"] == "user" else "assistant",
                "message": msg["content"]
            })
        
        # Fetch context from session state (if not exist, use empty dict)
        context = st.session_state.get("conversation_context", {})
        
        payload = {
            "message": message,
            "conversation_history": conversation_history,
            "conversation_context": context
        }
        
        # Call the backend API
        response = requests.post(api_url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Update conversation context with any new values from backend
            if "conversation_context" in data:
                st.session_state.conversation_context = data["conversation_context"]
                logging.info(f"FRONTEND: Updated conversation context: {st.session_state.conversation_context}")
            
            # Return the full response data to allow for enhanced display
            if "response" in data:
                return data  # Return the full data object instead of just the response text
            else:
                # Fallback for absent response field
                return {"response": "I'm sorry, I couldn't process that request properly. Please try again or rephrase your question."}
        else:
            # Handle non-200 status codes
            logging.error(f"Backend API error: {response.status_code} - {response.text}")
            try:
                error_detail = response.json().get("detail", "No additional details")
                return {"response": f"Error: The backend returned status code {response.status_code}. Details: {error_detail}"}
            except Exception:
                return {"response": f"Error: The backend returned status code {response.status_code}. Please try again later."}
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error: {str(e)}"
        st.error(error_msg)
        return {"response": f"I'm having trouble connecting to the server right now. Error: {str(e)}"}
        
    except Exception as e:
        # Handle connection errors and exceptions
        logging.error(f"Error calling backend assistant: {e}")
        return {"response": f"I'm having trouble connecting to the server right now. Error: {str(e)}"}

def create_salary_info_response(prompt, salary_preference=None):
    """
    Generate a salary information response for a given prompt, detecting role, location, and user preference for current or historical salary data.
    Returns a markdown-formatted string with salary ranges.
    """
    import re
    # Simple salary database (expand as needed)
    salary_db = {
        "software engineer": {
            "us": (90000, 130000, 170000),
            "uk": (40000, 60000, 85000),
            "germany": (50000, 70000, 95000),
            "india": (800000, 1600000, 3000000),
            "default": (60000, 90000, 120000),
        },
        "data scientist": {
            "us": (95000, 140000, 180000),
            "uk": (42000, 65000, 90000),
            "germany": (55000, 80000, 110000),
            "india": (1000000, 1800000, 3200000),
            "default": (65000, 95000, 125000),
        },
        "product manager": {
            "us": (100000, 145000, 200000),
            "uk": (50000, 80000, 120000),
            "germany": (60000, 95000, 140000),
            "india": (1200000, 2000000, 3500000),
            "default": (70000, 110000, 150000),
        },
        "designer": {
            "us": (70000, 105000, 140000),
            "uk": (35000, 55000, 80000),
            "germany": (40000, 65000, 90000),
            "india": (600000, 1200000, 2200000),
            "default": (50000, 80000, 110000),
        },
        # Add more roles as needed
    }

    # Detect role (very basic matching)
    prompt_lower = prompt.lower()
    detected_role = None
    for role in salary_db.keys():
        if role in prompt_lower:
            detected_role = role
            break
    if not detected_role:
        # Try to extract a generic tech role
        detected_role = "software engineer"  # fallback

    # Detect location
    location_map = {
        "us": ["us", "usa", "united states", "america"],
        "uk": ["uk", "united kingdom", "england", "london"],
        "germany": ["germany", "berlin", "munich", "frankfurt"],
        "india": ["india", "bangalore", "delhi", "mumbai", "hyderabad"],
    }
    detected_location = None
    for loc_key, loc_terms in location_map.items():
        for term in loc_terms:
            if term in prompt_lower:
                detected_location = loc_key
                break
        if detected_location:
            break
    if not detected_location:
        detected_location = "default"

    # Get salary info
    entry, mid, senior = salary_db.get(detected_role, salary_db["software engineer"]).get(detected_location, salary_db["software engineer"]["default"])

    # Format salary string
    if detected_location == "india":
        fmt = lambda v: f"₹{v:,}"
        location_str = "India"
    elif detected_location == "uk":
        fmt = lambda v: f"£{v:,}"
        location_str = "UK"
    elif detected_location == "germany":
        fmt = lambda v: f"€{v:,}"
        location_str = "Germany"
    else:
        fmt = lambda v: f"${v:,}"
        location_str = "US/Other"

    # Preference string for display
    pref_str = "Current" if salary_preference == "current" else ("Historical" if salary_preference == "historical" else "Estimated")

    response = f"""
### {pref_str} Salary Ranges for {detected_role.title()} ({location_str})

| Level     | Estimated Salary      |
|-----------|----------------------|
| Entry     | {fmt(entry)}         |
| Mid       | {fmt(mid)}           |
| Senior    | {fmt(senior)}        |

*Note: Salaries are approximate and can vary based on company, location, and experience.*
"""
    # Optionally, add a debug line for development
    # response += f"\n\n_Detected preference: {salary_preference}_"
    return response

def create_job_description_response():
    """Create a response for job description queries"""
    return """
    Here's a draft job description for a Software Engineer position:
    
    # Software Engineer
    
    ## About the Role
    We're looking for a talented Software Engineer to join our growing engineering team. You'll be working on developing and maintaining our core product, collaborating with cross-functional teams, and implementing new features.
    
    ## Responsibilities
    - Design, develop, and maintain high-quality software
    - Write clean, efficient, and well-documented code
    - Collaborate with product managers, designers, and other engineers
    - Troubleshoot and debug issues
    - Participate in code reviews and contribute to engineering best practices
    
    ## Requirements
    - Bachelor's degree in Computer Science or related field
    - 3+ years of experience in software development
    - Proficiency in one or more programming languages (Python, JavaScript, Java)
    - Experience with web development and RESTful APIs
    - Strong problem-solving skills and attention to detail
    
    Would you like me to refine this for a specific role or technology stack?
    """

def create_screening_questions_response():
    """Create a response for screening questions queries"""
    return """
    Here are some effective screening questions for a software engineering candidate:
    
    1. **Technical Background**:
       - What programming languages are you most comfortable with?
       - Describe a challenging technical problem you solved recently.
    
    2. **Experience Assessment**:
       - Tell me about your experience with [specific technology/tool].
       - How have you implemented CI/CD in previous roles?
    
    3. **Problem-Solving**:
       - How would you approach optimizing a slow-performing application?
       - Describe your debugging process when encountering an unexpected error.
    
    4. **Collaboration & Communication**:
       - How do you handle disagreements with team members over technical approaches?
       - Describe how you've worked with non-technical stakeholders.
    
    5. **Growth & Learning**:
       - What new technology or skill have you learned recently?
       - How do you stay updated with industry trends?
    
    Would you like me to tailor these questions for a specific role or seniority level?
    """

def create_interview_questions_response():
    """Create a response for interview questions queries"""
    return """
    Here are some in-depth interview questions for technical roles:
    
    ### Technical Questions
    1. How would you design a scalable API for our product?
    2. Explain the differences between optimistic and pessimistic concurrency control.
    3. How would you implement a caching strategy for our application?
    4. Describe how you would architect a microservices solution for our platform.
    
    ### Behavioral Questions
    1. Tell me about a time when you had to meet a tight deadline. How did you manage it?
    2. Describe a situation where you had to learn a new technology quickly.
    3. How have you handled disagreements with team members in the past?
    4. Give an example of a project where you demonstrated leadership.
    
    ### Problem-Solving Questions
    1. How would you debug a production issue that can't be replicated in development?
    2. Our system is experiencing performance issues during peak hours. How would you approach diagnosing and fixing it?
    3. We need to migrate from our current database to a new one with minimal downtime. How would you approach this?
    
    Would you like me to provide follow-up questions for any of these topics?
    """

def create_resume_analysis_response():
    """Create a response for resume analysis queries"""
    return """
    Based on the resume you shared, here's my analysis:
    
    ### Strengths
    - Strong technical background with 5+ years of experience in software development
    - Proficiency in multiple programming languages (Python, JavaScript, Java)
    - Experience with modern frameworks and tools (React, Node.js, Docker)
    - Track record of leading successful projects
    
    ### Areas for Development
    - Limited experience with cloud infrastructure (only mentions AWS basics)
    - No mention of testing methodologies or quality assurance practices
    - Could benefit from more specific metrics of success in previous roles
    
    ### Fit for Role
    - **Technical Skills**: 8/10 - Strong match for our tech stack
    - **Experience Level**: 7/10 - Good alignment with senior developer role
    - **Domain Knowledge**: 6/10 - Some relevant industry experience, but not specific to our sector
    - **Overall Match**: 7/10 - Strong candidate worth advancing to interview stage
    
    ### Recommended Interview Focus Areas
    1. Deep dive into cloud architecture knowledge
    2. Testing practices and quality assurance approach
    3. Leadership experience and team collaboration
    
    Would you like me to analyze another resume or compare multiple candidates?
    """

def create_assessment_response():
    """Create a response for assessment queries"""
    return """
    Here's a suggested technical assessment for a Full-Stack Developer:
    
    ### Part 1: Coding Exercise (1-2 hours)
    Create a simple full-stack application with:
    - Backend API with 2-3 endpoints
    - Frontend interface to interact with the API
    - Basic data persistence
    
    ### Part 2: System Design (45 minutes)
    Design a scalable architecture for a real-time chat application supporting:
    - Multiple devices per user
    - Message history
    - Offline message delivery
    - Group chats
    
    ### Part 3: Code Review (30 minutes)
    Review a provided piece of code and:
    - Identify potential bugs or issues
    - Suggest improvements for performance and readability
    - Explain your reasoning for each suggestion
    
    ### Evaluation Criteria
    - **Functionality**: Does the solution work as expected?
    - **Code Quality**: Is the code clean, well-structured, and maintainable?
    - **Performance**: Are there any obvious performance issues?
    - **Best Practices**: Does the solution follow industry standards?
    - **Communication**: How well does the candidate explain their decisions?
    
    Would you like me to tailor this assessment for a different role or skill level?
    """

def create_minimum_wage_response(location=None):
    """Create a response for minimum wage queries with location-specific information"""
    # Minimum wage database by location (as of April 2025)
    min_wage_db = {
        "seattle": {
            "rate": 19.97,
            "currency": "$",
            "notes": "For large employers (501+ employees). Small employers must pay $17.25 or provide $3.25/hour in medical benefits.",
            "source": "Seattle Office of Labor Standards",
            "effective": "January 1, 2025"
        },
        "washington": {
            "rate": 16.28,
            "currency": "$",
            "notes": "Statewide minimum wage for all employers in Washington State.",
            "source": "Washington State Department of Labor & Industries",
            "effective": "January 1, 2025"
        },
        "california": {
            "rate": 16.00,
            "currency": "$",
            "notes": "For employers with 26+ employees. $15.50 for smaller employers.",
            "source": "California Department of Industrial Relations",
            "effective": "January 1, 2025"
        },
        "new york": {
            "rate": 16.00,
            "currency": "$",
            "notes": "NYC, Long Island, and Westchester County. $15.00 for the rest of the state.",
            "source": "New York State Department of Labor",
            "effective": "January 1, 2025"
        },
        "federal": {
            "rate": 7.25,
            "currency": "$",
            "notes": "Federal minimum wage in the United States.",
            "source": "U.S. Department of Labor",
            "effective": "July 24, 2009"
        }
    }
    
    # Default to federal minimum wage if no location match
    wage_info = min_wage_db.get("federal")
    location_name = "United States (Federal)"
    
    # Normalize location name for matching
    if location:
        location = location.lower().strip()
        # Remove common words that might interfere with matching
        for word in ["city", "of", "the", "state", "county"]:
            location = location.replace(f" {word} ", " ").strip()
        
        # Check for matches in our database
        for loc_key, loc_data in min_wage_db.items():
            if loc_key in location or location in loc_key:
                wage_info = loc_data
                location_name = loc_key.title()
                break
    
    # Create a properly formatted response without HTML tags
    response = f"""### Current Minimum Wage for {location_name}

The current minimum hourly wage rate is **{wage_info['currency']}{wage_info['rate']:.2f}**.

**Additional Information:**
- For large employers (501+ employees). Small employers must pay ${17.25} or provide ${3.25}/hour in medical benefits.
- Effective date: {wage_info['effective']}
- Source: {wage_info['source']}

*Note: Minimum wage rates are subject to change. Always check with the official labor department for the most up-to-date information.*
"""
    return response

def general_response():
    """Create a general response for other queries"""
    return """
    I'm your AI recruiting assistant. I can help you with:
    
    - **Job Descriptions**: Drafting or refining job postings
    - **Screening Questions**: Creating effective candidate screening questions
    - **Interview Questions**: Developing role-specific interview questions
    - **Resume Analysis**: Reviewing candidate resumes and providing insights
    - **Candidate Assessments**: Designing technical or skill-based assessments
    - **Minimum Wage Information**: Current minimum wage rates by location
    
    Let me know what specific recruiting task you'd like assistance with!
    """
