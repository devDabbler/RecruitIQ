"""
Enhanced matching module for the Recruiter Dashboard.
Provides improved UI for job-candidate matching with detailed explanations.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import json
from utils.ui_helpers import display_skills_badges, format_skills_list

def page():
    """Display the enhanced matching page in the Streamlit application."""
    # st.title("✨ Advanced Matching")  # Removed duplicate header
    
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

    tab1, tab2, tab3 = st.tabs(["Match Candidates to Jobs", "Match Jobs to Candidates", "Find Similar Jobs"])
    
    with tab1:
        match_candidates_to_jobs()
    
    with tab2:
        match_jobs_to_candidates()
    
    with tab3:
        find_similar_jobs()

def match_candidates_to_jobs():
    """Interface for finding candidates that match a job."""
    st.header("Find Best Matching Candidates")
    
    # Get list of jobs
    try:
        response = requests.get("http://localhost:8000/api/jobs")
        if response.status_code == 200:
            jobs = response.json().get("results", [])
            job_options = {f"{job['id']}: {job['title']}": job['id'] for job in jobs}
            
            # Job selection
            selected_job_option = st.selectbox(
                "Select a job to find matching candidates",
                options=list(job_options.keys())
            )
            
            if selected_job_option:
                job_id = job_options[selected_job_option]
                min_score = st.slider("Minimum match score", 0, 100, 30, key="enhanced_match_candidates_min_score")
                
                if st.button("Find Matching Candidates"):
                    st.info("Searching for candidates that match this job...")
                    
                    # Call the enhanced matching API
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/enhanced-matching/match-candidates",
                            json={"job_ids": [job_id], "min_score": min_score}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            candidates = data.get("candidates", [])
                            
                            if candidates:
                                st.success(f"Found {len(candidates)} matching candidates!")
                                
                                # Create visualization of match scores
                                score_data = pd.DataFrame([
                                    {
                                        "Candidate": c["name"],
                                        "Overall Match": c["match_score"],
                                        "Skills Match": c.get("skill_match_score", 0),
                                        "Role Match": c.get("role_match_score", 0),
                                        "Experience Match": c.get("experience_match_score", 0)
                                    }
                                    for c in candidates
                                ])
                                
                                # Plot horizontal bar chart of overall scores
                                fig = px.bar(
                                    score_data.sort_values("Overall Match", ascending=True),
                                    y="Candidate",
                                    x="Overall Match",
                                    title="Candidate Match Scores",
                                    orientation='h',
                                    color="Overall Match",
                                    color_continuous_scale="viridis",
                                    range_color=[0, 100]
                                )
                                st.plotly_chart(fig)
                                
                                # Show detailed breakdown
                                st.subheader("Match Score Components")
                                component_data = pd.melt(
                                    score_data, 
                                    id_vars=['Candidate'], 
                                    value_vars=['Skills Match', 'Role Match', 'Experience Match'],
                                    var_name='Component', 
                                    value_name='Score'
                                )
                                
                                fig2 = px.bar(
                                    component_data,
                                    x="Candidate",
                                    y="Score",
                                    color="Component",
                                    barmode="group",
                                    title="Match Score Components"
                                )
                                st.plotly_chart(fig2)
                                
                                # Display detailed candidate information
                                for candidate in candidates:
                                    with st.expander(f"{candidate['name']} - Score: {candidate['match_score']:.1f}%"):
                                        st.write("**Match Explanation:**")
                                        st.write(candidate["match_explanation"])
                                        
                                        # Two columns for details
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.write("**Position:**", candidate.get("position", "N/A"))
                                            st.write("**Experience Level:**", candidate.get("experience_level", "N/A"))
                                            st.write("**Years Experience:**", candidate.get("years_experience", "N/A"))
                                        
                                        with col2:
                                            st.write("**Skills:**")
                                            skills = candidate.get("skills", [])
                                            if skills:
                                                # Use the safe skills display function
                                                display_skills_badges(skills, max_per_row=3, badge_style="compact")
                                            else:
                                                st.write("No skills listed")
                            else:
                                st.warning("No matching candidates found. Try lowering the minimum match score.")
                        else:
                            st.error(f"Error: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"Error calling matching API: {str(e)}")
        else:
            st.error(f"Error fetching jobs: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error connecting to backend: {str(e)}")

def match_jobs_to_candidates():
    """Interface for finding jobs that match a candidate."""
    st.header("Find Best Matching Jobs")
    
    # Get list of candidates
    try:
        response = requests.get("http://localhost:8000/api/candidates")
        if response.status_code == 200:
            candidates = response.json().get("results", [])
            
            # Create a more detailed candidate selection interface
            st.subheader("Select a Candidate")
            
            # Create a grid layout for candidate cards
            col1, col2 = st.columns(2)
            
            # Display candidate cards in a grid
            selected_candidate_id = None
            
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
                    'location': c.get('location', 'Location not specified')
                }
                processed_candidates.append(candidate_info)
            
            # Create a filter for easier candidate finding
            search_term = st.text_input("Search candidates by name, skills, or position:", 
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
            
            # Display candidates in a more appealing format
            if not display_candidates:
                st.warning("No candidates found matching your search criteria.")
            else:
                # Use radio buttons in a custom container to select candidates
                candidate_radio_options = {c['name']: c['id'] for c in display_candidates}
                
                # Add a placeholder option to avoid auto-selection
                if 'selected_candidate' not in st.session_state:
                    st.session_state.selected_candidate = ""
                
                # Create custom candidate cards in a radio button group
                selected_candidate_id = st.radio(
                    "Choose a candidate:",
                    options=list(candidate_radio_options.keys()),
                    key="candidate_selector",
                    index=0 if display_candidates else None,
                    label_visibility="collapsed"
                )
                
                if selected_candidate_id:
                    # Get the ID of the selected candidate
                    candidate_id = candidate_radio_options[selected_candidate_id]
                    
                    # Find the corresponding candidate data
                    selected_candidate_data = next((c for c in display_candidates if c['id'] == candidate_id), None)
                    
                    # Display detailed information about the selected candidate
                    if selected_candidate_data:
                        st.markdown("---")
                        st.subheader("Selected Candidate")
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.markdown(f"### {selected_candidate_data['name']}")
                            st.markdown(f"**Position:** {selected_candidate_data['position']}")
                            if selected_candidate_data['company']:
                                st.markdown(f"**Company:** {selected_candidate_data['company']}")
                            st.markdown(f"**Location:** {selected_candidate_data['location']}")
                            st.markdown(f"**Experience:** {selected_candidate_data['experience_years']}")
                        
                        with col2:
                            st.markdown("**Contact:**")
                            st.markdown(f"📧 {selected_candidate_data['email']}")
                        
                        # Display skills in a nicer format
                        if selected_candidate_data['skills']:
                            st.markdown("**Skills:**")
                            # Format skills safely before displaying
                            formatted_skills = format_skills_list(selected_candidate_data['skills'])
                            if formatted_skills:
                                # Use the safe skills display function
                                display_skills_badges(formatted_skills, max_per_row=3, badge_style="compact")
                            else:
                                st.caption("No valid skills found.")
            
            # If a candidate is selected, show the minimum score slider and search button
            if selected_candidate_id:
                st.markdown("---")
                min_score = st.slider("Minimum match score", 0, 100, 30, key="enhanced_match_jobs_min_score")
                
                if st.button("Find Matching Jobs"):
                    st.info("Searching for jobs that match this candidate...")
                    
                    # Call the enhanced matching API
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/enhanced-matching/match-jobs",
                            json={"candidate_id": candidate_id, "min_score": min_score}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            jobs = data.get("jobs", [])
                            
                            if jobs:
                                st.success(f"Found {len(jobs)} matching jobs!")
                                
                                # Create visualization of match scores
                                score_data = pd.DataFrame([
                                    {
                                        "Job": j["title"],
                                        "Overall Match": j["match_score"],
                                        "Skills Match": j.get("skill_match_score", 0),
                                        "Role Match": j.get("role_match_score", 0),
                                        "Experience Match": j.get("experience_match_score", 0)
                                    }
                                    for j in jobs
                                ])
                                
                                # Plot horizontal bar chart of overall scores
                                fig = px.bar(
                                    score_data.sort_values("Overall Match", ascending=True),
                                    y="Job",
                                    x="Overall Match",
                                    title="Job Match Scores",
                                    orientation='h',
                                    color="Overall Match",
                                    color_continuous_scale="viridis",
                                    range_color=[0, 100]
                                )
                                st.plotly_chart(fig)
                                
                                # Show detailed breakdown
                                st.subheader("Match Score Components")
                                component_data = pd.melt(
                                    score_data, 
                                    id_vars=['Job'], 
                                    value_vars=['Skills Match', 'Role Match', 'Experience Match'],
                                    var_name='Component', 
                                    value_name='Score'
                                )
                                
                                fig2 = px.bar(
                                    component_data,
                                    x="Job",
                                    y="Score",
                                    color="Component",
                                    barmode="group",
                                    title="Match Score Components"
                                )
                                st.plotly_chart(fig2)
                                
                                # Display detailed job information
                                for job in jobs:
                                    with st.expander(f"{job['title']} - Score: {job['match_score']:.1f}%"):
                                        st.write("**Match Explanation:**")
                                        st.write(job["match_explanation"])
                                        
                                        # Two columns for details
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.write("**Department:**", job.get("department", "N/A"))
                                            st.write("**Location:**", job.get("location", "N/A"))
                                        
                                        with col2:
                                            st.write("**Skills:**")
                                            skills = job.get("skills", [])
                                            if skills:
                                                # Format skills safely
                                                formatted_skills = format_skills_list(skills)
                                                if formatted_skills:
                                                    st.write(", ".join(formatted_skills))
                                                else:
                                                    st.write("No valid skills found")
                                            else:
                                                st.write("No skills listed")
                                                
                                        if job.get("description"):
                                            # Replace the nested expander with a different UI pattern
                                            st.write("**Description:**")
                                            st.markdown(
                                                f"""<details>
                                                <summary>Click to view full description</summary>
                                                <div style="padding: 10px; border-left: 2px solid #ccc;">
                                                {job["description"]}
                                                </div>
                                                </details>""", 
                                                unsafe_allow_html=True
                                            )
                            else:
                                st.warning("No matching jobs found. Try lowering the minimum match score.")
                        else:
                            st.error(f"Error: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"Error calling matching API: {str(e)}")
        else:
            st.error(f"Error fetching candidates: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error connecting to backend: {str(e)}")

def find_similar_jobs():
    """Interface for finding similar jobs."""
    st.header("Find Similar Jobs")
    
    # Get list of jobs
    try:
        response = requests.get("http://localhost:8000/api/jobs")
        if response.status_code == 200:
            jobs = response.json().get("results", [])
            job_options = {f"{job['id']}: {job['title']}": job['id'] for job in jobs}
            
            # Job selection
            selected_job_option = st.selectbox(
                "Select a job to find similar jobs",
                options=list(job_options.keys())
            )
            
            if selected_job_option:
                job_id = job_options[selected_job_option]
                limit = st.slider("Number of similar jobs to find", 1, 10, 5)
                
                if st.button("Find Similar Jobs"):
                    st.info("Searching for similar jobs...")
                    
                    # Call the enhanced matching API
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/enhanced-matching/similar-jobs",
                            json={"job_id": job_id, "limit": limit}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            similar_jobs = data.get("similar_jobs", [])
                            
                            if similar_jobs:
                                st.success(f"Found {len(similar_jobs)} similar jobs!")
                                
                                # Create visualization of similarity scores
                                score_data = pd.DataFrame([
                                    {
                                        "Job": j["title"],
                                        "Similarity Score": j["similarity_score"]
                                    }
                                    for j in similar_jobs
                                ])
                                
                                # Plot horizontal bar chart of similarity scores
                                fig = px.bar(
                                    score_data.sort_values("Similarity Score", ascending=True),
                                    y="Job",
                                    x="Similarity Score",
                                    title="Job Similarity Scores",
                                    orientation='h',
                                    color="Similarity Score",
                                    color_continuous_scale="viridis",
                                    range_color=[0, 100]
                                )
                                st.plotly_chart(fig)
                                
                                # Display detailed job information
                                for job in similar_jobs:
                                    with st.expander(f"{job['title']} - Similarity: {job['similarity_score']:.1f}%"):
                                        st.write("**Similarity Explanation:**")
                                        st.write(job["similarity_explanation"])
                                        
                                        # Two columns for details
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.write("**Department:**", job.get("department", "N/A"))
                                            st.write("**Location:**", job.get("location", "N/A"))
                                        
                                        with col2:
                                            st.write("**Skills:**")
                                            skills = job.get("skills", [])
                                            if skills:
                                                # Format skills safely
                                                formatted_skills = format_skills_list(skills)
                                                if formatted_skills:
                                                    st.write(", ".join(formatted_skills))
                                                else:
                                                    st.write("No valid skills found")
                                            else:
                                                st.write("No skills listed")
                            else:
                                st.warning("No similar jobs found.")
                        else:
                            st.error(f"Error: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"Error calling matching API: {str(e)}")
        else:
            st.error(f"Error fetching jobs: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error connecting to backend: {str(e)}")

if __name__ == "__main__":
    enhanced_matching_tab()
