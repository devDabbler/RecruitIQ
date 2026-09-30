"""An unrelated title must never come back as a partial match.

Regression net for the relevance banding rewrite (2026-09-30). Before it,
"plumber" returned three data engineers labelled "moderate", because cosine
similarity from nomic-embed-text sits at 0.45 to 0.64 for everyone when
nothing in the pool is related, and the bands were drawn at 0.55/0.45.

The numbers in TestMeasuredCalibration are real similarities measured on the
demo seed; they are the reason the bands sit where they sit. Everything here
runs without Postgres, Ollama or an LLM.
"""
import asyncio
from types import SimpleNamespace

from backend.services import assistant_tools
from backend.services.assistant_tools import no_match_note, partial_match_note
from backend.services.search_relevance import (
    RELEVANCE_BANDS,
    band_hits,
    evidence_in,
    query_terms,
    rank_hits,
    relevance_band,
)
from backend.services.vector_search_service import MIN_SEARCH_RELEVANCE


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def hit(name, similarity, position="", headline="", company="", skills=""):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "position": position,
        "headline": headline,
        "company": company,
        "skills": skills,
        "location": "Remote",
        "similarity": similarity,
    }


class TestQueryTerms:
    def test_stopwords_and_role_words_are_not_evidence(self):
        assert query_terms("people who have worked in insurance") == ["insurance"]
        assert query_terms("retail store managers") == ["retail", "store"]
        assert query_terms("mechanical engineer") == ["mechanical"]
        assert query_terms("senior engineering managers") == []
        assert query_terms("architect") == []

    def test_short_forms_survive_only_when_established(self):
        assert query_terms("ML and SQL people") == ["ml", "sql"]
        assert query_terms("go developers") == ["go"]  # kept, but matched as a whole word only
        assert query_terms("a UX lead") == ["ux"]

    def test_terms_keep_order_and_dedupe(self):
        assert query_terms("kafka, kafka and Kafka streams") == ["kafka", "streams"]
        assert query_terms("") == [] and query_terms(None) == []


class TestEvidence:
    TEXT = "Data Platform Engineer | Allstate | lakehouse migrations at a national insurance carrier | Python, Spark, Kubernetes"

    def test_plain_word_and_plural_and_prefix(self):
        assert evidence_in(self.TEXT, ["insurance"]) == ["insurance"]
        assert evidence_in(self.TEXT, ["migrations"]) == ["migrations"]
        assert evidence_in(self.TEXT, ["migration"]) == ["migration"]
        assert evidence_in("Registered Nurse, ICU", ["nurses"]) == ["nurses"]
        assert evidence_in("financial services risk", ["finance"]) == ["finance"]

    def test_short_forms_match_whole_words_only(self):
        assert evidence_in("PostgreSQL and Go", ["sql"]) == []
        assert evidence_in("SQL, dbt, Snowflake", ["sql"]) == ["sql"]
        assert evidence_in("Google Cloud", ["go"]) == []

    def test_aliases_and_hyphens(self):
        assert evidence_in("Machine Learning Engineer", ["ml"]) == ["ml"]
        assert evidence_in("Senior Front-End Engineer", ["frontend"]) == ["frontend"]
        assert evidence_in("Site Reliability Manager", ["sre"]) == ["sre"]
        assert evidence_in("Quantitative Developer", ["quant"]) == ["quant"]

    def test_generic_words_in_the_profile_are_not_evidence_for_anything(self):
        # "manager" is in the profile, but it was stripped from the query.
        assert evidence_in("Technical Product Manager", query_terms("retail store managers")) == []


class TestBands:
    def test_strong_needs_no_evidence(self):
        assert relevance_band(RELEVANCE_BANDS["strong"], []) == "strong"

    def test_moderate_needs_evidence(self):
        s = RELEVANCE_BANDS["strong"] - 0.01
        assert relevance_band(s, ["kafka"]) == "moderate"
        assert relevance_band(s, []) == "weak"

    def test_evidence_below_the_moderate_floor_is_still_weak(self):
        assert relevance_band(RELEVANCE_BANDS["moderate"] - 0.01, ["kafka"]) == "weak"

    def test_below_search_floor_is_weak_whatever_it_matched(self):
        hits = [hit("Ada", MIN_SEARCH_RELEVANCE - 0.01, headline="insurance claims")]
        assert band_hits(hits, "insurance", MIN_SEARCH_RELEVANCE)[0]["relevance"] == "weak"


class TestMeasuredCalibration:
    """Real similarities from the demo seed with nomic-embed-text vectors,
    2026-09-30. Each row is (query, top hit's position/headline, similarity)
    and the band the recruiter should see. Move a band outside these and the
    plumber comes back."""

    UNRELATED = [
        ("plumber", "Senior Data Engineer", "Senior Data Engineer with 7 years of experience", 0.551),
        ("underwater welders", "Senior Software Engineer", "", 0.535),
        ("accountant", "Summer Associate - Data Analyst", "", 0.563),
        ("civil engineer", "Software Development Engineer", "", 0.618),
        ("mechanical engineer", "Systems Engineer", "C++ engineer, medical device firmware", 0.639),
        ("retail store managers", "Technical Product Manager", "Technical Product Manager with 4 years", 0.604),
        ("chief happiness officer", "Senior Software Development Engineer", "", 0.483),
    ]
    RELATED = [
        ("machine learning engineers with python", "Machine Learning Engineer", "LLM applications engineer", "Python", 0.776, "strong"),
        ("data scientists", "Data Scientist", "Data Scientist with 3 years of experience", "", 0.755, "strong"),
        ("engineering managers", "Engineering Manager", "Platform lead, ex-Stripe infrastructure", "", 0.675, "strong"),
        ("someone strong in SQL and dbt", "Analytics Engineer", "Analytics engineer, dbt and warehouse modeling", "SQL", 0.645, "moderate"),
        ("people with kubernetes experience", "Site Reliability Manager", "SRE-flavored platform lead", "Kubernetes", 0.570, "moderate"),
        ("people who have worked in insurance", "Data Platform Engineer", "lakehouse migrations at a national insurance carrier", "", 0.538, "moderate"),
        ("commercial airline pilots", "Analytics Engineer", "Airline analytics engineer moving to platform work", "", 0.600, "moderate"),
        ("new grads", "Research Assistant", "New grad, strong Kaggle record", "", 0.549, "moderate"),
    ]

    def test_unrelated_titles_are_weak(self):
        for query, position, headline, similarity in self.UNRELATED:
            shown, kept_out = rank_hits([hit("X", similarity, position=position, headline=headline)], query, 8)
            assert shown == [] and kept_out[0]["relevance"] == "weak", (query, position, similarity)

    def test_related_profiles_keep_their_band(self):
        for query, position, headline, skills, similarity, band in self.RELATED:
            shown, _ = rank_hits([hit("X", similarity, position=position, headline=headline, skills=skills)], query, 8)
            assert shown and shown[0]["relevance"] == band, (query, position, similarity, shown)

    def test_a_partial_match_says_what_it_matched_on(self):
        shown, _ = rank_hits(
            [hit("X", 0.600, position="Analytics Engineer", headline="Airline analytics engineer")],
            "commercial airline pilots",
            8,
        )
        assert shown[0]["matched_on"] == ["airline"]


class TestRanking:
    def test_strong_first_then_moderate_then_cut(self):
        pool = [
            hit("Weak High", 0.62, position="Systems Engineer"),
            hit("Moderate", 0.50, position="Analyst", headline="airline operations"),
            hit("Strong Low", 0.66, position="Pilot"),
            hit("Strong High", 0.70, position="Pilot"),
        ]
        shown, kept_out = rank_hits(pool, "airline pilots", 2)
        assert [h["name"] for h in shown] == ["Strong High", "Strong Low"]
        assert [h["name"] for h in kept_out] == ["Moderate", "Weak High"]

    def test_evidence_outranks_similarity_among_non_strong_hits(self):
        # The person who actually names the industry sits behind a dozen
        # engineers who share nothing but vocabulary; the pool re-rank puts
        # them first and the engineers nowhere.
        pool = [hit(f"Engineer {i}", 0.56 - i * 0.001, position="Software Engineer") for i in range(12)]
        pool.append(hit("Ben", 0.47, position="Software Engineer II", headline="insurance claims systems"))
        shown, kept_out = rank_hits(pool, "people who have worked in insurance", 8)
        assert [h["name"] for h in shown] == ["Ben"]
        assert len(kept_out) == 12


class _Registry:
    def __init__(self):
        self.llm_service = SimpleNamespace(get_embedding_model=lambda: SimpleNamespace(is_degraded=False))


def _search_tool(monkeypatch, pool_by_location):
    """search_candidates bound to a fake search that answers from a dict of
    location -> pool (None for the unfiltered search)."""
    from backend.services import service_registry, vector_search_service

    calls = []
    monkeypatch.setattr(service_registry, "get_registry", lambda: _Registry())

    def fake_search(self, db, query, limit=10, location=None, min_similarity=0.0):
        calls.append({"query": query, "limit": limit, "location": location, "min_similarity": min_similarity})
        return [dict(h) for h in pool_by_location.get(location, [])]

    monkeypatch.setattr(vector_search_service.VectorSearchService, "search_candidates_by_text", fake_search)
    tools = {t.name: t for t in assistant_tools.build_assistant_tools(SimpleNamespace())}
    return tools["search_candidates"], calls


class TestSearchTool:
    def test_unrelated_query_returns_nobody_and_says_so(self, monkeypatch):
        pool = [hit(f"Engineer {i}", 0.55, position="Senior Data Engineer") for i in range(3)]
        tool, calls = _search_tool(monkeypatch, {None: pool})
        result = run(tool.run(query="plumber"))
        assert result["candidates"] == [] and result["count"] == 0
        assert result["note"] == no_match_note("plumber")
        assert "weak" not in result["note"]
        # The pool is pulled past the visible limit so evidence can re-rank it.
        assert calls[0]["limit"] > 8 and calls[0]["min_similarity"] == MIN_SEARCH_RELEVANCE

    def test_partial_matches_carry_their_words_and_a_note(self, monkeypatch):
        pool = [
            hit("Leilani", 0.62, position="Operations Analyst", headline="Airline operations analyst"),
            hit("Noise", 0.60, position="Senior Software Engineer"),
        ]
        tool, _ = _search_tool(monkeypatch, {None: pool})
        result = run(tool.run(query="commercial airline pilots"))
        assert [c["name"] for c in result["candidates"]] == ["Leilani"]
        assert result["candidates"][0]["relevance"] == "moderate"
        assert result["candidates"][0]["matched_on"] == ["airline"]
        assert result["note"] == partial_match_note("commercial airline pilots")

    def test_strong_matches_get_no_note(self, monkeypatch):
        pool = [hit("Ada", 0.75, position="Data Scientist"), hit("Grace", 0.58, position="Analyst", headline="data")]
        tool, _ = _search_tool(monkeypatch, {None: pool})
        result = run(tool.run(query="data scientists"))
        assert [c["relevance"] for c in result["candidates"]] == ["strong", "moderate"]
        assert "note" not in result

    def test_location_miss_falls_back_to_real_matches_elsewhere(self, monkeypatch):
        seattle = [hit("Local Noise", 0.58, position="Systems Engineer")]
        anywhere = [hit("Ada", 0.75, position="Python Engineer", skills="Python")]
        tool, _ = _search_tool(monkeypatch, {"Seattle": seattle, None: anywhere})
        result = run(tool.run(query="python engineers", location="Seattle"))
        assert result["count"] == 0 and result["location_filter"] == "Seattle"
        assert [c["name"] for c in result["candidates_elsewhere"]] == ["Ada"]
        assert "Seattle" in result["note"]

    def test_nobody_anywhere_is_a_no_match_not_a_location_miss(self, monkeypatch):
        noise = [hit("Noise", 0.58, position="Systems Engineer")]
        tool, _ = _search_tool(monkeypatch, {"Seattle": noise, None: noise})
        result = run(tool.run(query="plumber", location="Seattle"))
        assert result["count"] == 0 and result["candidates_elsewhere"] == []
        assert result["note"] == no_match_note("plumber")

    def test_notes_read_as_sentences_to_a_visitor(self):
        import re

        for note in (no_match_note("plumber"), partial_match_note("plumber")):
            assert not re.search(r"\b(tell the user|do not|never|you must)\b", note, re.I), note
            assert not re.search("[—–]", note), note
