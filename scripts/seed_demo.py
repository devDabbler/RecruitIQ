"""Seed the demo dataset (Phase 3 spec §7).

Idempotent: safe to run repeatedly. Every row is keyed on a natural identifier
(candidate email, job title+department, the application/saved-job pairs), so a
second run updates in place rather than duplicating. Re-running after a schema
change is the intended way to repair a half-populated database.

    poetry run python scripts/seed_demo.py
    poetry run python scripts/seed_demo.py --no-embeddings   # skip Ollama
    poetry run python scripts/seed_demo.py --team-only       # team and interviews only
    poetry run python scripts/seed_demo.py --notes-tags-only # notes and tags only
    poetry run python scripts/seed_demo.py --timelines-only  # stage timestamps only

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
from datetime import datetime, timedelta

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.models.models import (
    ApplicationStage,
    Candidate,
    CandidateSkill,
    CandidateTag,
    Feedback,
    Interview,
    Job,
    JobApplication,
    Note,
    PipelineStage,
    SavedJob,
    StageDefaultInterviewer,
    User,
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

# Applications mirror the candidate's own funnel position, in the vocabulary
# the ATS Phase A migration introduced: an application is active until it
# reaches an outcome. Where it is inside the funnel lives in its stage rows.
STATUS_TO_APPLICATION = {
    "active": "active",
    "screening": "active",
    "interviewing": "active",
    "offered": "active",
    "hired": "hired",
    "rejected": "rejected",
    "on_hold": "active",
    "withdrawn": "withdrawn",
}

# How far along the pipeline a seeded application is, by candidate status.
# Index into pipeline_service.DEFAULT_STAGES of the round in progress; None
# for terminal applications.
STATUS_TO_STAGE_INDEX = {
    "active": 0,
    "screening": 1,
    "interviewing": 3,
    "offered": 7,
    "on_hold": 1,
    "hired": None,
    "rejected": None,
    "withdrawn": None,
}

# Synthetic tags and notes (ATS Phase C). Keyed on the candidate's email rather
# than their id: ids are random per database, emails are fixed, so every fresh
# database gets the same tags on the same people.
SEED_TAGS = [
    "referral",
    "relocation-ok",
    "remote-only",
    "visa-sponsorship",
    "returning-candidate",
    "strong-sql",
    "leadership",
    "contract-to-hire",
]

SEED_NOTES = [
    "Phone screen went well. Clear on why they want to move.",
    "Open to two office days a week. Prefers mornings for interviews.",
    "Strong portfolio. Ask about the data platform migration they led.",
    "Prefers a start date after the end of the quarter.",
    "Referred by a former colleague on the platform team.",
]


def seed_tags_for(email: str) -> list[str]:
    """Zero to two tags, decided by the email alone."""
    if stable_index(f"tags-{email}", 100) >= 60:
        return []
    picks = {
        SEED_TAGS[stable_index(f"tag-a-{email}", len(SEED_TAGS))],
        SEED_TAGS[stable_index(f"tag-b-{email}", len(SEED_TAGS))],
    }
    return sorted(picks)


def seed_note_for(email: str):
    """One note for about four in ten candidates, or None."""
    if stable_index(f"note-{email}", 100) >= 40:
        return None
    return SEED_NOTES[stable_index(f"note-body-{email}", len(SEED_NOTES))]

# ATS Phase B. Synthetic people, no passwords: nobody can sign in as them until
# someone runs scripts/create_admin.py --email ... --role ... with a password
# from the environment.
TEAM = [
    ("Priya Raman", "priya.raman@team.recruitiq.dev", "hiring_manager"),
    ("Daniel Okafor", "daniel.okafor@team.recruitiq.dev", "hiring_manager"),
    ("Lena Fischer", "lena.fischer@team.recruitiq.dev", "hiring_team"),
    ("Marcus Webb", "marcus.webb@team.recruitiq.dev", "interviewer"),
    ("Sofia Alvarez", "sofia.alvarez@team.recruitiq.dev", "interviewer"),
    ("Kenji Watanabe", "kenji.watanabe@team.recruitiq.dev", "interviewer"),
]

# Rounds the seed staffs: the job's hiring manager runs the review, the
# interviewers run the conversations.
INTERVIEW_ROUNDS = ("hm_review", "technical_interview", "problem_solving", "case_study")

FEEDBACK_NOTES = {
    "passed": [
        "Strong fundamentals and clear communication.",
        "Worked through the problem methodically and asked good questions.",
        "Good depth in their primary area. Would be glad to work with them.",
    ],
    "failed": [
        "Struggled to explain the reasoning behind past design decisions.",
        "Not enough depth in the core skills for this level.",
    ],
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
    # The six below existed only in the original dev database, which made a
    # fresh install seed 2 jobs instead of 8 (found deploying Phase 4). Ported
    # here verbatim, plus salary bands the legacy rows never had.
    {
        "title": "Senior Data Scientist",
        "department": "Data Science",
        "job_overview": (
            "Lead advanced analytics and machine learning projects. Mentor junior "
            "data scientists and drive business impact through data-driven insights."
        ),
        "required_qualifications": (
            "PhD or MS in Computer Science, Statistics, or related field\n"
            "5+ years experience in data science or machine learning\n"
            "Expertise in Python, SQL, and ML frameworks (TensorFlow, PyTorch)\n"
            "Strong communication and leadership skills"
        ),
        "location": "Austin, TX",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "senior",
        "min_salary": 155000,
        "max_salary": 195000,
        "skills": "Python,Machine Learning,Deep Learning,SQL,TensorFlow,PyTorch,Statistics,Data Visualization",
    },
    {
        "title": "Junior Data Scientist",
        "department": "Data Science",
        "job_overview": (
            "Support data analysis and model development. Work with senior team "
            "members to deliver actionable insights."
        ),
        "required_qualifications": (
            "BS or MS in Computer Science, Math, or related field\n"
            "0-2 years experience in data analysis or machine learning\n"
            "Proficiency in Python and data analysis libraries\n"
            "Eagerness to learn and grow in a fast-paced environment"
        ),
        "location": "Miami, FL",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "entry",
        "min_salary": 85000,
        "max_salary": 110000,
        "skills": "Python,Pandas,Scikit-learn,SQL,Data Cleaning,Data Visualization",
    },
    {
        "title": "Software Development Engineer",
        "department": "Engineering",
        "job_overview": (
            "Design, develop, and maintain scalable software solutions. Collaborate "
            "with cross-functional teams to deliver high-quality products."
        ),
        "required_qualifications": (
            "BS in Computer Science or related field\n"
            "2+ years experience in software development\n"
            "Experience with modern software engineering practices\n"
            "Strong problem-solving and teamwork skills"
        ),
        "location": "San Francisco, CA",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 140000,
        "max_salary": 180000,
        "skills": "Python,Java,C++,REST APIs,Docker,CI/CD,Agile,Git",
    },
    {
        "title": "Product Manager",
        "department": "Product",
        "job_overview": (
            "Own the product lifecycle from ideation to launch. Work closely with "
            "engineering, design, and business teams to deliver value to users."
        ),
        "required_qualifications": (
            "BS/BA in Business, Engineering, or related field\n"
            "3+ years experience in product management\n"
            "Strong communication and organizational skills\n"
            "Experience with Agile methodologies"
        ),
        "location": "San Francisco, CA",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 145000,
        "max_salary": 185000,
        "skills": "Product Management,Agile,User Research,Roadmapping,Stakeholder Management,Data Analysis",
    },
    {
        "title": "Gen AI Engineer",
        "department": "AI Research",
        "job_overview": (
            "Develop and deploy generative AI models for real-world applications. "
            "Collaborate with research and engineering teams to push the boundaries of AI."
        ),
        "required_qualifications": (
            "MS or PhD in Computer Science, AI, or related field\n"
            "3+ years experience with deep learning and NLP\n"
            "Hands-on experience with LLMs and generative models\n"
            "Strong publication record or open-source contributions a plus"
        ),
        "location": "Boston, MA",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "senior",
        "min_salary": 175000,
        "max_salary": 225000,
        "skills": "Python,Large Language Models,NLP,Deep Learning,Prompt Engineering,PyTorch,Transformers",
    },
    {
        "title": "Data Engineer",
        "department": "Data Engineering",
        "job_overview": (
            "Build and maintain robust data pipelines and infrastructure. Ensure "
            "data quality and availability for analytics and machine learning."
        ),
        "required_qualifications": (
            "BS in Computer Science, Engineering, or related field\n"
            "2+ years experience in data engineering\n"
            "Experience with cloud platforms and big data tools\n"
            "Strong SQL and programming skills"
        ),
        "location": "Seattle, WA",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 130000,
        "max_salary": 170000,
        "skills": "Python,SQL,ETL,Data Warehousing,Airflow,AWS,Spark,Docker",
    },
]

# All 40 candidates, entirely synthetic. The original script only carried 17
# and leaned on 23 legacy rows in the dev database - rows that included real
# parsed resumes, which the spec (§6) bars from the public demo, and which a
# fresh install does not have anyway. Positions deliberately span all eight
# jobs so the Matching screen has plausible pairings to rank.
#
# Headlines name the candidate's industry (insurance, healthcare, retail,
# travel, financial services...) because recruiters search by industry and the
# headline is embedded: an all-tech-company roster made "insurance experience"
# return nothing but weak similarity noise.
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
    ("Elena", "Vasquez", "Denver, CO", "Applied scientist, causal inference for a real estate marketplace",
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
    ("Rachel", "Kim", "Seattle, WA", "MLOps engineer serving clinical ML models in healthcare",
     "Machine Learning Engineer", "MLOps Engineer", "Tempus AI",
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
    ("Hannah", "Bright", "Portland, OR", "Data scientist, retail demand forecasting and pricing",
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
    ("Isabel", "Moreau", "Chicago, IL", "Data platform engineer, lakehouse migrations at a national insurance carrier",
     "Data Engineer", "Data Platform Engineer", "Allstate",
     ["Python", "Spark", "Delta Lake", "Airflow", "AWS", "Terraform"]),
    ("Aisha", "Karim", "Boston, MA", "LLM applications engineer, agents and tool use",
     "Gen AI Engineer", "Machine Learning Engineer", "HubSpot",
     ["Python", "Large Language Models", "Prompt Engineering", "LangChain", "Deep Learning", "Transformers"]),
    ("Viktor", "Novak", "Seattle, WA", "Streaming infrastructure, Kafka at petabyte scale",
     "Data Engineer", "Staff Data Engineer", "Netflix",
     ["Python", "Kafka", "Spark", "ETL", "AWS", "Data Warehousing"]),
    ("Fatima", "El-Sayed", "Austin, TX", "Applied ML for travel pricing and demand forecasting",
     "Senior Data Scientist", "Senior Data Scientist", "Expedia",
     ["Python", "Machine Learning", "Statistics", "SQL", "TensorFlow", "Data Visualization"]),
    ("Ben", "Castellano", "San Francisco, CA", "Backend generalist, Go and Postgres for insurance claims systems at an insurtech",
     "Software Development Engineer", "Software Engineer II", "Lemonade",
     ["Go", "Python", "REST APIs", "Docker", "CI/CD", "PostgreSQL"]),
    ("Ingrid", "Sorensen", "Remote, US", "PM for data products, ex-analyst",
     "Product Manager", "Product Manager", "Tableau",
     ["Product Management", "Data Analysis", "User Research", "Roadmapping", "SQL", "Agile"]),
    ("Kwame", "Boateng", "New York, NY", "Quant turned ML engineer, financial services risk models",
     "Machine Learning Engineer", "Quantitative Developer", "Two Sigma",
     ["Python", "PyTorch", "Feature Engineering", "AWS", "SQL", "Statistics"]),
    ("Lucia", "Ferrari", "Boston, MA", "PhD NLP, evaluation harnesses for LLMs",
     "Gen AI Engineer", "Research Scientist", "Allen Institute for AI",
     ["Python", "NLP", "Transformers", "Large Language Models", "Deep Learning", "Hugging Face"]),
    ("Derek", "Osei", "Chicago, IL", "Airline analytics engineer moving to platform work",
     "Data Engineer", "Analytics Engineer", "United Airlines",
     ["SQL", "dbt", "Airflow", "Python", "Snowflake", "Data Warehousing"]),
    ("Maya", "Lindholm", "Denver, CO", "Experimentation platform DS, ex-consultant",
     "Senior Data Scientist", "Data Science Manager", "Slack",
     ["Python", "Experimentation", "Statistics", "SQL", "Machine Learning", "Causal Inference"]),
    ("Ravi", "Chandran", "San Francisco, CA", "Distributed systems, service mesh migrations",
     "Engineering Manager, Platform", "Senior Staff Engineer", "LinkedIn",
     ["Distributed Systems", "Kubernetes", "Terraform", "Go", "Leadership", "Mentorship"]),
    ("Sofia", "Reyes", "Miami, FL", "Bootcamp grad from travel and hospitality, strong SQL portfolio",
     "Junior Data Scientist", "Business Analyst", "Royal Caribbean",
     ["Python", "SQL", "Pandas", "Data Visualization", "Data Cleaning"]),
    ("Ethan", "Caldwell", "Portland, OR", "Full stack engineer on telehealth products, healthcare",
     "Software Development Engineer", "Software Engineer", "Teladoc Health",
     ["TypeScript", "React", "Python", "REST APIs", "Docker", "Git"]),
    ("Zara", "Hussain", "Remote, US", "Platform PM, internal tooling and DX",
     "Product Manager", "Associate Product Manager", "GitLab",
     ["Product Management", "Developer Experience", "Agile", "User Stories", "Data Analysis"]),
    ("Anders", "Vik", "Seattle, WA", "Model serving at the edge, ONNX and Triton",
     "Machine Learning Engineer", "ML Infrastructure Engineer", "Adobe",
     ["Python", "Kubernetes", "MLflow", "AWS", "CI/CD", "Feature Engineering"]),
    ("Camille", "Dubois", "New York, NY", "Data scientist, health insurance marketing and attribution",
     "Senior Data Scientist", "Senior Analyst", "Oscar Health",
     ["Python", "R", "Statistics", "SQL", "Machine Learning", "Data Visualization"]),
    ("Jamal", "Winters", "Atlanta, GA", "Kafka pipelines for retail supply chain, CDC and lakehouse",
     "Data Engineer", "Data Engineer", "Home Depot",
     ["Python", "Kafka", "Spark", "Airflow", "AWS", "Docker"]),
    ("Rin", "Nakamura", "San Francisco, CA", "Agents and retrieval, shipped two LLM products",
     "Gen AI Engineer", "Senior Software Engineer", "Replit",
     ["Python", "Large Language Models", "RAG", "Prompt Engineering", "PostgreSQL", "Docker"]),
    ("Olive", "Bennett", "Boston, MA", "MS CS, undergrad TA, one fintech banking internship",
     "Junior Data Scientist", "Graduate Student", "Northeastern University",
     ["Python", "Scikit-learn", "Pandas", "SQL", "Statistics"]),
    ("Hugo", "Almeida", "Austin, TX", "SRE-flavored platform lead",
     "Engineering Manager, Platform", "Site Reliability Manager", "Cloudflare",
     ["Leadership", "Kubernetes", "Terraform", "Distributed Systems", "Hiring", "CI/CD"]),
    ("Talia", "Rosen", "Chicago, IL", "Growth PM with experimentation depth",
     "Product Manager", "Growth Product Manager", "Duolingo",
     ["Product Management", "A/B Testing", "User Research", "Roadmapping", "Stakeholder Management"]),
    ("George", "Antoniou", "Denver, CO", "C++ engineer, medical device firmware in healthcare",
     "Software Development Engineer", "Systems Engineer", "Medtronic",
     ["C++", "Python", "REST APIs", "Git", "Agile", "Docker"]),
    ("Leilani", "Kahale", "Remote, US", "Airline operations analyst pivoting into data science",
     "Junior Data Scientist", "Operations Analyst", "Hawaiian Airlines",
     ["SQL", "Python", "Data Visualization", "Pandas", "Data Cleaning"]),
    ("Stefan", "Weber", "Seattle, WA", "Recommender systems, embeddings and ranking",
     "Machine Learning Engineer", "Applied Scientist", "Amazon",
     ["Python", "PyTorch", "Feature Engineering", "MLflow", "AWS", "SQL"]),
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

    # Every candidate not yet on a pipeline gets a funnel position, including
    # the ones already in the database from earlier phases -- 7 of those carry
    # a NULL status, which the Dashboard would otherwise render as a blank column.
    candidates = db.query(Candidate).order_by(Candidate.created_at, Candidate.id).all()
    # A candidate on a pipeline gets their status from it (pipeline_service
    # keeps it in sync). Reassigning it here would contradict their board,
    # and the draw shifts for everyone whenever a candidate is added (Phase C
    # added Add candidate and upload intake), so only people with no stage
    # history yet are given a funnel position.
    on_a_pipeline = {
        candidate_id
        for (candidate_id,) in db.query(JobApplication.candidate_id)
        .join(ApplicationStage, ApplicationStage.application_id == JobApplication.id)
        .distinct()
    }
    funnel_rng = random.Random(SEED_FUNNEL)
    for candidate, status in zip(candidates, _weighted_statuses(funnel_rng, len(candidates))):
        if candidate.id in on_a_pipeline:
            continue
        if not candidate.status or candidate.status == "active":
            candidate.status = status
    db.commit()
    return candidates


def _seed_stage_history(db, application: JobApplication, candidate_status: str) -> None:
    """Position one application on its job's pipeline from the candidate's status.

    Deterministic: the same status always yields the same rows, and an
    application that already has rows is left alone so a re-run never
    rewinds a board someone has been clicking on.
    """
    from backend.services import pipeline_service as ps

    if application.stages:
        return
    stages = ps.ensure_job_stages(db, application.job_id)
    target = STATUS_TO_STAGE_INDEX.get(candidate_status, 0)
    final = STATUS_TO_APPLICATION.get(candidate_status, "active")
    when = application.applied_at

    for index, stage in enumerate(stages):
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status="pending")
        if final == "hired":
            row.status = "skipped" if stage.key == "offer_declined" else "passed"
        elif final in ("rejected", "withdrawn"):
            if index == 0:
                row.status = "passed"
            elif index == 1:
                row.status = "failed" if final == "rejected" else "skipped"
            else:
                row.status = "skipped"
        elif target is not None and index < target:
            row.status = "passed"
        elif index == target:
            row.status = "in_progress"
        if row.status != "pending":
            row.started_at = when
        if row.status in ("passed", "failed", "skipped"):
            row.completed_at = when
        db.add(row)
    application.status = final


def stage_timeline(seed_key: str, rows: list[tuple[str, str, str]], now: datetime):
    """Believable, deterministic timestamps for one seeded application.

    rows: (stage key, stage kind, status) in pipeline order. Returns
    (applied_at, [(started_at, completed_at), ...]) aligned with rows, or
    (None, ...) when nothing was ever reached.

    The application's latest moment is anchored to `now`: the stage it is
    waiting at started 1 to 5 days ago (about a quarter of the time, 8 to 13
    days ago, so "No movement in 7+ days" has honest entries), or, for a
    finished application, its outcome landed 2 to 76 days ago. Earlier rounds
    are laid out backwards from there, each lasting 1 to 6 days plus some
    hours, ending exactly when the next began. Every number comes from
    stable_index, so the same application gets the same shape every run.
    """
    spans: list[tuple] = [(None, None)] * len(rows)
    worked = [
        i
        for i, (_key, kind, status) in enumerate(rows)
        if kind == "round" and status in ("passed", "failed", "in_progress")
    ]
    if not worked:
        return None, spans
    current = next((i for i in worked if rows[i][2] == "in_progress"), None)
    hours = timedelta(hours=stable_index(f"hour-{seed_key}", 9))
    if current is not None:
        if stable_index(f"stuck-{seed_key}", 4) == 0:
            wait = timedelta(days=8 + stable_index(f"wait-{seed_key}", 6))
        else:
            wait = timedelta(days=1 + stable_index(f"wait-{seed_key}", 5))
        anchor = now - wait - hours
    else:
        anchor = now - timedelta(days=2 + stable_index(f"end-{seed_key}", 75)) - hours

    spans = list(spans)
    boundary = anchor
    for index in reversed(worked):
        if index == current:
            spans[index] = (anchor, None)
            continue
        key = rows[index][0]
        duration = timedelta(
            days=1 + stable_index(f"{seed_key}:{key}", 6),
            hours=stable_index(f"{seed_key}:{key}:h", 20),
        )
        spans[index] = (boundary - duration, boundary)
        boundary -= duration

    for index, (_key, kind, status) in enumerate(rows):
        if kind == "outcome" and status == "passed":
            spans[index] = (anchor, anchor)
        elif status == "skipped":
            later = [spans[i][0] for i in worked if i > index]
            spans[index] = (None, later[0] if later else anchor)

    applied_at = spans[worked[0]][0] - timedelta(hours=1 + stable_index(f"applied-{seed_key}", 5))
    return applied_at, spans


def _spread_stage_timeline(db, application: JobApplication, now: datetime) -> bool:
    """Give one seeded application realistic stage timestamps, once.

    Only touches an application whose rows still carry the flat timestamps
    _seed_stage_history and the Phase A migration wrote: every started or
    completed time equal to applied_at. Anything a person has moved has real
    timestamps and is left exactly as it is. A spread application starts its
    first stage an hour or more after applied_at, so it is no longer flat and
    a re-run is a no-op.

    Interviews and feedback seed_interviews wrote from those flat times move
    with their stage (assigned when it started, submitted when it ended), so
    no feedback reads as submitted before its round began. Interviews and
    feedback with any other timestamp were written by a person and are kept.
    """
    if application.applied_at is None:
        return False
    rows = (
        db.query(ApplicationStage, PipelineStage)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .filter(ApplicationStage.application_id == application.id)
        .order_by(PipelineStage.position)
        .all()
    )
    touched = [row for row, _stage in rows if row.status != "pending"]
    if not touched:
        return False
    flat_at = application.applied_at
    flat_values = (None, flat_at)
    if not all(row.started_at in flat_values and row.completed_at in flat_values for row in touched):
        return False
    applied_at, spans = stage_timeline(
        f"{application.candidate_id}:{application.job_id}",
        [(stage.key, stage.kind, row.status) for row, stage in rows],
        now,
    )
    if applied_at is None:
        return False
    for (row, _stage), (started, completed) in zip(rows, spans):
        row.started_at = started
        row.completed_at = completed
        for interview in row.interviews:
            if interview.created_at == flat_at and started is not None:
                interview.created_at = started
            feedback = interview.feedback
            if feedback is not None and feedback.submitted_at == flat_at:
                feedback.submitted_at = completed or started or feedback.submitted_at
    application.applied_at = applied_at
    return True


def seed_timelines(db, now: datetime, email_domain: str = EMAIL_DOMAIN) -> int:
    """Spread the stage timestamps of the seeded candidates' applications.

    The `--timelines-only` path, for a database seeded before ATS Phase D
    (prod). Touches only applications of seeded candidates (the demo email
    domain) whose history is still flat; everything else is left alone.
    Returns how many were laid out.
    """
    applications = (
        db.query(JobApplication)
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .filter(Candidate.email.like(f"%@{email_domain}"))
        .order_by(JobApplication.id)
        .all()
    )
    spread = sum(_spread_stage_timeline(db, application, now) for application in applications)
    db.commit()
    return spread


def seed_pipeline(db, candidates: list[Candidate], jobs: list[Job]) -> None:
    """Applications and saved jobs, consistent with each candidate's status."""
    now = datetime.utcnow()
    spread = 0
    by_title = {job.title: job for job in jobs}

    for candidate in candidates:
        # Prefer the job the candidate actually applied for; fall back to a
        # stable arbitrary one so every candidate appears somewhere.
        job = by_title.get(candidate.position_applied or "") or jobs[
            stable_index(candidate.id, len(jobs))
        ]
        app_status = STATUS_TO_APPLICATION.get(candidate.status or "active", "active")

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
        application.source = candidate.source or "direct"
        application.notes = f"Seeded demo application ({app_status})."
        db.flush()
        _seed_stage_history(db, application, candidate.status or "active")
        db.flush()
        spread += _spread_stage_timeline(db, application, now)

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
    print(f"  stage timelines laid out: {spread}")


def seed_notes_and_tags(db, candidates: list[Candidate]) -> None:
    """Tags and a candidate-level note, added only where missing (idempotent).

    Authored by the first hiring manager or hiring team user the Phase B seed
    created, so the thread shows a name; null (shown as "Earlier note") if
    there is none. Never edits or removes a note or tag someone added.
    """
    author = (
        db.query(User)
        .filter(User.role.in_(("hiring_manager", "hiring_team")))
        .order_by(User.email)
        .first()
    )
    for candidate in candidates:
        email = candidate.email or candidate.id
        for tag in seed_tags_for(email):
            exists = (
                db.query(CandidateTag)
                .filter(CandidateTag.candidate_id == candidate.id, CandidateTag.tag == tag)
                .first()
            )
            if exists is None:
                db.add(CandidateTag(candidate_id=candidate.id, tag=tag))
        body = seed_note_for(email)
        if body is not None:
            exists = (
                db.query(Note)
                .filter(Note.candidate_id == candidate.id, Note.body == body)
                .first()
            )
            if exists is None:
                db.add(
                    Note(candidate_id=candidate.id, author_id=author.id if author else None, body=body)
                )
    db.commit()


def seed_team(db) -> dict[str, list[User]]:
    """The synthetic team, keyed by role. Additive: an existing person keeps
    whatever role someone gave them on the Team page."""
    by_role: dict[str, list[User]] = {}
    for name, email, role in TEAM:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, name=name, role=role, hashed_password=None)
            db.add(user)
        elif not user.name:
            user.name = name
        by_role.setdefault(user.role, []).append(user)
    db.commit()
    return by_role


def _pick(people: list[User], key: str) -> User:
    return people[stable_index(key, len(people))]


def seed_interviews(db, team: dict[str, list[User]], jobs: list[Job]) -> None:
    """Hiring managers on jobs, a default interviewer per job, and interview
    history matching each application's stage rows.

    Deterministic and additive: a stage row that already has an interview is
    left alone, so a re-run never duplicates or rewrites anyone's feedback.
    Rounds that are done get feedback; the round in progress is left waiting,
    so the Interviews page has something outstanding to show.
    """
    from backend.services import pipeline_service as ps

    managers = team.get("hiring_manager", [])
    interviewers = team.get("interviewer", [])
    if not managers or not interviewers:
        return

    for job in jobs:
        if job.hiring_manager_id is None:
            job.hiring_manager_id = _pick(managers, f"manager-{job.title}").id
        stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
        technical = stages.get("technical_interview")
        if technical is not None and not technical.default_interviewers:
            technical.default_interviewers.append(
                StageDefaultInterviewer(user_id=_pick(interviewers, f"default-{job.title}").id)
            )
    db.flush()

    rows = (
        db.query(ApplicationStage)
        .join(PipelineStage, ApplicationStage.stage_id == PipelineStage.id)
        .filter(
            PipelineStage.key.in_(INTERVIEW_ROUNDS),
            ApplicationStage.status.in_(("in_progress", "passed", "failed")),
        )
        .order_by(ApplicationStage.id)
        .all()
    )
    for row in rows:
        if row.interviews:
            continue
        job = row.application.job
        if row.stage.key == "hm_review" and job.hiring_manager_id:
            person = db.get(User, job.hiring_manager_id)
        else:
            person = _pick(interviewers, f"{row.application_id}-{row.stage.key}")
        interview = Interview(
            interviewer_id=person.id,
            assignment_source="manual",
            created_at=row.started_at or datetime.utcnow(),
        )
        row.interviews.append(interview)
        if row.status in ("passed", "failed"):
            passed = row.status == "passed"
            notes = FEEDBACK_NOTES[row.status]
            interview.feedback = Feedback(
                rating=(4 + stable_index(f"rating-{row.id}", 2)) if passed else 2,
                recommendation=(
                    ("strong_hire" if stable_index(f"rec-{row.id}", 3) == 0 else "hire")
                    if passed
                    else "no_hire"
                ),
                notes=notes[stable_index(f"note-{row.id}", len(notes))],
                submitted_at=row.completed_at or row.started_at or datetime.utcnow(),
            )
    db.commit()


def embed(db, candidates: list[Candidate], jobs: list[Job], force: bool = False) -> None:
    from backend.services.ollama_embeddings import OllamaEmbeddingAdapter
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(
        embedding_model=OllamaEmbeddingAdapter(
            base_url=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai")
        )
    )
    missing_jobs = jobs if force else [j for j in jobs if j.embedding is None]
    missing_candidates = candidates if force else [c for c in candidates if c.embedding is None]

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
    parser.add_argument(
        "--re-embed",
        action="store_true",
        help=(
            "recompute every embedding, not just missing ones. Required after "
            "a change to the embedded text (profile fields or _candidate_text), "
            "otherwise existing rows keep stale vectors"
        ),
    )
    parser.add_argument(
        "--team-only",
        action="store_true",
        help=(
            "only add the synthetic team and interview history (ATS Phase B). Never "
            "changes a candidate, a candidate's status, or an application"
        ),
    )
    parser.add_argument(
        "--notes-tags-only",
        action="store_true",
        help=(
            "only add the synthetic notes and tags (ATS Phase C) to the seeded "
            "candidates. Additive: never changes a candidate or an existing note or tag"
        ),
    )
    parser.add_argument(
        "--timelines-only",
        action="store_true",
        help=(
            "only lay out realistic stage timestamps (ATS Phase D) on the seeded "
            "candidates' applications whose history is still flat. Never changes an "
            "application a person has moved, a candidate, or a status"
        ),
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        get_or_create_demo_user(db)

        if args.timelines_only:
            print(f"  stage timelines laid out: {seed_timelines(db, datetime.utcnow())}")
            return 0

        if args.notes_tags_only:
            seeded = (
                db.query(Candidate)
                .filter(Candidate.email.like(f"%@{EMAIL_DOMAIN}"))
                .order_by(Candidate.email)
                .all()
            )
            seed_notes_and_tags(db, seeded)
            print(f"  notes: {db.query(Note).count()}  tagged: "
                  f"{db.query(CandidateTag.candidate_id).distinct().count()}")
            return 0

        if args.team_only:
            jobs = db.query(Job).order_by(Job.id).all()
            seed_interviews(db, seed_team(db), jobs)
            print(f"  team: {db.query(User).filter(User.role != 'demo').count()}  "
                  f"interviews: {db.query(Interview).count()}  feedback: {db.query(Feedback).count()}")
            return 0

        jobs = seed_jobs(db)
        candidates = seed_candidates(db, random.Random(SEED_FIELDS))
        seed_pipeline(db, candidates, jobs)
        seed_interviews(db, seed_team(db), jobs)
        seed_notes_and_tags(db, candidates)

        if args.no_embeddings:
            print("  embeddings skipped (--no-embeddings)")
        else:
            embed(db, candidates, jobs, force=args.re_embed)

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
        print(f"  notes: {db.query(Note).count()}  tagged: "
              f"{db.query(CandidateTag.candidate_id).distinct().count()}")
        print(f"  team: {db.query(User).filter(User.role != 'demo').count()}  "
              f"interviews: {db.query(Interview).count()}  feedback: {db.query(Feedback).count()}")
        print(f"  funnel: {dict(sorted(funnel.items()))}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
