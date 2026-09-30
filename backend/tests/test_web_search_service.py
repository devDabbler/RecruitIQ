"""The web search backends behind the salary tool. No network.

Google closed the Custom Search JSON API to new customers (shutdown
2027-01-01), so a fresh install's only working option is a third-party SERP
backend. These tests pin the fallback order, the result shape every backend
must produce, and that no backend puts an API key in the log.
"""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest

from backend.services.web_search_service import WebSearchService

KEY = "test-scraperapi-key-0123456789abcdef"


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Response:
    def __init__(self, payload, status=200, url="https://api.example.invalid/?api_key=" + KEY):
        self._payload = payload
        self.status_code = status
        self.request = httpx.Request("GET", url)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Client error '{self.status_code}' for url '{self.request.url}'",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._payload


def _service(monkeypatch, responses, **env):
    for name in ("GOOGLE_API_KEY", "GOOGLE_CSE_ID", "SERPAPI_KEY", "SCRAPERAPI_KEY", "BING_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    service = WebSearchService()
    calls = []

    async def fake_get(url, params=None, **kwargs):
        calls.append(SimpleNamespace(url=url, params=params or {}))
        response = responses.pop(0)
        return response

    service.http_client = SimpleNamespace(get=fake_get)
    return service, calls


SCRAPERAPI_PAYLOAD = {
    "search_information": {"total_results": 3},
    "organic_results": [
        {"position": 1, "title": "Data Engineer Salary in Austin", "link": "https://example.invalid/a", "snippet": "$120k"},
        {"position": 2, "title": "Senior Data Engineer pay", "link": "https://example.invalid/b", "snippet": "$150k"},
    ],
}


class TestBackendSelection:
    def test_no_keys_means_no_backend_and_no_results(self, monkeypatch):
        service, calls = _service(monkeypatch, [])
        assert service.has_backend is False
        assert run(service.search("data engineer salary austin")) == []
        assert calls == []

    def test_scraperapi_alone_is_a_backend(self, monkeypatch):
        service, calls = _service(monkeypatch, [_Response(SCRAPERAPI_PAYLOAD)], SCRAPERAPI_KEY=KEY)
        assert service.has_backend is True
        results = run(service.search("data engineer salary austin", max_results=5))
        assert results == [
            {"title": "Data Engineer Salary in Austin", "link": "https://example.invalid/a", "snippet": "$120k"},
            {"title": "Senior Data Engineer pay", "link": "https://example.invalid/b", "snippet": "$150k"},
        ]
        assert len(calls) == 1
        assert calls[0].url == "https://api.scraperapi.com/structured/google/search"
        assert calls[0].params == {"api_key": KEY, "query": "data engineer salary austin", "num": 5}

    def test_scraperapi_is_the_fallback_after_google_fails(self, monkeypatch):
        # Prod today: Google keys present but the API is closed (403), then
        # ScraperAPI answers. Google's failure must not end the search.
        service, calls = _service(
            monkeypatch,
            [_Response({"error": "forbidden"}, status=403), _Response(SCRAPERAPI_PAYLOAD)],
            GOOGLE_API_KEY="g", GOOGLE_CSE_ID="cx", SCRAPERAPI_KEY=KEY,
        )
        results = run(service.search("data engineer salary austin"))
        assert len(results) == 2
        assert [c.url for c in calls] == [
            "https://www.googleapis.com/customsearch/v1",
            "https://api.scraperapi.com/structured/google/search",
        ]

    def test_scraperapi_failure_is_empty_not_raised(self, monkeypatch):
        service, _ = _service(monkeypatch, [_Response({}, status=500)], SCRAPERAPI_KEY=KEY)
        assert run(service.search("anything")) == []

    def test_results_are_capped_at_the_request(self, monkeypatch):
        service, _ = _service(monkeypatch, [_Response(SCRAPERAPI_PAYLOAD)], SCRAPERAPI_KEY=KEY)
        assert len(run(service.search_scraperapi("q", num_results=1))) == 1


class TestKeysStayOutOfTheLog:
    @pytest.mark.parametrize(
        "env, url_hint",
        [
            ({"GOOGLE_API_KEY": KEY, "GOOGLE_CSE_ID": "cx"}, "googleapis"),
            ({"SERPAPI_KEY": KEY}, "serpapi"),
            ({"SCRAPERAPI_KEY": KEY}, "scraperapi"),
        ],
    )
    def test_failed_call_logs_no_key(self, monkeypatch, caplog, env, url_hint):
        # httpx's error text carries the full request URL, which for every
        # backend here carries the key as a query parameter. The prod
        # journal used to show the Google key on each 403.
        service, _ = _service(monkeypatch, [_Response({}, status=403)], **env)
        with caplog.at_level(logging.DEBUG, logger="backend.services.web_search_service"):
            assert run(service.search("q")) == []
        assert KEY not in caplog.text
        assert url_hint  # the parametrize label, kept for readability
