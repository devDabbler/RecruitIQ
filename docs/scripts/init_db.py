import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the models
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.utils.database import engine, Base
from backend.models.models import Candidate, Resume

def init_db():
    """Initialize the database by creating all tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db() 