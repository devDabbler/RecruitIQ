"""Tag normalization (ATS Phase C, spec 2026-10-03 section 3.1: lower-kebab-case on write).

Mirrored by `normalizeTag` in web/src/lib/intake.ts, and both are pinned by the
same table of cases, so the preview under the tag input always shows exactly
what the server will store.
"""
from __future__ import annotations

import re
import unicodedata

MAX_TAG_LENGTH = 50

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_tag(raw: str) -> str:
    """`"C# Developer"` -> `"csharp-developer"`. Raises ValueError when nothing usable is left."""
    folded = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode("ascii")
    text = folded.lower().replace("+", "plus").replace("#", "sharp")
    tag = _NON_ALNUM.sub("-", text).strip("-")[:MAX_TAG_LENGTH].rstrip("-")
    if not tag:
        raise ValueError("A tag needs at least one letter or number.")
    return tag
