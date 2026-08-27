"""768-dim embeddings from the existing Ollama endpoint (nomic-embed-text).

Replaces the sentence-transformers (384-dim, PyTorch) adapter. Design rules
from the revival spec §4.2/§4.4: best-effort with a hard timeout, no retries
against a possibly-busy GPU, deterministic local fallback so cached scores
stay stable when the tunnel is down.
"""
import hashlib
import logging
from typing import List, Union

import httpx
import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


class OllamaEmbeddingAdapter:
    """Duck-type compatible with the old SentenceTransformerAdapter:
    encode() -> np.ndarray, embed_query() -> list, embed_documents() -> list[list]."""

    def __init__(self, base_url: str, model: str = "nomic-embed-text", timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout)
        self._warned_offline = False

    def _fallback(self, text: str) -> List[float]:
        # Deterministic pseudo-embedding: stable across calls so Redis-cached
        # scores don't jitter while the tunnel is down. Not semantically useful.
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        return rng.standard_normal(EMBEDDING_DIM).tolist()

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            embeddings = resp.json()["embeddings"]
            if len(embeddings) != len(texts) or any(len(e) != EMBEDDING_DIM for e in embeddings):
                raise ValueError(
                    f"expected {len(texts)}x{EMBEDDING_DIM} embeddings, got "
                    f"{len(embeddings)}x{len(embeddings[0]) if embeddings else 0}"
                )
            self._warned_offline = False
            return embeddings
        except Exception as e:
            if not self._warned_offline:
                logger.warning(f"Ollama embeddings unavailable ({e}); using deterministic fallback")
                self._warned_offline = True
            return [self._fallback(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_batch([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed_batch(list(texts))

    def encode(self, text: Union[str, List[str]]) -> np.ndarray:
        """cache_utils.get_embedding_cached calls this in a thread pool."""
        if isinstance(text, str):
            return np.array(self._embed_batch([text])[0])
        return np.array(self._embed_batch(list(text)))
