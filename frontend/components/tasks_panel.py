import streamlit as st
from datetime import datetime

from utils.session_utils import get_user_tier
import asyncio

def tasks_panel():
    st.subheader("📋 Today's Tasks")
    tier = get_user_tier()
    # --- TODO: Replace demo data with async API call when backend is ready ---
    async def fetch_tasks(api_url):
        # TODO: Implement real backend call here
        await asyncio.sleep(0.1)
        return None  # Return None to simulate backend unavailable
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    tasks = None
    with st.spinner("Loading tasks from backend..."):
        try:
            tasks = st.experimental_async(fetch_tasks)(api_url)
            if hasattr(tasks, "send"):
                tasks = st.run(tasks)
        except Exception as e:
            tasks = None
    if tasks is None:
        st.warning("Showing demo data. Backend tasks API unavailable.")
        tasks = [
            {"title": "Review resume for Software Engineer position", "priority": "High", "due": "Today, 2PM"},
            {"title": "Schedule final interview with John Smith", "priority": "High", "due": "Today, 5PM"},
            {"title": "Provide feedback on Marketing Manager candidates", "priority": "Medium", "due": "Today, EOD"},
            {"title": "Update job description for Product Manager", "priority": "Low", "due": "Tomorrow"},
            {"title": "Check references for DevOps Engineer candidate", "priority": "Medium", "due": "Tomorrow"}
        ]
    today = datetime.now().strftime("%A, %B %d")
    st.markdown(f"**{today}**")
    for task in tasks:
        col1, col2 = st.columns([4, 1])
        priority_color = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
        with col1:
            st.markdown(f"**{task['title']}**")
            st.caption(f"Due: {task['due']}")
        with col2:
            st.markdown(f"{priority_color[task['priority']]} {task['priority']}")
        if tier == "basic":
            st.caption(":lock: Premium feature: Task analytics and reminders only available for premium users.")
            st.button("Upgrade to Premium", key=f"upgrade_{task['title']}")
        st.divider()
    # --- END TODO ---
