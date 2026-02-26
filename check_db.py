"""Quick script to check database status."""
import sqlite3
from pathlib import Path

db_path = Path("curriculum.db")
if not db_path.exists():
    print("Database not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM curriculum")
count = cursor.fetchone()[0]
print(f"\nTotal records: {count}")

cursor.execute("SELECT subject, grade, completeness_score FROM curriculum ORDER BY completeness_score DESC")
rows = cursor.fetchall()

print(f"\nSubjects by completeness:")
for row in rows:
    score = row[2]
    subject = row[0]
    grade = row[1]
    indicator = "[OK]" if score >= 60 else "[WARN]" if score >= 30 else "[LOW]"
    print(f"  {indicator} {score:5.1f}% - {subject:30s} {grade}")

conn.close()
