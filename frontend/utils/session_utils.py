# frontend/utils/session_utils.py
import streamlit as st

def get_user_tier():
    """Returns the current user's subscription tier ('basic' or 'premium')."""
    # TODO: Replace with real API/profile call for user tier
    return st.session_state.get("user_tier", "basic")
