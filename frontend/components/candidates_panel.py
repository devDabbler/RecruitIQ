import streamlit as st

import streamlit as st
import httpx

def _parse_match_score(candidate):
    # Try to get a match score as a percentage string, fallback to demo
    score = candidate.get('match_score')
    if score is not None:
        try:
            pct = int(float(score) * 100)
            return f"{pct}%"
        except Exception:
            pass
    return candidate.get('matches', "-")

async def fetch_candidates(api_url):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/candidates?page_size=10")
            response.raise_for_status()
            data = response.json()
            candidates = data.get("results", data) if isinstance(data, dict) else data
            return candidates
    except Exception as e:
        st.error(f"Error fetching candidates: {str(e)}")
        return None

def candidates_panel():
    st.subheader("👥 Candidates to Review")
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    candidates = None
    with st.spinner("Loading candidates from backend..."):
        try:
            candidates = st.experimental_async(fetch_candidates)(api_url)
            if hasattr(candidates, "send"):
                candidates = st.run(candidates)
        except Exception as e:
            candidates = None
    if candidates is None:
        st.warning("Showing demo data. Backend candidates API unavailable.")
        candidates = [
            {"id": "c1", "name": "Alex Thompson", "position": "Full Stack Developer", "matches": "92%", "status": "New Application"},
            {"id": "c2", "name": "Priya Patel", "position": "Data Engineer", "matches": "88%", "status": "Technical Round"},
            {"id": "c3", "name": "James Wilson", "position": "Product Manager", "matches": "85%", "status": "References"},
            {"id": "c4", "name": "Linda Martinez", "position": "Marketing Specialist", "matches": "78%", "status": "New Application"}
        ]
    for i, candidate in enumerate(candidates):
        # Ensure we have a unique identifier for each candidate
        candidate_id = candidate.get('id', f"candidate_{i}")
        name = candidate.get('name') or f"{candidate.get('first_name','')} {candidate.get('last_name','')}".strip() or "Unknown"
        st.markdown(f"**{name}**")
        col1, col2 = st.columns(2)
        with col1:
            # Display current job position with more prominence
            current_job = candidate.get('current_position', '-')
            if current_job != '-':
                st.markdown(f"**🏢 {current_job}**")
            else:
                st.caption(f"{candidate.get('position_applied', '-')}")
        with col2:
            st.caption(f"Match: {_parse_match_score(candidate)}")
        try:
            pct = int(_parse_match_score(candidate).strip('%')) / 100
        except Exception:
            pct = 0.5
        st.progress(pct)
        st.caption(f"Status: {candidate.get('status', '-')}")
        btn1, btn2, btn3 = st.columns([1, 1, 2])
        with btn1:
            st.button("👍", key=f"approve_panel_{candidate_id}_{i}")
        with btn2:
            st.button("👎", key=f"reject_panel_{candidate_id}_{i}")
        with btn3:
            st.button("🔍 Review", key=f"review_panel_{candidate_id}_{i}")
        st.divider()
