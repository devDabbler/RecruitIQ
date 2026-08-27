import random
from datetime import datetime, timedelta
from backend.models.models import Candidate, Resume, Skill, Job
from backend.utils.database import SessionLocal
from sqlalchemy.exc import IntegrityError
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

# ---- SAMPLE JOBS ----
sample_jobs = [
    {
        "title": "Software Development Engineer",
        "department": "Engineering",
        "job_overview": "Work on scalable backend systems, APIs, and cloud infrastructure for our SaaS platform.",
        "required_qualifications": "BS/MS in Computer Science, 2+ years of backend experience, strong Python/Go skills, familiarity with AWS and Docker.",
        "location": "Seattle, WA",
        "location_type": "on_site",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 120000,
        "max_salary": 160000,
        "status": "open",
        "hiring_manager": "Jane Smith",
        "recruiter": "Sean Collins",
        "application_deadline": (datetime.now() + timedelta(days=30)),
        "start_date": (datetime.now() + timedelta(days=45)),
        "job_metadata": {},
        "skills": "Python,Go,AWS,Docker,Microservices,REST",
    },
    {
        "title": "Data Scientist",
        "department": "Data Science",
        "job_overview": "Develop machine learning models for product analytics and personalization.",
        "required_qualifications": "MS/PhD in Computer Science, Statistics, or related field. Experience with Python, TensorFlow, NLP, and large datasets.",
        "location": "Remote",
        "location_type": "remote",
        "job_type": "full_time",
        "experience_level": "mid",
        "min_salary": 130000,
        "max_salary": 170000,
        "status": "open",
        "hiring_manager": "Michael Lee",
        "recruiter": "Sean Collins",
        "application_deadline": (datetime.now() + timedelta(days=30)),
        "start_date": (datetime.now() + timedelta(days=60)),
        "job_metadata": {},
        "skills": "Python,TensorFlow,PyTorch,NLP,SQL,Statistics,Machine Learning",
    },
]

# ---- SAMPLE CANDIDATES ----
candidate_profiles = [
    # SDE Profiles
    {
        "first_name": "Alice",
        "last_name": "Nguyen",
        "email": "alice.nguyen@example.com",
        "phone": "+1-415-555-0101",
        "location": "San Francisco, CA",
        "headline": "Senior Software Engineer | Cloud & Distributed Systems",
        "skills": ["Python", "AWS", "Kubernetes", "Go", "Docker"],
        "experiences": [
            {"title": "Senior Software Engineer", "company": "Google", "location": "Mountain View, CA", "date_range": "2019-06 - Present", "description": "Lead backend development for Google Cloud Storage. Designed scalable microservices and mentored junior engineers."},
            {"title": "Software Engineer", "company": "Dropbox", "location": "San Francisco, CA", "date_range": "2016-05 - 2019-05", "description": "Built file synchronization features and improved system reliability by 30%."},
            {"title": "Backend Developer", "company": "Atlassian", "location": "Sydney, Australia", "date_range": "2014-01 - 2016-04", "description": "Developed REST APIs for Jira and Confluence integrations."},
        ],
        "education": [
            {"degree": "M.S. Computer Science", "institution": "Stanford University", "date_range": "2012 - 2014"},
            {"degree": "B.S. Computer Engineering", "institution": "University of Melbourne", "date_range": "2008 - 2012"},
        ],
        "publications": [
            {"title": "Efficient Cloud Storage Algorithms", "publisher": "IEEE Cloud Computing", "date": "2019", "description": "A study on distributed storage optimization techniques."}
        ],
        "summary": "Experienced backend/cloud engineer with a passion for scalable infrastructure and distributed systems.",
        "position_applied": "Software Development Engineer",
    },
    {
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@example.com",
        "phone": "+1-206-555-0202",
        "location": "Seattle, WA",
        "headline": "Backend Engineer | Distributed Systems | AWS",
        "skills": ["Python", "Go", "AWS", "Docker", "PostgreSQL"],
        "experiences": [
            {"title": "Backend Engineer", "company": "Amazon", "location": "Seattle, WA", "date_range": "2018-08 - Present", "description": "Architected and maintained distributed systems for Amazon Prime Video."},
            {"title": "Software Engineer", "company": "Expedia Group", "location": "Seattle, WA", "date_range": "2015-06 - 2018-07", "description": "Built scalable APIs and improved deployment automation."},
            {"title": "Junior Developer", "company": "Zillow", "location": "Seattle, WA", "date_range": "2013-06 - 2015-05", "description": "Worked on real estate data pipelines and analytics tools."},
        ],
        "education": [
            {"degree": "B.S. Computer Science", "institution": "University of Washington", "date_range": "2009 - 2013"},
        ],
        "publications": [],
        "summary": "Backend engineer with deep experience in distributed systems, AWS, and scalable APIs.",
        "position_applied": "Software Development Engineer",
    },
    # DS Profiles
    {
        "first_name": "Brian",
        "last_name": "Lee",
        "email": "brian.lee@example.com",
        "phone": "+1-646-555-0202",
        "location": "New York, NY",
        "headline": "Data Scientist | Machine Learning | NLP",
        "skills": ["Python", "TensorFlow", "PyTorch", "SQL", "NLP"],
        "experiences": [
            {"title": "Lead Data Scientist", "company": "Spotify", "location": "New York, NY", "date_range": "2020-01 - Present", "description": "Developed recommendation systems and led NLP research projects."},
            {"title": "Data Scientist", "company": "Bloomberg", "location": "New York, NY", "date_range": "2017-06 - 2019-12", "description": "Built financial time series models and anomaly detection pipelines."},
            {"title": "Research Intern", "company": "Facebook AI Research", "location": "Menlo Park, CA", "date_range": "2016-06 - 2016-08", "description": "Worked on entity recognition and text classification for Messenger."},
        ],
        "education": [
            {"degree": "Ph.D. Computer Science", "institution": "Columbia University", "date_range": "2014 - 2019"},
            {"degree": "B.S. Mathematics", "institution": "Cornell University", "date_range": "2010 - 2014"},
        ],
        "publications": [
            {"title": "Deep Learning for Music Recommendation", "publisher": "NeurIPS", "date": "2021", "description": "Advanced neural architectures for personalized music suggestions."}
        ],
        "summary": "Data scientist with deep expertise in ML, NLP, and large-scale data systems.",
        "position_applied": "Data Scientist",
    },
    {
        "first_name": "Priya",
        "last_name": "Singh",
        "email": "priya.singh@example.com",
        "phone": "+1-312-555-0303",
        "location": "Chicago, IL",
        "headline": "Data Scientist | Recommendation Systems",
        "skills": ["Python", "SQL", "TensorFlow", "Pandas", "Data Visualization"],
        "experiences": [
            {"title": "Data Scientist", "company": "Netflix", "location": "Los Gatos, CA", "date_range": "2019-07 - Present", "description": "Built and deployed recommendation models for streaming content."},
            {"title": "Data Analyst", "company": "Grubhub", "location": "Chicago, IL", "date_range": "2016-09 - 2019-06", "description": "Analyzed user data to optimize delivery logistics and promotions."},
            {"title": "Research Assistant", "company": "University of Chicago", "location": "Chicago, IL", "date_range": "2014-09 - 2016-08", "description": "Worked on social network analysis and data collection."},
        ],
        "education": [
            {"degree": "M.S. Data Science", "institution": "University of Chicago", "date_range": "2014 - 2016"},
            {"degree": "B.S. Statistics", "institution": "Delhi University", "date_range": "2010 - 2014"},
        ],
        "publications": [
            {"title": "Personalized Content Ranking at Scale", "publisher": "KDD", "date": "2022", "description": "Scalable ranking algorithms for streaming platforms."}
        ],
        "summary": "Data scientist specializing in recommendations, analytics, and large-scale data systems.",
        "position_applied": "Data Scientist",
    },
    # More SDE/DS profiles can be added here for a larger demo set
]


def populate_postgresql():
    session = SessionLocal()
    # Insert jobs first
    job_title_to_id = {}
    for job in sample_jobs:
        try:
            job_obj = Job(
                title=job["title"],
                department=job["department"],
                job_overview=job["job_overview"],
                required_qualifications=job["required_qualifications"],
                location=job["location"],
                location_type=job["location_type"],
                job_type=job["job_type"],
                experience_level=job["experience_level"],
                min_salary=job["min_salary"],
                max_salary=job["max_salary"],
                status=job["status"],
                hiring_manager=job["hiring_manager"],
                recruiter=job["recruiter"],
                application_deadline=job["application_deadline"],
                start_date=job["start_date"],
                job_metadata=job["job_metadata"],
                skills=job["skills"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(job_obj)
            session.flush()
            session.commit()
            job_title_to_id[job["title"]] = job_obj.id
            print(f"Inserted job: {job['title']}")
        except IntegrityError:
            session.rollback()
            print(f"Job {job['title']} already exists, skipping.")
        except Exception as e:
            session.rollback()
            print(f"Error inserting job {job['title']}: {e}")
    # Print all jobs for verification
    try:
        jobs = session.query(Job).all()
        print("Current jobs in database:")
        for j in jobs:
            print(f"  - {j.id}: {j.title} ({j.created_at})")
    except Exception as e:
        print(f"Error querying jobs for verification: {e}")
    # Insert candidates
    candidate_email_to_id = {}
    for profile in candidate_profiles:
        try:
            job_id = job_title_to_id.get(profile.get("position_applied"))
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
                job_id=job_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            skill_objs = []
            for skill_name in profile["skills"]:
                skill = session.query(Skill).filter_by(name=skill_name).first()
                if not skill:
                    skill = Skill(name=skill_name)
                    session.add(skill)
                    session.flush()
                skill_objs.append(skill)
            candidate.skills = skill_objs
            candidate.education = profile.get("education", [])
            candidate.work_experience = profile.get("experiences", [])
            candidate.interactions = []
            candidate.candidate_notes = []
            session.add(candidate)
            session.flush()
            candidate_email_to_id[profile["email"]] = candidate.id
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
    return candidate_email_to_id


def populate_neo4j(candidate_email_to_id):
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "test")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Insert jobs
        for job in sample_jobs:
            session.run(
                """
                MERGE (j:Job {title: $title})
                SET j.department = $department, j.job_overview = $job_overview, j.required_qualifications = $required_qualifications, j.location = $location, j.location_type = $location_type, j.job_type = $job_type, j.experience_level = $experience_level, j.min_salary = $min_salary, j.max_salary = $max_salary, j.status = $status, j.hiring_manager = $hiring_manager, j.recruiter = $recruiter, j.skills = $skills
                """,
                title=job["title"],
                department=job["department"],
                job_overview=job["job_overview"],
                required_qualifications=job["required_qualifications"],
                location=job["location"],
                location_type=job["location_type"],
                job_type=job["job_type"],
                experience_level=job["experience_level"],
                min_salary=job["min_salary"],
                max_salary=job["max_salary"],
                status=job["status"],
                hiring_manager=job["hiring_manager"],
                recruiter=job["recruiter"],
                skills=job["skills"],
            )
        # Insert candidates and relationships
        for profile in candidate_profiles:
            candidate_id = candidate_email_to_id.get(profile["email"])
            if not candidate_id:
                continue
            session.run(
                """
                MERGE (c:Candidate {id: $id})
                SET c.email = $email, c.first_name = $first_name, c.last_name = $last_name, c.phone = $phone, c.location = $location, c.headline = $headline, c.summary = $summary, c.skills = $skills
                """,
                id=candidate_id,
                email=profile["email"],
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                phone=profile["phone"],
                location=profile["location"],
                headline=profile["headline"],
                summary=profile["summary"],
                skills=", ".join(profile["skills"]),
            )
            # Experiences
            for exp in profile["experiences"]:
                session.run(
                    """
                    MERGE (e:Experience {title: $title, company: $company, date_range: $date_range})
                    MERGE (c:Candidate {id: $id})
                    MERGE (c)-[:HAS_EXPERIENCE]->(e)
                    SET e.location = $location, e.description = $description
                    """,
                    id=candidate_id,
                    title=exp["title"],
                    company=exp["company"],
                    date_range=exp["date_range"],
                    location=exp["location"],
                    description=exp["description"],
                )
            # Education
            for edu in profile["education"]:
                session.run(
                    """
                    MERGE (ed:Education {degree: $degree, institution: $institution, date_range: $date_range})
                    MERGE (c:Candidate {id: $id})
                    MERGE (c)-[:HAS_EDUCATION]->(ed)
                    """,
                    id=candidate_id,
                    degree=edu["degree"],
                    institution=edu["institution"],
                    date_range=edu["date_range"],
                )
            # Publications
            for pub in profile.get("publications", []):
                session.run(
                    """
                    MERGE (p:Publication {title: $title, publisher: $publisher, date: $date})
                    MERGE (c:Candidate {id: $id})
                    MERGE (c)-[:HAS_PUBLICATION]->(p)
                    SET p.description = $description
                    """,
                    id=candidate_id,
                    title=pub["title"],
                    publisher=pub.get("publisher"),
                    date=pub.get("date"),
                    description=pub.get("description"),
                )
            # Candidate-Job relationship
            if profile.get("position_applied"):
                session.run(
                    """
                    MATCH (c:Candidate {id: $id}), (j:Job {title: $job_title})
                    MERGE (c)-[:APPLIED_FOR]->(j)
                    """,
                    id=candidate_id,
                    job_title=profile["position_applied"]
                )
    driver.close()

if __name__ == "__main__":
    print("Populating PostgreSQL...")
    candidate_email_to_id = populate_postgresql()
    print("Populating Neo4j...")
    populate_neo4j(candidate_email_to_id)
    print("Done!")

def populate_neo4j():
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "test")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Insert jobs
        for job in sample_jobs:
            session.run(
                """
                MERGE (j:Job {title: $title})
                SET j.department = $department, j.job_overview = $job_overview, j.required_qualifications = $required_qualifications, j.location = $location, j.location_type = $location_type, j.job_type = $job_type, j.experience_level = $experience_level, j.min_salary = $min_salary, j.max_salary = $max_salary, j.status = $status, j.hiring_manager = $hiring_manager, j.recruiter = $recruiter, j.skills = $skills
                """,
                title=job["title"],
                department=job["department"],
                job_overview=job["job_overview"],
                required_qualifications=job["required_qualifications"],
                location=job["location"],
                location_type=job["location_type"],
                job_type=job["job_type"],
                experience_level=job["experience_level"],
                min_salary=job["min_salary"],
                max_salary=job["max_salary"],
                status=job["status"],
                hiring_manager=job["hiring_manager"],
                recruiter=job["recruiter"],
                skills=job["skills"],
            )
        # Insert candidates and relationships
        for profile in candidate_profiles:
            session.run(
                """
                MERGE (c:Candidate {email: $email})
                SET c.first_name = $first_name, c.last_name = $last_name, c.phone = $phone, c.location = $location, c.headline = $headline, c.summary = $summary, c.skills = $skills
                """,
                email=profile["email"],
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                phone=profile["phone"],
                location=profile["location"],
                headline=profile["headline"],
                summary=profile["summary"],
                skills=", ".join(profile["skills"]),
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
            # Candidate-Job relationship
            if profile.get("position_applied"):
                session.run(
                    """
                    MATCH (c:Candidate {email: $email}), (j:Job {title: $job_title})
                    MERGE (c)-[:APPLIED_FOR]->(j)
                    """,
                    email=profile["email"],
                    job_title=profile["position_applied"]
                )
    driver.close()

if __name__ == "__main__":
    print("Populating PostgreSQL...")
    populate_postgresql()
    print("Populating Neo4j...")
    populate_neo4j()
    print("Done!")
