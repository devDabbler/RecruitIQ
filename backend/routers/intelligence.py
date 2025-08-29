from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
from pydantic import BaseModel

from ..utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence")


class SalaryBenchmarkRequest(BaseModel):
    job_title: str
    location: str
    experience_level: Optional[str] = None


@router.get("/salary-benchmark")
async def get_salary_benchmark(
    job_title: str = Query(..., description="Job title to research"),
    location: str = Query(..., description="Location for salary data"),
    experience_level: Optional[str] = Query(None, description="Experience level (entry, mid, senior, lead)"),
    db: Session = Depends(get_db)
):
    """Get comprehensive salary benchmark for a job title and location."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.get_comprehensive_salary_benchmark(
            job_title=job_title,
            location=location,
            experience_level=experience_level
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in salary benchmark endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark_salary")
async def post_salary_benchmark(payload: SalaryBenchmarkRequest, db: Session = Depends(get_db)):
    """POST endpoint to match frontend. Returns structure the UI expects."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.get_comprehensive_salary_benchmark(
            job_title=payload.job_title,
            location=payload.location,
            experience_level=payload.experience_level,
        )

        if result.get("status") == "success":
            return {"status": "completed", "benchmark": result.get("data")}
        else:
            # Keep consistent error handling
            raise HTTPException(status_code=500, detail=result.get("message", "Failed to fetch salary benchmark"))

    except Exception as e:
        logger.error(f"Error in POST salary benchmark endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/city-viability")
async def get_city_viability_report(
    role: str = Query(..., description="Job role/title to research"),
    city: str = Query(..., description="City to analyze"),
    seniority: Optional[str] = Query(None, description="Seniority level (entry, mid, senior, lead)"),
    time_range: Optional[str] = Query(None, description="Time range (e.g., '6 months', '12 months')"),
    include_actions: bool = Query(True, description="Include actionable sourcing tactics"),
    db: Session = Depends(get_db)
):
    """Generate a comprehensive city viability snapshot for sourcing a role."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_city_viability_report(
            role=role,
            city=city,
            seniority=seniority,
            time_range=time_range,
            include_actions=include_actions
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in city viability endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/city-comparison")
async def get_city_comparison(
    role: str = Query(..., description="Job role/title to research"),
    city1: str = Query(..., description="First city (typically non-tech hub)"),
    city2: str = Query(..., description="Second city (typically tech hub)"),
    seniority: Optional[str] = Query(None, description="Seniority level"),
    db: Session = Depends(get_db)
):
    """Generate a two-city comparison for sourcing viability."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_city_comparison(
            role=role,
            city1=city1,
            city2=city2,
            seniority=seniority
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in city comparison endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/non-tech-hub-shortlist")
async def get_non_tech_hub_shortlist(
    role: str = Query(..., description="Job role/title to research"),
    num_cities: int = Query(5, description="Number of cities to include in shortlist"),
    db: Session = Depends(get_db)
):
    """Generate a shortlist of top non-tech hub US cities for sourcing a role."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_non_tech_hub_shortlist(
            role=role,
            num_cities=num_cities
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in non-tech hub shortlist endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sourcing-plan")
async def get_sourcing_plan(
    role: str = Query(..., description="Job role/title to source"),
    city: str = Query(..., description="Target city for sourcing"),
    db: Session = Depends(get_db)
):
    """Generate a detailed sourcing plan for a role in a specific city."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_sourcing_plan(
            role=role,
            city=city
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in sourcing plan endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hiring-manager-briefing")
async def get_hiring_manager_briefing(
    role: str = Query(..., description="Job role/title to hire"),
    city: str = Query(..., description="Target city for hiring"),
    db: Session = Depends(get_db)
):
    """Generate a 1-page briefing for hiring managers on hiring challenges."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_hiring_manager_briefing(
            role=role,
            city=city
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in hiring manager briefing endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/json-report")
async def get_json_report(
    role: str = Query(..., description="Job role/title to research"),
    city: str = Query(..., description="Target city"),
    time_range: Optional[str] = Query(None, description="Time range"),
    db: Session = Depends(get_db)
):
    """Generate JSON-only data for dashboards and integrations."""
    try:
        from backend.services.service_registry import provide_market_research_service
        market_research_service = provide_market_research_service()

        result = await market_research_service.generate_json_report(
            role=role,
            city=city,
            time_range=time_range
        )

        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])

    except Exception as e:
        logger.error(f"Error in JSON report endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
