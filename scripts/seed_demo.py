"""Seed the demo dataset (Phase 3 spec §7).

Idempotent: safe to run repeatedly. Every row is keyed on a natural identifier
(candidate email, job title+department, the application/saved-job pairs), so a
second run updates in place rather than duplicating. Re-running after a schema
change is the intended way to repair a half-populated database.

    poetry run python scripts/seed_demo.py
    poetry run python scripts/seed_demo.py --no-embeddings   # skip Ollama

Authored during Phase 3 rather than Phase 4 because a Dashboard or Matching
screen cannot be built or verified against an empty database. Phase 4 loads this
same script on the droplet, so the public demo shows what was developed against.

Two things this deliberately does *not* do:

- Create an admin. That needs a password, and a password in a seed script is a
  password in git. `scripts/create_admin.py` prompts for one.
- Persist match scores. There is no match-score table; /api/enhanced-matching/*
  computes them live from the pgvector embeddings this script writes. Seeding
  the embeddings *is* seeding the match scores.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import zlib

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.models.models import (
    Candidate,
    CandidateSkill,
    Job,
    JobApplication,
    SavedJob,
)
from backend.utils.auth import get_or_create_demo_user
from backend.utils.database import SessionLocal

# Fixed seeds: the same run produces the same pipeline, so a screenshot taken
# today still matches the database next month.
#
# One RNG *per stage* rather than one shared generator. A shared one would be
# consumed a different number of times on a second run -- the `or _phone(rng)`
# calls below short-circuit once a value exists -- so every later draw would
# shift and a "no-op" re-run would silently reshuffle the whole funnel.
RNG_SEED = 20260827
SEED_FIELDS = RNG_SEED + 1
SEED_FUNNEL = RNG_SEED + 2
SEED_SAVED = RNG_SEED + 3


def stable_index(value: str, modulus: int) -> int:
    """Deterministic bucket for a string.

    Not `hash()`: Python randomises string hashing per process unless
    PYTHONHASHSEED is pinned, so `hash(id) % n` would pick a different job on
    every run and quietly make this script non-idempotent.
    """
    return zlib.crc32(value.encode("utf-8")) % modulus

TARGET_CANDIDATES = 40
TARGET_JOBS = 8

# Statuses come from CandidateStatus in backend/models/candidate.py. Weighted to
# look like a real funnel rather than a uniform spread -- most people sit at the
# top of it.
PIPELINE_WEIGHTS = [
    ("active", 10),
    ("screening", 6),
    ("interviewing", 5),
    ("offered", 2),
    ("hired", 2),
    ("rejected", 4),
    ("on_hold", 2),
]

SOURCES = ["linkedin", "referral", "job_board", "indeed", "direct_application", "agency"]

# Applications mirror the candidate's own funnel position; a candidate who is
# "interviewing" should not show a "submitted" application against the job they
# are interviewing for.
STATUS_TO_APPLICATION = {
    "active": "submitted",
    "screening": "reviewing",
    "interviewing": "interviewing",
    "offered": "interviewing",
    "hired": "accepted",
    "rejected": "rejected",
    "on_hold": "reviewing",
}

NEW_JOBS = [
    {
        "title": "Machine Learning Engineer",
        "department": "Engineering",
        "job_overview": (
            "Build and ship production ML systems: feature pipelines, training "
            "infrastructure, and low-latency inference services."
        ),
        "required_qualifications": (
            "3+ years building ML systems in production\n"
            "Strong Python and PyTorch or TensorFlow\n"
            "Experience with feature stores and model serving\n"
            "Comfortable owning a service end to end"
        ),
        "location": "Seattle, WA",
        "location_type": "hybrid",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 165000,
        "max_salary": 210000,
        "skills": "Python,PyTorch,MLflow,Kubernetes,AWS,Feature Engineering",
    },
    {
        "title": "Engineering Manager, Platform",
        "department": "Engineering",
        "job_overview": (
            "Lead the platform team that owns data infrastructure, CI/CD, and "
            "the internal developer experience. Six engineers, two of them senior."
        ),
        "required_qualifications": (
            "2+ years managing engineers, with a hands-on background\n"
            "Has run a platform or infrastructure team\n"
            "Track record hiring and growing senior engineers\n"
            "Fluent in distributed systems trade-offs"
        ),
        "location": "Remote, US",
        "location_type": "remote",
        "job_type": "full_time",
        "experience_level": "senior",
        "min_salary": 195000,
        "max_salary": 245000,
        "skills": "Leadership,Distributed Systems,Kubernetes,Terraform,Hiring,Mentorship",
    },
]

# 17 candidates to bring the existing 23 up to 40. Positions deliberately span
# all eight jobs so the Matching screen has plausible pairings to rank.
NEW_CANDIDATES = [
    ("Priya", "Raghavan", "Seattle, WA", "ML Engineer scaling recsys to 40M users",
     "Machine Learning Engineer", "Senior ML Engineer", "Instacart",
     ["Python", "PyTorch", "Kubernetes", "MLflow", "Feature Engineering", "AWS"]),
    ("Marcus", "Bell", "Austin, TX", "Platform lead, ex-Stripe infrastructure",
     "Engineering Manager, Platform", "Engineering Manager", "Stripe",
     ["Leadership", "Kubernetes", "Terraform", "Distributed Systems", "Hiring", "Go"]),
    ("Yuki", "Tanaka", "San Francisco, CA", "LLM systems engineer, retrieval and evals",
     "Gen AI Engineer", "AI Engineer", "Notion",
     ["Python", "LangChain", "RAG", "Prompt Engineering", "PostgreSQL", "pgvector"]),
    ("Daniel", "Okonkwo", "Chicago, IL", "Data engineer, streaming pipelines at scale",
     "Data Engineer", "Senior Data Engineer", "Grubhub",
     ["Python", "Spark", "Kafka", "Airflow", "dbt", "Snowflake"]),
    ("Elena", "Vasquez", "Denver, CO", "Applied scientist, causal inference and experimentation",
     "Senior Data Scientist", "Staff Data Scientist", "Zillow",
     ["Python", "R", "Causal Inference", "Experimentation", "SQL", "Statistics"]),
    ("Sam", "Whitfield", "Remote, US", "Full stack engineer, React and Python",
     "Software Development Engineer", "Software Engineer", "Shopify",
     ["TypeScript", "React", "Python", "FastAPI", "PostgreSQL", "Docker"]),
    ("Amara", "Diallo", "New York, NY", "Product manager for ML-powered search",
     "Product Manager", "Senior Product Manager", "Spotify",
     ["Product Strategy", "Roadmapping", "SQL", "A/B Testing", "Stakeholder Management"]),
    ("Jonas", "Lindqvist", "Boston, MA", "Recent MS in Statistics, two ML internships",
     "Junior Data Scientist", "Data Science Intern", "Wayfair",
     ["Python", "Pandas", "Scikit-learn", "SQL", "Data Visualization"]),
    ("Rachel", "Kim", "Seattle, WA", "MLOps engineer, model serving and monitoring",
     "Machine Learning Engineer", "MLOps Engineer", "Zillow",
     ["Python", "Kubernetes", "MLflow", "Prometheus", "AWS", "CI/CD"]),
    ("Tobias", "Herrmann", "Remote, US", "Backend engineer moving into platform work",
     "Engineering Manager, Platform", "Staff Engineer", "Datadog",
     ["Go", "Distributed Systems", "Terraform", "Kubernetes", "Mentorship"]),
    ("Nina", "Petrova", "San Francisco, CA", "NLP engineer, fine-tuning and evaluation",
     "Gen AI Engineer", "NLP Engineer", "Scale AI",
     ["Python", "PyTorch", "Transformers", "LLM Evaluation", "Hugging Face"]),
    ("Carlos", "Mendes", "Miami, FL", "Analytics engineer, dbt and warehouse modeling",
     "Data Engineer", "Analytics Engineer", "MercadoLibre",
     ["SQL", "dbt", "Snowflake", "Python", "Airflow", "Data Modeling"]),
    ("Hannah", "Bright", "Portland, OR", "Data scientist, forecasting and pricing",
     "Senior Data Scientist", "Data Scientist", "Nike",
     ["Python", "Time Series", "Forecasting", "SQL", "Statistics", "Tableau"]),
    ("Omar", "Haddad", "Austin, TX", "Frontend-leaning full stack, design systems",
     "Software Development Engineer", "Senior Frontend Engineer", "Atlassian",
     ["TypeScript", "React", "Next.js", "Tailwind CSS", "Accessibility", "Testing"]),
    ("Grace", "Sullivan", "Remote, US", "Technical PM, developer platform",
     "Product Manager", "Technical Product Manager", "Twilio",
     ["Product Strategy", "APIs", "Developer Experience", "SQL", "Roadmapping"]),
    ("Wei", "Zhang", "Boston, MA", "New grad, strong Kaggle record",
     "Junior Data Scientist", "Research Assistant", "MIT",
     ["Python", "Pandas", "Scikit-learn", "Data Cleaning", "SQL"]),
    ("Isabel", "Moreau", "Chicago, IL", "Data platform engineer, lakehouse migrations",
     "Data Engineer", "Data Platform Engineer", "McDonald's",
     ["Python", "Spark", "Delta Lake", "Airflow", "AWS", "Terraform"]),
]

EMAIL_DOMAIN = "demo.recruitiq.dev"


def _email(first: str, last: str) -> str:
    return f"{first}.{last}".lower().replace(" ", "").replace("'", "") + f"@{EMAIL_DOMAIN}"


def _phone(rng: random.Random) -> str:
    return f"{rng.randint(200, 989)}-{rng.randint(200, 989)}-{rng.randint(1000, 9999)}"


def _weighted_statuses(rng: random.Random, n: int) -> list[str]:
    """Deterministic funnel: build the exact distribution, then shuffle it.

    Sampling independently would let a small n drift far from the weights and
    leave, say, zero candidates in "interviewing" -- an empty column on the
    Dashboard.
    """
    pool: list[str] = []
    total_weight = sum(w for _, w in PIPELINE_WEIGHTS)
    for status, weight in PIPELINE_WEIGHTS:
        pool.extend([status] * max(1, round(n * weight / total_weight)))
    while len(pool) < n:
        pool.append("active")
    pool = pool[:n]
    rng.shuffle(pool)
    return pool


def seed_jobs(db) -> list[Job]:
    for spec in NEW_JOBS:
        job = (
            db.query(Job)
            .filter(Job.title == spec["title"], Job.department == spec["department"])
            .first()
        )
        if job is None:
            job = Job(**spec, status="open", job_metadata={}, views=0, applications=0)
            db.add(job)
        else:
            for key, value in spec.items():
                setattr(job, key, value)
    db.commit()

    jobs = db.query(Job).order_by(Job.id).all()
    # Views are cosmetic, but a job listing showing 0 views everywhere reads as
    # broken rather than new. Derived from the id so the number is stable across
    # runs instead of depending on how many draws earlier stages made.
    for job in jobs:
        if not job.views:
            job.views = 18 + stable_index(f"views-{job.id}", 322)
    db.commit()
    return jobs


def seed_candidates(db, rng: random.Random) -> list[Candidate]:
    for (
        first,
        last,
        location,
        headline,
        position_applied,
        current_position,
        current_company,
        skills,
    ) in NEW_CANDIDATES:
        email = _email(first, last)
        candidate = db.query(Candidate).filter(Candidate.email == email).first()
        if candidate is None:
            candidate = Candidate(email=email)
            db.add(candidate)
            db.flush()  # need candidate.id for the skill rows below
        candidate.first_name = first
        candidate.last_name = last
        candidate.location = location
        candidate.headline = headline
        candidate.position_applied = position_applied
        candidate.current_position = current_position
        candidate.current_company = current_company
        candidate.phone = candidate.phone or _phone(rng)
        candidate.source = candidate.source or rng.choice(SOURCES)

        existing = {s.skill_name for s in candidate.skills}
        for skill_name in skills:
            if skill_name not in existing:
                db.add(
                    CandidateSkill(
                        candidate_id=candidate.id,
                        skill_name=skill_name,
                        proficiency=rng.choice(["intermediate", "advanced", "expert"]),
                        years_of_experience=rng.randint(1, 9),
                    )
                )
    db.commit()

    # Every candidate gets a funnel position, including the ones already in the
    # database from earlier phases -- 7 of those carry a NULL status, which the
    # Dashboard would otherwise render as a blank column.
    candidates = db.query(Candidate).order_by(Candidate.created_at, Candidate.id).all()
    funnel_rng = random.Random(SEED_FUNNEL)
    for candidate, status in zip(candidates, _weighted_statuses(funnel_rng, len(candidates))):
        if not candidate.status or candidate.status == "active":
            candidate.status = status
    db.commit()
    return candidates


def seed_pipeline(db, candidates: list[Candidate], jobs: list[Job]) -> None:
    """Applications and saved jobs, consistent with each candidate's status."""
    by_title = {job.title: job for job in jobs}

    for candidate in candidates:
        # Prefer the job the candidate actually applied for; fall back to a
        # stable arbitrary one so every candidate appears somewhere.
        job = by_title.get(candidate.position_applied or "") or jobs[
            stable_index(candidate.id, len(jobs))
        ]
        app_status = STATUS_TO_APPLICATION.get(candidate.status or "active", "submitted")

        application = (
            db.query(JobApplication)
            .filter(
                JobApplication.job_id == job.id,
                JobApplication.candidate_id == candidate.id,
            )
            .first()
        )
        if application is None:
            application = JobApplication(job_id=job.id, candidate_id=candidate.id)
            db.add(application)
        application.status = app_status
        application.source = candidate.source or "direct"
        application.notes = f"Seeded demo application ({app_status})."

        # A third of candidates also save an unrelated job, so the saved-jobs
        # route returns something on the Candidate Detail screen. Decided from
        # the candidate id, not a draw, so re-running picks the same third.
        if stable_index(f"saved-{candidate.id}", 100) < 34:
            others = [j for j in jobs if j.id != job.id]
            other = others[stable_index(f"which-{candidate.id}", len(others))]
            saved = (
                db.query(SavedJob)
                .filter(SavedJob.job_id == other.id, SavedJob.candidate_id == candidate.id)
                .first()
            )
            if saved is None:
                db.add(
                    SavedJob(
                        job_id=other.id,
                        candidate_id=candidate.id,
                        notes="Saved for later.",
                    )
                )
    db.commit()

    # Job.applications is a denormalised counter the Jobs screen reads directly.
    for job in jobs:
        job.applications = (
            db.query(JobApplication).filter(JobApplication.job_id == job.id).count()
        )
    db.commit()


def embed(db, candidates: list[Candidate], jobs: list[Job]) -> None:
    from backend.services.ollama_embeddings import OllamaEmbeddingAdapter
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(
        embedding_model=OllamaEmbeddingAdapter(
            base_url=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai")
        )
    )
    missing_jobs = [j for j in jobs if j.embedding is None]
    missing_candidates = [c for c in candidates if c.embedding is None]

    ok = sum(bool(svc.store_job_embedding(db, j.id)) for j in missing_jobs)
    print(f"  jobs embedded:       {ok}/{len(missing_jobs)} (of {len(jobs)} total)")
    ok = sum(bool(svc.store_candidate_embedding(db, c.id)) for c in missing_candidates)
    print(f"  candidates embedded: {ok}/{len(missing_candidates)} (of {len(candidates)} total)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="skip the Ollama round trips (leaves new rows unsearchable by vector)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        get_or_create_demo_user(db)

        jobs = seed_jobs(db)
        candidates = seed_candidates(db, random.Random(SEED_FIELDS))
        seed_pipeline(db, candidates, jobs)

        if args.no_embeddings:
            print("  embeddings skipped (--no-embeddings)")
        else:
            embed(db, candidates, jobs)

        if len(candidates) < TARGET_CANDIDATES or len(jobs) < TARGET_JOBS:
            print(
                f"  note: {len(candidates)}/{TARGET_CANDIDATES} candidates, "
                f"{len(jobs)}/{TARGET_JOBS} jobs",
                file=sys.stderr,
            )

        funnel: dict[str, int] = {}
        for candidate in candidates:
            funnel[candidate.status or "unset"] = funnel.get(candidate.status or "unset", 0) + 1
        print(f"  candidates: {len(candidates)}  jobs: {len(jobs)}")
        print(f"  applications: {db.query(JobApplication).count()}  "
              f"saved: {db.query(SavedJob).count()}")
        print(f"  funnel: {dict(sorted(funnel.items()))}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
