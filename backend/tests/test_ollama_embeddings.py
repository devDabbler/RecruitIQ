"""OllamaEmbeddingAdapter: 768-dim embeddings over HTTP with graceful offline fallback."""
import numpy as np
import pytest

from backend.services.ollama_embeddings import OllamaEmbeddingAdapter


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_adapter(monkeypatch, embeddings=None, fail=False):
    adapter = OllamaEmbeddingAdapter(base_url="http://fake:11434", model="nomic-embed-text")

    def fake_post(url, json=None, timeout=None):
        if fail:
            raise ConnectionError("tunnel down")
        n = len(json["input"])
        vecs = embeddings or [[0.1] * 768 for _ in range(n)]
        return FakeResponse({"embeddings": vecs})

    monkeypatch.setattr(adapter._client, "post", fake_post)
    return adapter


def test_embed_query_returns_768_list(monkeypatch):
    adapter = make_adapter(monkeypatch)
    vec = adapter.embed_query("data engineer with airflow")
    assert isinstance(vec, list)
    assert len(vec) == 768


def test_embed_documents_batches(monkeypatch):
    adapter = make_adapter(monkeypatch)
    vecs = adapter.embed_documents(["a", "b", "c"])
    assert len(vecs) == 3 and all(len(v) == 768 for v in vecs)


def test_encode_single_returns_ndarray(monkeypatch):
    adapter = make_adapter(monkeypatch)
    out = adapter.encode("hello")
    assert isinstance(out, np.ndarray) and out.shape == (768,)


def test_encode_list_returns_2d_ndarray(monkeypatch):
    adapter = make_adapter(monkeypatch)
    out = adapter.encode(["hello", "world"])
    assert isinstance(out, np.ndarray) and out.shape == (2, 768)


def test_offline_fallback_is_deterministic_768(monkeypatch):
    adapter = make_adapter(monkeypatch, fail=True)
    v1 = adapter.embed_query("same text")
    v2 = adapter.embed_query("same text")
    v3 = adapter.embed_query("different text")
    assert len(v1) == 768
    assert v1 == v2, "fallback must be deterministic for caching"
    assert v1 != v3
