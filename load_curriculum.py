#!/usr/bin/env python3
"""Load curriculum data from JSON into SQLite database."""

import json
import sqlite3
import os
from pathlib import Path

DATA_DIR = os.getenv("DATA_DIR", ".")
CURRICULUM_DB = os.path.join(DATA_DIR, "curriculum.db")
CURRICULUM_JSON = os.path.join(DATA_DIR, "curriculum_parsed.json")

def load_curriculum_from_json():
    """Load curriculum data from JSON file into SQLite database."""
    
    if not Path(CURRICULUM_JSON).exists():
        print(f"❌ Curriculum JSON not found: {CURRICULUM_JSON}")
        return False
    
    # Load JSON with UTF-8 encoding
    with open(CURRICULUM_JSON, 'r', encoding='utf-8') as f:
        curriculum_data = json.load(f)
    
    print(f"📚 Loaded {len(curriculum_data)} curriculum entries from JSON")
    
    # Create/connect to database
    conn = sqlite3.connect(CURRICULUM_DB)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curriculum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            grade TEXT NOT NULL,
            strand TEXT,
            strand_number TEXT,
            substrand TEXT,
            substrand_number TEXT,
            num_lessons TEXT,
            learning_outcomes TEXT,
            key_inquiry_questions TEXT,
            suggested_learning_experiences TEXT,
            core_competencies TEXT,
            values_list TEXT,
            pcis TEXT,
            assessment TEXT,
            UNIQUE(subject, grade, substrand)
        )
    """)
    
    # Insert data
    inserted = 0
    skipped = 0
    for entry in curriculum_data:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO curriculum (
                    subject, grade, strand, strand_number, substrand, 
                    substrand_number, num_lessons, learning_outcomes,
                    key_inquiry_questions, suggested_learning_experiences,
                    core_competencies, values_list, pcis, assessment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("subject", ""),
                entry.get("grade", ""),
                entry.get("strand", ""),
                entry.get("strand_number", ""),
                entry.get("substrand", ""),
                entry.get("substrand_number", ""),
                entry.get("num_lessons", ""),
                json.dumps(entry.get("learning_outcomes", [])),
                json.dumps(entry.get("key_inquiry", [])),
                json.dumps(entry.get("activities", [])),
                json.dumps(entry.get("competencies", [])),
                json.dumps(entry.get("values_", [])),
                json.dumps(entry.get("pcis", [])),
                json.dumps(entry.get("assessment", []))
            ))
            inserted += 1
        except Exception as e:
            print(f"⚠️  Error inserting {entry.get('subject')} {entry.get('grade')}: {e}")
            skipped += 1
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM curriculum")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT DISTINCT subject, grade FROM curriculum ORDER BY subject, grade")
    subjects = cursor.fetchall()
    
    print(f"✅ Inserted: {inserted} entries")
    print(f"⏭️  Skipped: {skipped} entries")
    print(f"📊 Total in database: {total}")
    print(f"\n📖 Available subjects/grades:")
    for subject, grade in subjects:
        cursor.execute("SELECT COUNT(*) FROM curriculum WHERE subject = ? AND grade = ?", (subject, grade))
        count = cursor.fetchone()[0]
        print(f"   - {subject} ({grade}): {count} strands")
    
    conn.close()
    return True

if __name__ == "__main__":
    success = load_curriculum_from_json()
    if success:
        print("\n✅ Curriculum data loaded successfully!")
    else:
        print("\n❌ Failed to load curriculum data")
