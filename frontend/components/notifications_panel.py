import streamlit as st
from datetime import datetime, timedelta
from frontend.utils.session_utils import get_user_tier
import asyncio

def notifications_panel():
    st.subheader("🔔 Recent Notifications")
    tier = get_user_tier()
    # --- TODO: Replace demo data with async API call when backend is ready ---
    async def fetch_notifications(api_url):
        # TODO: Implement real backend call here
        await asyncio.sleep(0.1)
        return None  # Return None to simulate backend unavailable
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    notifications = None
    with st.spinner("Loading notifications from backend..."):
        try:
            notifications = st.experimental_async(fetch_notifications)(api_url)
            if hasattr(notifications, "send"):
                notifications = st.run(notifications)
        except Exception as e:
            notifications = None
    if notifications is None:
        st.warning("Showing demo data. Backend notifications API unavailable.")
        notifications = [
            {"message": "Emma Johnson accepted the offer for Senior Data Scientist", "time": "10 minutes ago"},
            {"message": "New application received for Frontend Developer position", "time": "1 hour ago"},
            {"message": "Interview feedback submitted by Tech Lead for Michael Chen", "time": "3 hours ago"}
        ]
    for notification in notifications:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{notification['message']}**")
        with col2:
            st.caption(f"{notification['time']}")
        if tier == "basic":
            st.caption(":lock: Premium feature: Notification history and insights only available for premium users.")
            st.button("Upgrade to Premium", key=f"upgrade_{notification['message']}")
        st.divider()
    # --- END TODO ---
