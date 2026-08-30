"""Assistant tool definitions — the Phase 2 replacement for intent_processor.py.

Each tool is a (JSON schema, async implementation) pair. The LLM picks tools
via native tool calling (see tool_loop.py); implementations are thin wrappers
over the existing services and ORM queries, so they stay independently
testable without any LLM in the loop.

Spec §4.6: search_candidates, match_to_job, explain_match, get_market_data,
get_candidate, get_job, list_pipeline, get_candidate_resume.
(`get_candidate_resume` stands in for the spec's `parse_resume`: chat has no
file upload, so the useful chat-side capability is reading an already-parsed
resume. Fresh parsing still happens on the upload endpoint.)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema for the arguments object
    run: Callable[..., Awaitable[dict]]


def _candidate_summary(c) -> dict:
    return {
        "id": c.id,
        "name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
        "email": c.email,
        "location": c.location,
        "current_position": c.current_position,
        "current_company": c.current_company,
        "position_applied": c.position_applied,
        "status": c.status,
        "skills": [s.skill_name for s in (c.skills or [])],
    }


def _job_summary(j, include_details: bool = False) -> dict:
    data = {
        "id": j.id,
        "title": j.title,
        "department": j.department,
        "location": j.location,
        "status": j.status,
        "skills": [s.strip() for s in j.skills.split(",")] if getattr(j, "skills", None) else [],
    }
    if include_details:
        data["overview"] = j.job_overview
        data["required_qualifications"] = j.required_qualifications
    return data


def build_assistant_tools(db: Session) -> List[Tool]:
    """Build the tool set bound to this request's DB session."""
    from backend.models.models import Candidate, Job, Resume
    from backend.services.service_registry import get_registry

    registry = get_registry()

    def _vector_service():
        from backend.services.vector_search_service import VectorSearchService

        return VectorSearchService(registry.llm_service.get_embedding_model())

    async def search_candidates(query: str, limit: int = 8, location: Optional[str] = None) -> dict:
        service = _vector_service()
        results = service.search_candidates_by_text(db, query, limit=int(limit), location=location)
        if not results and location and "," in location:
            # "Seattle, WA" misses rows stored as plain "Seattle"; the city
            # alone is the broadest substring that is still a location match.
            city = location.split(",")[0].strip()
            results = service.search_candidates_by_text(db, query, limit=int(limit), location=city)
        out = {"query": query, "candidates": results, "count": len(results)}
        if location:
            out["location_filter"] = location
            if not results:
                out["note"] = (
                    "No candidates matched that location. Consider retrying without "
                    "the location filter and telling the user where the matches actually are."
                )
        return out

    async def get_candidate(candidate: str) -> dict:
        row = db.query(Candidate).filter(Candidate.id == candidate).first()
        if row is None:
            like = f"%{candidate}%"
            row = (
                db.query(Candidate)
                .filter((Candidate.first_name + " " + Candidate.last_name).ilike(like))
                .first()
            )
        if row is None:
            return {"error": f"No candidate found matching {candidate!r}"}
        data = _candidate_summary(row)
        data["has_resume"] = db.query(Resume).filter(Resume.candidate_id == row.id).count() > 0
        return data

    async def get_job(job: str) -> dict:
        row = None
        if str(job).isdigit():
            row = db.query(Job).filter(Job.id == int(job)).first()
        if row is None:
            row = db.query(Job).filter(Job.title.ilike(f"%{job}%")).first()
        if row is None:
            # Semantic fallback: "the ML role" should still find NLP Engineer
            hits = _vector_service().search_jobs_by_text(db, str(job), limit=1)
            if hits:
                row = db.query(Job).filter(Job.id == hits[0]["id"]).first()
        if row is None:
            return {"error": f"No job found matching {job!r}"}
        return _job_summary(row, include_details=True)

    async def match_to_job(job: str, limit: int = 10) -> dict:
        job_info = await get_job(job)
        if "error" in job_info:
            return job_info
        from backend.services.agent_framework.agent_factory import AgentFactory

        agent = AgentFactory.create_agent("matching", matching_integrator=registry.matching_integrator)
        result = await agent.execute(
            {"job_id": job_info["id"], "strategy": "enhanced", "db": db, "min_score": 40.0, "limit": int(limit)}
        )
        if result.get("status") != "completed":
            return {"error": f"Matching failed: {result.get('message')}"}
        matches = result.get("results")
        if isinstance(matches, dict) and "matches" in matches:
            matches = matches["matches"]
        return {
            "job_id": job_info["id"],
            "job_title": job_info["title"],
            "matches": [
                {
                    "id": m.get("id"),
                    "name": m.get("name", ""),
                    "match_score": round(float(m.get("match_score", 0.0)), 1),
                }
                for m in (matches or [])
            ],
        }

    async def explain_match(job: str, candidate: str) -> dict:
        job_info = await get_job(job)
        if "error" in job_info:
            return job_info
        cand_info = await get_candidate(candidate)
        if "error" in cand_info:
            return cand_info
        job_skills = {s.lower() for s in job_info.get("skills", [])}
        cand_skills = {s.lower() for s in cand_info.get("skills", [])}
        overlap = sorted(job_skills & cand_skills)
        missing = sorted(job_skills - cand_skills)
        match_result = await match_to_job(str(job_info["id"]), limit=50)
        score = next(
            (m["match_score"] for m in match_result.get("matches", []) if m["id"] == cand_info["id"]),
            None,
        )
        return {
            "job": {"id": job_info["id"], "title": job_info["title"]},
            "candidate": {"id": cand_info["id"], "name": cand_info["name"]},
            "match_score": score,
            "matching_skills": overlap,
            "missing_skills": missing,
            "candidate_position": cand_info.get("current_position"),
        }

    async def get_market_data(role: str, location: str, experience_level: Optional[str] = None) -> dict:
        service = registry.market_research_service
        data = await service.get_comprehensive_salary_benchmark(role, location, experience_level)
        return data if isinstance(data, dict) else {"result": data}

    async def list_pipeline() -> dict:
        by_status = dict(
            db.query(Candidate.status, func.count(Candidate.id)).group_by(Candidate.status).all()
        )
        top_positions = [
            {"position": p or "(unspecified)", "count": n}
            for p, n in (
                db.query(Candidate.position_applied, func.count(Candidate.id))
                .group_by(Candidate.position_applied)
                .order_by(func.count(Candidate.id).desc())
                .limit(8)
                .all()
            )
        ]
        open_jobs = db.query(Job).filter(Job.status == "open").count()
        return {
            "total_candidates": db.query(Candidate).count(),
            "candidates_by_status": by_status,
            "top_applied_positions": top_positions,
            "open_jobs": open_jobs,
            "total_jobs": db.query(Job).count(),
        }

    async def get_candidate_resume(candidate: str) -> dict:
        cand_info = await get_candidate(candidate)
        if "error" in cand_info:
            return cand_info
        resume = (
            db.query(Resume)
            .filter(Resume.candidate_id == cand_info["id"])
            .order_by(Resume.id.desc())
            .first()
        )
        if resume is None or not resume.parsed_content:
            return {"error": f"No parsed resume on file for {cand_info['name']}"}
        content = resume.parsed_content
        if len(content) > 6000:
            content = content[:6000] + "\n...[truncated]"
        return {"candidate": cand_info["name"], "resume_id": resume.id, "parsed_content": content}

    return [
        Tool(
            name="search_candidates",
            description=(
                "Semantic search over all candidates in the ATS. Call this whenever the user asks to "
                "find, list, or source candidates by skills, role, or free-text description "
                "(e.g. 'machine learning engineers with python'). Matches by meaning, not keywords. "
                "For place-based asks like 'python developers in Seattle', put the skills/role in "
                "query and the place in location; do not put the place in query."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language description of the candidates wanted (skills, role); do not include the location here"},
                    "limit": {"type": "integer", "description": "Max results (default 8)"},
                    "location": {"type": "string", "description": "Optional city/state filter, e.g. 'Seattle' or 'Austin, TX'. Substring match on the candidate's location."},
                },
                "required": ["query"],
            },
            run=search_candidates,
        ),
        Tool(
            name="get_candidate",
            description="Fetch one candidate's full profile (skills, position, status) by id or name. Call this when the user asks about a specific person.",
            parameters={
                "type": "object",
                "properties": {
                    "candidate": {"type": "string", "description": "Candidate id (UUID) or (partial) name"},
                },
                "required": ["candidate"],
            },
            run=get_candidate,
        ),
        Tool(
            name="get_job",
            description="Fetch one job's details by numeric id or (partial/semantic) title. Call this when the user references a specific role or req.",
            parameters={
                "type": "object",
                "properties": {
                    "job": {"type": "string", "description": "Job id or title, e.g. '24' or 'Data Engineer'"},
                },
                "required": ["job"],
            },
            run=get_job,
        ),
        Tool(
            name="match_to_job",
            description="Rank the best-matching candidates for a job using the full matching pipeline (role fit, skill overlap, experience). Call this for 'who should I consider for X' questions.",
            parameters={
                "type": "object",
                "properties": {
                    "job": {"type": "string", "description": "Job id or title"},
                    "limit": {"type": "integer", "description": "Max candidates (default 10)"},
                },
                "required": ["job"],
            },
            run=match_to_job,
        ),
        Tool(
            name="explain_match",
            description="Explain why a specific candidate does or does not fit a specific job: overall score, overlapping skills, missing skills. Call this for 'why is X a good fit for Y' questions.",
            parameters={
                "type": "object",
                "properties": {
                    "job": {"type": "string", "description": "Job id or title"},
                    "candidate": {"type": "string", "description": "Candidate id or name"},
                },
                "required": ["job", "candidate"],
            },
            run=explain_match,
        ),
        Tool(
            name="get_market_data",
            description="Get salary benchmark data for a role in a location. Call this when the user asks about compensation, salary ranges, or market rates.",
            parameters={
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Job title, e.g. 'Data Engineer'"},
                    "location": {"type": "string", "description": "City/region, e.g. 'Seattle, WA'"},
                    "experience_level": {"type": "string", "description": "Optional: entry, mid, senior"},
                },
                "required": ["role", "location"],
            },
            run=get_market_data,
        ),
        Tool(
            name="list_pipeline",
            description="Summarize the recruiting pipeline: candidate counts by status, top applied-for positions, open job count. Call this for 'how many candidates/jobs', pipeline health, or breakdown questions.",
            parameters={"type": "object", "properties": {}},
            run=list_pipeline,
        ),
        Tool(
            name="get_candidate_resume",
            description="Read the parsed resume text on file for a candidate. Call this when the user asks what is on someone's resume or wants their background details.",
            parameters={
                "type": "object",
                "properties": {
                    "candidate": {"type": "string", "description": "Candidate id or name"},
                },
                "required": ["candidate"],
            },
            run=get_candidate_resume,
        ),
    ]


async def execute_tool(tools: List[Tool], name: str, arguments: Dict[str, Any]) -> dict:
    """Execute one tool call, returning an error dict rather than raising."""
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await tool.run(**(arguments or {}))
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001 - tool failures go back to the model
        logger.exception("Tool %s failed", name)
        return {"error": f"{type(e).__name__}: {e}"}
