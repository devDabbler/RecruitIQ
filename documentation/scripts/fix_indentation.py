import re

# Read the file
with open('backend/utils/unified_resume_parser.py', 'r') as file:
    content = file.read()

# Fix the indentation issue
fixed_content = re.sub(
    r'(                entry\["start_date"\] = start_date)(.+?)(entry\["end_date"\] = end_date)(.+?)(return experience_entries)(.+?)(def _extract_skills)',
    r'\1\n                \3\n\n        \5\n\n    \7',
    content,
    flags=re.DOTALL
)

# Write the fixed content back to the file
with open('backend/utils/unified_resume_parser.py', 'w') as file:
    file.write(fixed_content)

print("Fixed indentation in unified_resume_parser.py") 