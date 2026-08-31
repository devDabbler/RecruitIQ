"""pgvector-backed embedding storage and cosine similarity search.

Replaces the deleted Neo4j graph_service vector layer (Phase 1b). One 768-dim
vector per job/candidate, computed from concatenated descriptive text.
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Region vocabulary for the location filter. Candidate locations are stored as
# "City, ST", so a state list is matched as "%, ST%"; metro areas that span one
# state are matched by city name. Recruiters ask in regions ("anywhere on the
# west coast") far more often than exact strings, and an ILIKE on the literal
# region name matches zero rows.
_REGION_STATES = {
    "west coast": ["CA", "OR", "WA"],
    "east coast": ["ME", "NH", "MA", "RI", "CT", "NY", "NJ", "PA", "DE", "MD", "DC", "VA", "NC", "SC", "GA", "FL"],
    "pacific northwest": ["WA", "OR"],
    "pnw": ["WA", "OR"],
    "new england": ["ME", "NH", "VT", "MA", "RI", "CT"],
    "midwest": ["OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"],
    "south": ["TX", "OK", "AR", "LA", "MS", "AL", "TN", "KY", "GA", "FL", "SC", "NC", "VA", "WV"],
    "southwest": ["AZ", "NM", "NV", "TX", "OK"],
    "mountain west": ["CO", "UT", "ID", "MT", "WY", "NV"],
}
_REGION_CITIES = {
    "bay area": ["San Francisco", "Oakland", "San Jose", "Berkeley", "Palo Alto", "Mountain View", "Sunnyvale"],
    "socal": ["Los Angeles", "San Diego", "Irvine", "Long Beach", "Santa Monica", "Pasadena"],
    "southern california": ["Los Angeles", "San Diego", "Irvine", "Long Beach", "Santa Monica", "Pasadena"],
    "dmv": ["Washington", "Arlington", "Alexandria", "Bethesda"],
}


def location_filter_patterns(location: str) -> List[str]:
    """ILIKE patterns for a location ask: a region expands to its states or
    cities, anything else stays a plain substring match."""
    key = location.strip().lower()
    for prefix in ("anywhere on the ", "anywhere along the ", "along the ", "on the ", "the "):
        if key.startswith(prefix):
            key = key[len(prefix):]
            break
    if key in _REGION_STATES:
        return [f"%, {state}%" for state in _REGION_STATES[key]]
    if key in _REGION_CITIES:
        return [f"%{city}%" for city in _REGION_CITIES[key]]
    return [f"%{location.strip()}%"]


def _job_text(job) -> str:
    skills = job.skills or ""
    if isinstance(skills, list):
        skills = ", ".join(skills)
    return " | ".join(
        p for p in [job.title, job.job_overview, job.required_qualifications, skills] if p
    )


def _candidate_text(candidate) -> str:
    skills = ""
    if getattr(candidate, "skills", None):
        skills = ", ".join(s.skill_name for s in candidate.skills)
    return " | ".join(p for p in [candidate.current_position, skills] if p)


class VectorSearchService:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model

    def store_job_embedding(self, db, job_id: int) -> bool:
        from backend.models.models import Job

        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"store_job_embedding: job {job_id} not found")
            return False
        content = _job_text(job)
        if not content:
            return False
        job.embedding = self.embedding_model.embed_query(content)
        db.commit()
        return True

    def store_candidate_embedding(self, db, candidate_id: str) -> bool:
        from backend.models.models import Candidate

        candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
        if not candidate:
            logger.warning(f"store_candidate_embedding: candidate {candidate_id} not found")
            return False
        content = _candidate_text(candidate)
        if not content:
            return False
        candidate.embedding = self.embedding_model.embed_query(content)
        db.commit()
        return True

    def search_candidates_by_text(
        self, db, query: str, limit: int = 10, location: str = None
    ) -> List[Dict[str, Any]]:
        """Semantic candidate search: embed the natural-language query, cosine-rank
        candidates. This is the pgvector successor to the old (non-functional)
        Neo4j RAG retrieval; Phase 2's search_candidates tool will call it.

        `location` is a structured substring filter, not part of the embedding:
        candidate embeddings cover position and skills only, so "in Seattle" must
        be a WHERE clause or it silently matches nothing. Region names ("west
        coast") expand to their states via location_filter_patterns."""
        query_vec = self.embedding_model.embed_query(query)
        location_clause = ""
        params = {"qvec": str(query_vec), "limit": limit}
        if location:
            patterns = location_filter_patterns(location)
            ors = " OR ".join(f"c.location ILIKE :loc{i}" for i in range(len(patterns)))
            location_clause = f"AND ({ors})"
            params.update({f"loc{i}": p for i, p in enumerate(patterns)})
        rows = db.execute(
            text(
                f"""
                SELECT c.id, c.first_name, c.last_name, c.email, c.current_position,
                       c.location,
                       1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
                FROM candidates c
                WHERE c.embedding IS NOT NULL
                {location_clause}
                ORDER BY c.embedding <=> CAST(:qvec AS vector)
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
        return [
            {
                "id": r.id,
                "name": f"{r.first_name or ''} {r.last_name or ''}".strip(),
                "email": r.email,
                "position": r.current_position,
                "location": r.location,
                "similarity": max(0.0, min(1.0, float(r.similarity))),
            }
            for r in rows
        ]

    def search_jobs_by_text(self, db, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Cosine-rank jobs against a natural-language query (e.g. a job title)."""
        query_vec = self.embedding_model.embed_query(query)
        rows = db.execute(
            text(
                """
                SELECT j.id, j.title, j.department, j.location, j.skills,
                       1 - (j.embedding <=> CAST(:qvec AS vector)) AS similarity
                FROM jobs j
                WHERE j.embedding IS NOT NULL
                ORDER BY j.embedding <=> CAST(:qvec AS vector)
                LIMIT :limit
                """
            ),
            {"qvec": str(query_vec), "limit": limit},
        ).fetchall()
        return [
            {
                "id": r.id,
                "title": r.title,
                "department": r.department,
                "location": r.location,
                "skills": [s.strip() for s in r.skills.split(",")] if r.skills else [],
                "similarity": max(0.0, min(1.0, float(r.similarity))),
            }
            for r in rows
        ]

    def find_similar_jobs(self, db, job_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Cosine similarity over jobs.embedding; excludes the query job."""
        rows = db.execute(
            text(
                """
                SELECT j.id, j.title, j.department, j.location, j.skills,
                       1 - (j.embedding <=> q.embedding) AS similarity
                FROM jobs j, jobs q
                WHERE q.id = :job_id
                  AND j.id != :job_id
                  AND j.embedding IS NOT NULL
                  AND q.embedding IS NOT NULL
                ORDER BY j.embedding <=> q.embedding
                LIMIT :limit
                """
            ),
            {"job_id": job_id, "limit": limit},
        ).fetchall()
        return [
            {
                "id": r.id,
                "title": r.title,
                "department": r.department,
                "location": r.location,
                "skills": [s.strip() for s in r.skills.split(",")] if r.skills else [],
                "similarity": max(0.0, min(1.0, float(r.similarity))),
            }
            for r in rows
        ]
