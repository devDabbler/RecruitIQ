"""Crawler must chunk text without langchain installed."""
import sys


def test_crawler_uses_custom_text_splitter(monkeypatch):
    # Simulate langchain being absent so a regression back to it fails loudly
    monkeypatch.setitem(sys.modules, "langchain", None)
    monkeypatch.setitem(sys.modules, "langchain.text_splitter", None)

    from backend.services.crawler_service import CrawlerService
    from backend.utils.config import Settings

    service = CrawlerService(Settings())
    assert service.text_splitter is not None, "text_splitter must not depend on langchain"

    chunks = service.text_splitter.split_text("para one\n\n" + ("word " * 400) + "\n\npara two")
    assert len(chunks) >= 2
    assert all(len(c) <= 1200 for c in chunks)  # chunk_size 1000 + tolerance for overlap boundaries
