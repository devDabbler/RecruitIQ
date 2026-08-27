"""One-shot: embed every job and candidate into pgvector via the Ollama endpoint.

Usage:  poetry run python scripts/backfill_embeddings.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.models import Candidate, Job
from backend.services.ollama_embeddings import OllamaEmbeddingAdapter
from backend.services.vector_search_service import VectorSearchService


def main():
    engine = create_engine(os.environ["POSTGRES_CONN"].strip('"'))
    session = sessionmaker(bind=engine)()
    svc = VectorSearchService(
        embedding_model=OllamaEmbeddingAdapter(
            base_url=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai")
        )
    )

    jobs = session.query(Job.id).all()
    ok = sum(svc.store_job_embedding(session, j.id) for j in jobs)
    print(f"jobs embedded: {ok}/{len(jobs)}")

    candidates = session.query(Candidate.id).all()
    ok = sum(svc.store_candidate_embedding(session, c.id) for c in candidates)
    print(f"candidates embedded: {ok}/{len(candidates)}")


if __name__ == "__main__":
    main()
