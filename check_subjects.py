"""Quick test of what's in database."""
from curriculum_db import get_curriculum

entries = get_curriculum()
subjects = set(e['subject'] for e in entries)
print("Subjects in database:")
for s in sorted(subjects):
    grades = [e['grade'] for e in entries if e['subject'] == s]
    print(f"  {s}: {' '.join(sorted(set(grades)))}")
