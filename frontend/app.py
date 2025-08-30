# frontend/app.py
import streamlit as st
st.set_page_config(
    page_title="RecruitIQ",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enable hot reloading (dev only). Do not clear caches in normal runs; uncomment only when debugging.
# st.cache_data.clear()
# st.cache_resource.clear()

# Configure Streamlit to watch for file changes
# Configuration moved to .streamlit/config.toml

import streamlit_authenticator as stauth 
import yaml 

import sys
import os
import logging
from pathlib import Path

# Add modules path to system path
sys.path.append(os.path.dirname(__file__))

try:
    # Import all module pages
    from modules import dashboard, resume_upload, metrics, jobs, candidates, assistant
    from modules import market_intel, communications, candidate_matching, company_policies
    from modules import candidate_detail, job_detail, enhanced_matching, transformation
    from modules import candidate_pipeline, tasks_page, interviews_page, cache_management
    
except ImportError as e:
    print(f'ImportError occurred: {e}')
    logging.error(f'ImportError occurred: {e}')
    # Create empty module objects if imports fail
    class EmptyModule: pass
    dashboard = resume_upload = metrics = jobs = candidates = assistant = market_intel = communications = candidate_matching = company_policies = enhanced_matching = transformation = candidate_pipeline = tasks_page = interviews_page = cache_management = EmptyModule()
    dashboard.page = resume_upload.upload_resume = metrics.page = jobs.page = candidates.page = assistant.page = market_intel.page = communications.page = candidate_matching.page = company_policies.page = enhanced_matching.enhanced_matching_tab = transformation.page = candidate_pipeline.page = tasks_page.page = interviews_page.page = cache_management.page = lambda: None
    candidate_detail = job_detail = EmptyModule()
    candidate_detail.page = job_detail.page = lambda: None

# Configure logging with file output for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('frontend.log')  # Removed extra navigation_debug file handler to improve performance
    ]
)
logger = logging.getLogger(__name__)

# Disable navigation debugging logger to avoid performance overhead
nav_logger = logging.getLogger('navigation_debug')
nav_logger.handlers.clear()
nav_logger.setLevel(logging.CRITICAL)
nav_logger.propagate = False

# Load CSS
def load_css():
    """Load and inject CSS from frontend/utils/style.css"""
    try:
        # Get absolute path of app.py, then look for CSS in the utils subdirectory
        script_path = Path(__file__).resolve() # Get absolute path of the script
        css_path = script_path.parent / "utils" / "style.css" # CSS is now in frontend/utils/
        logger.info(f"Loading CSS from {css_path}, exists: {css_path.exists()}")
        
        if css_path.exists():
            with open(css_path) as css_file:
                css_content = css_file.read()
                st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        else:
            # Updated warning to show the path being checked
            st.warning(f"Custom style.css not found at {css_path}. Using default styles.")
    except Exception as e:
        logger.error(f"Error loading CSS from {css_path}: {e}")
        st.warning("Could not load custom CSS due to an error. Using default styles.")

# --- Credential Loading & Authenticator Initialization ---
# Using placeholder credentials directly in the script as config.yaml is missing
# TODO: Move credentials to a secure configuration file (e.g., .streamlit/secrets.toml or a YAML file)

# Password must be hashed. You can generate hashes using:
# import streamlit_authenticator as stauth
# hashed_passwords = stauth.Hasher(['your_password']).generate()
# print(hashed_passwords) -> ['$2b$12$yT6i6rTSHcs4poDhCgPB/Oj2FATdQXOnmTt5eLrelgKXUFMjI5S/u', '$2b$12$...']
# Replace 'your_hashed_password' below with the output

credentials = {
    "usernames": {
        "testuser": {
            "email": "test@example.com",
            "name": "Test User",
            "password": "$2b$12$yT6i6rTSHcs4poDhCgPB/Oj2FATdQXOnmTt5eLrelgKXUFMjI5S/u", # Hash for 'password'
        }
    }
}

cookie_name = "recruitiq_auth_cookie"
cookie_key = "random_secret_key_123" # Use a strong, random key
cookie_expiry_days = 30

authenticator = stauth.Authenticate(
    credentials,
    cookie_name,
    cookie_key,
    cookie_expiry_days
)

# Initialize session state variables (crucial for authenticator)
def initialize_session_state():
    # Ensure authentication_status exists, default to None if not set by authenticator
    if "authentication_status" not in st.session_state:
        st.session_state.authentication_status = None
    if "name" not in st.session_state:
        st.session_state.name = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "user_tier" not in st.session_state:
        st.session_state.user_tier = "basic"

    # Keep existing initializations
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
    if "previous_page" not in st.session_state:
        st.session_state.previous_page = st.session_state.current_page
    if "view_handled" not in st.session_state:
        st.session_state.view_handled = False
    # Initialize API URL for backend communication
    if "api_url" not in st.session_state:
        st.session_state.api_url = "http://localhost:8000"

initialize_session_state()

# --- Page Imports (Lazy Loading Setup) ---
# Define page modules paths relative to the frontend directory
page_modules = {
    "dashboard": {"icon": "📊", "title": "Dashboard", "func": dashboard.page},
    "resume_upload": {"icon": "📄", "title": "Resume Upload", "func": resume_upload.upload_resume},
    "metrics": {"icon": "📈", "title": "Recruitment Analytics", "func": metrics.page},
    "jobs": {"icon": "💼", "title": "Jobs", "func": jobs.page},
    "candidates": {"icon": "👥", "title": "Candidates", "func": candidates.page},
    "assistant": {"icon": "🤖", "title": "AI Assistant", "func": assistant.page},
    "market_intel": {"icon": "🔍", "title": "Market Intelligence", "func": market_intel.page},
    "communications": {"icon": "📱", "title": "Communications", "func": communications.page},
    "candidate_matching": {"icon": "🔄", "title": "Candidate Matching", "func": candidate_matching.page},
    "enhanced_matching": {"icon": "✨", "title": "Advanced Matching", "func": enhanced_matching.page},
    "company_policies": {"icon": "📝", "title": "Company Policies", "func": company_policies.page},
    "transformation": {"icon": "🔄", "title": "Data Transformation", "func": transformation.page},
    "candidate_pipeline": {"icon": "⏩", "title": "Candidate Pipeline", "func": candidate_pipeline.page},
    # New pages for tasks and interviews
    "tasks_page": {"icon": "✅", "title": "Tasks", "func": tasks_page.page},
    "interviews_page": {"icon": "🗓️", "title": "Interviews", "func": interviews_page.page},
    "cache_management": {"icon": "⚡", "title": "Cache Management", "func": cache_management.page},
    # Detail views (not shown in sidebar)
    "candidate_detail": {"icon": "👤", "title": "Candidate Details", "func": candidate_detail.page, "show_in_sidebar": False},
    "job_detail": {"icon": "🔎", "title": "Job Details", "func": job_detail.page, "show_in_sidebar": False},

}

# --- Module Categories (Based on Refactor Plan and Existing Files) ---
MODULE_CATEGORIES = {
    "core": {
        "icon": "🏢",
        "title": "Core Platform",
        "modules": ["dashboard", "candidates", "jobs", "resume_upload", "metrics", "candidate_matching", "candidate_pipeline", "tasks_page", "interviews_page"]
    },
    "transformation": {
        "icon": "🔄",
        "title": "Data Transformation",
        "modules": ["transformation"]
    },
    "premium": {
        "icon": "⭐",
        "title": "Premium Features",
        "modules": ["enhanced_matching", "market_intel", "assistant"]
    },
    "admin": {
        "icon": "⚙️",
        "title": "Administration",
        "modules": ["communications", "company_policies", "cache_management"]
    }
}

# Build sidebar navigation
def build_sidebar_navigation():
    """Build the categorized sidebar navigation menu based on the application mode."""
    with st.sidebar:
        st.markdown("<div class='sidebar-header'>RecruitIQ</div>", unsafe_allow_html=True)
        
        if st.session_state.get("authentication_status"):
            user_name = st.session_state.get("name", "User")
            user_email = credentials["usernames"][st.session_state.get("username", "")].get("email", "")
            user_tier = st.session_state.get("user_tier", "basic")
            st.markdown(f'''
            <div class="user-profile">
                <div class="user-avatar">{user_name[0].upper()}</div>
                <div class="user-info">
                    <div class="user-name">{user_name}</div>
                    <div class="user-email">{user_email}</div>
                    <div class="user-tier">{user_tier.title()} Plan</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
        st.markdown("---")

        st.markdown("---")
        
        for category_id, category in MODULE_CATEGORIES.items():
            visible_modules = [m for m in category['modules'] if m in page_modules and page_modules[m].get("show_in_sidebar", True)]
            if visible_modules:
                st.markdown(f"### {category['icon']} {category['title']}")
                for module_id in visible_modules:
                    page_info = page_modules[module_id]
                    if st.button(f"{page_info['icon']} {page_info['title']}", key=f"nav_{module_id}", use_container_width=True):
                        if st.session_state.current_page != module_id:
                            st.session_state.current_page = module_id
                            st.rerun()
        
        if st.session_state.get("authentication_status"):
            st.markdown("---")
            authenticator.logout('Logout', 'sidebar', key='auth_logout_sidebar')

# Main application function
def main():
    """Main application function."""
    # NAVIGATION DEBUGGING - Entry point
    nav_logger.info("="*80)
    nav_logger.info("MAIN FUNCTION CALLED")
    nav_logger.info("="*80)
    nav_logger.info(f"Timestamp: {datetime.datetime.now()}")
    
    # Initialize session state for navigation if it doesn't exist
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
        nav_logger.info("Initialized current_page to 'dashboard'")
    
    # Log current session state
    nav_logger.info("Session State at Entry:")
    for key, value in st.session_state.items():
        if key.startswith(('current_page', 'selected_', 'view_', 'api_')):
            nav_logger.info(f"  {key}: {value}")
    
    # Check for view parameter in URL query parameters
    view = st.query_params.get("view", None)
    job_id = st.query_params.get("id", None)
    
    nav_logger.info(f"URL Parameters: view={view}, id={job_id}")
    
    # Check for pending navigation in session state (fallback if query params don't work)
    pending_nav_page = st.session_state.get("pending_navigation_page", None)
    pending_nav_id = st.session_state.get("pending_navigation_id", None)
    
    nav_logger.info(f"Session State Navigation: page={pending_nav_page}, id={pending_nav_id}")
    
    # Handle job detail navigation via view parameter OR session state
    if (view == "job_detail" and job_id) or (pending_nav_page == "job_detail" and pending_nav_id):
        nav_logger.info("DETECTED JOB DETAIL NAVIGATION REQUEST")
        
        # Use URL params if available, otherwise use session state
        final_job_id = job_id if job_id else pending_nav_id
        nav_logger.info(f"  view parameter: {view}")
        nav_logger.info(f"  id parameter: {job_id}")
        nav_logger.info(f"  pending_nav_page: {pending_nav_page}")
        nav_logger.info(f"  pending_nav_id: {pending_nav_id}")
        nav_logger.info(f"  final_job_id: {final_job_id}")
        nav_logger.info(f"  view_handled flag: {st.session_state.get('view_handled', False)}")
        
        if not st.session_state.get("view_handled", False):
            nav_logger.info("Processing job detail navigation...")
            st.session_state.current_page = "job_detail"
            st.session_state.selected_job_id = str(final_job_id)
            st.session_state.view_handled = True
            
            # Clear pending navigation
            if "pending_navigation_page" in st.session_state:
                del st.session_state["pending_navigation_page"]
            if "pending_navigation_id" in st.session_state:
                del st.session_state["pending_navigation_id"]
            
            nav_logger.info(f"SET: current_page = 'job_detail'")
            nav_logger.info(f"SET: selected_job_id = '{final_job_id}'")
            nav_logger.info(f"SET: view_handled = True")
            nav_logger.info("CLEARED: pending navigation state")
            logger.info(f"Navigating to job detail page for ID: {final_job_id}")
        else:
            nav_logger.info("Job detail navigation already handled, skipping...")
    
    # Handle candidate detail navigation via view parameter OR session state
    elif (view == "candidate_detail" and job_id) or (pending_nav_page == "candidate_detail" and pending_nav_id):
        nav_logger.info("DETECTED CANDIDATE DETAIL NAVIGATION REQUEST")
        
        # Use URL params if available, otherwise use session state
        final_candidate_id = job_id if job_id else pending_nav_id  # Note: using job_id param for candidate ID
        nav_logger.info(f"  view parameter: {view}")
        nav_logger.info(f"  id parameter: {job_id}")
        nav_logger.info(f"  pending_nav_page: {pending_nav_page}")
        nav_logger.info(f"  pending_nav_id: {pending_nav_id}")
        nav_logger.info(f"  final_candidate_id: {final_candidate_id}")
        nav_logger.info(f"  view_handled flag: {st.session_state.get('view_handled', False)}")
        
        if not st.session_state.get("view_handled", False):
            nav_logger.info("Processing candidate detail navigation...")
            st.session_state.current_page = "candidate_detail"
            st.session_state.selected_candidate_id = str(final_candidate_id)
            st.session_state.view_handled = True
            
            # Clear pending navigation
            if "pending_navigation_page" in st.session_state:
                del st.session_state["pending_navigation_page"]
            if "pending_navigation_id" in st.session_state:
                del st.session_state["pending_navigation_id"]
            
            nav_logger.info(f"SET: current_page = 'candidate_detail'")
            nav_logger.info(f"SET: selected_candidate_id = '{final_candidate_id}'")
            nav_logger.info(f"SET: view_handled = True")
            nav_logger.info("CLEARED: pending navigation state")
            logger.info(f"Navigating to candidate detail page for ID: {final_candidate_id}")
        else:
            nav_logger.info("Candidate detail navigation already handled, skipping...")
    
    # Legacy: Check if there's a candidate ID in query params to show candidate detail (for backwards compatibility)
    elif job_id and not view:
        nav_logger.info("DETECTED LEGACY NAVIGATION REQUEST")
        nav_logger.info(f"  id parameter: {job_id}")
        nav_logger.info(f"  view_handled flag: {st.session_state.get('view_handled', False)}")
        
        if not st.session_state.get("view_handled", False):
            nav_logger.info("Processing legacy navigation...")
            # Navigate to candidate detail page
            st.session_state.current_page = "candidate_detail"
            st.session_state.selected_candidate_id = str(job_id)
            st.session_state.view_handled = True
            nav_logger.info(f"SET: current_page = 'candidate_detail'")
            nav_logger.info(f"SET: selected_candidate_id = '{job_id}'")
            nav_logger.info(f"SET: view_handled = True")
            logger.info(f"Navigating to candidate detail page for ID: {job_id}")
        else:
            nav_logger.info("Legacy navigation already handled, skipping...")
    
    # Reset view_handled flag when navigating to different pages without query params
    elif not view and not job_id and not pending_nav_page and st.session_state.get("view_handled", False):
        nav_logger.info("RESETTING VIEW_HANDLED FLAG")
        st.session_state.view_handled = False
        nav_logger.info("SET: view_handled = False")
        logger.info("Reset view_handled flag - no query params present")
    else:
        nav_logger.info("NO NAVIGATION LOGIC TRIGGERED")
    
    # Track previous page to detect page changes
    if "previous_page" not in st.session_state:
        st.session_state.previous_page = st.session_state.current_page
        nav_logger.info(f"Initialized previous_page to '{st.session_state.current_page}'")
    
    # Detect page changes
    if st.session_state.previous_page != st.session_state.current_page:
        nav_logger.info("PAGE CHANGE DETECTED")
        nav_logger.info(f"  Previous page: {st.session_state.previous_page}")
        nav_logger.info(f"  Current page: {st.session_state.current_page}")
        st.session_state.previous_page = st.session_state.current_page
    
    # Get user info using new st.user feature if available
    try:
        if hasattr(st, 'user') and st.user is not None:
            # We could potentially use this to update the credentials dynamically
            # Or store additional user metadata
            if "email" in st.user:
                st.session_state.user_email = st.user.email
            
            # Get IP address from st.context if available
            if hasattr(st, 'context') and hasattr(st.context, 'ip_address'):
                st.session_state.user_ip = st.context.ip_address
    except Exception as e:
        logger.error(f"Error accessing st.user: {e}")
    
    # Create a modern welcome header with user information
    if st.session_state.get("name"):
        st.markdown(f"""
        <div class="welcome-header">
            <div class="welcome-text">Welcome back, <span class="user-highlight">{st.session_state["name"]}</span></div>
            <div class="welcome-date">{datetime.datetime.now().strftime('%A, %B %d, %Y')}</div>
        </div>
        """, unsafe_allow_html=True)

    # Set data-page attribute on body for CSS targeting
    current_page = st.session_state.current_page
    nav_logger.info(f"FINAL CURRENT PAGE: {current_page}")
    
    st.markdown(f"""
    <script>
        document.body.setAttribute('data-page', '{current_page}');
        // Force layout recalculation
        document.body.style.display = 'none';
        document.body.offsetHeight; // Trigger reflow
        document.body.style.display = '';
    </script>
    """, unsafe_allow_html=True)

    # Create sidebar navigation without caching
    build_sidebar_navigation() # Display sidebar with logout button

    # Render the current page's title
    if st.session_state.current_page in page_modules:
        page_title = page_modules[st.session_state.current_page].get("title", "")
        if page_title:
            st.title(page_title)

    # Execute the page function
    page_func = page_modules.get(st.session_state.current_page, {}).get("func")
    if page_func:
        try:
            nav_logger.info(f"EXECUTING PAGE FUNCTION: {page_func.__module__}.{page_func.__name__}")
            page_func() # Execute the page function
            nav_logger.info(f"PAGE FUNCTION COMPLETED: {current_page}")
        except Exception as e:
            logger.error(f"Error running page {current_page}: {e}", exc_info=True)
            nav_logger.error(f"PAGE FUNCTION ERROR: {current_page} - {e}")
            st.error(f"An error occurred while loading the page: {e}")
    else:
        nav_logger.warning(f"NO FUNCTION ASSIGNED TO PAGE: {current_page}")
        st.warning(f"Page '{current_page}' is defined but has no function assigned.")
    
    nav_logger.info("="*80)
    nav_logger.info("MAIN FUNCTION COMPLETED")
    nav_logger.info("="*80)

# --- Authentication Logic and Main App Flow ---
# First, let's handle authentication
authenticator.login()

# Now apply CSS after authentication UI has been rendered but before content
load_css()

# Import datetime for the welcome header
import datetime

# Only proceed with the app logic if the user is authenticated
if st.session_state['authentication_status']:
    # Only show content if authenticated
    main()
elif st.session_state['authentication_status'] is False:
    st.error('Username/password is incorrect')
elif st.session_state['authentication_status'] is None:
    st.warning('Please enter your username and password')
