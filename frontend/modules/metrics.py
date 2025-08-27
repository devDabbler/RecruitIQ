# frontend/modules/metrics.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

def page():
    """Metrics and Analytics page content"""
    # st.title("Recruitment Analytics")  # Removed duplicate header
    
    # Date filter
    col1, col2 = st.columns([3, 1])
    with col2:
        date_range = st.selectbox(
            "Time Period",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Year to Date", "All Time"],
            index=1
        )
    
    # Top metrics row
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        display_metric_card("Open Positions", "24", "+2", "from last month")
    
    with col2:
        display_metric_card("Active Candidates", "152", "+18", "from last month")
    
    with col3:
        display_metric_card("Interviews This Week", "32", "-5", "from last week", is_positive=False)
    
    with col4:
        display_metric_card("Avg. Time to Hire", "38 days", "-3", "days improvement")
    
    # Main dashboard content in two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Hiring Pipeline")
        display_hiring_funnel()
        
        st.subheader("Recruiting Activity")
        display_recruiting_activity()
    
    with col2:
        st.subheader("Top Open Positions")
        display_top_positions()
        
        st.subheader("Candidate Sources")
        display_candidate_sources()
        
        st.subheader("Time to Hire by Department")
        display_time_to_hire()

def display_metric_card(label, value, change, change_label, is_positive=True):
    """Display a metric card with appropriate styling"""
    change_color = "green" if is_positive else "red"
    change_symbol = "↑" if (change.startswith("+") or change.startswith("-") == is_positive) else "↓"
    
    st.markdown(f"""
    <div style="background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
        <div style="font-size: 14px; color: #6c757d; margin-bottom: 5px;">{label}</div>
        <div style="font-size: 28px; font-weight: bold; margin-bottom: 5px;">{value}</div>
        <div style="font-size: 14px; color: {'#28a745' if is_positive else '#dc3545'};">
            {change_symbol} {change} {change_label}
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_hiring_funnel():
    """Display the hiring funnel visualization"""
    # Sample data
    funnel_data = pd.DataFrame({
        'Stage': ['Applications', 'Screened', 'Interview', 'Final Interview', 'Offer', 'Hired'],
        'Count': [450, 200, 80, 40, 25, 18],
        'Conversion': [100, 44, 40, 50, 63, 72]
    })
    
    # Create bar chart
    chart = alt.Chart(funnel_data).mark_bar().encode(
        x=alt.X('Count:Q', title='Candidates'),
        y=alt.Y('Stage:N', title=None, sort=None),
        color=alt.Color('Stage:N', legend=None, scale=alt.Scale(scheme='blues')),
        tooltip=['Stage', 'Count', 'Conversion']
    ).properties(height=250)
    
    st.altair_chart(chart, use_container_width=True)
    
    # Show conversion rates in a small table
    st.markdown("**Conversion Rates**")
    conversion_df = pd.DataFrame({
        'Stage': funnel_data['Stage'][1:],
        'Conversion Rate': [f"{x}%" for x in funnel_data['Conversion'][1:]]
    })
    st.dataframe(conversion_df, hide_index=True, use_container_width=True)

def display_recruiting_activity():
    """Display recruiting activity over time"""
    # Generate some sample data
    date_range = pd.date_range(end=datetime.now(), periods=30, freq='D')
    
    activity_data = pd.DataFrame({
        'Date': date_range,
        'Applications': [18, 22, 15, 19, 25, 28, 20, 22, 30, 35, 25, 22, 19, 15, 18, 
                       22, 27, 30, 35, 40, 38, 35, 30, 28, 25, 20, 18, 15, 20, 25],
        'Interviews': [8, 7, 6, 8, 10, 12, 8, 9, 12, 15, 10, 9, 8, 6, 7, 
                     9, 11, 14, 16, 18, 15, 14, 12, 10, 9, 8, 7, 6, 8, 10],
        'Offers': [2, 1, 2, 3, 2, 3, 1, 2, 3, 4, 3, 2, 2, 1, 2, 
                 3, 2, 3, 4, 5, 4, 3, 3, 2, 2, 1, 1, 2, 2, 3]
    })
    
    # Melt the dataframe for Altair
    melted_data = pd.melt(
        activity_data, 
        id_vars=['Date'], 
        value_vars=['Applications', 'Interviews', 'Offers'],
        var_name='Activity', 
        value_name='Count'
    )
    
    # Create line chart
    chart = alt.Chart(melted_data).mark_line(point=True).encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Count:Q', title='Count'),
        color=alt.Color('Activity:N', title='Activity Type'),
        tooltip=['Date', 'Activity', 'Count']
    ).properties(height=250)
    
    st.altair_chart(chart, use_container_width=True)

def display_top_positions():
    """Display top open positions"""
    positions = [
        {"title": "Senior Software Engineer", "open": 5, "candidates": 28},
        {"title": "Data Scientist", "open": 3, "candidates": 15},
        {"title": "Product Manager", "open": 2, "candidates": 20},
        {"title": "UX Designer", "open": 2, "candidates": 12},
        {"title": "DevOps Engineer", "open": 1, "candidates": 8}
    ]
    
    df = pd.DataFrame(positions)
    
    # Style the dataframe
    st.dataframe(
        df,
        column_config={
            "title": st.column_config.Column("Position"),
            "open": st.column_config.NumberColumn("Open Positions"),
            "candidates": st.column_config.NumberColumn("Active Candidates")
        },
        hide_index=True,
        use_container_width=True
    )

def display_candidate_sources():
    """Display candidate sources pie chart"""
    source_data = pd.DataFrame({
        'Source': ['LinkedIn', 'Indeed', 'Company Website', 'Referral', 'Other'],
        'Percentage': [45, 25, 15, 10, 5]
    })
    
    chart = alt.Chart(source_data).mark_arc().encode(
        theta=alt.Theta(field="Percentage", type="quantitative"),
        color=alt.Color(field="Source", type="nominal", scale=alt.Scale(scheme='category10')),
        tooltip=['Source', 'Percentage']
    ).properties(height=200)
    
    st.altair_chart(chart, use_container_width=True)

def display_time_to_hire():
    """Display time to hire by department"""
    time_data = pd.DataFrame({
        'Department': ['Engineering', 'Product', 'Marketing', 'Sales', 'Design'],
        'Days': [45, 38, 30, 35, 42]
    })
    
    chart = alt.Chart(time_data).mark_bar().encode(
        y=alt.Y('Department:N', title=None, sort='-x'),
        x=alt.X('Days:Q', title='Average Days to Hire'),
        color=alt.Color('Department:N', legend=None),
        tooltip=['Department', 'Days']
    ).properties(height=200)
    
    st.altair_chart(chart, use_container_width=True)
