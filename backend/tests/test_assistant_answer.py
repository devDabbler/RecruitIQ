"""The answer finalizer: what both chat endpoints do to the model's text.

The local 8B model writes a single subject in bold instead of the profile
link the prompt asks for ("**Senior Data Scientist** requires ..."), and the
chat renderer shows a link inside bold as literal text. So the server links
returned names itself, the way it already normalises dashes.
"""
from __future__ import annotations

from backend.services.assistant_answer import entities_in, finalize_answer, linkify

ADA = {"id": "c-1", "name": "Ada Lovelace", "current_position": "Senior Data Scientist"}
JOB = {"id": 7, "title": "Senior Data Scientist", "status": "open"}
JUNIOR = {"id": 8, "title": "Junior Data Scientist", "status": "open"}
DS = {"id": 9, "title": "Data Scientist", "status": "closed"}


class TestLinkify:
    def test_bold_subject_becomes_a_link(self):
        text = "**Senior Data Scientist** requires:\n- Python\n- SQL"
        assert linkify(text, [JOB]) == "[Senior Data Scientist](/jobs/7) requires:\n- Python\n- SQL"

    def test_plain_mention_becomes_a_link_once(self):
        text = "Ada Lovelace is a strong fit. Ada Lovelace has Python."
        out = linkify(text, [ADA])
        assert out == "[Ada Lovelace](/candidates/c-1) is a strong fit. Ada Lovelace has Python."

    def test_existing_link_to_the_same_id_is_left_alone(self):
        text = "[Ada](/candidates/c-1) is a fit, and Ada Lovelace knows SQL."
        assert linkify(text, [ADA]) == text

    def test_existing_link_labels_are_not_relinked(self):
        # The name inside another link's label is not a plain mention.
        text = "See [Ada Lovelace's profile](/candidates/c-1)."
        assert linkify(text, [ADA]) == text

    def test_longer_title_wins_over_the_one_inside_it(self):
        text = "Did you mean Senior Data Scientist or Junior Data Scientist? Data Scientist is closed."
        out = linkify(text, [{"matching_jobs": [JOB, JUNIOR, DS]}])
        assert out == (
            "Did you mean [Senior Data Scientist](/jobs/7) or [Junior Data Scientist](/jobs/8)? "
            "[Data Scientist](/jobs/9) is closed."
        )

    def test_match_is_whole_word_and_case_insensitive(self):
        assert linkify("the senior data scientist role", [JOB]) == "the [senior data scientist](/jobs/7) role"
        assert linkify("XSenior Data Scientists", [JOB]) == "XSenior Data Scientists"

    def test_possessive_keeps_the_apostrophe_outside(self):
        assert linkify("Ada Lovelace's resume lists SQL.", [ADA]) == "[Ada Lovelace](/candidates/c-1)'s resume lists SQL."

    def test_names_no_tool_returned_are_untouched(self):
        text = "There is no Chief Happiness Officer job. Grace Hopper is not in the ATS."
        assert linkify(text, [{"error": "No job", "open_jobs": [JOB]}]) == text

    def test_bold_around_a_model_written_link_is_unwrapped(self):
        # The renderer would show this as literal "[Ada](/candidates/c-1)" in bold.
        text = "**[Ada Lovelace](/candidates/c-1)** is a fit."
        assert linkify(text, [ADA]) == "[Ada Lovelace](/candidates/c-1) is a fit."

    def test_bold_span_with_extra_words_keeps_them(self):
        text = "**Senior Data Scientist role**: open in Austin."
        assert linkify(text, [JOB]) == "[Senior Data Scientist](/jobs/7) role: open in Austin."

    def test_every_tool_shape_is_understood(self):
        found = entities_in(
            [
                {"job_id": 7, "job_title": "Senior Data Scientist", "matches": [ADA]},
                {"job": JUNIOR, "candidate": {"id": "c-2", "name": "Grace Hopper"}},
                {"candidate": "Alan Turing", "candidate_id": "c-3", "parsed_content": "..."},
                {"applied_job": DS},
            ]
        )
        assert found["candidates"] == {"c-1": "Ada Lovelace", "c-2": "Grace Hopper", "c-3": "Alan Turing"}
        assert found["jobs"] == {"7": "Senior Data Scientist", "8": "Junior Data Scientist", "9": "Data Scientist"}

    def test_no_results_or_empty_text_is_a_no_op(self):
        assert linkify("Hello! Ask me about candidates.", []) == "Hello! Ask me about candidates."
        assert linkify("", [ADA]) == ""

    def test_very_short_names_are_not_linked(self):
        # A two-letter name would link every "AI" in the answer.
        assert linkify("AI roles are open.", [{"id": 3, "title": "AI"}]) == "AI roles are open."


class TestRepairLinks:
    def test_mistyped_id_is_repaired_from_the_label(self):
        # Seen live: the cloud model doubled a character in a UUID.
        ada = {"id": "5f9a1a3c-3ebe-40e5-8c4b-f707a2d2c4bb", "name": "Adam Templeton"}
        text = "[Adam Templeton](/candidates/5f9a1a1a3c-3ebe-40e5-8c4b-f707a2d2c4bb) against [Senior Data Scientist](/jobs/19)."
        out = linkify(text, [{"candidate": ada, "job": {"id": 19, "title": "Senior Data Scientist"}}])
        assert out == "[Adam Templeton](/candidates/5f9a1a3c-3ebe-40e5-8c4b-f707a2d2c4bb) against [Senior Data Scientist](/jobs/19)."

    def test_missing_id_is_filled_in(self):
        assert linkify("[Senior Data Scientist](/jobs/)", [JOB]) == "[Senior Data Scientist](/jobs/7)"

    def test_first_name_label_repairs_when_unique(self):
        assert linkify("[Ada](/candidates/nope)", [ADA]) == "[Ada](/candidates/c-1)"

    def test_ambiguous_or_unknown_label_is_left_alone(self):
        two = [ADA, {"id": "c-2", "name": "Ada Byron"}]
        assert linkify("[Ada](/candidates/nope)", two) == "[Ada](/candidates/nope)"
        assert linkify("[Grace Hopper](/candidates/nope)", [ADA]) == "[Grace Hopper](/candidates/nope)"

    def test_wrong_kind_is_not_repaired(self):
        # A job title under /candidates/ is a different mistake; leave it for the checker.
        text = "[Senior Data Scientist](/candidates/7)"
        assert linkify(text, [JOB]) == text


class TestFinalizeAnswer:
    def test_dashes_then_links(self):
        text = "**Ada Lovelace** – Senior Data Scientist — $80,000–$110,000"
        assert finalize_answer(text, [ADA, JOB]) == (
            "[Ada Lovelace](/candidates/c-1) - [Senior Data Scientist](/jobs/7) - $80,000-$110,000"
        )

    def test_none_is_empty(self):
        assert finalize_answer(None, []) == ""
