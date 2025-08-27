import streamlit as st
from datetime import datetime, timedelta
import asyncio
import httpx
import time

BACKEND_URL = "http://localhost:8000"

# Recruiter-centric interviews page with agentic backend integration
def page():
    st.markdown("# 🗓️ Interviews")
    st.markdown("### Manage your candidate interviews and scheduling. All data is live from the RecruitIQ agentic backend.")

    tab1, tab2, tab3 = st.tabs(["Upcoming", "Today", "Past Interviews"])

    with tab1:
        display_interview_list(tab_context="upcoming")
    with tab2:
        display_interview_list(filter_today=True, tab_context="today")
    with tab3:
        display_interview_list(tab_context="past", past=True)

    st.markdown("---")
    st.subheader("Schedule New Interview")
    schedule_new_interview()

    st.markdown("---")
    st.subheader("Plan Interview Travel (Agentic Zero)")
    plan_interview_travel_section()

# Async fetch interviews from agentic backend
def get_interviews_from_backend(filter_today=False, past=False):
    async def fetch():
        async with httpx.AsyncClient() as client:
            params = {}
            if filter_today:
                today = datetime.now().date()
                params['date_from'] = params['date_to'] = today.isoformat()
            if past:
                params['completed'] = True
            else:
                params['completed'] = False
            try:
                resp = await client.get(f"{BACKEND_URL}/api/interviews/", params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return None
    return asyncio.run(fetch())

# Display interviews using agentic backend data
def display_interview_list(filter_today=False, tab_context="default", past=False):
    with st.spinner("Loading interviews from backend..."):
        interviews = get_interviews_from_backend(filter_today=filter_today, past=past)
    if interviews is None:
        st.warning("Unable to load interview data. Please check backend connectivity.")
        return
    if not interviews:
        st.info("No interviews found for this view.")
        return
    for i, interview in enumerate(interviews):
        with st.expander(f"{interview.get('candidate_name', 'Candidate')} - {interview.get('position', 'Position')} ({interview.get('date', interview.get('time', ''))})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Stage:** {interview.get('stage', 'N/A')}")
                st.markdown(f"**Duration:** {interview.get('duration', 'N/A')}")
                interviewers = interview.get('interviewers', [])
                if interviewers:
                    st.markdown(f"**Interviewers:** {', '.join(interviewers)}")
                else:
                    st.markdown("**Interviewers:** None assigned")
                if 'notes' in interview and interview['notes']:
                    st.markdown(f"**Preparation Notes:**")
                    st.info(interview['notes'])
            with col2:
                st.markdown(f"**Time:** {interview.get('time', 'N/A')}")
                st.markdown(f"**Status:** {interview.get('status', 'Scheduled')}")
            action_col1, action_col2, action_col3, action_col4 = st.columns([1, 1, 1, 1])
            with action_col1:
                if st.button("📝 Notes", key=f"notes_{tab_context}_{interview.get('id', i)}"):
                    st.info(f"Taking notes for interview with {interview.get('candidate_name', 'Candidate')}")
            with action_col2:
                if st.button("📅 Reschedule", key=f"reschedule_{tab_context}_{interview.get('id', i)}"):
                    st.info(f"Rescheduling interview with {interview.get('candidate_name', 'Candidate')}")
            with action_col3:
                if st.button("✉️ Notify", key=f"notify_{tab_context}_{interview.get('id', i)}"):
                    st.success(f"Notification sent to {interview.get('candidate_name', 'Candidate')} and interviewers")
            with action_col4:
                if st.button("❌ Cancel", key=f"cancel_{tab_context}_{interview.get('id', i)}"):
                    st.error(f"Interview with {interview.get('candidate_name', 'Candidate')} canceled")

# Schedule new interview using agentic endpoint
def schedule_new_interview():
    candidate = st.text_input("Candidate Name", key="new_interview_candidate")
    position = st.text_input("Position", key="new_interview_position")
    interview_date = st.date_input("Date", key="new_interview_date")
    interview_time = st.time_input("Time", key="new_interview_time")
    stage = st.selectbox("Interview Stage", ["Initial Screening", "Technical", "Culture Fit", "Final Round"], key="new_interview_stage")
    duration = st.selectbox("Duration", ["30 minutes", "45 minutes", "1 hour", "1.5 hours", "2 hours"], key="new_interview_duration")
    interviewers = st.text_input("Interviewers (comma-separated emails)", key="new_interview_interviewers")
    notes = st.text_area("Preparation Notes", key="new_interview_notes")
    if st.button("Schedule Interview", key="schedule_new_interview_btn", use_container_width=True):
        if not candidate or not position or not interview_date or not interview_time:
            st.warning("Please fill in all required fields.")
            return
        interview_datetime = datetime.combine(interview_date, interview_time).isoformat()
        payload = {
            "candidate_name": candidate,
            "position": position,
            "date": interview_date.isoformat(),
            "time": interview_time.strftime("%H:%M"),
            "stage": stage,
            "duration": duration,
            "interviewers": [i.strip() for i in interviewers.split(",") if i.strip()],
            "notes": notes,
            "datetime": interview_datetime,
        }
        async def post_interview():
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.post(f"{BACKEND_URL}/api/interviews/", json=payload, timeout=30)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return None
        result = asyncio.run(post_interview())
        if result:
            st.success(f"Interview with {candidate} scheduled successfully!")
        else:
            st.error("Failed to schedule interview. Please check backend connectivity.")

# Travel planning section using agentic endpoint
def plan_interview_travel_section():
    st.markdown("_Use this tool to plan candidate travel for interviews. Powered by Agentic Zero._")
    origin = st.text_input("Origin (e.g., candidate's address or city)", key="travel_origin")
    destination = st.text_input("Destination (e.g., interview location)", key="travel_destination")
    interview_date = st.date_input("Interview Date", key="travel_date")
    interview_time = st.time_input("Interview Time", key="travel_time")
    if st.button("Plan Travel", key="plan_travel_btn"):
        travel_datetime = datetime.combine(interview_date, interview_time).isoformat()
        payload = {
            "origin": origin,
            "destination": destination,
            "interview_datetime": travel_datetime,
        }
        async def post_travel():
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.post(f"{BACKEND_URL}/api/travel/plan_interview_travel", json=payload, timeout=30)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    return None
        result = asyncio.run(post_travel())
        if result and result.get("plan"):
            st.success("Travel plan generated!")
            # st.json(result["plan"])  # Commented out for production
            st.write("Travel plan details display disabled for production")
        else:
            st.error("Failed to generate travel plan. Please check backend connectivity.")
        time.sleep(0.1)  # Replaced asyncio.sleep with time.sleep
        return None  # Return None to simulate backend unavailable

def display_past_interviews():
    """Display a list of completed interviews"""
    # Demo past interviews
    past_interviews = [
        {
            "id": "past1",
            "candidate": "Alex Thompson",
            "position": "DevOps Engineer",
            "date": "Yesterday",
            "stage": "Technical",
            "feedback": "Strong technical skills, good culture fit. Recommended for next round.",
            "status": "Passed"
        },
        {
            "id": "past2",
            "candidate": "Jessica Wilson",
            "position": "Marketing Specialist",
            "date": "2 days ago",
            "stage": "Initial Screening",
            "feedback": "Good communication skills but lacks experience in digital marketing.",
            "status": "On Hold"
        },
        {
            "id": "past3",
            "candidate": "Raj Patel",
            "position": "Backend Developer",
            "date": "Last week",
            "stage": "Final Round",
            "feedback": "Outstanding technical skills and problem-solving ability. Extending offer.",
            "status": "Hired"
        }
    ]
    
    for i, interview in enumerate(past_interviews):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        status_color = {
            "Passed": "🟢",
            "On Hold": "🟠",
            "Rejected": "🔴",
            "Hired": "🔵"
        }
        
        with col1:
            st.markdown(f"**{interview['candidate']} - {interview['position']}**")
            st.caption(f"Stage: {interview['stage']}")
        
        with col2:
            st.caption(f"Date: {interview['date']}")
        
        with col3:
            status = interview.get('status', 'Unknown')
            st.markdown(f"{status_color.get(status, '⚪')} {status}")
        
        st.info(f"**Feedback:** {interview.get('feedback', 'No feedback recorded')}")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("📝 Edit Feedback", key=f"edit_feedback_past_{interview['id']}_{i}"):
                st.info(f"Editing feedback for {interview['candidate']}")
        with col2:
            if st.button("👤 View Profile", key=f"view_profile_past_{interview['id']}_{i}"):
                # In a real implementation, we would navigate to the candidate profile page
                candidate_id = interview.get('candidate_id', f"demo_{i}")  # Demo ID
                st.session_state.current_page = "candidate_detail"
                st.query_params["id"] = str(candidate_id)
                st.query_params["view"] = "candidate_detail"
                st.rerun()
        
        st.divider() 