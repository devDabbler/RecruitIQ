# frontend/modules/tasks_page.py
import streamlit as st
from datetime import datetime
import asyncio
from utils.session_utils import get_user_tier

def page():
    """Display tasks page with detailed task information and management features"""
    st.markdown("# 📝 Tasks")
    st.markdown("### Manage your recruiting tasks and priorities")
    
    # Define tabs for task organization
    tab1, tab2, tab3 = st.tabs(["All Tasks", "Due Today", "Completed"])
    
    with tab1:
        display_task_list(tab_context="all")
    
    with tab2:
        display_task_list(filter_today=True, tab_context="today")
    
    with tab3:
        display_completed_tasks()
    
    # Task Creation Section
    st.markdown("---")
    st.subheader("Create New Task")
    
    col1, col2 = st.columns(2)
    with col1:
        task_title = st.text_input("Task Title")
    with col2:
        priority = st.selectbox("Priority", ["High", "Medium", "Low"])
    
    col1, col2 = st.columns(2)
    with col1:
        due_date = st.date_input("Due Date")
    with col2:
        category = st.selectbox("Category", ["Interview Prep", "Candidate Review", "Job Posting", "Other"])
    
    description = st.text_area("Description")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Create Task", key="create_new_task_btn", use_container_width=True):
            create_task(task_title, priority, due_date, category, description)

def create_task(task_title, priority, due_date, category, description):
    async def create_task_api(api_url, task_title, priority, due_date, category, description):
        endpoint = f"{api_url}/api/tasks/"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(endpoint, json={
                    "title": task_title,
                    "priority": priority,
                    "due_date": due_date.isoformat(),
                    "category": category,
                    "description": description
                })
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            st.error(f"Failed to create task: {e}")
            return None
    
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    with st.spinner("Creating task..."):
        try:
            task = st.experimental_async(create_task_api)(api_url, task_title, priority, due_date, category, description)
            if hasattr(task, "send"):
                task = st.run(task)
            if task:
                st.success(f"Task '{task_title}' created successfully!")
        except Exception as e:
            st.error(f"Failed to create task: {e}")

def display_task_list(filter_today=False, tab_context="default"):
    """Display a list of tasks, optionally filtered by due date"""
    async def fetch_tasks(api_url, filter_today=False, completed=False):
        endpoint = f"{api_url}/api/tasks/"
        params = {}
        if filter_today:
            params['due_today'] = True
        if completed:
            params['completed'] = True
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                return resp.json().get('results', [])
        except Exception as e:
            st.error(f"Failed to fetch tasks: {e}")
            return []
    
    api_url = st.session_state.get("api_url", "http://localhost:8000/api")
    tasks = None
    
    with st.spinner("Loading tasks from backend..."):
        try:
            tasks = st.experimental_async(fetch_tasks)(api_url, filter_today)
            if hasattr(tasks, "send"):
                tasks = st.run(tasks)
        except Exception as e:
            tasks = None
    
    if tasks is None:
        st.warning("Showing demo data. Backend tasks API unavailable.")
        tasks = [
            {
                "id": "task1",
                "title": "Review resume for Software Engineer position",
                "priority": "High",
                "due": "Today, 2PM",
                "due_date": datetime.now(),
                "description": "Review John Smith's resume for the Senior Software Engineer position",
                "category": "Candidate Review",
                "completed": False
            },
            {
                "id": "task2",
                "title": "Schedule final interview with John Smith",
                "priority": "High",
                "due": "Today, 5PM",
                "due_date": datetime.now(),
                "description": "Schedule final interview with John Smith for the Software Engineer position",
                "category": "Interview Prep",
                "completed": False
            },
            {
                "id": "task3",
                "title": "Provide feedback on Marketing Manager candidates",
                "priority": "Medium",
                "due": "Today, EOD",
                "due_date": datetime.now(),
                "description": "Review and provide feedback on the current Marketing Manager candidates",
                "category": "Candidate Review",
                "completed": False
            },
            {
                "id": "task4",
                "title": "Update job description for Product Manager",
                "priority": "Low",
                "due": "Tomorrow",
                "due_date": datetime.now(),
                "description": "Update the job description for the Product Manager position with new requirements",
                "category": "Job Posting",
                "completed": False
            },
            {
                "id": "task5",
                "title": "Check references for DevOps Engineer candidate",
                "priority": "Medium",
                "due": "Tomorrow",
                "due_date": datetime.now(),
                "description": "Call the references for the DevOps Engineer candidate",
                "category": "Candidate Review",
                "completed": False
            }
        ]
    
    # Apply filter if needed
    if filter_today:
        today = datetime.now().date()
        tasks = [task for task in tasks if not task.get('completed', False) and getattr(task.get('due_date'), 'date', lambda: today)() == today]
    
    # Display tasks
    for i, task in enumerate(tasks):
        # Generate a unique expander ID for this task but don't use it as a key parameter
        expander_id = f"{tab_context}_{task['id']}_{i}"
        with st.expander(f"{task['title']} - {task['due']}"):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            priority_color = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
            
            with col1:
                st.markdown(f"**Description:** {task.get('description', 'No description available')}")
                st.markdown(f"**Category:** {task.get('category', 'Uncategorized')}")
            
            with col2:
                st.markdown(f"**Priority:** {priority_color[task['priority']]} {task['priority']}")
            
            with col3:
                st.markdown(f"**Due:** {task['due']}")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("✅ Complete", key=f"complete_{tab_context}_{task['id']}_{i}"):
                    st.success(f"Task '{task['title']}' marked as complete!")
            with col2:
                if st.button("✏️ Edit", key=f"edit_{tab_context}_{task['id']}_{i}"):
                    st.info(f"Editing task '{task['title']}'")
            with col3:
                if st.button("🗑️ Delete", key=f"delete_{tab_context}_{task['id']}_{i}"):
                    st.error(f"Task '{task['title']}' deleted!")

def display_completed_tasks():
    """Display a list of completed tasks"""
    # Demo completed tasks
    completed_tasks = [
        {
            "id": "complete1",
            "title": "Phone screening for Frontend Developer",
            "priority": "Medium",
            "completed_date": "Yesterday",
            "category": "Interview Prep",
            "completed": True
        },
        {
            "id": "complete2",
            "title": "Update job posts on LinkedIn",
            "priority": "Medium",
            "completed_date": "2 days ago",
            "category": "Job Posting",
            "completed": True
        },
        {
            "id": "complete3",
            "title": "Prepare interview questions for Data Scientist role",
            "priority": "High",
            "completed_date": "Last week",
            "category": "Interview Prep",
            "completed": True
        }
    ]
    
    for i, task in enumerate(completed_tasks):
        # Use a combination of id and index to ensure uniqueness
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{task['title']}**")
            st.caption(f"Category: {task['category']}")
        with col2:
            st.caption(f"Completed: {task['completed_date']}")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("↩️ Restore", key=f"restore_completed_{task['id']}_{i}"):
                st.info(f"Task '{task['title']}' restored!")
        with col2:
            if st.button("🗑️ Delete", key=f"delete_completed_{task['id']}_{i}"):
                st.error(f"Task '{task['title']}' permanently deleted!")
        
        st.divider() 