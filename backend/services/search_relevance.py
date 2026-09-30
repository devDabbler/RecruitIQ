"""Relevance banding for the assistant's semantic candidate search.

Cosine similarity from nomic-embed-text has a high, query-dependent
baseline. Measured on the demo seed (2026-09-30, 63 candidates with real
vectors), a query that nobody in the pipeline could match still scores
0.43 to 0.64 against every profile, while real matches score 0.65 to 0.78:

    query                          top hit                          similarity
    plumber                        Senior Data Engineer             0.551
    underwater welders             Senior Software Engineer         0.535
    accountant                     Summer Associate, Data Analyst   0.563
    civil engineer                 Software Development Engineer    0.618
    mechanical engineer            Systems Engineer                 0.639
    commercial airline pilots      airline analytics engineer       0.600
    someone strong in SQL and dbt  Analytics Engineer               0.645
    people with kubernetes exp.    Site Reliability Manager         0.570
    machine learning engineers     Machine Learning Engineer        0.776
    data scientists                Data Scientist                   0.755

"Mechanical engineer" at 0.639 and "SQL and dbt" at 0.645 sit five
thousandths apart, so no similarity threshold on its own can tell a partial
match from the closest unrelated person. The old strong/moderate/weak bands
at 0.55/0.45 called every one of the unrelated hits above "moderate", which
is how a plumber search came back with three data engineers described as
partial matches.

The banding here is hybrid: the embedding still ranks, but a hit is only
called a match when the numbers or the words back it up.

    strong    similarity at or above RELEVANCE_BANDS["strong"]. The profile
              is about what was asked, even when no word is shared
              (paraphrases and synonyms are what the embedding is for).
    moderate  similarity at or above RELEVANCE_BANDS["moderate"] and at
              least one specific word from the query appears in the
              candidate's position, company, headline or skills, the same
              fields the embedding saw. The words travel with the hit as
              `matched_on`, so an answer can say what the partial match is
              a match on ("airline", not "commercial airline pilot").
    weak      everything else above the search floor. Kept out of the
              assistant's results entirely; the transparency page shows
              them with the reason.

Generic role words (engineer, manager, senior, analyst) never count as
evidence: "retail store managers" must not make every product manager a
partial match, and "mechanical engineer" must not light up every engineer.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

# Cosine similarity floors for each band. Published by the transparency
# endpoint. "moderate" additionally needs lexical evidence (see module doc).
RELEVANCE_BANDS: Dict[str, float] = {"strong": 0.65, "moderate": 0.45}

# The fields lexical evidence is read from, in the order they are joined.
# Deliberately the same fields the embedding text is built from
# (vector_search_service._candidate_text), so the transparency page can show
# one string and say "this is everything both checks looked at".
EVIDENCE_FIELDS: Tuple[str, ...] = ("position", "company", "headline", "skills")

# How many rows above the floor the search pulls before banding and
# re-ranking. A candidate whose headline names the industry asked for can
# sit at 0.47 behind a dozen engineers at 0.55 who share nothing but
# vocabulary; the pool has to reach that far down for evidence to matter.
# The demo dataset is a few dozen people and prod a few dozen more, so this
# is the whole pipeline in practice, and each row is a handful of strings.
SEARCH_POOL_SIZE = 100

# Words that describe the ask rather than the person. Stripped before
# evidence is looked for.
STOPWORDS = frozenset(
    """
    a an the and or of for to in on at with without from by as is are be who
    whom whose that which what any anyone anybody some someone somebody people
    person persons candidate candidates folks profiles profile talent
    find me show list give get need want looking look search seeking hire hiring
    have has having had worked working work works experience experienced
    background expertise skill skills skilled knowledge know knows knowing
    proficient proficiency familiar familiarity strong solid good great deep
    years year plus based located available open current currently recent
    recently former previous previously new our we you your i my their them
    they it its this these those there here also very really quite rather
    can could would should will about into over under between across around
    """.split()
)

# Role vocabulary that appears in nearly every title. Present in the query
# it says what kind of person is wanted, but finding it in a profile proves
# nothing about the search: "manager" is not evidence that a Technical
# Product Manager is a retail store manager.
GENERIC_ROLE_WORDS = frozenset(
    """
    engineer engineers engineering developer developers dev devs programmer
    programmers coder coders manager managers management director directors
    head heads officer officers chief lead leads leader leaders principal
    staff senior sr junior jr mid midlevel entry associate associates
    specialist specialists analyst analysts scientist scientists architect
    architects designer designers consultant consultants professional
    professionals expert experts intern interns internship contractor
    contractors owner owners coordinator coordinators administrator
    administrators assistant assistants executive executives president
    vp vice role roles position positions job jobs title titles team teams
    software technical technology technologies tech it level levels
    """.split()
)

# Spelling variants and short forms recruiters type. A term matches if it or
# any alias is found. Kept to variants of the same thing, not to related
# concepts: "frontend" must not make every React developer a partial match
# on the strength of a guessed synonym.
ALIASES: Dict[str, Tuple[str, ...]] = {
    "ml": ("machine learning", "machine-learning"),
    "ai": ("artificial intelligence",),
    "genai": ("gen ai", "generative ai", "generative"),
    "nlp": ("natural language",),
    "llm": ("large language", "llms"),
    "llms": ("llm", "large language"),
    "k8s": ("kubernetes",),
    "kubernetes": ("k8s",),
    "js": ("javascript",),
    "javascript": ("js",),
    "ts": ("typescript",),
    "py": ("python",),
    "postgres": ("postgresql",),
    "postgresql": ("postgres",),
    "sre": ("site reliability",),
    "devops": ("dev ops",),
    "frontend": ("front-end", "front end"),
    "backend": ("back-end", "back end"),
    "fullstack": ("full-stack", "full stack"),
    "ux": ("user experience",),
    "ui": ("user interface",),
    "qa": ("quality assurance",),
    "pm": ("product manager", "project manager"),
    "grad": ("graduate",),
    "grads": ("graduate", "new grad"),
    "phd": ("ph.d", "doctorate"),
    "quant": ("quantitative",),
    "fintech": ("financial", "finance", "fintech"),
    "insurtech": ("insurance", "insurtech"),
    "healthtech": ("health", "healthcare", "healthtech"),
    "ecommerce": ("e-commerce", "ecommerce"),
    "e-commerce": ("e-commerce", "ecommerce"),
}

# Words that mean something else inside a tech profile: "agent" is an LLM
# agent, "driver" a device driver, "pilot" a pilot programme, "real" is
# real-time, "model" a machine learning model. Found on its own, such a word
# is not evidence for a query about real estate agents or truck drivers. It
# counts only when another word from the query also matches, or when it is
# the only specific word in the query (a search for "agents" means agents).
AMBIGUOUS_TERMS = frozenset(
    """
    agent agents driver drivers pilot pilots real model models store stores
    operations operation service services support security office field
    market markets network networks stream streams system systems
    """.split()
)

# Two-letter tokens are noise ("go" matches "google") unless they are one of
# these established short forms, which are matched as whole words.
SHORT_TERMS = frozenset(
    "ml ai js ts py ux ui qa pm bi hr go sql aws gcp api etl sre nlp llm cto ios".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")


def query_terms(query: str) -> List[str]:
    """The specific words in a search, in order, without stopwords or
    generic role vocabulary. "people who have worked in insurance" gives
    ["insurance"]; "retail store managers" gives ["retail", "store"];
    "engineers" gives []."""
    terms: List[str] = []
    for raw in _TOKEN_RE.findall(str(query or "").lower()):
        token = raw.strip(".-")
        if not token or token in STOPWORDS or token in GENERIC_ROLE_WORDS:
            continue
        if len(token) < 3 and token not in SHORT_TERMS:
            continue
        if token not in terms:
            terms.append(token)
    return terms


def _stems(term: str) -> List[str]:
    """Prefixes to look for when a term is in the query. English plural and
    inflection endings are trimmed so "nurses" finds "nurse", "welders"
    finds "welder" and "finance" finds "financial"; each stem is still at
    least four characters, so trimming never turns a word into noise."""
    stems = [term]
    if term.endswith("ies") and len(term) > 5:
        stems.append(term[:-3] + "y")
    elif term.endswith("s") and not term.endswith("ss") and len(term) >= 5:
        stems.append(term[:-1])
    if term.endswith("ing") and len(term) >= 7:
        stems.append(term[:-3])
    elif term.endswith("ed") and len(term) >= 6:
        stems.append(term[:-2])
    for stem in list(stems):
        if stem.endswith("e") and len(stem) >= 6:
            stems.append(stem[:-1])
    return [s for s in dict.fromkeys(stems) if len(s) >= 4 or s == term]


def _matches(needle: str, texts: Iterable[str], whole_word: bool) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + (r"(?![a-z0-9])" if whole_word else "")
    return any(re.search(pattern, text) for text in texts)


def evidence_in(text: str, terms: Iterable[str]) -> List[str]:
    """The query terms that appear in `text`: a term counts when the text
    contains it, one of its stems as a word prefix, or one of its aliases.
    Short forms ("ml", "sql") must match as whole words."""
    lowered = str(text or "").lower()
    texts = (lowered, lowered.replace("-", ""), lowered.replace("-", " "))
    matched: List[str] = []
    for term in terms:
        short = len(term) <= 3
        found = _matches(term, texts, whole_word=short)
        if not found and not short:
            found = any(_matches(stem, texts, whole_word=False) for stem in _stems(term)[1:])
        if not found:
            found = any(_matches(alias, texts, whole_word=len(alias) <= 3) for alias in ALIASES.get(term, ()))
        if found:
            matched.append(term)
    return matched


def evidence_holds(terms: Iterable[str], matched_on: Iterable[str]) -> bool:
    """Whether the matched words are enough to call a hit a partial match.

    One unambiguous word is enough ("airline"). An ambiguous word on its own
    is not, unless it is the only specific word the query had: "real estate
    agent" matching only "agent" is an LLM-agents engineer, but "agents"
    matching "agent" is what was asked for. Two matched words of any kind
    hold, since the second one supplies the context.
    """
    terms = list(terms)
    matched = [m for m in matched_on if m]
    if not matched:
        return False
    if len(matched) >= 2 or len(terms) <= 1:
        return True
    return any(m not in AMBIGUOUS_TERMS for m in matched)


def relevance_band(similarity: float, matched_on: Iterable[str] = (), terms: Iterable[str] = None) -> str:
    """strong, moderate or weak for one hit. Without evidence the only way
    to be a match is the strong floor; see the module docstring for why.
    `terms` is the query's own term list, needed to judge an ambiguous
    match; when omitted, the matched words are taken as the whole query."""
    matched = list(matched_on)
    if similarity >= RELEVANCE_BANDS["strong"]:
        return "strong"
    if similarity >= RELEVANCE_BANDS["moderate"] and evidence_holds(
        matched if terms is None else terms, matched
    ):
        return "moderate"
    return "weak"


def profile_text(hit: Dict[str, Any]) -> str:
    """The text evidence is read from: the hit's EVIDENCE_FIELDS, joined."""
    parts = []
    for field in EVIDENCE_FIELDS:
        value = hit.get(field)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value if v)
        if value:
            parts.append(str(value))
    return " | ".join(parts)


_BAND_ORDER = {"strong": 0, "moderate": 1, "weak": 2}


def band_hits(hits: List[Dict[str, Any]], query: str, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
    """Label every hit in place with `matched_on` and `relevance`. Hits under
    `min_similarity` are weak whatever they match on."""
    terms = query_terms(query)
    for hit in hits:
        matched = evidence_in(profile_text(hit), terms)
        hit["matched_on"] = matched
        similarity = float(hit.get("similarity", 0.0))
        hit["relevance"] = (
            "weak" if similarity < min_similarity else relevance_band(similarity, matched, terms)
        )
    return hits


def rank_hits(
    hits: List[Dict[str, Any]], query: str, limit: int, min_similarity: float = 0.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Band a search pool and split it into what the assistant may show and
    what it may not.

    Returns (shown, kept_out). `shown` is the strong hits by similarity,
    then the moderate ones by similarity, cut at `limit`. `kept_out` is
    every weak hit plus any match that fell past the cut, so a caller that
    wants to explain the result can show both lists.
    """
    band_hits(hits, query, min_similarity)
    ordered = sorted(hits, key=lambda h: (_BAND_ORDER[h["relevance"]], -float(h.get("similarity", 0.0))))
    matches = [h for h in ordered if h["relevance"] != "weak"]
    shown = matches[: max(0, int(limit))]
    kept_out = matches[len(shown):] + [h for h in ordered if h["relevance"] == "weak"]
    return shown, kept_out
