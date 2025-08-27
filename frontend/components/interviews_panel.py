import streamlit as st
from datetime import datetime, timedelta
from utils.session_utils import get_user_tier
import asyncio

def interviews_panel():
    st.subheader("🗓️ Upcoming Interviews")
    tier = get_user_tier()
    # --- TODO: Replace demo data with async API call when backend is ready ---
    async def fetch_interviews(api_url):
        # TODO: Implement real backend call here
        await asyncio.sleep(0.1)
        return None  # Return None to simulate backend unavailable
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    interviews = None
    with st.spinner("Loading interviews from backend..."):
        try:
            interviews = st.experimental_async(fetch_interviews)(api_url)
            if hasattr(interviews, "send"):
                interviews = st.run(interviews)
        except Exception as e:
            interviews = None
    if interviews is None:
        st.warning("Showing demo data. Backend interviews API unavailable.")
        interviews = [
            {"candidate": "Emma Johnson", "position": "Senior Data Scientist", "time": "Today, 11:30 AM", "stage": "Technical"},
            {"candidate": "Michael Chen", "position": "Frontend Developer", "time": "Today, 3:00 PM", "stage": "Final"},
            {"candidate": "Sophia Rodriguez", "position": "UX Designer", "time": "Tomorrow, 10:00 AM", "stage": "Portfolio Review"},
            {"candidate": "David Kim", "position": "Product Manager", "time": "Tomorrow, 2:30 PM", "stage": "First Round"}
        ]
    for interview in interviews:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(f"**{interview['candidate']}**")
            st.caption(f"{interview['position']}")
        with col2:
            st.markdown(f"**{interview['time']}**")
        with col3:
            st.markdown(f"**{interview['stage']}**")
        btn1, btn2, btn3 = st.columns([1, 1, 3])
        with btn1:
            st.button("📝 Notes", key=f"notes_{interview['candidate']}")
        with btn2:
            st.button("🔍 View", key=f"view_{interview['candidate']}")
        if tier == "basic":
            st.caption(":lock: Premium feature: Interview analytics and feedback only available for premium users.")
            st.button("Upgrade to Premium", key=f"upgrade_{interview['candidate']}")
        st.divider()
    # --- END TODO ---
