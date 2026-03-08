"""Curriculum database utilities - reads from cbc_parser.py generated database."""

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
    """Initialize/verify curriculum database exists.
    
    Note: The actual table creation is handled by cbc_parser.py.
    This function just ensures the database file exists.
    """
    db_path = Path(CURRICULUM_DB)
    if not db_path.exists():
        print(f"[WARN] Curriculum database not found at {db_path}")
        print("       Run cbc_parser.py to generate the database from PDFs")
        return False
    print(f"[OK] Curriculum database found: {db_path}")
    return True


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(CURRICULUM_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_curriculum(subject=None, grade=None, substrand=None):
    """Retrieve curriculum entries from the parser-generated database.
    
    Args:
        subject: Filter by subject name (optional)
        grade: Filter by grade (optional)
        substrand: Filter by substrand (optional)
    
    Returns:
        List of curriculum entries or single entry if all filters provided
    """
    if not Path(CURRICULUM_DB).exists():
        return [] if not (subject and grade and substrand) else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if subject and grade and substrand:
            cursor.execute("""
                SELECT * FROM curriculum 
                WHERE subject = ? AND grade = ? AND substrand = ?
            """, (subject, grade, substrand))
            row = cursor.fetchone()
            return parse_curriculum_row(row) if row else None
        elif subject and grade:
            cursor.execute("""
                SELECT * FROM curriculum 
                WHERE subject = ? AND grade = ?
                ORDER BY strand, substrand
            """, (subject, grade))
            rows = cursor.fetchall()
            return [parse_curriculum_row(row) for row in rows]
        elif subject:
            cursor.execute("""
                SELECT * FROM curriculum 
                WHERE subject = ?
                ORDER BY grade, strand, substrand
            """, (subject,))
            rows = cursor.fetchall()
            return [parse_curriculum_row(row) for row in rows]
        else:
            cursor.execute("""
                SELECT * FROM curriculum 
                ORDER BY subject, grade, strand, substrand
            """)
            rows = cursor.fetchall()
            return [parse_curriculum_row(row) for row in rows]
    finally:
        conn.close()


def parse_curriculum_row(row):
    """Parse database row into Python dict matching the parser schema."""
    if not row:
        return None
    
    # Handle both old and new column names for compatibility
    row_dict = dict(row)
    
    return {
        'id': row_dict.get('id'),
        'subject': row_dict.get('subject', ''),
        'grade': row_dict.get('grade', ''),
        'strand': row_dict.get('strand', ''),
        'strand_number': row_dict.get('strand_number', ''),
        'substrand': row_dict.get('substrand', ''),
        'substrand_number': row_dict.get('substrand_number', ''),
        'num_lessons': row_dict.get('num_lessons', ''),
        'learning_outcomes': json.loads(row_dict.get('learning_outcomes') or '[]'),
        'key_inquiry_questions': json.loads(row_dict.get('key_inquiry') or '[]'),
        'suggested_learning_experiences': json.loads(row_dict.get('activities') or '[]'),
        'core_competencies': json.loads(row_dict.get('competencies') or '[]'),
        'values': json.loads(row_dict.get('values_') or '[]'),
        'pcis': json.loads(row_dict.get('pcis') or '[]'),
        'assessment': json.loads(row_dict.get('assessment') or '[]'),
        'link_subjects': json.loads(row_dict.get('link_subjects') or '[]'),
        'raw_text': row_dict.get('raw_text', ''),
    }


def search_curriculum(query, limit=10):
    """Search curriculum by keyword in substrand, strand, or learning outcomes.
    
    Args:
        query: Search term
        limit: Maximum results to return
    
    Returns:
        List of matching curriculum entries
    """
    if not Path(CURRICULUM_DB).exists():
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        search_term = f"%{query}%"
        cursor.execute("""
            SELECT * FROM curriculum 
            WHERE substrand LIKE ? 
               OR strand LIKE ? 
               OR learning_outcomes LIKE ?
               OR key_inquiry LIKE ?
               OR activities LIKE ?
            ORDER BY subject, grade
            LIMIT ?
        """, (search_term, search_term, search_term, search_term, search_term, limit))
        rows = cursor.fetchall()
        return [parse_curriculum_row(row) for row in rows]
    finally:
        conn.close()


def get_curriculum_stats():
    """Get database statistics."""
    if not Path(CURRICULUM_DB).exists():
        return {'total': 0, 'by_subject': {}, 'by_grade': {}}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) as total FROM curriculum")
        total = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT subject, COUNT(*) as count 
            FROM curriculum 
            GROUP BY subject 
            ORDER BY count DESC
        """)
        by_subject = {row['subject']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT grade, COUNT(*) as count 
            FROM curriculum 
            GROUP BY grade 
            ORDER BY grade
        """)
        by_grade = {row['grade']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total': total,
            'by_subject': by_subject,
            'by_grade': by_grade,
        }
    finally:
        conn.close()


def get_subjects():
    """Get list of unique subjects."""
    if not Path(CURRICULUM_DB).exists():
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT subject FROM curriculum ORDER BY subject")
        return [row['subject'] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_grades():
    """Get list of unique grades."""
    if not Path(CURRICULUM_DB).exists():
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT grade FROM curriculum ORDER BY grade")
        return [row['grade'] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_strands(subject=None, grade=None):
    """Get list of strands, optionally filtered by subject and grade."""
    if not Path(CURRICULUM_DB).exists():
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if subject and grade:
            cursor.execute("""
                SELECT DISTINCT strand FROM curriculum 
                WHERE subject = ? AND grade = ?
                ORDER BY strand
            """, (subject, grade))
        elif subject:
            cursor.execute("""
                SELECT DISTINCT strand FROM curriculum 
                WHERE subject = ?
                ORDER BY strand
            """, (subject,))
        else:
            cursor.execute("SELECT DISTINCT strand FROM curriculum ORDER BY strand")
        return [row['strand'] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_substrands(subject=None, grade=None, strand=None):
    """Get list of substrands, optionally filtered."""
    if not Path(CURRICULUM_DB).exists():
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if subject and grade and strand:
            cursor.execute("""
                SELECT DISTINCT substrand FROM curriculum 
                WHERE subject = ? AND grade = ? AND strand = ?
                ORDER BY substrand
            """, (subject, grade, strand))
        elif subject and grade:
            cursor.execute("""
                SELECT DISTINCT substrand FROM curriculum 
                WHERE subject = ? AND grade = ?
                ORDER BY substrand
            """, (subject, grade))
        else:
            cursor.execute("SELECT DISTINCT substrand FROM curriculum ORDER BY substrand")
        return [row['substrand'] for row in cursor.fetchall()]
    finally:
        conn.close()


def calculate_completeness(data):
    """Calculate data completeness score (0-100)."""
    checks = [
        ('strand', lambda x: len((x or '').strip()) > 0),
        ('substrand', lambda x: len((x or '').strip()) > 0),
        ('learning_outcomes', lambda x: len(x or []) >= 2),
        ('key_inquiry_questions', lambda x: len(x or []) >= 1),
        ('suggested_learning_experiences', lambda x: len(x or []) >= 3),
        ('core_competencies', lambda x: len(x or []) >= 1),
        ('values', lambda x: len(x or []) >= 1),
    ]
    
    completed = sum(1 for field, check in checks if check(data.get(field)))
    return (completed / len(checks)) * 100


def insert_curriculum(subject, grade, data, status="manual"):
    """Insert or update a curriculum entry (for admin edits).
    
    Note: This is for manual admin edits, not for the parser.
    The parser uses its own insert_substrand function.
    """
    if not Path(CURRICULUM_DB).exists():
        return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if entry exists
        cursor.execute("""
            SELECT id FROM curriculum 
            WHERE subject = ? AND grade = ? AND substrand = ?
        """, (subject, grade, data.get('substrand', '')))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute("""
                UPDATE curriculum SET
                    strand = ?,
                    learning_outcomes = ?,
                    key_inquiry = ?,
                    activities = ?,
                    competencies = ?,
                    values_ = ?
                WHERE id = ?
            """, (
                data.get('strand', ''),
                json.dumps(data.get('learning_outcomes', [])),
                json.dumps(data.get('key_inquiry_questions', [])),
                json.dumps(data.get('suggested_learning_experiences', [])),
                json.dumps(data.get('core_competencies', [])),
                json.dumps(data.get('values', [])),
                existing['id']
            ))
            conn.commit()
            return existing['id']
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO curriculum (
                    subject, grade, strand, substrand,
                    learning_outcomes, key_inquiry, activities,
                    competencies, values_
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subject, grade,
                data.get('strand', ''),
                data.get('substrand', ''),
                json.dumps(data.get('learning_outcomes', [])),
                json.dumps(data.get('key_inquiry_questions', [])),
                json.dumps(data.get('suggested_learning_experiences', [])),
                json.dumps(data.get('core_competencies', [])),
                json.dumps(data.get('values', []))
            ))
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()
