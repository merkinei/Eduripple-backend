"""Curriculum database schema and utilities."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

# DATA_DIR env var points to a persistent volume on Railway.
# Defaults to current directory for local development.
DATA_DIR = os.getenv("DATA_DIR", ".")
CURRICULUM_DB = os.path.join(DATA_DIR, "curriculum.db")

def init_curriculum_db():
    """Initialize curriculum database with schema."""
    db_path = Path(CURRICULUM_DB)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create curriculum table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curriculum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            grade TEXT NOT NULL,
            strand TEXT,
            substrand TEXT,
            learning_outcomes TEXT,
            key_inquiry_questions TEXT,
            suggested_learning_experiences TEXT,
            core_competencies TEXT,
            curriculum_values TEXT,
            status TEXT DEFAULT 'auto_extracted',
            completeness_score REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            UNIQUE(subject, grade)
        )
    """)
    
    # Create audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curriculum_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curriculum_id INTEGER,
            change_type TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT DEFAULT 'system',
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(curriculum_id) REFERENCES curriculum(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"[OK] Curriculum database initialized: {db_path}")


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(CURRICULUM_DB)
    conn.row_factory = sqlite3.Row
    return conn


def insert_curriculum(subject, grade, data, status="auto_extracted"):
    """Insert or update curriculum entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate completeness score
    score = calculate_completeness(data)
    
    # Convert lists to JSON strings
    data_to_store = {
        'subject': subject,
        'grade': grade,
        'strand': data.get('strand', ''),
        'substrand': data.get('substrand', ''),
        'learning_outcomes': json.dumps(data.get('learning_outcomes', [])),
        'key_inquiry_questions': json.dumps(data.get('key_inquiry_questions', [])),
        'suggested_learning_experiences': json.dumps(data.get('suggested_learning_experiences', [])),
        'core_competencies': json.dumps(data.get('core_competencies', [])),
        'curriculum_values': json.dumps(data.get('values', [])),
        'status': status,
        'completeness_score': score,
    }
    
    try:
        cursor.execute("""
            INSERT INTO curriculum 
            (subject, grade, strand, substrand, learning_outcomes, 
             key_inquiry_questions, suggested_learning_experiences, 
             core_competencies, curriculum_values, status, completeness_score)
            VALUES 
            (:subject, :grade, :strand, :substrand, :learning_outcomes,
             :key_inquiry_questions, :suggested_learning_experiences,
             :core_competencies, :curriculum_values, :status, :completeness_score)
            ON CONFLICT(subject, grade) DO UPDATE SET
            strand = :strand,
            substrand = :substrand,
            learning_outcomes = :learning_outcomes,
            key_inquiry_questions = :key_inquiry_questions,
            suggested_learning_experiences = :suggested_learning_experiences,
            core_competencies = :core_competencies,
            curriculum_values = :curriculum_values,
            status = :status,
            completeness_score = :completeness_score,
            last_updated = CURRENT_TIMESTAMP
        """, data_to_store)
        
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_curriculum(subject=None, grade=None):
    """Retrieve curriculum entries."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if subject and grade:
        cursor.execute("SELECT * FROM curriculum WHERE subject = ? AND grade = ?", (subject, grade))
        row = cursor.fetchone()
        conn.close()
        return parse_curriculum_row(row) if row else None
    else:
        cursor.execute("SELECT * FROM curriculum ORDER BY subject, grade")
        rows = cursor.fetchall()
        conn.close()
        return [parse_curriculum_row(row) for row in rows]


def parse_curriculum_row(row):
    """Parse database row into Python objects."""
    if not row:
        return None
    
    return {
        'id': row['id'],
        'subject': row['subject'],
        'grade': row['grade'],
        'strand': row['strand'],
        'substrand': row['substrand'],
        'learning_outcomes': json.loads(row['learning_outcomes'] or '[]'),
        'key_inquiry_questions': json.loads(row['key_inquiry_questions'] or '[]'),
        'suggested_learning_experiences': json.loads(row['suggested_learning_experiences'] or '[]'),
        'core_competencies': json.loads(row['core_competencies'] or '[]'),
        'values': json.loads(row['curriculum_values'] or '[]'),
        'status': row['status'],
        'completeness_score': row['completeness_score'],
        'last_updated': row['last_updated'],
        'notes': row['notes'],
    }


def calculate_completeness(data):
    """Calculate data completeness score (0-100)."""
    checks = [
        ('strand', lambda x: len((x or '').strip()) > 0),
        ('substrand', lambda x: len((x or '').strip()) > 0),
        ('learning_outcomes', lambda x: len(x or []) >= 2),
        ('key_inquiry_questions', lambda x: len(x or []) >= 3),
        ('suggested_learning_experiences', lambda x: len(x or []) >= 5),
        ('core_competencies', lambda x: len(x or []) >= 2),
        ('values', lambda x: len(x or []) >= 2),
    ]
    
    completed = sum(1 for field, check in checks if check(data.get(field)))
    return (completed / len(checks)) * 100


def get_curriculum_stats():
    """Get database statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM curriculum")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT status, COUNT(*) as count FROM curriculum GROUP BY status")
    by_status = {row['status']: row['count'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT AVG(completeness_score) as avg_score FROM curriculum")
    avg_score = cursor.fetchone()['avg_score'] or 0
    
    conn.close()
    
    return {
        'total': total,
        'by_status': by_status,
        'average_completeness': round(avg_score, 1),
    }
