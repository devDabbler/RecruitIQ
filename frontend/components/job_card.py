import streamlit as st
import httpx
from collections import defaultdict

async def fetch_job_candidates(api_url, job_id):
    """Fetch candidates for a specific job"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/jobs/{job_id}/candidates")
            response.raise_for_status()
            return response.json()
    except Exception:
        return None

async def fetch_job_tasks(api_url, job_id):
    """Fetch tasks for a specific job"""
    try:
        # This would be a real endpoint in production
        # For now, simulate a task list
        await httpx.AsyncClient().get("https://httpbin.org/status/200", timeout=0.1)
        return None  # Return None to use demo data
    except Exception:
        return None

def get_recruiting_stages():
    """Get standard recruiting stages in order"""
    return [
        "New Application",
        "Resume Screening",
        "Shortlisted",
        "Recruiter Screen",
        "Interview 1",
        "Interview 2",
        "Interview 3",
        "Final Interview",
        "Offer Stage",
        "Background Check",
        "Hired",
        "Rejected",
        "Withdrawn"
    ]

def get_stage_emoji(stage):
    """Return emoji appropriate for the stage"""
    stage_emojis = {
        "New Application": "📥",
        "Resume Screening": "🔍",
        "Shortlisted": "✅",
        "Recruiter Screen": "📞",
        "Interview 1": "👤",
        "Interview 2": "👥",
        "Interview 3": "🤝",
        "Final Interview": "🌟",
        "Offer Stage": "📝",
        "Background Check": "🔎",
        "Hired": "🎉",
        "Rejected": "❌",
        "Withdrawn": "⏹️"
    }
    return stage_emojis.get(stage, "📋")

def render_candidate_card(candidate, job_id=None, idx=0):
    """Render a single candidate card with match score"""
    name = (candidate.get('name') or 
            f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or 
            "Unknown")
    
    # Try to get a match score as a percentage string
    match_score = candidate.get('match_score')
    if match_score is not None:
        try:
            pct = int(float(match_score) * 100)
            match_display = f"{pct}%"
        except:
            match_display = candidate.get('matches', "N/A")
    else:
        match_display = candidate.get('matches', "N/A")
    
    status = candidate.get('status', 'New Application')
    
    st.markdown(f"**{name}**")
    cols = st.columns([3, 1])
    with cols[0]:
        st.caption(f"{candidate.get('position', candidate.get('position_applied', 'Unknown Position'))}")
    with cols[1]:
        st.caption(f"Match: {match_display}")
    
    # Convert match score to progress bar percentage
    try:
        pct = int(match_display.strip('%')) / 100
    except:
        pct = 0.5
    
    st.progress(pct)
    st.caption(f"Status: {status}")
    
    # Create unique keys using job_id, candidate_id and index
    candidate_id = candidate.get('id', '')
    # Action buttons with unique keys
    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.button("👍", key=f"approve_job{job_id}_cand{candidate_id}_idx{idx}")
    with cols[1]:
        st.button("👎", key=f"reject_job{job_id}_cand{candidate_id}_idx{idx}")
    with cols[2]:
        if st.button("🔍 Review", key=f"review_job{job_id}_cand{candidate_id}_idx{idx}"):
            # In production, navigate to candidate detail view
            if candidate.get('id'):
                st.session_state.current_page = "candidate_detail"
                st.query_params["id"] = str(candidate.get('id'))
                st.query_params["view"] = "candidate_detail"
                st.rerun()

def render_task_card(task, job_id=None, idx=0):
    """Render a single task card"""
    priority_color = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
    
    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(f"**{task['title']}**")
        st.caption(f"Due: {task['due']}")
    with cols[1]:
        st.markdown(f"{priority_color[task['priority']]} {task['priority']}")
    
    st.divider()

def render_compact_candidate(candidate, job_id, stage, idx):
    """Render a compact view of candidate for the stages tab"""
    name = (candidate.get('name') or 
            f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or 
            "Unknown")
    
    # Try to get a match score as a percentage string
    match_score = candidate.get('match_score')
    if match_score is not None:
        try:
            pct = int(float(match_score) * 100)
            match_display = f"{pct}%"
        except:
            match_display = candidate.get('matches', "N/A")
    else:
        match_display = candidate.get('matches', "N/A")
    
    position = candidate.get('position', candidate.get('position_applied', 'Unknown Position'))
    
    # Use columns for a compact layout
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.markdown(f"**{name}**")
        st.caption(position)
    
    with col2:
        st.caption(f"Match: {match_display}")
    
    with col3:
        # Action button with unique key
        candidate_id = candidate.get('id', '')
        # Create a more unique key by including the stage and using name if no ID
        unique_id = candidate_id if candidate_id else name.replace(" ", "_")
        # Use a safer stage representation for the key
        safe_stage = stage.replace(" ", "_")
        button_key = f"view_stage{safe_stage}_cand{unique_id}_job{job_id}_idx{idx}"
        
        if st.button("View", key=button_key):
            if candidate_id:
                st.session_state.current_page = "candidate_detail"
                st.query_params["id"] = str(candidate_id)
                st.query_params["view"] = "candidate_detail"
                st.rerun()
    
    st.divider()

def render_stage_candidates(candidates, stage, job_id):
    """Render candidates for a specific stage"""
    stage_candidates = [c for c in candidates if c.get('stage', c.get('status', 'New Application')) == stage]
    
    if not stage_candidates:
        st.caption(f"No candidates in this stage")
        return
    
    for idx, candidate in enumerate(stage_candidates):
        render_compact_candidate(candidate, job_id, stage, idx)

def render_candidate_stages(candidates, job_id):
    """Render a visualization of candidates by stage"""
    if not candidates:
        st.info("No candidates found for this job")
        return
    
    # Count candidates by stage
    stages = get_recruiting_stages()
    stage_counts = defaultdict(int)
    
    for candidate in candidates:
        stage = candidate.get('stage', candidate.get('status', 'New Application'))
        stage_counts[stage] += 1
    
    # Create a horizontal bar chart of candidates by stage
    st.markdown("#### Candidates by Stage")
    
    # Create stage metrics
    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    
    for i, stage in enumerate(stages[:6]):  # Show first 6 stages in header metrics
        emoji = get_stage_emoji(stage)
        with cols[i % 3]:
            st.metric(f"{emoji} {stage}", stage_counts[stage])
    
    # Create a progress bar showing the hiring funnel
    st.markdown("##### Hiring Funnel")
    total_candidates = sum(stage_counts.values())
    if total_candidates > 0:
        for stage in stages:
            if stage_counts[stage] > 0:
                emoji = get_stage_emoji(stage)
                percent = stage_counts[stage] / total_candidates
                st.caption(f"{emoji} {stage}: {stage_counts[stage]} candidates")
                st.progress(percent)
    
    # Use tabs for detailed stage views (rather than nested expanders)
    st.markdown("##### Candidates by Stage")
    
    # Get stages that have candidates
    active_stages = [stage for stage in stages if stage_counts[stage] > 0]
    
    if active_stages:
        # Create tabs for each active stage
        stage_tabs = st.tabs([f"{get_stage_emoji(s)} {s} ({stage_counts[s]})" for s in active_stages])
        
        # Populate each tab with the candidates for that stage
        for i, stage in enumerate(active_stages):
            with stage_tabs[i]:
                render_stage_candidates(candidates, stage, job_id)
    else:
        st.info("No candidates in any stage")

def job_card(job, api_url):
    """Render an expandable job card with candidates and tasks"""
    # Demo candidate and task data (used when API fails)
    demo_candidates = [
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
    
    demo_tasks = [
        {"title": "Review resume for Software Engineer position", "priority": "High", "due": "Today, 2PM"},
        {"title": "Schedule final interview with John Smith", "priority": "High", "due": "Today, 5PM"},
        {"title": "Provide feedback on Marketing Manager candidates", "priority": "Medium", "due": "Today, EOD"},
        {"title": "Update job description for Product Manager", "priority": "Low", "due": "Tomorrow"}
    ]
    
    with st.expander(f"📋 {job.get('title', 'Unknown Job')} ({job.get('department', 'Dept')}) - {job.get('num_applicants', job.get('applicants', 0))} applicants"):
        # Job summary section
        st.markdown("#### Job Summary")
        job_cols = st.columns(3)
        with job_cols[0]:
            st.metric("Applicants", job.get('num_applicants', job.get('applicants', '-')))
        with job_cols[1]:
            st.metric("Views", job.get('num_views', job.get('views', '-')))
        with job_cols[2]:
            st.metric("Days Active", job.get('days_active', job.get('days', '-')))
        
        if job.get('location'):
            st.caption(f"Location: {job.get('location')}")
        
        # Quick action buttons for job
        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button("View Job", key=f"view_job_{job.get('id')}"):
                # Navigate to job detail page properly
                st.session_state.current_page = "job_detail"
                st.query_params.clear()
                st.query_params["view"] = "job_detail"
                st.query_params["id"] = str(job.get('id'))
                st.session_state.pop("view_handled", None)  # Reset to allow navigation
                st.rerun()
        with action_cols[1]:
            st.button("Edit Job", key=f"edit_job_{job.get('id')}")
        with action_cols[2]:
            st.button("Share Job", key=f"share_job_{job.get('id')}")
        
        st.divider()
        
        # Use tabs to organize content
        tab1, tab2, tab3 = st.tabs(["👥 Candidates", "📊 Stages", "📋 Tasks"])
        
        with tab1:
            st.markdown("#### Top Candidates (AI Ranked)")
            
            # Fetch candidates for this job
            candidates = None
            if job.get('id'):
                try:
                    candidates = st.experimental_async(fetch_job_candidates)(api_url, job.get('id'))
                    if hasattr(candidates, "send"):
                        candidates = st.run(candidates)
                except Exception:
                    candidates = None
            
            if not candidates:
                # Use demo data
                candidates = demo_candidates
            
            for idx, candidate in enumerate(candidates[:3]):  # Show top 3
                render_candidate_card(candidate, job.get('id'), idx)
            
            if len(candidates) > 3:
                if st.button(f"View all {len(candidates)} candidates", key=f"view_all_candidates_{job.get('id')}"):
                    # Navigate to job detail page or candidates view
                    st.session_state.current_page = "job_detail"
                    st.session_state.view_job_id = job.get('id')
                    st.rerun()
        
        with tab2:
            # Fetch candidates for this job (if not already fetched)
            candidates = None
            if job.get('id'):
                try:
                    candidates = st.experimental_async(fetch_job_candidates)(api_url, job.get('id'))
                    if hasattr(candidates, "send"):
                        candidates = st.run(candidates)
                except Exception:
                    candidates = None
            
            if not candidates:
                # Use demo data
                candidates = demo_candidates
            
            render_candidate_stages(candidates, job.get('id'))
        
        with tab3:
            st.markdown("#### Job Tasks")
            
            # Fetch tasks for this job
            tasks = None
            if job.get('id'):
                try:
                    tasks = st.experimental_async(fetch_job_tasks)(api_url, job.get('id'))
                    if hasattr(tasks, "send"):
                        tasks = st.run(tasks)
                except Exception:
                    tasks = None
            
            if not tasks:
                # Use demo data
                tasks = demo_tasks[:2]  # Just show 2 tasks per job
            
            for idx, task in enumerate(tasks):
                render_task_card(task, job.get('id'), idx)
            
            # Add task button
            st.button("+ Add Task", key=f"add_task_{job.get('id')}") 