import frontend.modules.candidate_matching as cm


def test_render_match_card_returns_html():
    sample = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "location": "Remote",
        "position": "Software Engineer",
        "current_company": "Acme",
        "experience_years": 5,
        "education": "BS Computer Science",
        "skills": ["Python", "Django", "AWS"],
        "experience": [{"title": "Engineer", "company": "Acme", "duration": "2y"}],
        "headline": "Experienced engineer",
        "match_score": 92,
        "match_explanation": "Great fit on skills and experience",
    }

    html = cm.render_match_card(sample)
    assert isinstance(html, str)
    assert "<div" in html
    assert "Jane Doe" in html
