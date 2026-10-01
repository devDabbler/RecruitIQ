"""OllamaEmbeddingAdapter: 768-dim embeddings over HTTP with graceful offline fallback."""
from contextvars import copy_context

import numpy as np
import pytest

from backend.services.matching_enhancer import MatchingEnhancer
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


def test_degraded_flag_is_per_request(monkeypatch):
    """The adapter is one shared instance; its degraded flag must not be.

    Two requests, one whose embed falls back and one whose embed succeeds,
    each read their own outcome no matter which ran last. Each request runs in
    its own context, which is what copy_context() stands in for here.
    """
    adapter = OllamaEmbeddingAdapter(base_url="http://fake:11434")

    def fake_post(url, json=None, timeout=None):
        if json["input"] == ["tunnel down"]:
            raise ConnectionError("tunnel down")
        return FakeResponse({"embeddings": [[0.1] * 768]})

    monkeypatch.setattr(adapter._client, "post", fake_post)

    failed, healthy = copy_context(), copy_context()
    failed.run(adapter.embed_query, "tunnel down")
    healthy.run(adapter.embed_query, "fine")

    assert failed.run(lambda: adapter.is_degraded) is True
    assert healthy.run(lambda: adapter.is_degraded) is False
    assert adapter.is_degraded is False, "neither request's outcome leaks out"


def test_enhancer_never_caches_a_placeholder_vector(monkeypatch):
    """An outage-time placeholder is noise; caching it would keep scoring that
    title against noise after the tunnel recovered."""
    up = {"value": False}
    calls = []
    adapter = OllamaEmbeddingAdapter(base_url="http://fake:11434")

    def fake_post(url, json=None, timeout=None):
        calls.append(json["input"])
        if not up["value"]:
            raise ConnectionError("tunnel down")
        return FakeResponse({"embeddings": [[0.1] * 768]})

    monkeypatch.setattr(adapter._client, "post", fake_post)
    enhancer = MatchingEnhancer(embedding_model=adapter)

    enhancer._embed("Data Engineer")
    enhancer._embed("Data Engineer")
    assert len(calls) == 2, "a placeholder must not be served from the cache"

    up["value"] = True
    real = enhancer._embed("Data Engineer")
    assert np.allclose(real, 0.1), "the recovered call returns the real vector"
    enhancer._embed("Data Engineer")
    assert len(calls) == 3, "a real vector is cached as before"
