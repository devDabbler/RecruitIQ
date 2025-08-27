import streamlit as st
import pandas as pd
import requests
import json
import os
import datetime
import logging
import time
from typing import Dict, Any, List, Optional
from functools import lru_cache

def delete_job_api(job_id):
    """Delete a job via the backend API."""
    api_url = st.session_state.get("api_url", "http://localhost:8000")
    
    # Ensure we have the correct API URL format
    if not api_url.endswith('/api'):
        api_url = f"{api_url}/api"
    
    try:
        response = requests.delete(f"{api_url}/jobs/{job_id}", timeout=10)
        response.raise_for_status()
        return True, response.json().get("message", "Job deleted.")
    except Exception as e:
        return False, f"Error deleting job: {str(e)}"
