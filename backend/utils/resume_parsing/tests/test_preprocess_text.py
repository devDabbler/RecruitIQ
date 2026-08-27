"""Regression tests for _MiniExperienceParser._preprocess_text.

The punctuation-normalization regexes in ``_preprocess_text`` were
encoding-corrupted: their ``\\u20XX`` escapes lost the ``\\u20`` prefix,
turning character classes like ``[\\u201C\\u201D]`` into ``[<1C<1D]``.
The class then matched the literal characters ``<``, ``1``, ``C``, ``D``
and rewrote plain ASCII, e.g. 'Full Stack Developer' -> 'Full Stack
"eveloper', and destroyed every digit 1/2/3/4/8/9 (so no date pattern
could ever match downstream).

These tests pin the intended behaviour: ASCII passes through untouched,
and smart quotes / unicode dashes / bullet variants are normalized.
"""

from backend.utils.resume_parsing.extractors.regex_extractor import (
    _MiniExperienceParser,
)


def test_preprocess_leaves_plain_ascii_untouched():
    parser = _MiniExperienceParser()
    line = "Full Stack Developer at TechCorp - San Francisco, CA (2018 - 2020)"
    assert parser._preprocess_text(line) == line


def test_preprocess_normalizes_unicode_punctuation():
    parser = _MiniExperienceParser()
    raw = "“Quoted” ‘word’ 2013–2014 ◦ item"
    expected = "\"Quoted\" 'word' 2013-2014 • item"
    assert parser._preprocess_text(raw) == expected
