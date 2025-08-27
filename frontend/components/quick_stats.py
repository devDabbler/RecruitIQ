import streamlit as st

def quick_stats_row():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if display_quick_stat_clickable("📝 Tasks", "5", "3 due today", "tasks"):
            # Navigate to tasks page (we'll create this)
            st.session_state.current_page = "tasks_page"
            st.rerun()
    with col2:
        if display_quick_stat_clickable("🗓️ Interviews", "8", "2 today", "interviews"):
            # Navigate to interviews page (we'll create this)
            st.session_state.current_page = "interviews_page"
            st.rerun()
    with col3:
        if display_quick_stat_clickable("👤 Candidates", "12", "4 new", "candidates"):
            # Navigate to candidates page (already exists)
            st.session_state.current_page = "candidates"
            st.rerun()
    with col4:
        if display_quick_stat_clickable("🚀 Jobs", "7", "3 active", "jobs"):
            # Navigate to jobs page (already exists)
            st.session_state.current_page = "jobs"
            st.rerun()

def display_quick_stat(label, value, subtitle):
    st.markdown(f"### {label}")
    st.markdown(f"<span style='font-size:2em'>{value}</span>", unsafe_allow_html=True)
    st.caption(subtitle)

def display_quick_stat_clickable(label, value, subtitle, component_id):
    """Creates a clickable stat card that returns True when clicked"""
    # Extract the emoji and text
    emoji = label.split()[0]
    text = label.split(' ', 1)[1] if ' ' in label else label
    
    # Create a container with hover effect for the entire clickable area
    container = st.container()
    with container:
        # Use a button styled as a link/card with a unique key incorporating component_id
        clicked = st.button(
            f"### {emoji} {text}\n\n**{value}**\n\n{subtitle}",
            key=f"quickstat_{component_id}_{text.lower()}",
            use_container_width=True
        )
        
        # Add hover styling
        st.markdown("""
        <style>
        div[data-testid="stButton"] > button:hover {
            background-color: rgba(0,0,0,0.05);
            cursor: pointer;
            transition: background-color 0.3s;
        }
        div[data-testid="stButton"] > button {
            background-color: transparent;
            color: inherit;
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            height: auto;
        }
        </style>
        """, unsafe_allow_html=True)
    
    return clicked
