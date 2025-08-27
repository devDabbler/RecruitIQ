"""
Confirmation script: Print all candidates' names, emails, and extracted roles/positions for manual review.
"""
from backend.utils.database import SessionLocal
from backend.models.models import Candidate

def main():
    session = SessionLocal()
    candidates = session.query(Candidate).all()
    print(f"{'Name':<30} {'Email':<35} {'Role/Position':<30}")
    print('-'*95)
    for c in candidates:
        name = f"{c.first_name} {c.last_name}"
        email = c.email
        role = getattr(c, 'current_position', None) or ''
        print(f"{name:<30} {email:<35} {role:<30}")
    session.close()

if __name__ == "__main__":
    main()
