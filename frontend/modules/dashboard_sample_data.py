def generate_sample_data():
    """
    Generate sample dashboard data for recruiter and hiring manager dashboards.
    Returns a dict with mock jobs, tasks, and metrics.
    """
    import datetime
    jobs = [
        {"title": "Software Engineer", "department": "Engineering", "status": "Open", "posted": datetime.datetime.now().isoformat(), "open_positions": 3, "applications": 24},
        {"title": "Data Scientist", "department": "Data", "status": "Closed", "posted": datetime.datetime.now().isoformat(), "open_positions": 0, "applications": 18},
        {"title": "Product Manager", "department": "Product", "status": "Open", "posted": datetime.datetime.now().isoformat(), "open_positions": 2, "applications": 30},
    ]
    tasks = [
        {"title": "Screen resumes", "job": "Software Engineer", "due": "2025-07-01"},
        {"title": "Schedule interviews", "job": "Product Manager", "due": "2025-07-02"},
    ]
    metrics = {
        "total_jobs": len(jobs),
        "open_jobs": sum(1 for j in jobs if j["status"] == "Open"),
        "closed_jobs": sum(1 for j in jobs if j["status"] == "Closed"),
        "tasks": len(tasks)
    }
    return {
        "jobs": jobs,
        "tasks": tasks,
        "metrics": metrics
    }
