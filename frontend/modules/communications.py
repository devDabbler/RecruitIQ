# frontend/modules/communications.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def page():
    """Communications page content"""
    # st.title("Communications")  # Removed duplicate header

    # Create tabs for different communication functionalities
    tab1, tab2, tab3, tab4 = st.tabs(["Messages", "Email Templates", "Communication History", "Saved Pitches"])
    
    with tab1:
        messages_dashboard()
    
    with tab2:
        email_templates()
    
    with tab3:
        communication_history()
        
    with tab4:
        saved_pitches()

def saved_pitches():
    """Display a list of saved candidate pitches for the current user."""
    st.subheader("Saved Candidate Pitches")
    
    # Sample data for saved pitches
    sample_pitches = [
        {
            "title": "Pitch for Senior Software Engineer at Innovate Inc.",
            "content": "Hi [Candidate Name], I came across your profile and was very impressed with your experience in Python and cloud technologies. At Innovate Inc., we're working on some groundbreaking projects, and I think your skills would be a perfect match for our Senior Software Engineer role. Would you be open to a brief chat next week to discuss how you could contribute to our team and how we can help you advance your career?",
            "created_at": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "title": "Data Scientist opportunity at DataDriven Co.",
            "content": "Hello [Candidate Name], Your extensive background in machine learning and data analysis caught my eye. We have an exciting opportunity for a Data Scientist at DataDriven Co. where you'll be able to work with large datasets and cutting-edge algorithms to solve real-world problems. This role offers a competitive salary, great benefits, and a chance to make a significant impact. Let me know if you're interested in learning more.",
            "created_at": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

    # You can attempt to fetch real data and fallback to sample data
    # For this example, we'll just display the sample data.
    if not sample_pitches:
        st.info("No saved pitches yet. Create your first pitch!")
    else:
        for pitch in sample_pitches:
            with st.container():
                st.markdown(f"**{pitch.get('title', 'Untitled')}**")
                st.markdown(f"<small style='color:gray'>Saved: {pitch.get('created_at', 'N/A')}</small>", unsafe_allow_html=True)
                st.markdown(f"<div style='background-color:#f9f9f9; border-left: 5px solid #ccc; padding: 10px; margin-top: 5px;'>{pitch.get('content','')}</div>", unsafe_allow_html=True)
                st.button("Use Pitch", key=f"use_{pitch['title']}")


def messages_dashboard():
    """Show candidate messages and allow for new messages."""
    st.subheader("Direct & Automated Messaging")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.write("**Conversations**")
        
        # Sample conversations
        candidates = ["Alice Johnson", "Bob Williams", "Charlie Brown", "Diana Miller"]
        selected_candidate = st.radio("Select a candidate:", candidates, label_visibility="collapsed")

    with col2:
        st.write(f"**Chat with {selected_candidate}**")
        
        # Messaging platform options
        st.radio("Platform:", ["Email", "SMS", "WhatsApp"], horizontal=True)

        # Sample chat history
        message_history = [
            {"sender": "Recruiter", "message": "Hi, is this a good time to talk about the role?", "time": "10:30 AM"},
            {"sender": selected_candidate, "message": "Yes, I have a few minutes now.", "time": "10:31 AM"},
            {"sender": "Recruiter", "message": "Great! I wanted to follow up on your application for the Product Manager position.", "time": "10:32 AM"}
        ]

        for msg in message_history:
            if msg["sender"] == "Recruiter":
                st.markdown(f"<div style='text-align: right; margin-bottom: 5px;'><span style='background-color: #dcf8c6; padding: 8px; border-radius: 7px;'>{msg['message']}</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: left; margin-bottom: 5px;'><span style='background-color: #fff; padding: 8px; border-radius: 7px;'>{msg['message']}</span></div>", unsafe_allow_html=True)

        st.text_input("Your message:", placeholder="Type your message here...")
        st.button("Send", use_container_width=True)


def email_templates():
    """Email template management."""
    st.subheader("Email Templates")
    
    # Sample email templates
    templates = {
        "Initial Outreach": {
            "subject": "Opportunity at [Company Name]",
            "body": "Hi [Candidate Name],\n\nI hope this email finds you well. I came across your profile and was impressed by your experience. We have an opening for a [Job Title] role that seems to align with your skills. Would you be open to a brief chat sometime this week?\n\nBest regards,\n[Your Name]"
        },
        "Interview Invitation": {
            "subject": "Interview Invitation for [Job Title] at [Company Name]",
            "body": "Dear [Candidate Name],\n\nThank you for your interest in the [Job Title] position. We would like to invite you for an interview to discuss your application further. Please let us know what time works best for you.\n\nSincerely,\n[Your Name]"
        },
        "Rejection": {
            "subject": "Update on your application for [Job Title]",
            "body": "Dear [Candidate Name],\n\nThank you for your time and interest. After careful consideration, we have decided to move forward with other candidates. We wish you the best in your job search.\n\nRegards,\n[Your Name]"
        }
    }

    template_name = st.selectbox("Select a template:", list(templates.keys()))
    
    if template_name:
        template = templates[template_name]
        st.text_input("Subject", template["subject"])
        st.text_area("Body", template["body"], height=200)

    st.button("Use Template", use_container_width=True)
    st.button("Create New Template", use_container_width=True)


def communication_history():
    """Display communication history with candidates."""
    st.subheader("Communication History")

    # Sample data for communication history
    data = {
        "Date": [datetime.now() - timedelta(days=i) for i in range(5)],
        "Candidate": ["John Doe", "Jane Smith", "Peter Jones", "Mary Brown", "Chris Green"],
        "Type": ["Email", "SMS", "Email", "WhatsApp", "Email"],
        "Subject/Preview": [
            "Re: Interview Schedule",
            "Quick question about your availability...",
            "Your application for Software Engineer",
            "Following up on our conversation.",
            "Job offer from Acme Corp"
        ],
        "Status": ["Opened", "Delivered", "Sent", "Read", "Replied"]
    }
    df = pd.DataFrame(data)

    # Displaying the dataframe as a table
    st.dataframe(df, use_container_width=True)
    st.button("Export History", use_container_width=True)
