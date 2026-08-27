import random
from datetime import datetime, timedelta
from backend.models.models import Candidate, Resume, Skill
from backend.utils.database import SessionLocal
from sqlalchemy.exc import IntegrityError
from neo4j import GraphDatabase

# ---- SAMPLE DATA ----
candidate_profiles = [
    {
        "first_name": "Alice",
        "last_name": "Nguyen",
        "email": "alice.nguyen@example.com",
        "phone": "+1-415-555-0101",
        "location": "San Francisco, CA",
        "headline": "Senior Software Engineer | Cloud & Distributed Systems",
        "skills": ["Python", "AWS", "Kubernetes", "Go", "Docker"],
        "experiences": [
            {
                "title": "Senior Software Engineer",
                "company": "Google",
                "location": "Mountain View, CA",
                "date_range": "2019-06 - Present",
                "description": "Lead backend development for Google Cloud Storage. Designed scalable microservices and mentored junior engineers.",
            },
            {
                "title": "Software Engineer",
                "company": "Dropbox",
                "location": "San Francisco, CA",
                "date_range": "2016-05 - 2019-05",
                "description": "Built file synchronization features and improved system reliability by 30%.",
            },
            {
                "title": "Backend Developer",
                "company": "Atlassian",
                "location": "Sydney, Australia",
                "date_range": "2014-01 - 2016-04",
                "description": "Developed REST APIs for Jira and Confluence integrations.",
            },
        ],
        "education": [
            {
                "degree": "M.S. Computer Science",
                "institution": "Stanford University",
                "date_range": "2012 - 2014",
            },
            {
                "degree": "B.S. Computer Engineering",
                "institution": "University of Melbourne",
                "date_range": "2008 - 2012",
            },
        ],
        "publications": [
            {
                "title": "Efficient Cloud Storage Algorithms",
                "publisher": "IEEE Cloud Computing",
                "date": "2019",
                "description": "A study on distributed storage optimization techniques.",
            }
        ],
        "summary": "Experienced backend/cloud engineer with a passion for scalable infrastructure and distributed systems.",
    },
    {
        "first_name": "Brian",
        "last_name": "Lee",
        "email": "brian.lee@example.com",
        "phone": "+1-646-555-0202",
        "location": "New York, NY",
        "headline": "Data Scientist | Machine Learning | NLP",
        "skills": ["Python", "TensorFlow", "PyTorch", "SQL", "NLP"],
        "experiences": [
            {
                "title": "Lead Data Scientist",
                "company": "Spotify",
                "location": "New York, NY",
                "date_range": "2020-01 - Present",
                "description": "Developed recommendation systems and led NLP research projects.",
            },
            {
                "title": "Data Scientist",
                "company": "Bloomberg",
                "location": "New York, NY",
                "date_range": "2017-06 - 2019-12",
                "description": "Built financial time series models and anomaly detection pipelines.",
            },
            {
                "title": "Research Intern",
                "company": "Facebook AI Research",
                "location": "Menlo Park, CA",
                "date_range": "2016-06 - 2016-08",
                "description": "Worked on entity recognition and text classification for Messenger.",
            },
        ],
        "education": [
            {
                "degree": "Ph.D. Computer Science",
                "institution": "Columbia University",
                "date_range": "2014 - 2019",
            },
            {
                "degree": "B.S. Mathematics",
                "institution": "Cornell University",
                "date_range": "2010 - 2014",
            },
        ],
        "publications": [
            {
                "title": "Deep Learning for Music Recommendation",
                "publisher": "NeurIPS",
                "date": "2021",
                "description": "Advanced neural architectures for personalized music suggestions.",
            }
        ],
        "summary": "Data scientist with deep expertise in ML, NLP, and large-scale data systems.",
    },
    # ... 8 more candidate dictionaries (omitted for brevity, but will be included in the actual script) ...
]

# ---- POSTGRESQL POPULATION ----
def populate_postgresql():
    session = SessionLocal()
    for profile in candidate_profiles:
        try:
            # Prepare all top-level and parsed_data fields for UI alignment
            candidate = Candidate(
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                email=profile["email"],
                phone=profile.get("phone", "-"),
                location=profile.get("location", "-"),
                headline=profile.get("headline", "-"),
                status="active",
                current_position=profile["experiences"][0]["title"],
                current_company=profile["experiences"][0]["company"],
                notes=profile.get("notes", None),
                position_applied=profile.get("position_applied", None),
                job_id=profile.get("job_id", None),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            # Add or get skills
            skill_objs = []
            for skill_name in profile["skills"]:
                skill = session.query(Skill).filter_by(name=skill_name).first()
                if not skill:
                    skill = Skill(name=skill_name)
                    session.add(skill)
                    session.flush()
                skill_objs.append(skill)
            candidate.skills = skill_objs
            # Add top-level education and work_experience for UI
            candidate.education = profile.get("education", [])
            candidate.work_experience = profile.get("experiences", [])
            # Add empty interactions and candidate_notes
            candidate.interactions = []
            candidate.candidate_notes = []
            session.add(candidate)
            session.flush()
            # Compose parsed_data for resume and API
            parsed_data = {
                "first_name": profile["first_name"],
                "last_name": profile["last_name"],
                "email": profile["email"],
                "phone": profile.get("phone", "-"),
                "location": profile.get("location", "-"),
                "headline": profile.get("headline", "-"),
                "skills": profile["skills"],
                "education": profile.get("education", []),
                "experience": profile.get("experiences", []),
                "publications": profile.get("publications", []),
                "summary": profile.get("summary", "-"),
                "interactions": [],
                "candidate_notes": [],
            }
            resume = Resume(
                candidate_id=candidate.id,
                file_id=f"sample-{candidate.id}",
                file_path="/dev/null",
                file_name=f"{candidate.first_name}_{candidate.last_name}_Sample.pdf",
                file_type="pdf",
                parsed_content=profile["summary"],
                parsed_data=parsed_data,
                vector_embedding={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(resume)
            session.commit()
            print(f"Inserted candidate {candidate.first_name} {candidate.last_name} (UI-aligned)")
        except IntegrityError:
            session.rollback()
            print(f"Candidate {profile['email']} already exists, skipping.")
        except Exception as e:
            session.rollback()
            print(f"Error inserting candidate {profile['email']}: {e}")
    session.close()

# ---- NEO4J POPULATION ----
from dotenv import load_dotenv
import os

def populate_neo4j():
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "test")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        for profile in candidate_profiles:
            # Create Candidate node
            session.run(
                """
                MERGE (c:Candidate {email: $email})
                SET c.first_name = $first_name, c.last_name = $last_name, c.phone = $phone, c.location = $location, c.headline = $headline, c.summary = $summary
                """,
                email=profile["email"],
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                phone=profile["phone"],
                location=profile["location"],
                headline=profile["headline"],
                summary=profile["summary"]
            )
            # Experiences
            for exp in profile["experiences"]:
                session.run(
                    """
                    MERGE (e:Experience {title: $title, company: $company, date_range: $date_range})
                    MERGE (c:Candidate {email: $email})
                    MERGE (c)-[:HAS_EXPERIENCE]->(e)
                    SET e.location = $location, e.description = $description
                    """,
                    title=exp["title"],
                    company=exp["company"],
                    date_range=exp["date_range"],
                    location=exp["location"],
                    description=exp["description"],
                    email=profile["email"]
                )
            # Education
            for edu in profile["education"]:
                session.run(
                    """
                    MERGE (ed:Education {degree: $degree, institution: $institution, date_range: $date_range})
                    MERGE (c:Candidate {email: $email})
                    MERGE (c)-[:HAS_EDUCATION]->(ed)
                    """,
                    degree=edu["degree"],
                    institution=edu["institution"],
                    date_range=edu["date_range"],
                    email=profile["email"]
                )
            # Publications
            for pub in profile.get("publications", []):
                session.run(
                    """
                    MERGE (p:Publication {title: $title, publisher: $publisher, date: $date})
                    MERGE (c:Candidate {email: $email})
                    MERGE (c)-[:HAS_PUBLICATION]->(p)
                    SET p.description = $description
                    """,
                    title=pub["title"],
                    publisher=pub.get("publisher"),
                    date=pub.get("date"),
                    description=pub.get("description"),
                    email=profile["email"]
                )
    driver.close()

if __name__ == "__main__":
    print("Populating PostgreSQL...")
    populate_postgresql()
    print("Populating Neo4j...")
    populate_neo4j()
    print("Done!")
