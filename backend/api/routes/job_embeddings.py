"""
Job embedding API routes - Neo4j embedding endpoints removed in Phase 1a.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("job_embeddings_api")

router = APIRouter()


class JobEmbeddingRequest(BaseModel):
    force_update: bool = False
    job_ids: Optional[List[int]] = None


@router.post("/api/jobs/generate-embeddings")
async def generate_embeddings(request: JobEmbeddingRequest):
    """Neo4j embedding endpoint removed in Phase 1a."""
    raise HTTPException(
        status_code=410,
        detail="Neo4j-based job embeddings have been removed. Embeddings are now managed via pgvector."
    )


@router.post("/api/jobs/sync-and-generate-embeddings")
async def sync_and_generate_embeddings(request: JobEmbeddingRequest):
    """Neo4j sync+embedding endpoint removed in Phase 1a."""
    raise HTTPException(
        status_code=410,
        detail="Neo4j-based job sync and embedding has been removed."
    )


@router.get("/api/jobs/verify-neo4j-setup")
async def verify_neo4j_setup():
    """Neo4j verification endpoint removed in Phase 1a."""
    raise HTTPException(
        status_code=410,
        detail="Neo4j has been removed from this project."
    )
