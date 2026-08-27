from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
db_url = os.getenv("POSTGRES_CONN")

# Create engine
engine = create_engine(db_url)

# Drop all existing tables with CASCADE
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS resume_experience CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS resume_education CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS resume_hashes CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS experiences CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS resume_skills CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS personal_info CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS work_experience CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS education CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS candidate_applications CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS recruiter_tasks CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS candidate_interactions CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS automated_reminders CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS candidate_skills CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS resumes CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS candidates CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS jobs CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    conn.commit()

print("Successfully dropped all tables")
