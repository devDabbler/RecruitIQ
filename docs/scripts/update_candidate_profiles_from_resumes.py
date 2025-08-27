"""
Script to extract and update candidate profiles from all resumes in the database.
For each candidate with a resume, parses the PDF, extracts position, skills, and experience, and updates the DB.
"""
import os
from PyPDF2 import PdfReader
from backend.utils.database import SessionLocal
from backend.models.models import Candidate, Resume
from sqlalchemy.orm import joinedload
import re

# Simple keyword list for full stack and related skills
FULL_STACK_KEYWORDS = [
    'python', 'ruby', 'rails', 'react', 'javascript', 'node', 'django', 'html', 'css', 'mysql', 'redis',
    'aws', 'docker', 'microservices', 'rest', 'api', 'linux', 'shell', 'typescript', 'vue', 'angular'
]

POSITION_PATTERNS = [
    r'(Full Stack Developer|Full Stack Engineer|Software Engineer|Backend Developer|Frontend Developer)'
]

EXPERIENCE_PATTERN = r'(\d+)[+]?\s+(years|yrs)'


def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.lower()
    except Exception as e:
        print(f"Warning: Could not parse PDF '{pdf_path}': {e}")
        return None


def extract_profile_fields(text):
    # 1. Try explicit position/role/title
    position = None
    explicit_patterns = [
        r'position\s*[:\-]?\s*([\w\s]+)',
        r'role\s*[:\-]?\s*([\w\s]+)',
        r'title\s*[:\-]?\s*([\w\s]+)',
    ] + POSITION_PATTERNS
    for pat in explicit_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            position = match.group(1).strip()
            break
    # 2. Infer from most recent experience section if not found
    if not position:
        # Look for experience section, then grab first job title
        exp_section = re.search(r'(experience|work history|employment)\s*[:\-]?\s*(.*?)(education|skills|$)', text, re.IGNORECASE | re.DOTALL)
        if exp_section:
            # Try to find a job title in this section (e.g., lines starting with a title)
            lines = exp_section.group(2).split('\n')
            for line in lines:
                # Heuristic: line with 2-6 words, likely a title
                if 2 <= len(line.split()) <= 6:
                    position = line.strip()
                    break
    # 3. Fallback to summary/headline
    if not position:
        summary_match = re.search(r'(summary|headline)\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
        if summary_match:
            position = summary_match.group(2).split('.')[0].strip()
    # Extract skills
    skills = [kw for kw in FULL_STACK_KEYWORDS if kw in text]
    # Extract experience (years)
    exp_match = re.search(EXPERIENCE_PATTERN, text)
    years_exp = int(exp_match.group(1)) if exp_match else None
    return position, skills, years_exp


def main():
    session = SessionLocal()
    candidates = session.query(Candidate).options(joinedload(Candidate.resumes)).all()
    updated = 0
    for candidate in candidates:
        # Find the most recent resume with a valid file_path
        resumes = getattr(candidate, 'resumes', [])
        if not resumes:
            continue
        # Sort resumes by updated_at if available, else just use the first with a file
        sorted_resumes = sorted(
            [r for r in resumes if getattr(r, 'file_path', None) and os.path.exists(r.file_path)],
            key=lambda r: getattr(r, 'updated_at', getattr(r, 'created_at', None)),
            reverse=True
        )
        if not sorted_resumes:
            continue
        resume = sorted_resumes[0]
        pdf_path = resume.file_path
        text = extract_text_from_pdf(pdf_path)
        if not text:
            continue
        position, skills, years_exp = extract_profile_fields(text)
        print(f"Candidate: {candidate.first_name} {candidate.last_name} | Extracted Role: {position}")
        updated_flag = False
        if position and (not candidate.current_position or position.lower() not in candidate.current_position.lower()):
            candidate.current_position = position
            updated_flag = True
        if skills:
            # Merge with any existing skills
            existing = set(candidate.skills or [])
            candidate.skills = list(existing.union(skills))
            updated_flag = True
        if years_exp and (not hasattr(candidate, 'years_experience') or not candidate.years_experience):
            candidate.years_experience = years_exp
            updated_flag = True
        if updated_flag:
            updated += 1
    session.commit()
    print(f"Updated {updated} candidate profiles from resumes.")
    session.close()

if __name__ == "__main__":
    main()
