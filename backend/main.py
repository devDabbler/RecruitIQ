# Windows compatibility (mock Unix-only pwd module) must load before deps that need it
import backend.utils.win_compat  # noqa: F401

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
from fastapi import Depends, FastAPI
from backend.routers import matching, jobs, candidates, resume, assistant, crawler, enhanced_matching, intelligence
from backend.routers import auth, tasks, interviews, pitches, agent, performance, cache
from backend.api.routes import job_routes
from backend.utils.auth import enforce_read_only

# The read-only gate is an application-level dependency, not a per-route one, so
# a route added later is refused for the demo role by default instead of being
# quietly exposed. See backend/utils/auth.py for the read-only-POST allowlist.
app = FastAPI(dependencies=[Depends(enforce_read_only)])

# Import service registry and agent framework - this will handle all service initialization
from backend.services.service_registry import provide_llm_service
from backend.services.agent_framework import initialize_agents

# Sync (`def`) endpoints run in Starlette's threadpool, which defaults to 40
# workers - more than the 30 connections our engine can hand out (pool_size 10 +
# max_overflow 20). Left alone, enough concurrent requests would queue on
# connection checkout and 500 after pool_timeout. Capping the threadpool below
# the pool ceiling means concurrency is bounded where it is cheap (a waiting
# thread) instead of where it is expensive (a failed request), and it keeps this
# process's Postgres connection count predictable on a shared droplet.
THREADPOOL_LIMIT = 24


@app.on_event("startup")
async def limit_threadpool():
    import anyio.to_thread

    anyio.to_thread.current_default_thread_limiter().total_tokens = THREADPOOL_LIMIT


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
app.include_router(auth.router)
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
