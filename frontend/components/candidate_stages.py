import streamlit as st
from collections import defaultdict

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

def stage_metric_row(stage_counts):
    """Create a row of metrics for the initial stages in the funnel"""
    stages = get_recruiting_stages()
    cols = st.columns(3)
    
    for i, stage in enumerate(stages[:6]):  # Show first 6 stages
        emoji = get_stage_emoji(stage)
        with cols[i % 3]:
            st.metric(f"{emoji} {stage}", stage_counts[stage])

def candidate_funnel(candidates):
    """Display a visualization of the recruitment funnel"""
    if not candidates:
        st.info("No candidates available for funnel visualization")
        return
    
    stages = get_recruiting_stages()
    stage_counts = defaultdict(int)
    
    # Count candidates by stage
    for candidate in candidates:
        stage = candidate.get('stage', candidate.get('status', 'New Application'))
        stage_counts[stage] += 1
    
    # Display metrics for key stages
    st.markdown("### Candidate Pipeline")
    stage_metric_row(stage_counts)
    
    # Create a progress bar visualization of the funnel
    st.markdown("### Hiring Funnel")
    total_candidates = sum(stage_counts.values())
    
    if total_candidates > 0:
        for stage in stages:
            count = stage_counts[stage]
            if count > 0:
                emoji = get_stage_emoji(stage)
                percent = count / total_candidates
                st.caption(f"{emoji} {stage}: {count} candidates ({percent:.1%})")
                st.progress(percent)
    else:
        st.info("No candidates in the pipeline")
    
    # Display stage-specific information
    with st.expander("View all stages"):
        st.markdown("### All Stages")
        
        # Create a table of all stages and counts
        data = {"Stage": [], "Count": [], "Percentage": []}
        
        for stage in stages:
            count = stage_counts[stage]
            percentage = f"{(count / total_candidates) * 100:.1f}%" if total_candidates > 0 else "0%"
            
            data["Stage"].append(f"{get_stage_emoji(stage)} {stage}")
            data["Count"].append(count)
            data["Percentage"].append(percentage)
        
        st.dataframe(data)

def candidate_stages_panel(candidates=None):
    """Main component for displaying candidate stages"""
    if candidates is None:
        # Demo data
        candidates = [
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
    
    st.subheader("Candidate Pipeline Overview")
    candidate_funnel(candidates)
    
    # Display candidates by stage in expandable sections
    st.markdown("### Candidates by Stage")
    
    stages = get_recruiting_stages()
    for stage in stages:
        stage_candidates = [c for c in candidates if c.get('stage', c.get('status', 'New Application')) == stage]
        
        if stage_candidates:
            emoji = get_stage_emoji(stage)
            with st.expander(f"{emoji} {stage} ({len(stage_candidates)} candidates)"):
                for candidate in stage_candidates:
                    name = candidate.get('name') or f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}"
                    position = candidate.get('position', candidate.get('position_applied', 'Unknown Position'))
                    
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.markdown(f"**{name}**")
                        st.caption(position)
                    with col2:
                        match = candidate.get('matches', candidate.get('match_score', 'N/A'))
                        if isinstance(match, float):
                            match = f"{int(match * 100)}%"
                        st.caption(f"Match: {match}")
                    with col3:
                        st.button("View", key=f"view_{stage}_{candidate.get('id', name)}")
                    
                    st.divider() 