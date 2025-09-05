"""Lightweight shim for ExperienceAnalysisService expected by tests.

This provides minimal async methods used by demos/tests. It intentionally
doesn't perform heavy computation or external API calls.
"""
from typing import Dict, Any

class ExperienceAnalysisService:
    """Minimal experience analysis service for test import compatibility."""

    async def analyze_candidate_experience(self, candidate_id: int, db) -> Dict[str, Any]:
        # Return a conservative analysis shape expected by consumers
        return {
            "experience_count": 0,
            "total_achievements": 0,
            "unique_technologies": 0,
            "average_complexity": 0.0,
            "aggregated_achievements": [],
            "aggregated_technologies": {}
        }

    async def analyze_job_requirements(self, job_id: int, db) -> Dict[str, Any]:
        return {
            "required_achievements": [],
            "required_technologies": {},
            "complexity_requirements": 0.0,
            "industry_context": []
        }

__all__ = ["ExperienceAnalysisService"]
