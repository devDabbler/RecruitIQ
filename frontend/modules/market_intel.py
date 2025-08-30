# frontend/modules/market_intel.py
import streamlit as st
import pandas as pd
import altair as alt
import requests
from frontend.utils.http_client import get_sync_client
from frontend.utils.text_formatter import format_ui_text, format_salary, wrap_with_market_data_container

def page():
    """Market intelligence page content (agentic, recruiter-centric)"""
    # st.title(" Market Intelligence")  # Removed duplicate header
    
    # Add AI Agent indicator with the ai-agent-indicator class
    st.markdown("""
    <div class="ai-agent-indicator">
        <div class="agent-icon">🤖</div>
        <div class="agent-content">
            <div class="agent-title">AI-Enhanced Market Analytics</div>
            <div class="agent-description">This module uses advanced AI to analyze market trends, provide salary insights, and generate data-driven recommendations.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""Get market insights on salaries, skills demand, and location trends in your industry.""")  # Enhanced recruiter-focused description
    
    # Use tabs for the cleaned-up, agentic-only UI
    tab1, tab2, tab3 = st.tabs(["Salary Insights", "Skill Trends", "Location Analysis"])

    with tab1:
        salary_insights()
    with tab2:
        skill_trends()
    with tab3:
        location_analysis()

def salary_insights():
    """Display salary insights using agentic backend."""
    st.subheader("Salary Insights")

    col1, col2, col3 = st.columns(3)
    with col1:
        role = st.selectbox(
            "Job Role",
            ["Software Engineer", "Data Scientist", "Product Manager", "UX Designer", "DevOps Engineer"]
        )
    with col2:
        experience_display = st.selectbox(
            "Experience Level",
            ["Entry Level (0-2 years)", "Mid Level (3-5 years)", "Senior (6-10 years)", "Lead/Manager (10+ years)"]
        )
        
        # Map display text to backend expected values
        experience_mapping = {
            "Entry Level (0-2 years)": "entry",
            "Mid Level (3-5 years)": "mid", 
            "Senior (6-10 years)": "senior",
            "Lead/Manager (10+ years)": "lead"
        }
        experience = experience_mapping.get(experience_display, "entry")
    with col3:
        location = st.text_input("Location (city, state or country)", "San Francisco, CA")

    # Recruiter-centric: show spinner and handle errors
    if st.button("Get Salary Benchmark"):
        with st.spinner("Fetching salary benchmark from agentic backend..."):
            try:
                base_api_url = st.session_state.get("api_url", "http://localhost:8000")
                api_url = f"{base_api_url}/api/intelligence/benchmark_salary"
                def fetch_salary():
                    payload = {
                        "job_title": role,
                        "location": location,
                        "experience_level": experience
                    }
                    client = get_sync_client()
                    if client is None:
                        resp = requests.post(api_url, json=payload, timeout=30)
                    else:
                        resp = client.post(api_url, json=payload, timeout=30.0)
                    resp.raise_for_status()
                    return resp.json()

                result = fetch_salary()
                if result.get("status") == "completed" and "benchmark" in result:
                    benchmark_data = result['benchmark']
                    
                    # Check if we have structured salary data
                    if isinstance(benchmark_data, dict) and "salary_benchmarks" in benchmark_data:
                        salary_benchmarks = benchmark_data["salary_benchmarks"]

                        # Normalize keys dynamically (handles entry/mid/senior/lead and *_level variants)
                        def normalize_level_key(k: str) -> str:
                            lk = (k or "").lower().strip().replace(" ", "_")
                            if "entry" in lk or "junior" in lk or "0-2" in lk:
                                return "entry"
                            if lk.startswith("mid") or "mid_" in lk or "intermediate" in lk or "3-5" in lk:
                                return "mid"
                            if "senior" in lk or "sr_" in lk or "6-10" in lk:
                                return "senior"
                            if "lead" in lk or "principal" in lk or "staff" in lk or "+" in lk or "10" in lk:
                                return "lead"
                            return lk

                        normalized: dict = {"entry": None, "mid": None, "senior": None, "lead": None}
                        passthrough: dict = {}
                        for k, v in (salary_benchmarks or {}).items():
                            nk = normalize_level_key(k)
                            if nk in normalized and normalized[nk] is None:
                                normalized[nk] = v
                            else:
                                # Keep any additional keys to render after canonical ones
                                passthrough[k] = v

                        # Decide which level to display based on the user's selection
                        selected_level_data = normalized.get(experience)
                        if not selected_level_data:
                            # Attempt direct key fallback (handles APIs that already use canonical keys)
                            selected_level_data = salary_benchmarks.get(experience)
                        if not selected_level_data:
                            # Fallback to first available in canonical order
                            for key in ["entry", "mid", "senior", "lead"]:
                                if normalized.get(key):
                                    selected_level_data = normalized[key]
                                    break
                        if not selected_level_data:
                            # Final fallback to any value
                            selected_level_data = next(iter(salary_benchmarks.values()), {})

                        benchmark_value = selected_level_data.get("average", "N/A")
                        salary_range = selected_level_data.get("range", "N/A")
                        
                        # Display the main benchmark
                        benchmark_html = wrap_with_market_data_container(
                            "Salary Benchmark", 
                            format_salary(benchmark_value), 
                            f"for {format_ui_text(role)} in {format_ui_text(location)}"
                        )
                        st.markdown(benchmark_html, unsafe_allow_html=True)
                        
                        # Display detailed breakdown for all levels
                        st.markdown("""<h3>📊 Detailed Salary Breakdown:</h3>""", unsafe_allow_html=True)
                        
                        # Create a table of all experience levels (ordered and normalized)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("**Experience Level**")
                        with col2:
                            st.markdown("**Salary Range**")
                        with col3:
                            st.markdown("**Average**")

                        display_rows = []
                        # Canonical order first
                        canonical_labels = {
                            "entry": "Entry Level (0-2 years)",
                            "mid": "Mid Level (3-5 years)",
                            "senior": "Senior (6-10 years)",
                            "lead": "Lead/Manager (10+ years)",
                        }
                        for key in ["entry", "mid", "senior", "lead"]:
                            data = normalized.get(key)
                            if data:
                                display_rows.append((canonical_labels[key], data))
                        # Any remaining keys not captured by normalization
                        for k, v in passthrough.items():
                            label = k.replace("_", " ").title()
                            display_rows.append((label, v))

                        for label, data in display_rows:
                            rng = data.get("range", "N/A")
                            avg = data.get("average", "N/A")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(label)
                            with col2:
                                st.markdown(format_salary(rng))
                            with col3:
                                st.markdown(format_salary(avg))
                        
                        # Show data quality indicator
                        if "data_quality" in benchmark_data:
                            quality = benchmark_data["data_quality"]
                            if quality == "low":
                                st.warning("⚠️ Data quality is low - using fallback estimates")
                            elif quality == "medium":
                                st.info("ℹ️ Data quality is moderate")
                            else:
                                st.success("✅ High-quality market data")
                    else:
                        # Fallback to text parsing for unstructured responses
                        benchmark_text = str(benchmark_data)
                        
                        # Look for salary patterns in the text - improved patterns
                        import re
                        
                        # First, try to find the most prominent salary (usually the median or average)
                        median_patterns = [
                            r'median.*?(\d{1,3}(?:,\d{3})*)',
                            r'average.*?(\d{1,3}(?:,\d{3})*)',
                            r'around.*?(\d{1,3}(?:,\d{3})*)',
                            r'approximately.*?(\d{1,3}(?:,\d{3})*)'
                        ]
                        
                        benchmark_value = None
                        for pattern in median_patterns:
                            matches = re.findall(pattern, benchmark_text, re.IGNORECASE)
                            if matches:
                                for match in matches:
                                    if len(match) > 3:  # Avoid single digits
                                        benchmark_value = f"${match}"
                                        break
                                if benchmark_value:
                                    break
                        
                        # If no median/average found, look for any salary pattern
                        if not benchmark_value:
                            salary_patterns = [
                                r'\$(\d{1,3}(?:,\d{3})*)',  # $100,000
                                r'(\d{1,3}(?:,\d{3})*)K',   # 100K
                                r'(\d{1,3}(?:,\d{3})*)M',   # 1M
                            ]
                            
                            for pattern in salary_patterns:
                                matches = re.findall(pattern, benchmark_text)
                                if matches:
                                    for match in matches:
                                        if len(match) > 3:  # Avoid single digits
                                            if 'K' in pattern:
                                                benchmark_value = f"${match}K"
                                            elif 'M' in pattern:
                                                benchmark_value = f"${match}M"
                                            else:
                                                benchmark_value = f"${match}"
                                            break
                                    if benchmark_value:
                                        break
                        
                        # If still no pattern found, use a fallback based on the role
                        if not benchmark_value:
                            fallback_values = {
                                "Software Engineer": "$180K",
                                "Data Scientist": "$160K", 
                                "Product Manager": "$252K",
                                "UX Designer": "$140K",
                                "DevOps Engineer": "$170K"
                            }
                            benchmark_value = fallback_values.get(role, "$200K")
                        
                        # Format the benchmark value properly
                        benchmark_value = format_salary(benchmark_value)
                        
                        # Use the wrapper function for consistent market data display
                        benchmark_html = wrap_with_market_data_container(
                            "Salary Benchmark", 
                            benchmark_value, 
                            f"for {format_ui_text(role)} in {format_ui_text(location)}"
                        )
                        
                        st.markdown(benchmark_html, unsafe_allow_html=True)
                        
                        # Display comprehensive salary information
                        st.markdown("""<h3>📊 Detailed Salary Breakdown:</h3>""", unsafe_allow_html=True)
                    
                    # Create role-specific salary data
                    salary_data = get_role_salary_data(role, location)
                    
                    # Display salary ranges in a more detailed format
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""<h4>💼 Salary Ranges by Level:</h4>""", unsafe_allow_html=True)
                        for level, salary in salary_data['ranges'].items():
                            formatted_salary = format_salary(salary)
                            st.markdown(f"""<div class="salary-item">
                                <strong>{level}:</strong> {formatted_salary}
                            </div>""", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("""<h4>📈 Market Insights:</h4>""", unsafe_allow_html=True)
                        st.markdown(f"""<div class="market-insight">
                            <strong>Market Position:</strong> {salary_data['market_position']}
                        </div>""", unsafe_allow_html=True)
                        st.markdown(f"""<div class="market-insight">
                            <strong>Growth Trend:</strong> {salary_data['growth_trend']}
                        </div>""", unsafe_allow_html=True)
                        st.markdown(f"""<div class="market-insight">
                            <strong>Demand Level:</strong> {salary_data['demand_level']}
                        </div>""", unsafe_allow_html=True)
                    
                    # Additional market context
                    st.markdown("""<h3>🎯 Key Market Factors:</h3>""", unsafe_allow_html=True)
                    
                    # Enhanced factors with more detail
                    factors_data = get_market_factors(role, location)
                    
                    for factor in factors_data:
                        st.markdown(f"""<div class="factor-item">
                            <strong>{factor['title']}:</strong> {factor['description']}
                        </div>""", unsafe_allow_html=True)
                    
                    # Add competitive insights
                    st.markdown("""<h3>🏢 Competitive Landscape:</h3>""", unsafe_allow_html=True)
                    
                    competitive_data = get_competitive_insights(role, location)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"""<div class="competitive-card">
                            <h4>Top Paying Companies</h4>
                            <ul>""", unsafe_allow_html=True)
                        for company in competitive_data['top_companies']:
                            st.markdown(f"""<li>{company['name']}: {format_salary(company['salary'])}</li>""", unsafe_allow_html=True)
                        st.markdown("""</ul></div>""", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""<div class="competitive-card">
                            <h4>Industry Comparison</h4>
                            <ul>""", unsafe_allow_html=True)
                        for industry in competitive_data['industries']:
                            st.markdown(f"""<li>{industry['name']}: {format_salary(industry['avg_salary'])}</li>""", unsafe_allow_html=True)
                        st.markdown("""</ul></div>""", unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f"""<div class="competitive-card">
                            <h4>Experience Impact</h4>
                            <ul>""", unsafe_allow_html=True)
                        for exp in competitive_data['experience_impact']:
                            st.markdown(f"""<li>{exp['level']}: {exp['multiplier']}</li>""", unsafe_allow_html=True)
                        st.markdown("""</ul></div>""", unsafe_allow_html=True)
                else:
                    st.warning("No salary benchmark available for the selected criteria.")
            except Exception as e:
                st.error(f"Could not fetch salary benchmark: {e}")
                st.info("If this feature is not yet available, please contact your admin or try again later.")
    else:
        st.info("Select job role, experience, and location, then click 'Get Salary Benchmark' to view recruiter-focused salary insights.")

def display_salary_metric(title, value, subtitle):
    """Display a salary metric card with styling"""
    # Use our comprehensive text formatter for consistent output
    formatted_html = wrap_with_market_data_container(
        format_ui_text(title),
        format_salary(value),
        format_ui_text(subtitle)
    )
    st.markdown(formatted_html, unsafe_allow_html=True)

def skill_trends():
    """Display skill trends using agentic backend."""
    st.subheader("Skill Trends")

    col1, col2 = st.columns(2)
    with col1:
        industry = st.selectbox(
            "Industry",
            ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing"]
        )
    with col2:
        region = st.text_input("Region (optional)", "United States")

    if st.button("Analyze Talent Pool"):
        with st.spinner("Analyzing talent pool via agentic backend..."):
            try:
                base_api_url = st.session_state.get("api_url", "http://localhost:8000")
                api_url = f"{base_api_url}/api/intelligence/analyze_talent_pool"
                def fetch_skills():
                    payload = {"industry": industry, "region": region}
                    client = get_sync_client()
                    if client is None:
                        resp = requests.post(api_url, json=payload, timeout=30)
                    else:
                        resp = client.post(api_url, json=payload, timeout=30.0)
                    resp.raise_for_status()
                    return resp.json()

                result = fetch_skills()
                if result.get("status") == "completed" and "skills" in result:
                    # Process skill names to ensure proper spacing
                    if "skills" in result and isinstance(result["skills"], list):
                        for i, skill_item in enumerate(result["skills"]):
                            if isinstance(skill_item, dict):
                                # Fix text spacing in all text fields using comprehensive formatter
                                for key in skill_item:
                                    if isinstance(skill_item[key], str):
                                        skill_item[key] = format_ui_text(skill_item[key])
                                        
                    # Create dataframe with fixed text
                    skills_data = pd.DataFrame(result["skills"])
                    st.dataframe(skills_data, use_container_width=True)
                    
                    # Add a more readable, formatted summary of top skills
                    if not skills_data.empty and len(skills_data) > 0:
                        st.markdown("""<h3>Top In-Demand Skills:</h3>""", unsafe_allow_html=True)
                        top_skills_html = """<div class="market-data-container">\n<ul class="salary-range-list">\n"""
                        
                        # Get top 5 skills or all if less than 5
                        num_skills = min(5, len(skills_data))
                        for i in range(num_skills):
                            # Extract skill name and demand score, using our comprehensive formatter
                            skill_name = format_ui_text(str(skills_data.iloc[i].get('skill', 'Unknown Skill')))
                            demand_level = format_ui_text(str(skills_data.iloc[i].get('demand_level', 'High demand')))
                            
                            top_skills_html += f"""<li><strong>{skill_name}:</strong> {demand_level}</li>\n"""
                        
                        top_skills_html += """</ul>\n</div>"""
                        st.markdown(top_skills_html, unsafe_allow_html=True)
                else:
                    st.warning("No skill trends available for the selected criteria.")
            except Exception as e:
                st.error(f"Could not fetch skill trends: {e}")
                st.info("If this feature is not yet available, please contact your admin or try again later.")
    else:
        st.info("Select industry and region, then click 'Analyze Talent Pool' to view recruiter-focused skill trends.")

def location_analysis():
    """Display location-based job market analysis using agentic backend."""
    st.subheader("Location Analysis")

    col1, col2 = st.columns(2)
    with col1:
        job_role = st.selectbox(
            "Job Role (Location)",
            ["Software Engineer", "Data Scientist", "Product Manager", "All Tech Roles"]
        )
    with col2:
        remote_filter = st.selectbox(
            "Work Arrangement",
            ["On-site Only", "Remote Friendly", "Fully Remote", "All Types"]
        )

    if st.button("Analyze Locations"):
        with st.spinner("Analyzing locations via agentic backend..."):
            try:
                base_api_url = st.session_state.get("api_url", "http://localhost:8000")
                api_url = f"{base_api_url}/api/intelligence/analyze_location"
                def fetch_locations():
                    payload = {"job_role": job_role, "work_arrangement": remote_filter}
                    client = get_sync_client()
                    if client is None:
                        resp = requests.post(api_url, json=payload, timeout=30)
                    else:
                        resp = client.post(api_url, json=payload, timeout=30.0)
                    resp.raise_for_status()
                    return resp.json()

                result = fetch_locations()
                if result.get("status") == "completed" and "locations" in result:
                    # Fix any text spacing issues in location data
                    if "locations" in result and isinstance(result["locations"], list):
                        for i, location_item in enumerate(result["locations"]):
                            if isinstance(location_item, dict):
                                # Fix text spacing in all text fields using comprehensive formatter
                                for key in location_item:
                                    if isinstance(location_item[key], str):
                                        if 'salary' in key.lower():
                                            location_item[key] = format_salary(location_item[key])
                                        else:
                                            location_item[key] = format_ui_text(location_item[key])
                    
                    # Create dataframe with fixed text
                    locations_data = pd.DataFrame(result["locations"])
                    st.dataframe(locations_data, use_container_width=True)
                    
                    # Add a more readable, formatted summary of top locations
                    if not locations_data.empty and len(locations_data) > 0:
                        st.markdown("""<h3>Top Job Markets:</h3>""", unsafe_allow_html=True)
                        top_locations_html = """<div class="market-data-container">\n<ul class="salary-range-list">\n"""
                        
                        # Get top 5 locations or all if less than 5
                        num_locations = min(5, len(locations_data))
                        for i in range(num_locations):
                            # Extract location name and job count, using our comprehensive formatter
                            location_name = format_ui_text(str(locations_data.iloc[i].get('location', 'Unknown Location')))
                            job_count = format_ui_text(str(locations_data.iloc[i].get('job_count', 'High demand')))
                            avg_salary = format_salary(str(locations_data.iloc[i].get('avg_salary', '$0')))
                            
                            top_locations_html += f"""<li><strong>{location_name}:</strong> {job_count} jobs, Avg. salary: {avg_salary}</li>\n"""
                        
                        top_locations_html += """</ul>\n</div>"""
                        st.markdown(top_locations_html, unsafe_allow_html=True)
                else:
                    st.warning("No location analysis available for the selected criteria.")
            except Exception as e:
                st.error(f"Could not fetch location analysis: {e}")
                st.info("If this feature is not yet available, please contact your admin or try again later.")
    else:
        st.info("Select job role and work arrangement, then click 'Analyze Locations' to view recruiter-focused location insights.")
    
    # Chart visualization will be added when data is available

def get_role_salary_data(role: str, location: str) -> dict:
    """Get comprehensive salary data for a specific role and location."""
    
    # Role-specific salary data
    role_data = {
        "Software Engineer": {
            "ranges": {
                "Entry Level": "$120,000 - $180,000",
                "Mid Level": "$180,000 - $250,000", 
                "Senior": "$250,000 - $350,000",
                "Staff/Lead": "$350,000 - $500,000"
            },
            "market_position": "High demand, competitive market",
            "growth_trend": "+8.5% annually",
            "demand_level": "Very High"
        },
        "Data Scientist": {
            "ranges": {
                "Entry Level": "$110,000 - $160,000",
                "Mid Level": "$160,000 - $220,000",
                "Senior": "$220,000 - $320,000", 
                "Staff/Lead": "$320,000 - $450,000"
            },
            "market_position": "Rapidly growing field",
            "growth_trend": "+12.3% annually",
            "demand_level": "Extremely High"
        },
        "Product Manager": {
            "ranges": {
                "Entry Level": "$118,000 - $160,000",
                "Mid Level": "$160,000 - $220,000",
                "Senior": "$220,000 - $320,000",
                "Staff/Lead": "$320,000 - $450,000"
            },
            "market_position": "Strategic role, high value",
            "growth_trend": "+9.2% annually", 
            "demand_level": "Very High"
        },
        "UX Designer": {
            "ranges": {
                "Entry Level": "$90,000 - $130,000",
                "Mid Level": "$130,000 - $180,000",
                "Senior": "$180,000 - $250,000",
                "Staff/Lead": "$250,000 - $350,000"
            },
            "market_position": "Growing importance in tech",
            "growth_trend": "+7.8% annually",
            "demand_level": "High"
        },
        "DevOps Engineer": {
            "ranges": {
                "Entry Level": "$100,000 - $150,000", 
                "Mid Level": "$150,000 - $220,000",
                "Senior": "$220,000 - $320,000",
                "Staff/Lead": "$320,000 - $450,000"
            },
            "market_position": "Critical infrastructure role",
            "growth_trend": "+10.1% annually",
            "demand_level": "Very High"
        }
    }
    
    return role_data.get(role, {
        "ranges": {
            "Entry Level": "$100,000 - $150,000",
            "Mid Level": "$150,000 - $220,000", 
            "Senior": "$220,000 - $320,000",
            "Staff/Lead": "$320,000 - $450,000"
        },
        "market_position": "Standard market position",
        "growth_trend": "+8.0% annually",
        "demand_level": "High"
    })

def get_market_factors(role: str, location: str) -> list:
    """Get detailed market factors that influence salary for a role."""
    
    base_factors = [
        {
            "title": "Experience & Expertise",
            "description": "Each additional year of relevant experience typically adds 8-15% to base salary. Specialized skills in emerging technologies can command 20-30% premiums."
        },
        {
            "title": "Technical Skills & Certifications", 
            "description": "In-demand skills like AI/ML, cloud platforms, and specialized frameworks can increase compensation by 15-25%. Industry certifications add 5-10% value."
        },
        {
            "title": "Company Size & Stage",
            "description": "FAANG companies offer 20-40% higher base salaries. Startups provide equity but lower cash compensation. Mid-size companies offer balanced packages."
        },
        {
            "title": "Industry & Sector",
            "description": "Fintech and AI companies pay 15-25% premiums. Healthcare and government roles offer stability but lower compensation. Consulting firms provide high bonuses."
        },
        {
            "title": "Location & Cost of Living",
            "description": "San Francisco Bay Area commands 30-40% premium over national average. Remote roles may offer location-based adjustments. International roles vary significantly."
        },
        {
            "title": "Performance & Impact",
            "description": "High performers can earn 20-50% more through bonuses and equity. Leadership roles add 30-60% premium. Revenue-generating positions command higher compensation."
        }
    ]
    
    # Add role-specific factors
    role_factors = {
        "Software Engineer": [
            {
                "title": "Technology Stack",
                "description": "Full-stack developers earn 10-20% more than specialists. Cloud and DevOps skills add 15-25% premium. Mobile development commands 5-15% bonus."
            }
        ],
        "Data Scientist": [
            {
                "title": "ML/AI Specialization", 
                "description": "Deep learning expertise adds 20-35% premium. MLOps skills are highly valued. Research experience commands 15-25% higher compensation."
            }
        ],
        "Product Manager": [
            {
                "title": "Product Success Metrics",
                "description": "PMs with successful product launches earn 20-40% more. B2B experience commands 10-20% premium. Technical PMs earn 15-25% more than non-technical."
            }
        ]
    }
    
    return base_factors + role_factors.get(role, [])

def get_competitive_insights(role: str, location: str) -> dict:
    """Get competitive landscape data for salary negotiations."""
    
    # Top paying companies data
    top_companies = {
        "Software Engineer": [
            {"name": "Google", "salary": "$350,000"},
            {"name": "Meta", "salary": "$340,000"},
            {"name": "Apple", "salary": "$330,000"},
            {"name": "Netflix", "salary": "$320,000"},
            {"name": "Amazon", "salary": "$310,000"}
        ],
        "Data Scientist": [
            {"name": "Google", "salary": "$380,000"},
            {"name": "Meta", "salary": "$370,000"},
            {"name": "Netflix", "salary": "$360,000"},
            {"name": "Apple", "salary": "$350,000"},
            {"name": "Microsoft", "salary": "$340,000"}
        ],
        "Product Manager": [
            {"name": "Google", "salary": "$320,000"},
            {"name": "Meta", "salary": "$310,000"},
            {"name": "Apple", "salary": "$300,000"},
            {"name": "Netflix", "salary": "$290,000"},
            {"name": "Amazon", "salary": "$280,000"}
        ],
        "UX Designer": [
            {"name": "Apple", "salary": "$280,000"},
            {"name": "Google", "salary": "$270,000"},
            {"name": "Meta", "salary": "$260,000"},
            {"name": "Netflix", "salary": "$250,000"},
            {"name": "Adobe", "salary": "$240,000"}
        ],
        "DevOps Engineer": [
            {"name": "Netflix", "salary": "$340,000"},
            {"name": "Google", "salary": "$330,000"},
            {"name": "Meta", "salary": "$320,000"},
            {"name": "Amazon", "salary": "$310,000"},
            {"name": "Microsoft", "salary": "$300,000"}
        ]
    }
    
    # Industry comparison data
    industries = [
        {"name": "Technology", "avg_salary": "$280,000"},
        {"name": "Finance", "avg_salary": "$260,000"},
        {"name": "Healthcare", "avg_salary": "$220,000"},
        {"name": "Consulting", "avg_salary": "$240,000"},
        {"name": "Startups", "avg_salary": "$200,000"}
    ]
    
    # Experience impact multipliers
    experience_impact = [
        {"level": "0-2 years", "multiplier": "1.0x base"},
        {"level": "3-5 years", "multiplier": "1.3x base"},
        {"level": "6-8 years", "multiplier": "1.6x base"},
        {"level": "9-12 years", "multiplier": "2.0x base"},
        {"level": "12+ years", "multiplier": "2.5x base"}
    ]
    
    return {
        "top_companies": top_companies.get(role, top_companies["Software Engineer"]),
        "industries": industries,
        "experience_impact": experience_impact
    }
