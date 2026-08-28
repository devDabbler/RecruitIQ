"""Field-level scoring of extracted resume data against ground-truth labels.

Scalar fields (name/email/phone/location) score exact-match after
normalization. List fields (titles, companies, institutions) score set
recall with fuzzy containment. Skills score set F1.
"""
from __future__ import annotations

import re
from typing import Dict, List

SCALAR_FIELDS = ["name", "email", "phone", "location"]
LIST_FIELDS = ["experience_titles", "experience_companies", "education_institutions"]


def norm(value) -> str:
    if value is None:
        return ""
    s = str(value).lower().strip()
    s = re.sub(r"[^a-z0-9@+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_phone(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _fuzzy_in(needle: str, haystack: List[str]) -> bool:
    n = norm(needle)
    if not n:
        return False
    for h in haystack:
        hn = norm(h)
        if n == hn or n in hn or hn in n:
            return True
    return False


def score_extraction(extracted: dict, labels: dict) -> Dict[str, float]:
    """Return per-field scores in [0, 1] for one fixture."""
    scores: Dict[str, float] = {}

    personal = extracted.get("personal_info") or {}
    scores["name"] = 1.0 if norm(personal.get("name")) == norm(labels["name"]) else 0.0
    scores["email"] = 1.0 if norm(personal.get("email")) == norm(labels["email"]) else 0.0
    scores["phone"] = 1.0 if norm_phone(personal.get("phone")) == norm_phone(labels["phone"]) else 0.0
    got_loc = norm(personal.get("location"))
    want_loc = norm(labels["location"])
    scores["location"] = 1.0 if want_loc and (want_loc in got_loc or got_loc == want_loc) and got_loc else 0.0

    experiences = extracted.get("experience") or []
    got_titles = [e.get("title", "") for e in experiences if isinstance(e, dict)]
    got_companies = [e.get("company", "") for e in experiences if isinstance(e, dict)]
    scores["experience_titles"] = _recall(labels["experience_titles"], got_titles)
    scores["experience_companies"] = _recall(labels["experience_companies"], got_companies)

    education = extracted.get("education") or []
    got_institutions = [e.get("institution", "") for e in education if isinstance(e, dict)]
    scores["education_institutions"] = _recall(labels["education_institutions"], got_institutions)

    raw_skills = extracted.get("skills") or []
    got_skills = [s.get("name", "") if isinstance(s, dict) else str(s) for s in raw_skills]
    scores["skills_f1"] = _set_f1(labels["skills"], got_skills)

    return scores


def _recall(wanted: List[str], got: List[str]) -> float:
    """One-to-one matching: each extracted item can satisfy only one label,
    so 'Senior Data Engineer' can't count for both it and 'Data Engineer'."""
    if not wanted:
        return 1.0
    remaining = [norm(g) for g in got if norm(g)]
    hits = 0
    unmatched = []
    # pass 1: exact matches, so fuzzy pairing can't steal them
    for w in wanted:
        wn = norm(w)
        if wn in remaining:
            remaining.remove(wn)
            hits += 1
        else:
            unmatched.append(wn)
    # pass 2: fuzzy containment on what's left
    for wn in unmatched:
        for i, r in enumerate(remaining):
            if wn and (wn in r or r in wn):
                del remaining[i]
                hits += 1
                break
    return hits / len(wanted)


def _set_f1(wanted: List[str], got: List[str]) -> float:
    got_clean = [g for g in got if norm(g)]
    if not wanted and not got_clean:
        return 1.0
    if not wanted or not got_clean:
        return 0.0
    tp = sum(1 for w in wanted if _fuzzy_in(w, got_clean))
    precision_tp = sum(1 for g in got_clean if _fuzzy_in(g, wanted))
    recall = tp / len(wanted)
    precision = precision_tp / len(got_clean)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


ALL_FIELDS = SCALAR_FIELDS + LIST_FIELDS + ["skills_f1"]


def aggregate(per_fixture: List[Dict[str, float]]) -> Dict[str, float]:
    """Mean score per field across fixtures."""
    if not per_fixture:
        return {f: 0.0 for f in ALL_FIELDS}
    return {f: sum(s.get(f, 0.0) for s in per_fixture) / len(per_fixture) for f in ALL_FIELDS}
