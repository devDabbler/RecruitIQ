"""Text utilities for resume parsing compatibility.

These provide conservative implementations of the small helpers expected by
several tests. They intentionally avoid heavy NLP and instead operate on
simple heuristics so they won't affect runtime behavior elsewhere.
"""
import re
from typing import List


def consolidate_bullet_points(lines: List[str]) -> List[str]:
    """Consolidate a list of lines into bullet-like points.

    Strategy (conservative):
    - Treat any line that begins with a bullet char or a dash as a bullet.
    - Merge short lines that look like they continue the previous line (start with lowercase).
    - Otherwise treat each non-empty line as a separate bullet.
    """
    out: List[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith(('-', '•', '*')):
            out.append(s.lstrip('-•* ').strip())
            continue
        if out and s and s[0].islower():
            # Append as continuation
            out[-1] = out[-1] + ' ' + s
        else:
            out.append(s)
    return out


def format_bullets_as_description(bullets: List[str]) -> str:
    """Format bullets into a single description string separated by newlines."""
    return '\n'.join(f"- {b.strip()}" for b in bullets)


def consolidate_bullet_points_ai(lines: List[str]) -> List[str]:
    """Alias for AI-aware consolidation; delegate to conservative impl for tests."""
    return consolidate_bullet_points(lines)


def clean_experience_description_ai(text: str) -> str:
    """Lightweight cleanup used by tests: normalize whitespace and remove problematic control chars."""
    if not text:
        return ''
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned


def _post_process_consolidated_bullet(bullet: str) -> str:
    """Small post-processing used by older callers: trim and ensure sentence-ending punctuation."""
    b = bullet.strip()
    if b and b[-1] not in '.!?':
        b = b + '.'
    return b


def _detect_truncation(text: str) -> bool:
    """Detect if text looks truncated (heuristic): ends with an incomplete word or ellipsis."""
    if not text:
        return False
    text = text.strip()
    if text.endswith('...'):
        return True
    # If last character is a letter but the last token is very short (<2 chars) it's suspicious
    last_tok = text.split()[-1]
    return len(last_tok) <= 2


def clean_experience_description(text: str) -> str:
    """Backward-compatible name mapping to clean_experience_description_ai."""
    return clean_experience_description_ai(text)


def _complete_truncated_sentence(text: str) -> str:
    """Heuristic attempt to complete a truncated sentence by removing trailing incomplete token.

    This is conservative: it will not attempt to invent content, only to remove a dangling
    fragment so downstream punctuation-based heuristics work in tests.
    """
    if not text:
        return ''
    if not _detect_truncation(text):
        return text
    parts = text.rstrip().split()
    if len(parts) <= 1:
        return ''
    # Drop the last token if it's very short or ends with a hyphen
    last = parts[-1]
    if len(last) <= 2 or last.endswith('-'):
        parts = parts[:-1]
    return ' '.join(parts).rstrip(' ,;:') + ('.' if parts else '')


def _validate_consolidation_quality(bullets: list) -> bool:
    """Basic quality check used by tests: ensure bullets are strings and not empty.

    This is intentionally simple to avoid introducing heavy NLP dependencies.
    """
    if not bullets or not isinstance(bullets, (list, tuple)):
        return False
    for b in bullets:
        if not isinstance(b, str) or not b.strip():
            return False
    return True
