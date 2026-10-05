"""Complete candidate erasure (pilot plan Track 1 #2).

Deleting a candidate removes everything held about them: the profile and its
skills, education and experience; every application with its stage history,
interviews, feedback and sent-email log; notes and tags; saved jobs and
pitches; resume rows (parsed text and embeddings included); the stored resume
files; and the Redis parse/duplicate cache entries for those files.

The database part is one transaction, so a failure leaves nothing half
deleted. Files and cache entries cannot join that transaction, so they go
after the commit; a file that fails to delete is logged and counted in the
report rather than undoing an erasure that already happened.

ERASURE_STEPS is the single list of tables touched. A test walks the foreign
keys that lead back to `candidates` and fails if a table appears there that
this list does not cover, so a future table holding candidate data cannot
quietly survive a deletion.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.utils.cache_utils import make_cache_key

logger = logging.getLogger(__name__)

_APPLICATIONS = "SELECT id FROM job_applications WHERE candidate_id = :cid"
_STAGE_ROWS = f"SELECT id FROM application_stages WHERE application_id IN ({_APPLICATIONS})"
_INTERVIEWS = f"SELECT id FROM interviews WHERE application_stage_id IN ({_STAGE_ROWS})"

# Children before parents, so this works whether or not a given database has
# the ON DELETE CASCADE rules the migrations declare.
ERASURE_STEPS: tuple[tuple[str, str], ...] = (
    ("feedback", f"interview_id IN ({_INTERVIEWS})"),
    ("interviews", f"application_stage_id IN ({_STAGE_ROWS})"),
    ("application_stages", f"application_id IN ({_APPLICATIONS})"),
    ("email_log", f"application_id IN ({_APPLICATIONS})"),
    ("notes", f"candidate_id = :cid OR application_id IN ({_APPLICATIONS})"),
    ("job_applications", "candidate_id = :cid"),
    ("saved_jobs", "candidate_id = :cid"),
    ("candidate_pitches", "candidate_id = :cid"),
    ("candidate_tags", "candidate_id = :cid"),
    ("candidate_skills", "candidate_id = :cid"),
    ("candidate_education", "candidate_id = :cid"),
    ("candidate_experience", "candidate_id = :cid"),
    ("resumes", "candidate_id = :cid"),
    ("candidates", "id = :cid"),
)

ERASED_TABLES = frozenset(table for table, _ in ERASURE_STEPS)


@dataclass
class ErasureReport:
    candidate_id: str
    rows: dict[str, int] = field(default_factory=dict)
    files_removed: int = 0
    files_failed: int = 0
    cache_keys_removed: int = 0


class CandidateNotFound(Exception):
    pass


def erase_candidate(
    db: Session,
    candidate_id: str,
    storage: Optional[Any] = None,
    redis_client: Optional[Any] = None,
) -> ErasureReport:
    """Delete the candidate and every row, file and cache entry about them.

    `storage` is the resume storage backend in use (anything with a
    `delete_document(file_id)` method). `redis_client` is a synchronous Redis
    client; when omitted one is built from settings, and an unreachable Redis
    is logged and skipped since the cache entries expire on their own.
    """
    params = {"cid": candidate_id}
    exists = db.execute(text("SELECT 1 FROM candidates WHERE id = :cid"), params).first()
    if exists is None:
        raise CandidateNotFound(candidate_id)

    resume_rows = db.execute(
        text(
            "SELECT file_id, parsed_data->>'content_hash' AS content_hash "
            "FROM resumes WHERE candidate_id = :cid"
        ),
        params,
    ).all()
    file_ids = [r.file_id for r in resume_rows if r.file_id]
    content_hashes = [r.content_hash for r in resume_rows if r.content_hash]

    report = ErasureReport(candidate_id=candidate_id)
    try:
        # The intake path counts applications on the job; keep that honest.
        db.execute(
            text(
                "UPDATE jobs j SET applications = GREATEST(COALESCE(j.applications, 0) - a.n, 0) "
                "FROM (SELECT job_id, COUNT(*) AS n FROM job_applications "
                "WHERE candidate_id = :cid GROUP BY job_id) a WHERE j.id = a.job_id"
            ),
            params,
        )
        for table, where in ERASURE_STEPS:
            result = db.execute(text(f"DELETE FROM {table} WHERE {where}"), params)
            report.rows[table] = result.rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise

    for file_id in file_ids:
        if storage is None:
            report.files_failed += 1
            continue
        try:
            if storage.delete_document(file_id):
                report.files_removed += 1
        except Exception as exc:
            report.files_failed += 1
            logger.error("Erasure of %s: resume file %s not deleted: %s", candidate_id, file_id, exc)

    if content_hashes:
        report.cache_keys_removed = _clear_cache(content_hashes, redis_client)

    logger.info(
        "Erased candidate %s: rows=%s files_removed=%d files_failed=%d cache_keys=%d",
        candidate_id,
        {k: v for k, v in report.rows.items() if v},
        report.files_removed,
        report.files_failed,
        report.cache_keys_removed,
    )
    return report


def _clear_cache(content_hashes: list[str], redis_client: Optional[Any]) -> int:
    try:
        if redis_client is None:
            import redis

            from backend.utils.config import get_settings

            settings = get_settings()
            redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        removed = 0
        for content_hash in content_hashes:
            keys = [make_cache_key("resume_parse", content_hash)]
            keys.extend(redis_client.scan_iter(match=f"duplicate:{content_hash}:*"))
            removed += redis_client.delete(*keys)
        return removed
    except Exception as exc:
        logger.warning("Erasure cache cleanup skipped (Redis unavailable): %s", exc)
        return 0


def is_safe_file_id(file_id: str) -> bool:
    """Stored file ids are UUIDs; anything else is refused as a path."""
    try:
        return str(uuid.UUID(str(file_id))) == str(file_id).lower()
    except ValueError:
        return False
