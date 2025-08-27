"""
Startup Optimizer for RecruitIQ Backend
This module provides utilities to monitor and optimize backend startup performance.
"""

import time
import logging
import functools
from typing import Dict, List, Callable, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class StartupTimer:
    """Timer class to track startup performance."""
    
    def __init__(self):
        self.start_time = None
        self.checkpoints: Dict[str, float] = {}
        self.total_time = 0
    
    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        self.checkpoints.clear()
        logger.info("🚀 Starting backend initialization timer...")
    
    def checkpoint(self, name: str):
        """Record a checkpoint with timing information."""
        if self.start_time is None:
            logger.warning("Timer not started, cannot record checkpoint")
            return
        
        current_time = time.time()
        self.checkpoints[name] = current_time - self.start_time
        
        if len(self.checkpoints) > 1:
            # Calculate time since last checkpoint
            checkpoint_names = list(self.checkpoints.keys())
            last_checkpoint = checkpoint_names[-2]
            time_since_last = self.checkpoints[name] - self.checkpoints[last_checkpoint]
            logger.info(f"⏱️  {name}: {time_since_last:.2f}s (total: {self.checkpoints[name]:.2f}s)")
        else:
            logger.info(f"⏱️  {name}: {self.checkpoints[name]:.2f}s")
    
    def finish(self):
        """Finish timing and log summary."""
        if self.start_time is None:
            return
        
        self.total_time = time.time() - self.start_time
        logger.info(f"✅ Backend startup completed in {self.total_time:.2f} seconds")
        
        # Log breakdown
        if self.checkpoints:
            logger.info("📊 Startup breakdown:")
            for name, duration in self.checkpoints.items():
                percentage = (duration / self.total_time) * 100
                logger.info(f"   • {name}: {duration:.2f}s ({percentage:.1f}%)")

# Global timer instance
startup_timer = StartupTimer()

def time_startup_phase(phase_name: str):
    """Decorator to time a startup phase."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"⏱️  {phase_name}: {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {phase_name} failed after {duration:.2f}s: {e}")
                raise
        return wrapper
    return decorator

@contextmanager
def startup_phase(phase_name: str):
    """Context manager for timing startup phases."""
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        logger.info(f"⏱️  {phase_name}: {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ {phase_name} failed after {duration:.2f}s: {e}")
        raise

def optimize_imports():
    """Optimize import performance by pre-loading only essential modules."""
    logger.info("🔧 Optimizing imports...")
    
    # Only import essential modules during startup
    # Heavy modules will be loaded lazily when needed
    with startup_phase("Essential imports"):
        # Core modules only
        import backend.models.models
        import backend.utils.database

def lazy_load_heavy_modules():
    """Lazy load heavy modules that aren't needed immediately."""
    logger.info("🔄 Lazy loading heavy modules...")
    
    with startup_phase("Lazy module loading"):
        # These will be loaded when first accessed
        import backend.services.llm_service
        import backend.services.service_registry

def check_startup_performance():
    """Check if startup performance is within acceptable limits."""
    if startup_timer.total_time > 10:
        logger.warning(f"⚠️  Startup took {startup_timer.total_time:.2f}s - consider optimization")
        return False
    elif startup_timer.total_time > 5:
        logger.info(f"ℹ️  Startup took {startup_timer.total_time:.2f}s - acceptable performance")
        return True
    else:
        logger.info(f"🎉 Excellent startup performance: {startup_timer.total_time:.2f}s")
        return True

def get_startup_summary() -> Dict[str, Any]:
    """Get a summary of startup performance."""
    return {
        "total_time": startup_timer.total_time,
        "checkpoints": startup_timer.checkpoints,
        "performance_acceptable": check_startup_performance()
    } 