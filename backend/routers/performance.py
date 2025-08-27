"""
Performance monitoring router for RecruitIQ Backend
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import time
import psutil
import os

router = APIRouter()

@router.get("/performance/startup")
def get_startup_performance():
    """Get startup performance metrics."""
    try:
        from backend.utils.startup_optimizer import get_startup_summary
        return get_startup_summary()
    except ImportError:
        raise HTTPException(status_code=500, detail="Startup optimizer not available")

@router.get("/performance/system")
def get_system_performance():
    """Get current system performance metrics."""
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        
        # Get process info
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        return {
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            },
            "process": {
                "memory_rss": process_memory.rss,
                "memory_vms": process_memory.vms,
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")

@router.get("/performance/health")
def get_performance_health():
    """Get overall performance health status."""
    try:
        from backend.utils.startup_optimizer import startup_timer
        
        # Get system metrics
        system_metrics = get_system_performance()
        
        # Determine health status
        health_status = "healthy"
        warnings = []
        
        # Check CPU usage
        if system_metrics["cpu_percent"] > 80:
            health_status = "warning"
            warnings.append("High CPU usage")
        
        # Check memory usage
        if system_metrics["memory"]["percent"] > 85:
            health_status = "warning"
            warnings.append("High memory usage")
        
        # Check disk usage
        if system_metrics["disk"]["percent"] > 90:
            health_status = "critical"
            warnings.append("High disk usage")
        
        # Check startup time
        if hasattr(startup_timer, 'total_time') and startup_timer.total_time > 10:
            warnings.append("Slow startup time")
        
        return {
            "status": health_status,
            "warnings": warnings,
            "system_metrics": system_metrics,
            "startup_time": getattr(startup_timer, 'total_time', None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance health: {str(e)}") 