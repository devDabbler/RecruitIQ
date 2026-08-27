"""pgvector-backed embedding storage and cosine similarity search.

Replaces the deleted Neo4j graph_service vector layer (Phase 1b). One 768-dim
vector per job/candidate, computed from concatenated descriptive text.
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import text

logger = logging.getLogger(__name__)


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

    def search_candidates_by_text(self, db, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Semantic candidate search: embed the natural-language query, cosine-rank
        candidates. This is the pgvector successor to the old (non-functional)
        Neo4j RAG retrieval; Phase 2's search_candidates tool will call it."""
        query_vec = self.embedding_model.embed_query(query)
        rows = db.execute(
            text(
                """
                SELECT c.id, c.first_name, c.last_name, c.email, c.current_position,
                       1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
                FROM candidates c
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:qvec AS vector)
                LIMIT :limit
                """
            ),
            {"qvec": str(query_vec), "limit": limit},
        ).fetchall()
        return [
            {
                "id": r.id,
                "name": f"{r.first_name or ''} {r.last_name or ''}".strip(),
                "email": r.email,
                "position": r.current_position,
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
