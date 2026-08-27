# Import patches first to ensure cross-platform compatibility
from backend.patches import *

import logging
import time

# Set up more restrictive logging
logging.basicConfig(level=logging.DEBUG)

# Reduce verbosity for specific loggers
loggers_to_quiet = [
    "httpx", "httpcore", "urllib3", "LiteLLM", "pdfminer"
]
for logger_name in loggers_to_quiet:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Import startup optimizer
from backend.utils.startup_optimizer import startup_timer, startup_phase, optimize_imports, lazy_load_heavy_modules

# Import models first to ensure registration
from backend.models import models
from backend.utils.database import Base, engine, verify_postgres_connection

# Import routers
from fastapi import FastAPI
from backend.routers import matching, jobs, candidates, resume, assistant, crawler, enhanced_matching, intelligence
from backend.routers import tasks, interviews, pitches, agent, performance, cache
from backend.api.routes import job_routes

app = FastAPI()

# Import service registry and agent framework - this will handle all service initialization
from backend.services.service_registry import provide_llm_service
from backend.services.agent_framework import initialize_agents

@app.on_event("startup")
def startup_event():
    # Start the startup timer
    startup_timer.start()
    
    try:
        # Optimize imports - only load essential modules
        with startup_phase("Essential imports"):
            optimize_imports()
        
        # Verify PostgreSQL connection
        with startup_phase("PostgreSQL connection"):
            verify_postgres_connection()
        
        # Initialize agent framework
        with startup_phase("Agent framework initialization"):
            initialize_agents()
        
        # Lazy load heavy modules (LLM service will be initialized when first accessed)
        with startup_phase("Lazy module loading"):
            lazy_load_heavy_modules()
        
        # Finish timing and log summary
        startup_timer.finish()
        
    except Exception as e:
        logging.error(f"Backend startup failed: {str(e)}")
        logging.error("This may prevent the candidates page from working properly")
        raise e

# Include routers
app.include_router(matching.router, tags=["matching"])
app.include_router(enhanced_matching.router, tags=["enhanced-matching"])  # New enhanced matching router
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(job_routes.router, tags=["jobs"])  # New job routes with sync functionality
app.include_router(candidates.router, prefix="/api", tags=["candidates"])
app.include_router(resume.router, tags=["resume"])  # Removed prefix because resume.router already has /api/resume prefix
app.include_router(assistant.router, prefix="/api", tags=["assistant"])
# smart_assistant router removed - functionality merged into assistant.py
app.include_router(crawler.router, prefix="/api", tags=["crawler"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(interviews.router, prefix="/api", tags=["interviews"])
app.include_router(pitches.router, prefix="/api", tags=["pitches"])
app.include_router(agent.router, tags=["agent"]) # Agent router
app.include_router(intelligence.router, prefix="/api", tags=["intelligence"])  # Mount under /api to match frontend
app.include_router(performance.router, prefix="/api", tags=["performance"])
app.include_router(cache.router, tags=["cache"]) # Cache management router

# You can add more routers here if needed

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/startup-performance")
def get_startup_performance():
    """Get startup performance metrics."""
    from backend.utils.startup_optimizer import get_startup_summary
    return get_startup_summary()
