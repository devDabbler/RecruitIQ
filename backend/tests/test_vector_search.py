"""pgvector-backed embedding storage and similarity search (DB-integration)."""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_CONN = os.getenv("POSTGRES_CONN", "").strip('"')


def _pgvector_available():
    if not POSTGRES_CONN:
        return False
    try:
        engine = create_engine(POSTGRES_CONN)
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname='vector'")
            ).scalar() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pgvector_available(), reason="needs Postgres with pgvector")


class StubEmbedder:
    """Deterministic 768-dim embeddings; nearby texts share a prefix dimension."""

    def embed_query(self, txt):
        base = [0.0] * 768
        base[0] = 1.0 if "python" in txt.lower() else -1.0
        base[1] = len(txt) % 7 / 7.0
        return base

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]


@pytest.fixture
def db():
    engine = create_engine(POSTGRES_CONN)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def test_store_and_search_similar_jobs(db):
    from backend.models.models import Job
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())

    jobs = db.query(Job).limit(3).all()
    if len(jobs) < 2:
        pytest.skip("needs at least 2 seeded jobs")

    for job in jobs:
        assert svc.store_job_embedding(db, job.id) is True

    results = svc.find_similar_jobs(db, jobs[0].id, limit=5)
    assert isinstance(results, list) and len(results) >= 1
    assert all(r["id"] != jobs[0].id for r in results), "must exclude the query job"
    assert all(0.0 <= r["similarity"] <= 1.0 for r in results)


def test_store_candidate_embedding(db):
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidate = db.query(Candidate).first()
    if candidate is None:
        pytest.skip("needs seeded candidates")
    assert svc.store_candidate_embedding(db, candidate.id) is True

    row = db.execute(
        text("SELECT embedding IS NOT NULL FROM candidates WHERE id = :cid"),
        {"cid": candidate.id},
    ).scalar()
    assert row is True


def test_search_jobs_by_text(db):
    from backend.models.models import Job
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    jobs = db.query(Job).limit(3).all()
    if not jobs:
        pytest.skip("needs seeded jobs")
    for j in jobs:
        svc.store_job_embedding(db, j.id)

    results = svc.search_jobs_by_text(db, "python data engineer", limit=5)
    assert isinstance(results, list) and len(results) >= 1
    assert all({"id", "title", "skills", "similarity"} <= set(r) for r in results)


def test_search_candidates_by_text(db):
    """Natural-language semantic candidate search over pgvector (the RAG-showcase path)."""
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidates = db.query(Candidate).limit(3).all()
    if not candidates:
        pytest.skip("needs seeded candidates")
    for c in candidates:
        svc.store_candidate_embedding(db, c.id)

    results = svc.search_candidates_by_text(db, "python data engineer with airflow", limit=5)
    assert isinstance(results, list) and len(results) >= 1
    assert all({"id", "name", "position", "location", "similarity"} <= set(r) for r in results)
    sims = [r["similarity"] for r in results]
    assert sims == sorted(sims, reverse=True), "must be ranked best-first"


def test_search_candidates_by_text_location_filter(db):
    """The location arg is a case-insensitive substring WHERE, not semantics."""
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidates = db.query(Candidate).limit(2).all()
    if len(candidates) < 2:
        pytest.skip("needs at least 2 seeded candidates")

    originals = {c.id: c.location for c in candidates}
    try:
        candidates[0].location = "Testville, TS"
        candidates[1].location = "Elsewhere, EW"
        for c in candidates:
            assert svc.store_candidate_embedding(db, c.id) is True

        hits = svc.search_candidates_by_text(db, "python engineer", limit=10, location="testville")
        assert [r["id"] for r in hits] == [candidates[0].id]
        assert hits[0]["location"] == "Testville, TS"

        misses = svc.search_candidates_by_text(db, "python engineer", limit=10, location="zz-nowhere")
        assert misses == []
    finally:
        for c in candidates:
            c.location = originals[c.id]
        db.commit()


def test_search_candidates_by_text_region_filter(db):
    """Region names expand to their states: "west coast" finds "Seattle, WA"."""
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidates = db.query(Candidate).limit(3).all()
    if len(candidates) < 3:
        pytest.skip("needs at least 3 seeded candidates")

    originals = {c.id: c.location for c in candidates}
    try:
        candidates[0].location = "Seattle, WA"
        candidates[1].location = "Portland, OR"
        candidates[2].location = "Austin, TX"
        for c in candidates:
            assert svc.store_candidate_embedding(db, c.id) is True

        hits = svc.search_candidates_by_text(db, "python engineer", limit=50, location="west coast")
        hit_ids = {r["id"] for r in hits}
        assert candidates[0].id in hit_ids and candidates[1].id in hit_ids
        assert candidates[2].id not in hit_ids

        pnw = svc.search_candidates_by_text(
            db, "python engineer", limit=50, location="the Pacific Northwest"
        )
        assert {r["id"] for r in pnw} >= {candidates[0].id, candidates[1].id}
    finally:
        for c in candidates:
            c.location = originals[c.id]
        db.commit()
