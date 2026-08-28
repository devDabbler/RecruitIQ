"""Unit tests for the eval scorer (runs in CI; no LLM, no DB)."""
from evals.scorer import ALL_FIELDS, aggregate, norm, norm_phone, score_extraction

LABELS = {
    "name": "Maya Chen",
    "email": "maya.chen@example.com",
    "phone": "555-201-3345",
    "location": "Seattle, WA",
    "experience_titles": ["Senior Data Engineer", "Data Engineer"],
    "experience_companies": ["Cascadia Analytics", "Pugetworks"],
    "skills": ["Python", "SQL", "Airflow"],
    "education_institutions": ["University of Washington"],
}


def _perfect_extraction():
    return {
        "personal_info": {
            "name": "Maya Chen",
            "email": "maya.chen@example.com",
            "phone": "(555) 201-3345",
            "location": "Seattle, WA",
        },
        "experience": [
            {"title": "Senior Data Engineer", "company": "Cascadia Analytics"},
            {"title": "Data Engineer", "company": "Pugetworks"},
        ],
        "education": [{"institution": "University of Washington"}],
        "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Airflow"}],
    }


class TestScoreExtraction:
    def test_perfect_extraction_scores_one_everywhere(self):
        scores = score_extraction(_perfect_extraction(), LABELS)
        assert all(v == 1.0 for v in scores.values()), scores

    def test_empty_extraction_scores_zero(self):
        scores = score_extraction({}, LABELS)
        assert all(v == 0.0 for v in scores.values()), scores

    def test_phone_format_insensitive(self):
        data = _perfect_extraction()
        data["personal_info"]["phone"] = "+1 555.201.3345"
        # leading country code changes digits; without it formats are equal
        data["personal_info"]["phone"] = "555.201.3345"
        assert score_extraction(data, LABELS)["phone"] == 1.0

    def test_partial_experience_recall(self):
        data = _perfect_extraction()
        data["experience"] = [{"title": "Senior Data Engineer", "company": "Cascadia Analytics"}]
        scores = score_extraction(data, LABELS)
        assert scores["experience_titles"] == 0.5
        assert scores["experience_companies"] == 0.5

    def test_skills_f1_penalizes_hallucinated_skills(self):
        data = _perfect_extraction()
        data["skills"] = [{"name": s} for s in ["Python", "SQL", "Airflow", "Cobol", "Fortran", "Ada"]]
        scores = score_extraction(data, LABELS)
        assert 0.0 < scores["skills_f1"] < 1.0

    def test_string_skills_accepted(self):
        data = _perfect_extraction()
        data["skills"] = ["Python", "SQL", "Airflow"]
        assert score_extraction(data, LABELS)["skills_f1"] == 1.0

    def test_fuzzy_title_containment(self):
        data = _perfect_extraction()
        data["experience"][0]["title"] = "Senior Data Engineer (Platform)"
        assert score_extraction(data, LABELS)["experience_titles"] == 1.0


class TestHelpers:
    def test_norm(self):
        assert norm("  Maya   CHEN ") == "maya chen"
        assert norm(None) == ""

    def test_norm_phone(self):
        assert norm_phone("(555) 201-3345") == "5552013345"

    def test_aggregate_means_fields(self):
        agg = aggregate([{f: 1.0 for f in ALL_FIELDS}, {f: 0.0 for f in ALL_FIELDS}])
        assert all(v == 0.5 for v in agg.values())

    def test_aggregate_empty(self):
        agg = aggregate([])
        assert all(v == 0.0 for v in agg.values())
