"""Generate the eval fixture set: 30 synthetic resumes with ground-truth labels.

10 personas x 3 layout variants. Text and labels come from the same data
structures, so labels are correct by construction (no hand-verification
drift). All people, companies, and contact details are synthetic
(example.com emails, 555 phones) per the no-real-resumes policy.

Usage: poetry run python evals/generate_fixtures.py
Writes: evals/resumes/{id}.txt and evals/labels/{id}.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent

PERSONAS = [
    {
        "id": "p01",
        "name": "Maya Chen",
        "email": "maya.chen@example.com",
        "phone": "555-201-3345",
        "location": "Seattle, WA",
        "summary": "Data engineer with six years building batch and streaming pipelines.",
        "experience": [
            {
                "title": "Senior Data Engineer",
                "company": "Cascadia Analytics",
                "start": "2022",
                "end": "Present",
                "bullets": [
                    "Designed Airflow DAGs orchestrating 40+ daily ETL jobs into Snowflake",
                    "Cut pipeline failure rate 60% by adding data quality checks with Great Expectations",
                ],
            },
            {
                "title": "Data Engineer",
                "company": "Pugetworks",
                "start": "2019",
                "end": "2022",
                "bullets": [
                    "Built Kafka streaming ingestion for clickstream events at 50k msg/s",
                    "Migrated legacy SQL Server warehouse to BigQuery",
                ],
            },
        ],
        "education": [
            {"institution": "University of Washington", "degree": "BS", "field": "Informatics", "year": "2019"},
        ],
        "skills": ["Python", "SQL", "Airflow", "Snowflake", "Kafka", "dbt"],
    },
    {
        "id": "p02",
        "name": "Marcus Boone",
        "email": "marcus.boone@example.com",
        "phone": "555-882-4410",
        "location": "Fayetteville, NC",
        "summary": "Army logistics NCO transitioning to supply chain operations.",
        "experience": [
            {
                "title": "Operations Supervisor",
                "company": "Coastal Freight Systems",
                "start": "2023",
                "end": "Present",
                "bullets": [
                    "Supervise 12 dock workers across two shifts",
                    "Reduced load-out errors 25% with barcode scanning rollout",
                ],
            },
            {
                "title": "Logistics NCO (92A)",
                "company": "US Army",
                "start": "2015",
                "end": "2023",
                "bullets": [
                    "Managed $4.2M equipment inventory for a 140-soldier company",
                    "Led platoon supply operations during two overseas deployments",
                ],
            },
        ],
        "education": [
            {"institution": "Fayetteville Technical Community College", "degree": "AAS", "field": "Supply Chain Management", "year": "2022"},
        ],
        "skills": ["Inventory Management", "GCSS-Army", "Forklift Operation", "Microsoft Excel", "Team Leadership"],
    },
    {
        "id": "p03",
        "name": "Priya Raghavan-Wells",
        "email": "priya.rw@example.com",
        "phone": "+1 (555) 640-2211",
        "location": "Austin, TX",
        "summary": "Full-stack engineer focused on React and Node services.",
        "experience": [
            {
                "title": "Software Engineer II",
                "company": "Hillstone Software",
                "start": "2021",
                "end": "Present",
                "bullets": [
                    "Ship features across a React/TypeScript frontend and Node microservices",
                    "Reduced p95 API latency from 900ms to 220ms via query batching",
                ],
            },
            {
                "title": "Junior Web Developer",
                "company": "Bluebonnet Digital",
                "start": "2019",
                "end": "2021",
                "bullets": [
                    "Built marketing sites and internal dashboards for 20+ clients",
                ],
            },
        ],
        "education": [
            {"institution": "University of Texas at Austin", "degree": "BA", "field": "Mathematics", "year": "2019"},
        ],
        "skills": ["JavaScript", "TypeScript", "React", "Node.js", "PostgreSQL", "Docker"],
    },
    {
        "id": "p04",
        "name": "Tom Okafor",
        "email": "t.okafor@example.com",
        "phone": "555-113-9902",
        "location": "Columbus, OH",
        "summary": "Registered nurse with medical-surgical and ICU experience.",
        "experience": [
            {
                "title": "ICU Registered Nurse",
                "company": "Scioto Valley Medical Center",
                "start": "2020",
                "end": "Present",
                "bullets": [
                    "Provide critical care for 2-3 ICU patients per shift",
                    "Precept new graduate nurses during unit onboarding",
                ],
            },
            {
                "title": "Med-Surg Nurse",
                "company": "Franklin General Hospital",
                "start": "2017",
                "end": "2020",
                "bullets": [
                    "Managed 5-6 patient assignments on a 32-bed unit",
                ],
            },
        ],
        "education": [
            {"institution": "Ohio State University", "degree": "BSN", "field": "Nursing", "year": "2017"},
        ],
        "skills": ["Critical Care", "Epic EHR", "IV Therapy", "Patient Education", "BLS", "ACLS"],
    },
    {
        "id": "p05",
        "name": "Sofia Delgado",
        "email": "sofia.delgado@example.com",
        "phone": "555-778-0143",
        "location": "Denver, CO",
        "summary": "Technical recruiter turned talent operations lead.",
        "experience": [
            {
                "title": "Talent Operations Lead",
                "company": "Summitline",
                "start": "2022",
                "end": "Present",
                "bullets": [
                    "Own ATS administration and hiring analytics for a 400-person company",
                    "Cut time-to-offer from 34 to 21 days by rebuilding interview loops",
                ],
            },
            {
                "title": "Senior Technical Recruiter",
                "company": "Peakview Staffing",
                "start": "2018",
                "end": "2022",
                "bullets": [
                    "Closed 60+ software engineering hires per year across client accounts",
                ],
            },
        ],
        "education": [
            {"institution": "Colorado State University", "degree": "BA", "field": "Communication", "year": "2016"},
        ],
        "skills": ["Greenhouse", "Sourcing", "Hiring Analytics", "Stakeholder Management", "Boolean Search"],
    },
    {
        "id": "p06",
        "name": "Dmitri Volkov",
        "email": "d.volkov@example.com",
        "phone": "555-455-8821",
        "location": "Boston, MA",
        "summary": "Machine learning engineer specializing in NLP systems.",
        "experience": [
            {
                "title": "Machine Learning Engineer",
                "company": "Beacon Language AI",
                "start": "2021",
                "end": "Present",
                "bullets": [
                    "Fine-tune and deploy transformer models for document classification",
                    "Built evaluation harness cutting model regression escapes to zero",
                ],
            },
            {
                "title": "Data Scientist",
                "company": "Harborlight Insurance",
                "start": "2018",
                "end": "2021",
                "bullets": [
                    "Developed claims-fraud detection models saving $2M annually",
                ],
            },
        ],
        "education": [
            {"institution": "Northeastern University", "degree": "MS", "field": "Computer Science", "year": "2018"},
            {"institution": "Boston University", "degree": "BS", "field": "Statistics", "year": "2016"},
        ],
        "skills": ["Python", "PyTorch", "Transformers", "spaCy", "MLflow", "AWS SageMaker"],
    },
    {
        "id": "p07",
        "name": "Aisha Al-Rashid",
        "email": "aisha.alrashid@example.com",
        "phone": "555-330-6754",
        "location": "Minneapolis, MN",
        "summary": "Product manager for B2B SaaS platforms.",
        "experience": [
            {
                "title": "Senior Product Manager",
                "company": "Northfield Systems",
                "start": "2023",
                "end": "Present",
                "bullets": [
                    "Own roadmap for a $12M ARR workforce management product",
                    "Shipped self-serve onboarding lifting activation 18%",
                ],
            },
            {
                "title": "Product Manager",
                "company": "Lakeshore Software",
                "start": "2020",
                "end": "2023",
                "bullets": [
                    "Led three squads through discovery-to-launch on scheduling features",
                ],
            },
            {
                "title": "Business Analyst",
                "company": "Twin Cities Consulting",
                "start": "2017",
                "end": "2020",
                "bullets": [
                    "Documented requirements and process maps for ERP rollouts",
                ],
            },
        ],
        "education": [
            {"institution": "University of Minnesota", "degree": "BSB", "field": "Management Information Systems", "year": "2017"},
        ],
        "skills": ["Product Strategy", "Jira", "SQL", "A/B Testing", "Customer Discovery", "Roadmapping"],
    },
    {
        "id": "p08",
        "name": "Jake Sherwood",
        "email": "jake.sherwood@example.com",
        "phone": "555-909-1276",
        "location": "Remote",
        "summary": "DevOps engineer, career-changed from audio engineering.",
        "experience": [
            {
                "title": "DevOps Engineer",
                "company": "Driftwood Cloud",
                "start": "2022",
                "end": "Present",
                "bullets": [
                    "Maintain Terraform-managed AWS infrastructure across 3 environments",
                    "Moved CI from Jenkins to GitHub Actions cutting build times 40%",
                ],
            },
            {
                "title": "Audio Engineer",
                "company": "Redline Studios",
                "start": "2014",
                "end": "2021",
                "bullets": [
                    "Engineered live and studio sessions; managed studio signal infrastructure",
                ],
            },
        ],
        "education": [
            {"institution": "Full Sail University", "degree": "BS", "field": "Audio Engineering", "year": "2014"},
        ],
        "skills": ["AWS", "Terraform", "Kubernetes", "GitHub Actions", "Linux", "Bash"],
    },
    {
        "id": "p09",
        "name": "Linda Park",
        "email": "linda.park@example.com",
        "phone": "555-644-3387",
        "location": "San Jose, CA",
        "summary": "QA lead with strong test automation background.",
        "experience": [
            {
                "title": "QA Lead",
                "company": "Almaden Robotics",
                "start": "2020",
                "end": "Present",
                "bullets": [
                    "Lead a 5-person QA team covering firmware and cloud services",
                    "Grew automated regression coverage from 20% to 85% with Playwright",
                ],
            },
            {
                "title": "QA Engineer",
                "company": "Sunnyvale Apps",
                "start": "2016",
                "end": "2020",
                "bullets": [
                    "Wrote Selenium suites for consumer mobile/web products",
                ],
            },
        ],
        "education": [
            {"institution": "San Jose State University", "degree": "BS", "field": "Software Engineering", "year": "2016"},
        ],
        "skills": ["Playwright", "Selenium", "Python", "Test Planning", "CI/CD", "JIRA"],
    },
    {
        "id": "p10",
        "name": "Omar Haddad",
        "email": "omar.haddad@example.com",
        "phone": "555-517-2098",
        "location": "Chicago, IL",
        "summary": "Financial analyst moving into analytics engineering.",
        "experience": [
            {
                "title": "Analytics Engineer",
                "company": "Wacker Street Capital",
                "start": "2024",
                "end": "Present",
                "bullets": [
                    "Model financial datasets in dbt feeding Looker dashboards",
                ],
            },
            {
                "title": "Senior Financial Analyst",
                "company": "Lakeview Holdings",
                "start": "2019",
                "end": "2024",
                "bullets": [
                    "Built FP&A models and automated monthly reporting in Python",
                ],
            },
        ],
        "education": [
            {"institution": "University of Illinois Urbana-Champaign", "degree": "BS", "field": "Finance", "year": "2019"},
        ],
        "skills": ["SQL", "dbt", "Looker", "Python", "Financial Modeling", "Excel"],
    },
]


def layout_standard(p) -> str:
    lines = [p["name"], f"{p['email']} | {p['phone']} | {p['location']}", "", "SUMMARY", p["summary"], "", "EXPERIENCE"]
    for e in p["experience"]:
        lines.append(f"{e['title']}, {e['company']} | {e['start']} - {e['end']}")
        lines.extend(f"- {b}" for b in e["bullets"])
        lines.append("")
    lines.append("EDUCATION")
    for ed in p["education"]:
        lines.append(f"{ed['institution']} - {ed['degree']} in {ed['field']} ({ed['year']})")
    lines += ["", "SKILLS", ", ".join(p["skills"])]
    return "\n".join(lines)


def layout_compact(p) -> str:
    lines = [
        f"{p['name']} | {p['location']} | {p['email']} | {p['phone']}",
        "",
        p["summary"],
        "",
        "PROFESSIONAL EXPERIENCE",
    ]
    for e in p["experience"]:
        lines.append(f"{e['company']} | {e['title']} | {e['start']}-{e['end']}")
        lines.append(" * " + "; ".join(e["bullets"]))
    lines.append("")
    lines.append("EDUCATION: " + " / ".join(f"{ed['degree']}, {ed['field']}, {ed['institution']} {ed['year']}" for ed in p["education"]))
    lines.append("CORE SKILLS: " + " - ".join(p["skills"]))
    return "\n".join(lines)


def layout_dates_first(p) -> str:
    lines = [p["name"].upper(), p["location"], f"Email: {p['email']}", f"Phone: {p['phone']}", "", "WORK HISTORY"]
    for e in p["experience"]:
        lines.append(f"{e['start']} to {e['end']}")
        lines.append(f"{e['title']}")
        lines.append(f"{e['company']}")
        lines.extend(f"* {b}" for b in e["bullets"])
        lines.append("")
    lines.append("EDUCATION")
    for ed in p["education"]:
        lines.append(f"{ed['year']}  {ed['degree']} {ed['field']}, {ed['institution']}")
    lines += ["", "TECHNICAL SKILLS"]
    lines.extend(f"* {s}" for s in p["skills"])
    return "\n".join(lines)


LAYOUTS = {"a": layout_standard, "b": layout_compact, "c": layout_dates_first}


def labels_for(p) -> dict:
    return {
        "name": p["name"],
        "email": p["email"],
        "phone": p["phone"],
        "location": p["location"],
        "experience_titles": [e["title"] for e in p["experience"]],
        "experience_companies": [e["company"] for e in p["experience"]],
        "skills": p["skills"],
        "education_institutions": [ed["institution"] for ed in p["education"]],
    }


def main():
    resumes_dir = ROOT / "resumes"
    labels_dir = ROOT / "labels"
    resumes_dir.mkdir(exist_ok=True)
    labels_dir.mkdir(exist_ok=True)
    count = 0
    for p in PERSONAS:
        for suffix, layout in LAYOUTS.items():
            fixture_id = f"{p['id']}{suffix}"
            (resumes_dir / f"{fixture_id}.txt").write_text(layout(p), encoding="utf-8")
            (labels_dir / f"{fixture_id}.json").write_text(
                json.dumps(labels_for(p), indent=2), encoding="utf-8"
            )
            count += 1
    print(f"Wrote {count} fixtures to {resumes_dir}")


if __name__ == "__main__":
    main()
