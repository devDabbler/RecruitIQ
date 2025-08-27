from sqlalchemy.orm import Session

from backend.models import models
from backend.models import candidate as schemas # Use 'schemas' alias to avoid name clash

def get_candidate(db: Session, candidate_id: str):
    """Fetches a single candidate by their ID from the database."""
    # Assuming the Candidate model's primary key is 'id' and it's a string
    return db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()

# Add other CRUD functions for candidates here as needed (create, update, delete, list)
