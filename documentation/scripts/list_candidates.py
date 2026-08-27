# scripts/list_candidates.py
from backend.models.models import Candidate
from backend.utils.database import SessionLocal

import logging

logging.basicConfig(level=logging.INFO)

def update_roger_position(session):
    roger = session.query(Candidate).filter(Candidate.first_name.ilike('%roger%'), Candidate.last_name.ilike('%waters%')).first()
    if roger:
        if not getattr(roger, 'current_position', None):
            logging.info(f"Updating Roger Waters' current_position to 'Full Stack Developer'.")
            roger.current_position = 'Full Stack Developer'
            session.commit()
        else:
            logging.info(f"Roger Waters already has current_position: {roger.current_position}")
    else:
        logging.warning("Roger Waters not found in the database.")

def list_candidates():
    session = SessionLocal()

    update_roger_position(session)
    print("Listing all candidates:")
    for candidate in session.query(Candidate).all():
        print(f"Name: {candidate.first_name} {candidate.last_name}")
        print(f"Email: {candidate.email}")
        if not getattr(candidate, 'current_position', None):
            logging.debug(f"Candidate {candidate.first_name} {candidate.last_name} is missing current_position.")
        print(f"Current Position: {getattr(candidate, 'current_position', None)}")
        print(f"Skills: {[s.name for s in getattr(candidate, 'skills', [])]}")
        print("---")

    session.close()

if __name__ == "__main__":
    list_candidates()