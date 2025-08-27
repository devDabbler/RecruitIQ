# frontend/modules/resume_upload.py
import streamlit as st
import requests
import json
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000" # Adjust if needed

# ---------------------------------------------------------------------------
# Shared text cleaning utility
# ---------------------------------------------------------------------------

try:
    # Reuse the centralised cleaner from the backend for consistent behaviour.
    from backend.utils.advanced_text_cleaner import clean_resume_text

    def fix_merged_text(text: str):
        """Front-end helper that delegates to the shared AdvancedTextCleaner.

        Keeping only a thin wrapper here avoids duplicating an ever-growing list
        of hard-coded replacements on the client side.
        """

        if not text or not isinstance(text, str):
            return text

        # We perform a *light* clean (deep_clean=False) because the backend has
        # already executed a thorough pass. This ensures UI responsiveness
        # while still catching any artefacts introduced after serialisation.
        try:
            return clean_resume_text(text, deep_clean=False)
        except Exception as exc:
            logger.warning(f"Text cleaning failed in frontend fallback: {exc}")
            return text

except ModuleNotFoundError:
    # If the backend package isn't on the PYTHONPATH in certain deployment
    # scenarios, fall back to a basic implementation to avoid runtime errors.
    logger.warning("backend.utils.advanced_text_cleaner not available - running with basic cleaning.")

    def fix_merged_text(text: str):
        """Basic text cleaning fallback when backend module isn't available"""
        if not text or not isinstance(text, str):
            return text
        
        import re
        
        # Basic URL and email cleaning
        # Fix spaced emails (e.g., "john . doe @ example . com" -> "john.doe@example.com")
        text = re.sub(r'(\w+)\s+\.\s+(\w+)\s*@\s*(\w+)\s*\.\s*(\w+)', r'\1.\2@\3.\4', text)
        
        # Fix spaced URLs (e.g., "www . linkedin . com" -> "www.linkedin.com")
        text = re.sub(r'(www|http[s]?)\s*\.\s*(\w+)\s*\.\s*(com|org|net|edu|gov)', r'\1.\2.\3', text)
        
        # Fix spaced LinkedIn URLs specifically
        text = re.sub(r'linkedin\s*\.\s*com\s*/\s*profile\s*/\s*(\w+)', r'linkedin.com/profile/\1', text)
        
        return text

# Helper functions for displaying resume data in a more structured and visually appealing way

def format_date_for_display(date_str):
    """
    Convert ISO date format to a more appealing display format.
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD) or other format
        
    Returns:
        Formatted date string (e.g., "January 2023", "Jan 2020")
    """
    if not date_str:
        return ""
    
    try:
        from datetime import datetime
        
        # Handle different date formats
        if len(date_str) == 10 and '-' in date_str:  # ISO format YYYY-MM-DD
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%B %Y')  # e.g., "January 2023"
        elif len(date_str) == 7 and '-' in date_str:  # YYYY-MM format
            date_obj = datetime.strptime(date_str, '%Y-%m')
            return date_obj.strftime('%B %Y')  # e.g., "January 2023"
        elif len(date_str) == 4 and date_str.isdigit():  # YYYY format
            return date_str  # Just return the year
        else:
            # If it's already in a good format or unrecognized, return as is
            return date_str
    except (ValueError, TypeError):
        # If parsing fails, return the original string
        return date_str

def format_date_range(start_date, end_date, context="Period"):
    """
    Format a date range for display with appealing formatting.
    
    Args:
        start_date: Start date string
        end_date: End date string or None
        context: Context label (e.g., "Period", "Service Period")
        
    Returns:
        Formatted date range string
    """
    if not start_date and not end_date:
        return ""
    
    formatted_start = format_date_for_display(start_date) if start_date else ""
    formatted_end = format_date_for_display(end_date) if end_date else ""
    
    if formatted_start and formatted_end:
        # Both dates available
        if formatted_start == formatted_end:
            # Same month/year, just show once
            return f"**{context}:** {formatted_start}"
        else:
            return f"**{context}:** {formatted_start} to {formatted_end}"
    elif formatted_start:
        # Only start date - assume current/present
        return f"**{context}:** {formatted_start} to Present"
    elif formatted_end:
        # Only end date
        if context == "Service Period":
            return f"**{context}:** Until {formatted_end}"
        else:
            return f"**{context}:** Graduated {formatted_end}"
    
    return ""

def process_parsed_data(data):
    """Recursively process all text in the parsed data to fix merged words"""
    if not data:
        return data
        
    # Handle different data types
    if isinstance(data, str):
        return fix_merged_text(data)
    elif isinstance(data, list):
        return [process_parsed_data(item) for item in data]
    elif isinstance(data, dict):
        processed_dict = {}
        for key, value in data.items():
            processed_dict[key] = process_parsed_data(value)
        return processed_dict
    else:
        # For numbers, booleans, None, etc., return as is
        return data

def display_experience(experience_list, debug_expanders: bool = True):
    """Display experience entries in a structured, readable format"""
    if not experience_list or not isinstance(experience_list, list):
        return
    
    st.subheader("💼 Professional Experience")
    
    for exp in experience_list:
        col1, col2 = st.columns([3, 1])
        with col1:
            # Job title and company with formatting - apply text fix
            title = fix_merged_text(exp.get('title', 'Position'))
            company = fix_merged_text(exp.get('company', 'Company'))
            st.markdown(f"### {title} at {company}")
        
        with col2:
            # Date range and location in the right column
            start_date = exp.get('start_date', '')
            end_date = exp.get('end_date', '')
            location = fix_merged_text(exp.get('location', ''))
            
            # Format date range with appealing formatting
            date_display = format_date_range(start_date, end_date, "Period")
            if date_display:
                st.markdown(date_display)
            
            if location:
                st.markdown(f"**Location:** {location}")
        
        # Description with enhanced bullet formatting - apply text fix
        description = fix_merged_text(exp.get('description', ''))
        responsibilities = exp.get('responsibilities', [])
        
        # Debug output to see the full experience data
        if debug_expanders:
            with st.expander("Debug - Experience Data", expanded=False):
                st.write(exp)
            
        # First display any structured responsibilities (if available)
        if responsibilities and isinstance(responsibilities, list):
            st.markdown(f"**Responsibilities & Achievements:**")
            
            # Process each responsibility item to ensure proper formatting
            for resp in responsibilities:
                cleaned_resp = fix_merged_text(resp)
                if cleaned_resp:
                    # Remove existing bullet markers to avoid duplication
                    cleaned_resp = re.sub(r'^[•\-*⊛]\s*', '', cleaned_resp)
                    st.markdown(f"• {cleaned_resp}")
                    
        # If we don't have responsibilities list but have a description, process it
        elif description:
            st.markdown(f"**Responsibilities & Achievements:**")
            
            # Parse bullets from the formatted description
            bullets = []
            if '\n' in description:
                # Multi-line description - split by newlines (handle both single and double newlines)
                bullets = [line.strip() for line in re.split(r'\n+', description) if line.strip()]
            elif any(marker in description for marker in ['•', '-', '*', '⊛']):
                # Has bullet markers - split by them
                bullet_pattern = r'[•\-*⊛]\s*(.+?)(?=(?:[•\-*⊛])|$)'
                bullets = re.findall(bullet_pattern, description, re.DOTALL)
                bullets = [bullet.strip() for bullet in bullets if bullet.strip()]
            else:
                # Single paragraph - split by sentences if long enough
                if len(description) > 100:
                    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', description)
                    bullets = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]
                else:
                    bullets = [description]
            
            # Display bullets with native Streamlit formatting for better reliability
            if bullets and len(bullets) > 1:
                for bullet in bullets:
                    # Remove existing bullet markers to avoid duplication
                    cleaned_bullet = re.sub(r'^[•\-*⊛]\s*', '', bullet)
                    st.markdown(f"• {cleaned_bullet}")
            else:
                # Single description or fallback - use simple markdown
                st.markdown(f"> {description}")
        
        # Skills demonstrated
        skills = exp.get('skills_demonstrated', [])
        technologies = exp.get('technologies', [])
        if skills or technologies:
            all_skills = skills + technologies
            if all_skills:
                st.markdown("**Skills & Technologies:**")
                st.markdown(", ".join([f"`{skill}`" for skill in all_skills]))
        
        st.divider()

def display_education(education_list):
    """Display education entries in a structured, readable format"""
    if not education_list or not isinstance(education_list, list):
        return
    
    st.subheader("🎓 Education")
    
    for edu in education_list:
        col1, col2 = st.columns([3, 1])
        with col1:
            # Degree and institution with formatting
            degree = edu.get('degree')
            # Normalize degree to string safely
            if isinstance(degree, str):
                degree_header = degree.strip()
            elif degree is None:
                degree_header = ""
            else:
                degree_header = str(degree).strip()

            field = edu.get('field_of_study') or edu.get('major') or ''
            if field is None:
                field = ''
            elif not isinstance(field, str):
                field = str(field)

            institution = edu.get('institution') or 'Institution'
            if not isinstance(institution, str):
                institution = str(institution)
            institution = fix_merged_text(institution)
            if field:
                # Append field of study to degree header
                if degree_header:
                    degree_header = f"{degree_header} in {field}"
                else:
                    degree_header = field  # At least show field if degree missing
            st.markdown(f"### {degree_header if degree_header else 'Education'}")
            st.markdown(f"**Institution:** {institution}")
        
        with col2:
            # Date range and location in the right column
            start_date = edu.get('start_date', '')
            end_date = edu.get('end_date', '')
            location = edu.get('location') or ''
            if not isinstance(location, str):
                location = str(location)
            location = fix_merged_text(location)
            
            # Format date range with appealing formatting
            date_display = format_date_range(start_date, end_date, "Period")
            if date_display:
                st.markdown(date_display)
            
            if location:
                st.markdown(f"**Location:** {location}")
        
        # GPA and description
        gpa = edu.get('gpa')
        if gpa:
            st.markdown(f"**GPA:** {gpa}")
        
        description = edu.get('description') or ''
        if not isinstance(description, str):
            description = str(description)
        description = fix_merged_text(description)
        if description:
            st.markdown(description)
        
        # Courses, achievements, honors
        courses = edu.get('courses', [])
        if courses:
            st.markdown("**Relevant Courses:**")
            # Ensure course items are strings
            formatted_courses = []
            for c in courses:
                if isinstance(c, str):
                    formatted_courses.append(c.strip())
                elif isinstance(c, dict):
                    # Try common keys
                    name = c.get('name') or c.get('title') or c.get('course')
                    if isinstance(name, str):
                        formatted_courses.append(name.strip())
                else:
                    formatted_courses.append(str(c))
            st.markdown(", ".join([fc for fc in formatted_courses if fc]))
        
        achievements = edu.get('achievements', [])
        if achievements:
            st.markdown("**Achievements:**")
            for achievement in achievements:
                if not isinstance(achievement, str):
                    achievement = str(achievement)
                st.markdown(f"- {achievement}")
        
        st.divider()

def display_military(military_list):
    """Display military experience entries in a structured, readable format"""
    if not military_list or not isinstance(military_list, list):
        return
    
    st.subheader("🎖️ Military Experience")
    
    for mil in military_list:
        col1, col2 = st.columns([3, 1])
        with col1:
            # Rank/title and branch with formatting
            rank = fix_merged_text(mil.get('rank', mil.get('title', 'Position')))
            organization = fix_merged_text(mil.get('organization', mil.get('branch', 'Military')))
            st.markdown(f"### {rank}")
            st.markdown(f"**Branch:** {organization}")
        
        with col2:
            # Date range and location in the right column
            start_date = mil.get('start_date', '')
            end_date = mil.get('end_date', '')
            location = fix_merged_text(mil.get('location', ''))
            
            # Format date range with appealing formatting
            date_display = format_date_range(start_date, end_date, "Service Period")
            if date_display:
                st.markdown(date_display)
            
            if location:
                st.markdown(f"**Location:** {location}")
        
        # Description with better formatting
        description = fix_merged_text(mil.get('description', ''))
        if description:
            st.markdown(f"**Duties & Achievements:**")
            st.markdown(description)
        
        st.divider()

def display_skills(skills_list):
    """Display skills in a visually appealing way with meaningful categories"""
    if not skills_list:
        st.info("No skills found in the resume.")
        return
    
    st.subheader("🔧 Skills & Technologies")
    
    # Debug: Show what we received (remove this after testing)
    #st.write("DEBUG - Raw skills data:", skills_list[:3] if len(skills_list) > 3 else skills_list)
    
    # Import the safe skill processing from ui_helpers
    try:
        from frontend.utils.ui_helpers import format_skills_list
    except ImportError:
        # Fallback if import fails
        def format_skills_list(skills):
            """Fallback format_skills_list implementation"""
            if not skills:
                return []
            
            formatted = []
            for skill in skills:
                if isinstance(skill, str):
                    clean_skill = skill.strip()
                    if clean_skill:
                        formatted.append(clean_skill)
                elif isinstance(skill, dict):
                    skill_name = skill.get('name', skill.get('skill_name', str(skill)))
                    if skill_name and isinstance(skill_name, str):
                        clean_skill = skill_name.strip()
                        if clean_skill:
                            formatted.append(clean_skill)
            return formatted
    
    # Clean and format the skills first
    formatted_skills = format_skills_list(skills_list)
    
    if not formatted_skills:
        st.info("No valid skills could be extracted.")
        return
    
    # Now we need to categorize the skills using our backend categorization logic
    # Since we don't have categories from the backend, we'll apply them here
    skills_by_category = {}
    
    # Define the categorization function locally to avoid dependency issues
    def categorize_skill(skill_name: str) -> str:
        """Categorize a skill into a predefined category."""
        skill_name_lower = skill_name.lower()
        
        # Define enhanced skill categories with better organization
        # Order matters - more specific categories should be checked first
        categories = {
            "Executive & Strategic Leadership": [
                "p&l", "profit and loss", "p&l management", "profit loss management",
                "budget management", "financial management", "revenue management",
                "cost management", "strategic planning", "business strategy",
                "corporate strategy", "strategic initiatives", "strategic partnerships",
                "board reporting", "executive reporting", "stakeholder management",
                "investor relations", "governance", "risk management",
                "organizational development", "talent management", "succession planning",
                "change leadership", "transformation leadership", "digital transformation",
                "merger and acquisition", "m&a", "due diligence", "business development",
                "partnership development", "strategic alliances", "joint ventures",
                "charter development", "program charters", "project charters",
                "roadmap development", "technology roadmap", "product roadmap",
                "technology strategy", "innovation strategy", "digital strategy",
                "enterprise architecture", "technology governance", "technology portfolio",
                "vendor management", "contract negotiation", "procurement",
                "executive leadership", "c-level", "vp", "director level",
                "cross-functional leadership", "matrix management", "global leadership"
            ],
            "Technical Leadership & Architecture": [
                "technical leadership", "engineering leadership", "technology leadership",
                "software architecture", "system architecture", "enterprise architecture",
                "solution architecture", "cloud architecture", "microservices architecture",
                "distributed systems", "scalability", "performance optimization",
                "technical strategy", "technology evaluation", "technology assessment",
                "technical roadmap", "architecture review", "design patterns",
                "system design", "high-level design", "low-level design",
                "technical mentoring", "engineering management", "team leadership",
                "code review", "technical documentation", "architecture documentation",
                "technical debt management", "refactoring", "legacy system modernization",
                "api design", "database design", "infrastructure design"
            ],
            "Mobile Development": [
                "ios development", "android development", "mobile development",
                "react native", "flutter", "xamarin", "cordova", "phonegap",
                "swift", "kotlin", "objective-c", "dart", "mobile apps"
            ],
            "Emerging Technologies": [
                "blockchain", "cryptocurrency", "web3", "nft", "defi", "smart contracts",
                "ar", "vr", "augmented reality", "virtual reality",
                "iot", "internet of things", "edge computing", "quantum computing",
                "artificial intelligence", "ai"
            ],
            "Design & User Experience": [
                "ui design", "ux design", "user experience", "user interface",
                "graphic design", "web design", "prototyping", "wireframing",
                "figma", "sketch", "adobe creative suite", "photoshop", "illustrator",
                "user research", "usability testing", "design thinking"
            ],
            "Security & Compliance": [
                "cybersecurity", "information security", "network security",
                "penetration testing", "vulnerability assessment", "compliance",
                "gdpr", "hipaa", "sox", "encryption", "firewall", "vpn",
                "security audit", "risk assessment", "security frameworks"
            ],
            "Quality & Testing": [
                "quality assurance", "qa", "testing", "automated testing", "unit testing",
                "integration testing", "performance testing", "security testing",
                "test driven development", "tdd", "selenium", "pytest", "jest", "cypress",
                "test automation", "quality engineering"
            ],
            "DevOps & CI/CD": [
                "devops", "ci/cd", "continuous integration", "continuous deployment",
                "jenkins", "gitlab ci", "github actions", "ansible", 
                "puppet", "chef", "terraform", "infrastructure as code",
                "circleci", "travis ci", "bamboo", "teamcity", "octopus deploy",
                "deployment automation", "release management"
            ],
            "Data Science & Analytics": [
                "data science", "machine learning", "deep learning", "nlp", 
                "natural language processing", "computer vision", "tensorflow", 
                "pytorch", "scikit-learn", "pandas", "numpy", "matplotlib", 
                "seaborn", "jupyter", "spark", "hadoop", "tableau", "power bi",
                "statistical analysis", "data mining", "predictive modeling",
                "data engineering", "etl", "data pipeline", "big data"
            ],
            "Cloud & Infrastructure": [
                "aws", "amazon web services", "azure", "microsoft azure", 
                "gcp", "google cloud platform", "google cloud", "cloud computing",
                "kubernetes", "docker", "containerization", "microservices",
                "terraform", "serverless", "lambda", "ec2", "s3", "heroku",
                "digitalocean", "linode", "cloudflare", "firebase",
                "cloud migration", "cloud architecture", "multi-cloud"
            ],
            "Databases & Data Storage": [
                "database", "sql", "mysql", "postgresql", "postgres", "mongodb", 
                "oracle", "sql server", "redis", "elasticsearch", "dynamodb", 
                "cassandra", "neo4j", "sqlite", "mariadb", "couchdb", 
                "influxdb", "snowflake", "data warehouse", "data lake"
            ],
            "Web Technologies & Frameworks": [
                "react", "reactjs", "angular", "angularjs", "vue", "vuejs",
                "django", "flask", "spring", "spring boot", "express", "expressjs",
                "node.js", "nodejs", "jquery", "bootstrap", "tailwind", "next.js", "nextjs",
                "nuxt.js", "gatsby", "svelte", "ember", "backbone",
                "asp.net", "laravel", "rails", "ruby on rails", "fastapi", 
                "sinatra", "html", "css", "sass", "less", "scss"
            ],
            "Programming Languages": [
                "python", "java", "javascript", "typescript", "c++", "c#", "csharp",
                "ruby", "php", "swift", "kotlin", "go", "golang", "rust", 
                "scala", "perl", "r", "matlab", "cobol", "fortran", "assembly",
                "vb.net", "visual basic", "delphi", "objective-c", "haskell",
                "erlang", "elixir", "clojure", "f#", "lua", "bash", "powershell"
            ],
            "Development Tools & IDEs": [
                "git", "github", "gitlab", "bitbucket", "svn", "subversion",
                "visual studio", "vscode", "visual studio code", "intellij", 
                "eclipse", "xcode", "android studio", "sublime text", "atom", 
                "vim", "emacs", "postman", "insomnia", "jira", "confluence"
            ],
            "Project Management & Methodologies": [
                "project management", "program management", "product management",
                "agile", "scrum", "kanban", "waterfall", "lean", "six sigma",
                "pmp", "prince2", "trello", "asana", "monday.com", "notion",
                "sprint planning", "backlog management", "release planning",
                "portfolio management", "pmo", "project charter"
            ],
            "Leadership & Management": [
                "leadership", "team leadership", "team management", "people management",
                "staff management", "line management", "mentoring", "coaching",
                "change management", "resource management", "cross-functional leadership",
                "servant leadership", "transformational leadership", "hiring",
                "performance management", "team building", "conflict management"
            ],
            "Communication & Interpersonal": [
                "communication", "public speaking", "presentation", "presenting",
                "negotiation", "collaboration", "teamwork", "conflict resolution", 
                "customer service", "client relations", "stakeholder communication", 
                "technical writing", "documentation", "training", "facilitation",
                "relationship building", "interpersonal skills"
            ],
            "Problem Solving & Analytical": [
                "problem solving", "critical thinking", "analytical thinking",
                "troubleshooting", "debugging", "root cause analysis",
                "research", "data analysis", "business analysis", "systems analysis",
                "process improvement", "optimization", "analytical skills",
                "quantitative analysis", "logical thinking"
            ],
            "Business & Domain": [
                "business development", "sales", "marketing", "finance", "accounting",
                "operations", "strategy", "consulting", "product development",
                "market research", "competitive analysis", "roi analysis",
                "business intelligence", "market analysis", "customer development"
            ],
            "Languages": [
                "english", "spanish", "french", "german", "chinese", "japanese", 
                "russian", "arabic", "portuguese", "italian", "korean", "hindi",
                "mandarin", "cantonese", "dutch", "swedish", "norwegian", "danish"
            ]
        }
        
        # Check categories in order (most specific first)
        for category, keywords in categories.items():
            for keyword in keywords:
                # Exact match or substring match for longer keywords
                if keyword == skill_name_lower:
                    return category
                # For longer keywords (4+ chars), allow substring matching
                elif len(keyword) > 3 and keyword in skill_name_lower:
                    # But avoid false positives - check if it's a meaningful match
                    # Skip if the skill contains framework/library indicators that should override
                    if category == "Programming Languages" and any(indicator in skill_name_lower for indicator in [
                        "framework", "library", "lib", "api", "sdk", "platform"
                    ]):
                        continue
                    return category
        
        # Enhanced fallback logic for skills not explicitly categorized
        # AI/ML/Data Science patterns (more specific)
        if any(pattern in skill_name_lower for pattern in [
            "machine learning", "ml", "deep learning", "neural", "data science",
            "analytics", "statistics", "predictive", "modeling", "algorithm",
            "regression", "classification", "clustering", "nlp", "computer vision"
        ]):
            return "Data Science & Analytics"
        
        # Programming language patterns
        if any(pattern in skill_name_lower for pattern in [
            "script", "lang", "programming", "coding", ".js", ".py", ".java", 
            "compiler", "interpreter", "syntax"
        ]):
            return "Programming Languages"
        
        # Framework/Library patterns
        if any(pattern in skill_name_lower for pattern in [
            "framework", "library", "lib", ".js", "react", "angular", "vue",
            "django", "flask", "spring", "express", "api", "sdk"
        ]):
            return "Web Technologies & Frameworks"
        
        # Leadership patterns
        if any(pattern in skill_name_lower for pattern in [
            "leadership", "management", "strategy", "planning", "executive",
            "director", "manager", "lead", "head", "chief", "vp", "ceo", "cto"
        ]):
            # Determine if it's technical or general leadership
            if any(tech_pattern in skill_name_lower for tech_pattern in [
                "technical", "technology", "engineering", "software", "system",
                "architecture", "platform"
            ]):
                return "Technical Leadership & Architecture"
            elif any(exec_pattern in skill_name_lower for exec_pattern in [
                "strategic", "executive", "corporate", "business", "financial",
                "organizational", "transformation"
            ]):
                return "Executive & Strategic Leadership"
            else:
                return "Leadership & Management"
        
        # Check if it's a human language
        common_languages = [
            "english", "spanish", "french", "german", "chinese", "japanese",
            "korean", "russian", "arabic", "portuguese", "italian", "hindi",
            "mandarin", "cantonese", "dutch", "swedish", "norwegian", "danish",
            "finnish", "polish", "czech", "hungarian", "greek", "hebrew",
            "turkish", "thai", "vietnamese", "indonesian"
        ]
        if skill_name_lower in common_languages or "language" in skill_name_lower:
            return "Languages"
        
        return "Other Technical Skills"
    
    # Categorize each skill
    for skill in formatted_skills:
        category = categorize_skill(skill)
        if category not in skills_by_category:
            skills_by_category[category] = []
        skills_by_category[category].append(skill)
    
    # Define category order and styling for better organization
    category_config = {
        # Executive & Leadership Skills (Priority 1)
        "Executive & Strategic Leadership": {"icon": "👑", "color": "#8B0000", "priority": 1},
        "Technical Leadership & Architecture": {"icon": "🏗️", "color": "#4B0082", "priority": 2},
        "Leadership & Management": {"icon": "📊", "color": "#B8860B", "priority": 3},
        "Project Management & Methodologies": {"icon": "📋", "color": "#556B2F", "priority": 4},
        
        # Technical Skills (Priority 2)
        "Programming Languages": {"icon": "💻", "color": "#2E86AB", "priority": 5},
        "Web Technologies & Frameworks": {"icon": "🌐", "color": "#A23B72", "priority": 6},
        "Databases & Data Storage": {"icon": "🗄️", "color": "#F18F01", "priority": 7},
        "Cloud & Infrastructure": {"icon": "☁️", "color": "#C73E1D", "priority": 8},
        "DevOps & CI/CD": {"icon": "⚙️", "color": "#2E8B57", "priority": 9},
        "Data Science & Analytics": {"icon": "📈", "color": "#8A2BE2", "priority": 10},
        "Mobile Development": {"icon": "📱", "color": "#FF6B35", "priority": 11},
        "Development Tools & IDEs": {"icon": "🔧", "color": "#4682B4", "priority": 12},
        "Quality & Testing": {"icon": "🧪", "color": "#FF8C00", "priority": 13},
        "Security & Compliance": {"icon": "🔒", "color": "#DC143C", "priority": 14},
        "Design & User Experience": {"icon": "🎨", "color": "#9932CC", "priority": 15},
        "Emerging Technologies": {"icon": "🚀", "color": "#FF1493", "priority": 16},
        
        # Soft Skills & Professional (Priority 3)
        "Communication & Interpersonal": {"icon": "🗣️", "color": "#20B2AA", "priority": 17},
        "Problem Solving & Analytical": {"icon": "🧩", "color": "#8B4513", "priority": 18},
        "Business & Domain": {"icon": "💼", "color": "#800080", "priority": 19},
        
        # Others (Priority 4)
        "Languages": {"icon": "🌎", "color": "#2F4F4F", "priority": 20},
        "Technical Skills": {"icon": "⚙️", "color": "#696969", "priority": 21},
        "Other Technical Skills": {"icon": "⚙️", "color": "#696969", "priority": 21}
    }
    
    # Sort categories by priority
    sorted_categories = sorted(
        skills_by_category.items(), 
        key=lambda x: category_config.get(x[0], {"priority": 999})["priority"]
    )
    
    # Group categories for better layout
    leadership_categories = []
    technical_categories = []
    soft_skill_categories = []
    other_categories = []
    
    for category, skills in sorted_categories:
        if category in [
            "Executive & Strategic Leadership", "Technical Leadership & Architecture", 
            "Leadership & Management", "Project Management & Methodologies"
        ]:
            leadership_categories.append((category, skills))
        elif category in [
            "Programming Languages", "Web Technologies & Frameworks", 
            "Databases & Data Storage", "Cloud & Infrastructure", 
            "DevOps & CI/CD", "Data Science & Analytics", "Mobile Development",
            "Development Tools & IDEs", "Quality & Testing", 
            "Security & Compliance", "Design & User Experience", 
            "Emerging Technologies", "Other Technical Skills", "Technical Skills"
        ]:
            technical_categories.append((category, skills))
        elif category in [
            "Communication & Interpersonal", "Problem Solving & Analytical",
            "Business & Domain"
        ]:
            soft_skill_categories.append((category, skills))
        else:
            other_categories.append((category, skills))
    
    # Display Leadership & Strategic Skills (Priority 1)
    if leadership_categories:
        st.markdown("### 👑 Leadership & Strategic Skills")
        st.markdown("*Executive and strategic capabilities for senior technology roles*")
        
        for category, skills in leadership_categories:
            _display_skill_category(category, skills, category_config)
    
    # Display Technical Skills
    if technical_categories:
        st.markdown("### 💻 Technical Skills")
        
        # Use tabs for better organization of technical skills
        tech_tabs = st.tabs([
            "Core Tech", "Development", "Data & Cloud", "Tools & Testing"
        ])
        
        core_tech = [cat for cat in technical_categories if cat[0] in [
            "Programming Languages", "Web Technologies & Frameworks", "Databases & Data Storage"
        ]]
        dev_tools = [cat for cat in technical_categories if cat[0] in [
            "Development Tools & IDEs", "Mobile Development", "DevOps & CI/CD"
        ]]
        data_cloud = [cat for cat in technical_categories if cat[0] in [
            "Data Science & Analytics", "Cloud & Infrastructure", "Emerging Technologies"
        ]]
        quality_sec = [cat for cat in technical_categories if cat[0] in [
            "Quality & Testing", "Security & Compliance", "Design & User Experience", 
            "Other Technical Skills", "Technical Skills"
        ]]
        
        with tech_tabs[0]:
            for category, skills in core_tech:
                _display_skill_category(category, skills, category_config)
        
        with tech_tabs[1]:
            for category, skills in dev_tools:
                _display_skill_category(category, skills, category_config)
        
        with tech_tabs[2]:
            for category, skills in data_cloud:
                _display_skill_category(category, skills, category_config)
        
        with tech_tabs[3]:
            for category, skills in quality_sec:
                _display_skill_category(category, skills, category_config)
    
    # Display Professional & Soft Skills
    if soft_skill_categories:
        st.markdown("### 🤝 Professional & Soft Skills")
        for category, skills in soft_skill_categories:
            _display_skill_category(category, skills, category_config)
    
    # Display Other Skills
    if other_categories:
        st.markdown("### 🌎 Additional Skills")
        for category, skills in other_categories:
            _display_skill_category(category, skills, category_config)
    
    st.divider()

def _display_skill_category(category, skills, category_config):
    """Helper function to display a skill category with consistent styling"""
    config = category_config.get(category, {"icon": "•", "color": "#666666"})
    icon = config["icon"]
    
    # Display category header
    st.markdown(f"**{icon} {category}:**")
    
    # Create skill badges using native Streamlit components instead of HTML
    if skills:
        # Create a clean text representation of skills using code formatting
        skills_text = ""
        sorted_skills = sorted(skills)
        
        # Group skills in rows for better display
        skills_per_row = 6
        for i in range(0, len(sorted_skills), skills_per_row):
            row_skills = sorted_skills[i:i + skills_per_row]
            # Use code formatting for skill badges - more reliable than HTML
            skill_badges = " ".join([f"`{str(skill).strip()}`" for skill in row_skills if str(skill).strip()])
            if skill_badges:
                st.markdown(skill_badges)
        
        st.markdown("")  # Add spacing after skills
    else:
        st.markdown("*No skills in this category*")
    
    st.markdown("")  # Add spacing between categories

def display_personal_info(personal_info, debug_expanders: bool = True):
    """Display personal information in a structured format"""
    if not personal_info or not isinstance(personal_info, dict):
        return
    
    st.subheader("👤 Personal Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Enhanced name processing to handle parsing issues
        name = fix_merged_text(personal_info.get('name', ''))
        if name:
            # Clean up duplicate words and common parsing issues
            name_parts = name.split()
            
            # Remove duplicates and common parsing artifacts
            seen = set()
            cleaned_parts = []
            for part in name_parts:
                part_lower = part.lower()
                # Skip obvious duplicates and parsing artifacts
                if (part_lower not in seen and 
                    len(part) > 1 and 
                    part_lower not in ['ed', 'jr', 'sr', 'iii', 'iv'] or 
                    part_lower in ['jr', 'sr', 'iii', 'iv']):  # Keep actual suffixes
                    seen.add(part_lower)
                    cleaned_parts.append(part)
            
            # For cases like "Clint Ed Forest" -> "Clint Forest" (remove middle parsing artifacts)
            if len(cleaned_parts) == 3:
                # Check if middle word is a common parsing artifact
                middle = cleaned_parts[1].lower()
                if middle in ['ed', 'john', 'mike', 'alex', 'bob', 'joe', 'tom', 'sam']:
                    cleaned_parts = [cleaned_parts[0], cleaned_parts[2]]  # Keep first and last
            
            cleaned_name = ' '.join(cleaned_parts)
            st.markdown(f"**Name:** {cleaned_name}")
        
        # Enhanced email processing with proper hyperlink
        email = fix_merged_text(personal_info.get('email', ''))
        if email:
            # Clean and validate email format
            email = email.strip()
            # Remove any spaces in the email address
            email = re.sub(r'\s+', '', email)
            if '@' in email and '.' in email:
                # Create a simple clickable email without complex markdown
                st.markdown(f"**Email:** [{email}](mailto:{email})")
            else:
                st.markdown(f"**Email:** {email}")
        
        phone = fix_merged_text(personal_info.get('phone', ''))
        if phone:
            # Clean phone number formatting
            cleaned_phone = re.sub(r'[^\d\-\(\)\+\s]', '', phone)
            st.markdown(f"**Phone:** {cleaned_phone}")
    
    with col2:
        location = fix_merged_text(personal_info.get('location', ''))
        if location:
            st.markdown(f"**Location:** {location}")
        
        # Enhanced LinkedIn processing with proper hyperlink
        # Check for LinkedIn under various possible field names
        linkedin = None
        for field in ['linkedin', 'linkedin_url', 'linkedinurl']:
            if field in personal_info and personal_info[field]:
                linkedin = fix_merged_text(personal_info[field])
                if linkedin:
                    break
                    
        # Add debug expander to view all personal info fields
        if debug_expanders:
            with st.expander("Debug - Personal Info Fields", expanded=False):
                st.write(personal_info)
                    
        if linkedin:
            # Clean LinkedIn URL and create proper hyperlink
            linkedin = linkedin.strip()
            # Fix common spacing issues
            linkedin = re.sub(r'\s+', '', linkedin)  # Remove all spaces
            
            if linkedin:
                # Ensure proper URL format
                if not linkedin.startswith('http'):
                    if linkedin.startswith('www.'):
                        linkedin = f"https://{linkedin}"
                    elif linkedin.startswith('linkedin.com'):
                        linkedin = f"https://www.{linkedin}"
                    elif 'linkedin.com' not in linkedin:
                        linkedin = f"https://www.linkedin.com/in/{linkedin}"
                
                # Create simple clickable hyperlink with the URL as the link text
                display_linkedin = linkedin.replace('https://', '')
                st.markdown(f"**LinkedIn:** [{display_linkedin}]({linkedin})")
                st.markdown(f"[👥 View LinkedIn Profile]({linkedin})")
        
        website = fix_merged_text(personal_info.get('website', ''))
        if website:
            website = website.strip()
            if website:
                # Ensure proper URL format
                if not website.startswith('http'):
                    website = f"https://{website}"
                st.markdown(f"**Website:** {website}")
                st.markdown(f"[🌐 Visit Website]({website})")
        
        github = fix_merged_text(personal_info.get('github', ''))
        if github:
            github = github.strip()
            if github:
                # Ensure proper GitHub URL format
                if not github.startswith('http'):
                    if github.startswith('github.com'):
                        github = f"https://{github}"
                    elif not github.startswith('www.'):
                        github = f"https://github.com/{github}"
                    else:
                        github = f"https://{github}"
                
                st.markdown(f"**GitHub:** {github}")
                st.markdown(f"[💻 View Profile]({github})")
    
    st.divider()

def upload_resume():
    """Handles the resume upload, parsing, review, and confirmation workflow."""
    st.header("Upload Resume")
    
    # Always-on Agentic Features

    st.session_state.show_agent_reasoning = True
    st.session_state.agent_processing_strategy = "comprehensive"  # Enhanced agentic strategy
    st.session_state.enrich_linkedin = True
    st.session_state.generate_suggestions = True

    # Sidebar info only (no toggle)
    with st.sidebar:
        st.subheader("Resume Processing Options")
        st.info("🤖 This resume will be processed using Agentic Zero AI technology for optimal results.")
        with st.expander("What does Agentic Zero do?"):
            st.markdown("""
            **Agentic Zero** uses our advanced agent system to provide:

            📋 **Comprehensive Data Extraction**  
            📊 **Resume Quality Assessment**  
            💼 **LinkedIn Profile Enrichment**  
            📈 **Market Alignment Analysis**  
            📚 **Skill Enhancement Suggestions**  
            💬 **Interactive Q&A**  
            """)
            st.markdown("---")
            st.caption("Agentic Zero processing may take slightly longer but provides much richer insights.")
        # Advanced options always on, but not user-toggleable
        st.caption("All advanced agentic features are enabled by default.")
    st.divider()

    # Use a key for the file uploader to better manage state resets
    uploaded_file = st.file_uploader(
        "Choose a resume file (PDF, DOCX)",
        type=["pdf", "docx"],
        key="resume_uploader"
    )

    # Initialize session state variables if they don't exist
    if "parsed_data" not in st.session_state:
        st.session_state["parsed_data"] = None
    if "save_status" not in st.session_state:
        st.session_state["save_status"] = None # Can be None, "success", "error"
    if "saved_candidate_id" not in st.session_state:
        st.session_state["saved_candidate_id"] = None
    if "uploaded_file_info" not in st.session_state:
        st.session_state["uploaded_file_info"] = None # Store name/type if needed after upload

    if uploaded_file is not None:
        # Store file info if it's a new upload (name differs from stored)
        current_file_name = uploaded_file.name
        if st.session_state.uploaded_file_info is None or st.session_state.uploaded_file_info["name"] != current_file_name:
            st.session_state.uploaded_file_info = {"name": uploaded_file.name, "type": uploaded_file.type}
            # Clear previous parse/save state when a new file is uploaded
            st.session_state.parsed_data = None
            st.session_state.save_status = None
            st.session_state.saved_candidate_id = None
            logger.info(f"New file uploaded: {current_file_name}. Resetting state.")

        st.write("Selected file:", current_file_name)

        # Only show Parse button if data hasn't been parsed yet for this file
        if st.session_state.parsed_data is None and st.session_state.save_status is None:
            parse_button_text = "🤖 Process with Agentic Zero"
            if st.button(parse_button_text, type="primary"):
                with st.spinner("🤖 Agentic Zero processing resume... This may take longer but provides enhanced analysis."):
                    process_with_agent(uploaded_file)


    # Step 3: Review and confirm parsed data (only if parsed_data exists and not yet saved)
    parsed_data = st.session_state.get("parsed_data")
    save_status = st.session_state.get("save_status")

    if parsed_data and save_status is None: # Show review section only if parsed and not saved/error
        st.header("Review Parsed Resume Data")

        # Debug information at the top to show what was parsed
        st.info("📋 Resume successfully parsed! Here's what we found:")
        
        # Quick summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            _skills_for_metric = parsed_data.get('skills') or []
            st.metric("Skills Found", len(_skills_for_metric))
        with col2:
            _experience_for_metric = parsed_data.get('experience') or []
            st.metric("Experience Entries", len(_experience_for_metric))
        with col3:
            education_list_display = parsed_data.get('education') # Get value, could be None
            if education_list_display: # Checks if not None and not an empty list
                education_count = len(education_list_display)
            else: # Handles None or empty list
                education_count = 0
            st.metric("Education Entries", education_count)
        
        # --- Display Parsed Data in a more structured and visually appealing way ---
        st.markdown("## Resume Content Preview")
        
        # Display personal information
        display_personal_info(parsed_data.get("personal_info", {}))
        
        # Display summary if available
        summary = parsed_data.get("summary")
        if summary:
            st.subheader("📃 Summary")
            st.markdown(summary)
            st.divider()
        
        # Display skills in a visually appealing way
        display_skills(parsed_data.get("skills", []))
        
        # Display experience entries
        display_experience(parsed_data.get("experience", []))
        
        # Display education entries
        display_education(parsed_data.get("education", []))
        
        # Display military experience entries
        display_military(parsed_data.get("military", []))
        
        # Display other sections if available
        other_sections = parsed_data.get("other_sections")
        if other_sections and isinstance(other_sections, dict):
            for section_title, section_content in other_sections.items():
                st.subheader(f"📄 {section_title.replace('_', ' ').title()}")
                if isinstance(section_content, list):
                    for item in section_content:
                        if isinstance(item, dict):
                            # Format dictionary items
                            details = [f"**{k.replace('_', ' ').title()}:** {v}" for k, v in item.items() if v]
                            st.markdown("- " + ", ".join(details))
                        else:
                            st.markdown(f"- {item}")
                elif isinstance(section_content, str):
                    st.markdown(section_content)
                st.divider()


        st.divider()

        # --- Editable fields for user confirmation ---
        st.subheader("Confirm/Edit Key Details")
        with st.form("confirm_form"):
            personal_info = parsed_data.get("personal_info", {})

            # Pre-fill logic (handle cases where only 'name' is parsed)
            default_first_name = personal_info.get("first_name", "")
            default_last_name = personal_info.get("last_name", "")
            if not default_first_name and not default_last_name and personal_info.get("name"):
                 name_parts = personal_info["name"].strip().split(maxsplit=1)
                 default_first_name = name_parts[0]
                 default_last_name = name_parts[1] if len(name_parts) > 1 else ""

            first_name = st.text_input("First Name*", value=default_first_name)
            last_name = st.text_input("Last Name", value=default_last_name)
            email = st.text_input("Email*", value=personal_info.get("email", ""))

            submitted = st.form_submit_button("Confirm and Save Candidate")

            if submitted:
                if not first_name or not email:  # Basic validation
                    st.warning("First Name and Email are required.")
                else:
                    with st.spinner("Saving candidate..."):
                        # Update parsed_data with user edits before sending
                        personal_info["first_name"] = first_name
                        personal_info["last_name"] = last_name
                        personal_info["email"] = email
                        # Ensure the updated personal_info is in the payload
                        parsed_data["personal_info"] = personal_info

                        # Include original filename if available in session state
                        original_filename = st.session_state.uploaded_file_info.get("name") if st.session_state.uploaded_file_info else "unknown"

                        try:
                            # Initialize the save_response variable to avoid scope issues
                            save_response = {"success": False, "message": "No response received"}
                            
                            # Check if we have a resume_id from agent processing
                            resume_id = st.session_state.get("resume_id")
                            if resume_id is not None:
                                # Ensure resume_id is an integer for API compatibility
                                try:
                                    if not isinstance(resume_id, int):
                                        resume_id = int(resume_id)
                                        logger.info(f"Converted resume_id to int: {resume_id}")
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Could not convert resume_id to int: {e}. Using fallback approach.")
                                    # If conversion fails, use the old API method
                                    resume_id = None

                                if resume_id is not None:
                                    # Resume already exists, just update it with confirmed data
                                    payload = {
                                        "resume_id": resume_id,
                                        "personal_info": personal_info,
                                        "education": parsed_data.get("education", []),
                                        "experience": parsed_data.get("experience", []),
                                        "skills": parsed_data.get("skills", [])
                                    }
                                    
                                    # Special handling for military experience field
                                    military_data = parsed_data.get("military", [])
                                    logger.info(f"Military data before payload: type={type(military_data)}, value={military_data}")
                                    
                                    # Ensure military follows Experience schema structure
                                    if military_data is None:
                                        payload["military"] = []
                                    else:
                                        # Make sure each military entry has all required fields for Experience model
                                        formatted_military = []
                                        # Safe iteration over military_data
                                        for entry in (military_data if isinstance(military_data, list) else []):
                                            if isinstance(entry, dict):
                                                # Ensure required fields exist
                                                if not entry.get('title'):
                                                    entry['title'] = entry.get('position') or 'Military Service'
                                                if not entry.get('company'):
                                                    entry['company'] = entry.get('branch') or 'Military'
                                                if not entry.get('description'):
                                                    entry['description'] = entry.get('responsibilities') or ''
                                                # Add to formatted list
                                                formatted_military.append(entry)
                                        # Update payload with properly formatted military data
                                        payload["military"] = formatted_military
                                        logger.info(f"Formatted military data: {formatted_military}")

                                        
                                    logger.info(f"Updating existing resume with ID: {resume_id}")
                                    logger.info(f"Payload keys: {list(payload.keys())}")
                                    logger.info(f"Payload structure: military={type(payload.get('military'))}, education={type(payload.get('education'))}")
                                    
                                    try:
                                        # Attempt to serialize to verify JSON structure
                                        json_data = json.dumps(payload)
                                        logger.info(f"JSON validation successful, payload size: {len(json_data)} bytes")
                                    except TypeError as json_err:
                                        logger.error(f"JSON serialization error: {json_err}")
                                        
                                    response = requests.post(f"{BACKEND_URL}/api/resume/confirm", json=payload, timeout=180)
                                    
                                    if response.status_code == 404:
                                        logger.warning(f"Resume ID {resume_id} not found in database or cache. Falling back to creating a new resume.")
                                        # Remove resume_id from payload since it doesn't exist
                                        if 'resume_id' in payload:
                                            del payload['resume_id']
                                        
                                        # Repackage the data as a new resume submission
                                        new_payload = {
                                            "resume_data": parsed_data,
                                            "settings": {"save_to_database": False, "create_candidate": False}
                                        }
                                        
                                        logger.info(f"Falling back to new resume creation with payload size: {len(json.dumps(new_payload))}")
                                        # Try again with the new payload format
                                        response = requests.post(f"{BACKEND_URL}/api/resume/confirm", json=new_payload, timeout=180)
                                        
                                        if response.status_code != 200:
                                            logger.error(f"Fallback creation also failed: {response.status_code} - {response.text}")
                                        else:
                                            # Update save_response with the API response
                                            save_response = response.json()
                                            logger.info(f"Save response received after fallback: {json.dumps(save_response)}")
                                    elif response.status_code != 200:
                                        logger.error(f"Server returned error: {response.status_code} - {response.text}")
                                    else:
                                        # Update save_response with the API response
                                        save_response = response.json()
                                        logger.info(f"Save response received: {json.dumps(save_response)}")

                                else:
                                    # Fall back to old method if resume_id is not valid
                                    # Fix military data structure before sending
                                    if "military" in parsed_data and parsed_data["military"]:
                                        military_data = parsed_data["military"]
                                        formatted_military = []
                                        for entry in (military_data if isinstance(military_data, list) else []):
                                            if isinstance(entry, dict):
                                                # Ensure required fields exist
                                                if not entry.get('title'):
                                                    entry['title'] = entry.get('position') or 'Military Service'
                                                if not entry.get('company'):
                                                    entry['company'] = entry.get('branch') or 'Military'
                                                if not entry.get('description'):
                                                    entry['description'] = entry.get('responsibilities') or ''
                                                formatted_military.append(entry)
                                        parsed_data["military"] = formatted_military
                                        logger.info(f"Formatted military data in parsed_data: {formatted_military}")
                                    
                                    payload = {
                                        "resume_data": parsed_data,
                                        "settings": {"save_to_database": False, "create_candidate": False}
                                    }
                                    logger.info("Resume ID conversion failed, creating new resume instead")
                                    
                                    try:
                                        json_data = json.dumps(payload)
                                        logger.info(f"JSON validation successful, payload size: {len(json_data)} bytes")
                                    except TypeError as json_err:
                                        logger.error(f"JSON serialization error in fallback path: {json_err}")
                                    
                                    response = requests.post(f"{BACKEND_URL}/api/resume/confirm", json=payload, timeout=180)
                                    if response.status_code >= 400:
                                        logger.error(f"Error response from server: Status {response.status_code}")
                                        logger.error(f"Error details: {response.text}")
                                    else:
                                        # Update save_response with the API response
                                        save_response = response.json()
                                        logger.info(f"Save response received (fallback path): {json.dumps(save_response)}")
                            else:
                                # Fallback to the old method if no resume_id
                                # Fix military data structure before sending
                                if "military" in parsed_data and parsed_data["military"]:
                                    military_data = parsed_data["military"]
                                    formatted_military = []
                                    for entry in (military_data if isinstance(military_data, list) else []):
                                        if isinstance(entry, dict):
                                            # Ensure required fields exist
                                            if not entry.get('title'):
                                                entry['title'] = entry.get('position') or 'Military Service'
                                            if not entry.get('company'):
                                                entry['company'] = entry.get('branch') or 'Military'
                                            if not entry.get('description'):
                                                entry['description'] = entry.get('responsibilities') or ''
                                            formatted_military.append(entry)
                                    parsed_data["military"] = formatted_military
                                    logger.info(f"Formatted military data in parsed_data: {formatted_military}")
                                
                                payload = {
                                    "resume_data": parsed_data,
                                    "settings": {"save_to_database": False, "create_candidate": False}
                                }
                                logger.info("No resume_id found, creating new resume")
                                logger.info(f"Sending payload to /api/resume/confirm: {json.dumps(payload)}")
                                response = requests.post(f"{BACKEND_URL}/api/resume/confirm", json=payload, timeout=180)
                                if response.status_code == 404:
                                    logger.warning(f"New resume creation - received 404. Potentially an issue with the payload structure.")
                                    logger.info(f"Attempting with modified payload structure...")
                                    
                                    # Create a simpler payload structure
                                    simplified_payload = {}
                                    simplified_payload["resume_data"] = parsed_data
                                    simplified_payload["settings"] = {"save_to_database": False, "create_candidate": False}
                                    
                                    # Try again with the simplified payload
                                    response = requests.post(f"{BACKEND_URL}/api/resume/confirm", json=simplified_payload, timeout=180)
                                    
                                    if response.status_code >= 400:
                                        logger.error(f"Simplified payload also failed: {response.status_code} - {response.text}")
                                        save_response = {"success": False, "message": f"Failed to save resume: {response.text}"}
                                    else:
                                        try:
                                            save_response = response.json()
                                            logger.info(f"Save response received with simplified payload: {json.dumps(save_response)}")
                                        except Exception as json_err:
                                            logger.error(f"Could not parse successful response as JSON: {json_err}")
                                            save_response = {"success": False, "message": "Could not parse API response"}
                                elif response.status_code >= 400:
                                    logger.error(f"Error response from server: Status {response.status_code}")
                                    logger.error(f"Error details: {response.text}")
                                    # Even if there's an error, try to get the JSON response for detailed error info
                                    try:
                                        error_data = response.json()
                                        save_response = {"success": False, "message": error_data.get("detail", str(response.text))}
                                    except Exception as json_err:
                                        logger.error(f"Could not parse error response as JSON: {json_err}")
                                        save_response = {"success": False, "message": str(response.text)}
                                else:
                                    # Success case
                                    try:
                                        save_response = response.json()
                                        logger.info(f"Save response received: {json.dumps(save_response)}")
                                    except Exception as json_err:
                                        logger.error(f"Could not parse successful response as JSON: {json_err}")
                                        save_response = {"success": False, "message": "Could not parse API response"}
                            if save_response.get("success"):
                                st.session_state.save_status = "success"
                                st.session_state.saved_candidate_id = save_response.get("candidate_id")
                                st.session_state.parsed_data = None
                                # Clear the resume_id since it's now confirmed
                                if "resume_id" in st.session_state:
                                    del st.session_state.resume_id
                                if "file_id" in st.session_state:
                                    del st.session_state.file_id
                                logger.info(f"Candidate saved successfully. ID: {st.session_state.saved_candidate_id}")
                                st.rerun()
                            else:
                                error_msg = save_response.get("message", "Unknown error during save.")
                                logger.error(f"Failed to save candidate: {error_msg}")
                                
                                # Check if this is a duplicate entry error
                                if any(keyword in error_msg.lower() for keyword in ["duplicate", "already exists", "conflict"]):
                                    st.error(f"This candidate appears to already exist in the system: {error_msg}")
                                    st.info("If you intended to update an existing candidate, please search for them first or use a different email.")
                                else:
                                    st.error(f"Failed to save candidate: {error_msg}")
                                    
                                st.session_state.save_status = "error"
                        except requests.exceptions.Timeout:
                            logger.error("Save request timed out.")
                            st.error("Saving request timed out. Please try again.")
                            st.session_state.save_status = "error"
                        except requests.exceptions.HTTPError as e:
                            if e.response.status_code == 409:
                                logger.warning(f"Duplicate candidate detected: {e}")
                                st.error("This candidate already exists in the system.")
                                st.info("If you intended to update an existing candidate, please search for them first or use a different email.")
                            else:
                                logger.error(f"HTTP error during save: {e}")
                                st.error(f"Error during save: {e.response.reason if hasattr(e, 'response') else str(e)}")
                            st.session_state.save_status = "error"
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Network error during save: {e}")
                            st.error(f"Network error during save: {e}")
                            st.session_state.save_status = "error"
                        except Exception as e:
                            logger.error(f"An unexpected error occurred during save: {e}", exc_info=True)
                            st.error(f"An unexpected error occurred during save: {e}")
                            st.session_state.save_status = "error"


    # --- Post-Save Options ---
    if save_status == "success":
        st.success("Candidate saved successfully!")
        saved_candidate_id = st.session_state.get("saved_candidate_id")
        if saved_candidate_id:
            st.info(f"Candidate ID: {saved_candidate_id}") # Display ID

        col1, col2 = st.columns(2)
        with col1:
            # Button to navigate to the profile page using query params
            if st.button("View Candidate Profile", key="view_profile_btn"):
                if saved_candidate_id:
                    st.query_params["id"] = saved_candidate_id
                    # Reset the view_handled flag to allow navigation
                    st.session_state.pop("view_handled", None)
                    logger.info(f"Setting query param 'id' to {saved_candidate_id} for navigation.")
                    st.rerun()  # Trigger rerun to navigate immediately
                else:
                    st.warning("Cannot navigate, saved Candidate ID is missing.")

        with col2:
            if st.button("Upload Another Resume", key="upload_another_btn"):
                # Clear relevant session state for a new upload cycle
                st.session_state.uploaded_file_info = None
                st.session_state.parsed_data = None # Ensure parsed data is clear
                st.session_state.save_status = None
                st.session_state.saved_candidate_id = None
                logger.info("'Upload Another Resume' clicked. Resetting state.")
                st.rerun()

    elif save_status == "error":
        # If there was a save error, we keep the parsed data and form visible
        # The error message is displayed within the form submission logic
        st.error("There was an issue saving the candidate. Please review the details and try again, or check the backend logs.")
        # Optionally add a button to retry or clear
        if st.button("Try Again / Clear Form"):
             st.session_state.save_status = None # Reset save status to allow retry
             # Keep parsed_data so the form is still populated
             st.rerun()


def process_with_agent(uploaded_file):
    """Process resume using the ResumeProcessingAgent with transparent status indicators"""
    try:
        # Prepare the request
        files = [("files", (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type))]
        
        # Prepare task details
        task_details = {}
        if hasattr(st.session_state, 'agent_target_job_title') and st.session_state.agent_target_job_title:
            task_details["target_job_title"] = st.session_state.agent_target_job_title
        
        # Get optional configuration from session state
        enrich_linkedin = True  # Default to True
        generate_suggestions = True  # Default to True
        
        # Check if advanced options were set
        if "enrich_linkedin" in st.session_state:
            enrich_linkedin = st.session_state.enrich_linkedin
        if "generate_suggestions" in st.session_state:
            generate_suggestions = st.session_state.generate_suggestions
        
        # Add these options to task details
        task_details["enrich_linkedin"] = enrich_linkedin
        task_details["generate_suggestions"] = generate_suggestions
        
        data = {
            "agent_name": "ResumeProcessingAgent",
            "task_details_json": json.dumps(task_details)
        }
        
        # Show transparent progress indicator with expandable details
        with st.status("AI Agent analyzing resume...", expanded=True) as status:
            # Setup processing indicators - these will update as each step completes
            st.write("📝 Extracting structured data...")
            
            # Send the initial request
            logger.info(f"Sending file {uploaded_file.name} to agent processing endpoint")
            response = requests.post(
                f"{BACKEND_URL}/api/assistant/agent-task",
                files=files,
                data=data,
                timeout=180
            )
            
            # Update indicators based on task details
            st.write("📊 Assessing resume quality...")
            if enrich_linkedin:
                st.write("🌐 Searching for LinkedIn profile...")
            if generate_suggestions:
                st.write("📚 Generating skill suggestions...")
            
            # Final status
            status.update(label="AI analysis complete!", state="complete")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Agent processing successful: {result}")
            
            # Process agent results
            process_agent_results(result, uploaded_file.name)
            
        else:
            logger.error(f"Agent processing failed: HTTP {response.status_code} - {response.text}")
            st.error(f"Agent processing failed: {response.text}")
            st.session_state.parsed_data = None
            
    except requests.exceptions.Timeout:
        logger.error("Agent processing request timed out.")
        st.error("Agent processing timed out. The analysis may be complex or the server is busy.")
        st.session_state.parsed_data = None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during agent processing: {e}")
        st.error(f"Network error during agent processing: {e}")
        st.session_state.parsed_data = None
    except Exception as e:
        logger.error(f"Unexpected error during agent processing: {e}", exc_info=True)
        st.error(f"Unexpected error during agent processing: {e}")
        st.session_state.parsed_data = None

def process_with_basic_mode(uploaded_file):
    """Process resume using basic parsing endpoint"""
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        
        logger.info(f"Sending file {uploaded_file.name} to /api/resume/parse")
        data = {"save_to_db": "false"}
        response = requests.post(f"{BACKEND_URL}/api/resume/parse", files=files, data=data, timeout=180)
        response.raise_for_status()
        
        parsed_response = response.json()
        logger.info(f"Basic parsing successful: {parsed_response}")
        
        # Process basic results (existing logic)
        if response.status_code == 200:
            if parsed_response.get("parsed_data"):
                parsed_data = parsed_response["parsed_data"]
                if "resume_id" in parsed_response:
                    # Ensure resume_id is handled as an integer
                    try:
                        resume_id = parsed_response["resume_id"]
                        if resume_id is not None and not isinstance(resume_id, int):
                            resume_id = int(resume_id)
                            logger.info(f"Converted basic mode resume_id to int: {resume_id}")
                        parsed_data["resume_id"] = resume_id
                        st.session_state.resume_id = resume_id  # Store in session state
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not convert resume_id to int in basic mode: {e}. Using as-is.")
                        parsed_data["resume_id"] = parsed_response["resume_id"]
                        st.session_state.resume_id = parsed_response["resume_id"]
                processed_data = process_parsed_data(parsed_data)
                st.session_state.parsed_data = processed_data
            elif parsed_response.get("personal_info") or parsed_response.get("skills"):
                processed_data = process_parsed_data(parsed_response)
                st.session_state.parsed_data = processed_data
            else:
                st.session_state.parsed_data = None
            
            # Debug output
            logger.info(f"DEBUG - Parsed Data Structure: {list(st.session_state.parsed_data.keys()) if st.session_state.parsed_data else 'None'}")
            if st.session_state.parsed_data:
                with st.expander("Debug: Raw Parser Output", expanded=False):
                    # st.json(st.session_state.parsed_data)  # Commented out for production
                    st.write("Raw parser output display disabled for production")
            
            st.session_state.save_status = None
            st.session_state.saved_candidate_id = None
            logger.info("Basic parsing successful. Storing parsed data in session state.")
            st.success("Resume parsed! Review and confirm details below.")
            st.rerun()
        else:
            error_message = parsed_response.get('message', 'Parsing failed.')
            logger.error(f"Basic parsing failed: {error_message}")
            st.error(f"Parsing failed: {error_message}")
            st.session_state.parsed_data = None
            
    except requests.exceptions.Timeout:
        logger.error("Basic parsing request timed out.")
        st.error("Parsing timed out. The resume might be too large or complex.")
        st.session_state.parsed_data = None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during basic parsing: {e}")
        st.error(f"Network error during parsing: {e}")
        st.session_state.parsed_data = None
    except Exception as e:
        logger.error(f"Unexpected error during basic parsing: {e}", exc_info=True)
        st.error(f"Unexpected error during parsing: {e}")
        st.session_state.parsed_data = None

def process_agent_results(agent_result, filename):
    """Process and display agent processing results"""
    
    if "agent_metadata" not in st.session_state:
        st.session_state.agent_metadata = {}
    st.session_state.agent_metadata[filename] = agent_result

    # Check for the new, flattened successful response structure
    if agent_result.get("status") == "success" and "data" in agent_result:
        file_result = agent_result  # The entire result is what we need

        # Process the parsed data
        parsed_data = file_result['data']
        processed_data = process_parsed_data(parsed_data)
        st.session_state.parsed_data = processed_data
        
        # Store the resume_id and file_id from the agent response
        if "resume_id" in file_result:
            # Ensure resume_id is properly handled as an integer
            try:
                resume_id = file_result["resume_id"]
                if resume_id is not None and not isinstance(resume_id, int):
                    resume_id = int(resume_id)
                st.session_state.resume_id = resume_id
                logger.info(f"Stored resume_id from agent: {st.session_state.resume_id}")
            except (ValueError, TypeError) as e:
                # Handle the case where resume_id cannot be converted to int
                logger.warning(f"Could not convert resume_id to int: {e}. Using as-is.")
                st.session_state.resume_id = file_result["resume_id"]
                
        if "file_id" in file_result:
            st.session_state.file_id = file_result["file_id"]
            logger.info(f"Stored file_id from agent: {st.session_state.file_id}")
        
        # Store agent-specific analysis for enhanced display
        st.session_state.agent_analysis = {
            'quality_assessment': file_result.get('quality_assessment', {}),
            'market_alignment': file_result.get('market_alignment', {}),
        }
        
        st.session_state.save_status = None
        st.session_state.saved_candidate_id = None
        logger.info("Agent processing successful. Storing enhanced data in session state.")
        
        # Display a summary of the successful processing
        display_agent_success_summary(file_result)
        st.rerun()

    # Handle error responses
    elif agent_result.get("status") == "error":
        error_msg = agent_result.get('message', 'Agent processing failed with an unknown error.')
        logger.error(f"Agent processing failed: {error_msg}")
        st.error(f"Agent processing failed: {error_msg}")
        st.session_state.parsed_data = None

    # Fallback for unexpected structures
    else:
        logger.error(f"No valid results found in agent response: {agent_result}")
        st.error("Agent processing completed but no results were returned.")
        st.session_state.parsed_data = None

def display_agent_success_summary(file_result):
    """Display a summary of agent processing results with robust checks."""

    st.success(f"Agent processing complete for **{file_result.get('filename')}**")

    # Add an explanation of agent mode benefits
    with st.expander("🧠 Agent Mode Benefits", expanded=True):
        st.markdown("""
        **Agent Mode provides these enhancements:**
        - ✓ Resume Quality Assessment with scores and feedback
        - ✓ LinkedIn profile enrichment (when web search is configured)
        - ✓ Comprehensive structured data extraction
        - ✓ Extended validation and cleaning of resume data
        """)

    # Safely get quality assessment and display it prominently
    assessment = file_result.get('quality_assessment')
    if assessment and isinstance(assessment, dict):
        st.markdown("### 📊 Resume Quality Assessment")
        st.info("This analysis is unique to Agent Mode and helps evaluate the resume's effectiveness.")
        
        # Display scores in a more visually appealing way
        col1, col2, col3 = st.columns(3)
        
        clarity = assessment.get('clarity_score', 0)
        impact = assessment.get('impact_score', 0)
        relevance = assessment.get('skills_relevance_score', 0)
        
        col1.metric("Clarity Score", f"{clarity}/10", 
                   delta="Good" if clarity >= 7 else "Needs Improvement" if clarity <= 5 else None)
        
        col2.metric("Impact Score", f"{impact}/10", 
                  delta="Good" if impact >= 7 else "Needs Improvement" if impact <= 5 else None)
        
        col3.metric("Skills Relevance", f"{relevance}/10", 
                   delta="Good" if relevance >= 7 else "Needs Improvement" if relevance <= 5 else None)
        
        # Display feedback in a highlighted box
        if 'overall_feedback' in assessment:
            st.markdown("#### Feedback")
            st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px;'>{assessment['overall_feedback']}</div>", unsafe_allow_html=True)

    # Check for LinkedIn enrichment
    parsed_data = file_result.get('data', {})
    personal_info = parsed_data.get('personal_info', {})
    
    # Debug expander to see LinkedIn fields in agent results
    with st.expander("Debug - Agent Results Personal Info", expanded=False):
        st.write(personal_info)
    
    # Check for LinkedIn fields under various possible names
    linkedin_url = None
    for field in ['linkedin', 'linkedin_url', 'linkedinurl']:
        if field in personal_info and personal_info[field]:
            linkedin_url = personal_info[field]
            break
    
    if linkedin_url:
        # Clean the URL
        linkedin_url = re.sub(r'\s+', '', linkedin_url)  # Remove spaces
        # Ensure proper URL format
        if not linkedin_url.startswith('http'):
            if linkedin_url.startswith('www.'):
                linkedin_url = f"https://{linkedin_url}"
            elif linkedin_url.startswith('linkedin.com'):
                linkedin_url = f"https://www.{linkedin_url}"
            elif 'linkedin.com' not in linkedin_url:
                linkedin_url = f"https://www.linkedin.com/in/{linkedin_url}"
                
        # Display with cleaner URL text
        display_linkedin = linkedin_url.replace('https://', '')
        st.markdown("### 🔍 LinkedIn Enrichment")
        st.success(f"Found LinkedIn profile: [{display_linkedin}]({linkedin_url})")

    else:
        st.markdown("### 🔍 LinkedIn Enrichment")
        st.warning("No LinkedIn profile found. Please configure web search API keys for this feature.")

    # Safely get market alignment
    alignment = file_result.get('market_alignment')
    if alignment and isinstance(alignment, dict):
        st.markdown("### 📈 Market Alignment Analysis")

        matching_skills = alignment.get('matching_skills', [])
        missing_skills = alignment.get('missing_skills', [])

        col1, col2 = st.columns(2)
        col1.metric("Matching Skills", f"{len(matching_skills)}", 
                  delta="Good" if len(matching_skills) > len(missing_skills) else None)
                  
        col2.metric("Missing Skills", f"{len(missing_skills)}", 
                  delta="Improvement Needed" if len(missing_skills) > 2 else "Good" if len(missing_skills) <= 2 else None,
                  delta_color="inverse")

        # Show the actual skills
        if matching_skills:
            with st.expander("View Matching Skills", expanded=False):
                st.write(", ".join(f"`{skill}`" for skill in matching_skills))
                
        if missing_skills:
            with st.expander("View Missing Skills", expanded=False):
                st.write(", ".join(f"`{skill}`" for skill in missing_skills))

        # Display commentary in a highlighted box
        if 'commentary' in alignment:
            st.markdown("#### Market Feedback")
            st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px;'>{alignment['commentary']}</div>", unsafe_allow_html=True)
            
    # Display skill suggestions if available
    skill_suggestions = file_result.get('skill_suggestions')
    if skill_suggestions and isinstance(skill_suggestions, dict):
        st.markdown("### 🚀 Skill Enhancement Suggestions")
        st.info("Based on the candidate's experience, here are suggested skills to enhance their profile:")
        
        # Technical skills
        tech_skills = skill_suggestions.get('technical_skills', [])
        if tech_skills:
            st.markdown("#### Technical Skills to Add")
            skill_cols = st.columns(3)
            for i, skill in enumerate(tech_skills):
                col_idx = i % 3
                skill_cols[col_idx].markdown(f"💻 {skill}")
        
        # Soft skills
        soft_skills = skill_suggestions.get('soft_skills', [])
        if soft_skills:
            st.markdown("#### Soft Skills to Highlight")
            skill_cols = st.columns(3)
            for i, skill in enumerate(soft_skills):
                col_idx = i % 3
                skill_cols[col_idx].markdown(f"🧩 {skill}")
                
        # Certifications
        certifications = skill_suggestions.get('certifications', [])
        if certifications:
            st.markdown("#### Recommended Certifications")
            for cert in certifications:
                st.markdown(f"🏅 {cert}")
                
        # Recommendations
        recommendations = skill_suggestions.get('recommendations', '')
        if recommendations:
            st.markdown("#### Career Development Advice")
            st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px;'>{recommendations}</div>", unsafe_allow_html=True)

    st.info("Review the extracted details below. You can edit any field before saving the candidate.")
    
    # Add interactive follow-up questions feature
    with st.expander("Ask AI about this candidate"):
        follow_up_question = st.text_input("Ask a question about this candidate:", 
                                        placeholder="E.g., What are this candidate's strongest skills?")
        if st.button("Submit Question") and follow_up_question:
            with st.spinner("Analyzing..."):
                try:
                    # Prepare API request
                    payload = {
                        "question": follow_up_question,
                        "candidate_data": file_result.get('data', {}),
                        "context": {
                            "quality_assessment": file_result.get('quality_assessment', {}),
                            "market_alignment": file_result.get('market_alignment', {}),
                            "skill_suggestions": file_result.get('skill_suggestions', {})
                        }
                    }
                    
                    # Make request to backend API
                    response = requests.post(
                        f"{BACKEND_URL}/api/assistant/candidate-question", 
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        answer = response.json().get('answer')
                        st.markdown(f"""<div style='background-color: #f0f7fb; 
                                      border-left: 5px solid #2196F3; 
                                      padding: 10px; 
                                      border-radius: 3px;'>
                                      {answer}
                                      </div>""", unsafe_allow_html=True)
                    else:
                        st.error(f"Error getting answer: {response.text}")
                except Exception as e:
                    logger.error(f"Error during follow-up question analysis: {e}", exc_info=True)
                    st.error(f"Failed to analyze question: {e}")


# No separate confirm_resume function needed anymore

if __name__ == "__main__":
    # Add basic app structure if running this module directly (optional)
    st.set_page_config(layout="wide")
    upload_resume()
