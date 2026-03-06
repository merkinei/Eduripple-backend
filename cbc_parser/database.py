"""Normalized database schema and operations for CBC curriculum data.

This module provides:
- Normalized SQLite schema with proper relationships
- CRUD operations for curriculum data
- Duplicate protection via unique constraints
- Transaction support for bulk inserts
"""

import sqlite3
import json
import os
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Database path - use DATA_DIR env var for Railway deployment
DATA_DIR = os.getenv("DATA_DIR", ".")
DATABASE_PATH = os.path.join(DATA_DIR, "curriculum.db")


@dataclass
class CurriculumRecord:
    """A single curriculum record representing one learning outcome row."""
    subject: str
    grade: str
    strand: str
    substrand: str
    learning_outcome: str
    key_inquiry_questions: list[str] = field(default_factory=list)
    learning_experiences: list[str] = field(default_factory=list)
    core_competencies: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    pcis: list[str] = field(default_factory=list)
    assessment_methods: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    source_file: str = ""
    page_number: int = 0


# SQL Schema Definition
SCHEMA_SQL = """
-- Subjects table
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grades table
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    level_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strands table (linked to subject)
CREATE TABLE IF NOT EXISTS strands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE(subject_id, name) ON CONFLICT IGNORE
);

-- Substrands table (linked to strand)
CREATE TABLE IF NOT EXISTS substrands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strand_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strand_id) REFERENCES strands(id),
    UNIQUE(strand_id, name) ON CONFLICT IGNORE
);

-- Learning outcomes table (the main curriculum content)
CREATE TABLE IF NOT EXISTS learning_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    grade_id INTEGER NOT NULL,
    strand_id INTEGER NOT NULL,
    substrand_id INTEGER NOT NULL,
    outcome_text TEXT NOT NULL,
    source_file TEXT,
    page_number INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (grade_id) REFERENCES grades(id),
    FOREIGN KEY (strand_id) REFERENCES strands(id),
    FOREIGN KEY (substrand_id) REFERENCES substrands(id),
    UNIQUE(subject_id, grade_id, strand_id, substrand_id, outcome_text) ON CONFLICT IGNORE
);

-- Key inquiry questions (linked to learning outcomes)
CREATE TABLE IF NOT EXISTS inquiry_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_outcome_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    UNIQUE(learning_outcome_id, question_text) ON CONFLICT IGNORE
);

-- Core competencies
CREATE TABLE IF NOT EXISTS competencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Learning outcome to competency mapping (many-to-many)
CREATE TABLE IF NOT EXISTS outcome_competencies (
    learning_outcome_id INTEGER NOT NULL,
    competency_id INTEGER NOT NULL,
    PRIMARY KEY (learning_outcome_id, competency_id),
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY (competency_id) REFERENCES competencies(id)
);

-- Values
CREATE TABLE IF NOT EXISTS curriculum_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Learning outcome to values mapping (many-to-many)
CREATE TABLE IF NOT EXISTS outcome_values (
    learning_outcome_id INTEGER NOT NULL,
    value_id INTEGER NOT NULL,
    PRIMARY KEY (learning_outcome_id, value_id),
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY (value_id) REFERENCES curriculum_values(id)
);

-- Pertinent and Contemporary Issues (PCIs)
CREATE TABLE IF NOT EXISTS pcis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Learning outcome to PCI mapping (many-to-many)
CREATE TABLE IF NOT EXISTS outcome_pcis (
    learning_outcome_id INTEGER NOT NULL,
    pci_id INTEGER NOT NULL,
    PRIMARY KEY (learning_outcome_id, pci_id),
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY (pci_id) REFERENCES pcis(id)
);

-- Learning experiences (linked to learning outcome)
CREATE TABLE IF NOT EXISTS learning_experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_outcome_id INTEGER NOT NULL,
    experience_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    UNIQUE(learning_outcome_id, experience_text) ON CONFLICT IGNORE
);

-- Resources
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Learning outcome to resources mapping (many-to-many)
CREATE TABLE IF NOT EXISTS outcome_resources (
    learning_outcome_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    PRIMARY KEY (learning_outcome_id, resource_id),
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id)
);

-- Assessment methods
CREATE TABLE IF NOT EXISTS assessment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Learning outcome to assessment mapping (many-to-many)
CREATE TABLE IF NOT EXISTS outcome_assessments (
    learning_outcome_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    PRIMARY KEY (learning_outcome_id, assessment_id),
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES assessment_methods(id)
);

-- Achievement indicators (linked to learning outcome)
CREATE TABLE IF NOT EXISTS indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_outcome_id INTEGER NOT NULL,
    indicator_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (learning_outcome_id) REFERENCES learning_outcomes(id) ON DELETE CASCADE,
    UNIQUE(learning_outcome_id, indicator_text) ON CONFLICT IGNORE
);

-- Parse history tracking
CREATE TABLE IF NOT EXISTS parse_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    subject TEXT,
    grade TEXT,
    rows_extracted INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,
    parse_status TEXT DEFAULT 'completed',
    error_message TEXT,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_subject ON learning_outcomes(subject_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_grade ON learning_outcomes(grade_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_strand ON learning_outcomes(strand_id);
CREATE INDEX IF NOT EXISTS idx_strands_subject ON strands(subject_id);
CREATE INDEX IF NOT EXISTS idx_substrands_strand ON substrands(strand_id);
"""


class CurriculumDatabase:
    """Database manager for CBC curriculum data."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to DATABASE_PATH.
        """
        self.db_path = db_path or DATABASE_PATH
        self._connection: Optional[sqlite3.Connection] = None
        
    @contextmanager
    def get_connection(self):
        """Get a database connection as context manager.
        
        Yields:
            sqlite3.Connection object
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    def initialize(self):
        """Initialize the database schema."""
        logger.info(f"Initializing database: {self.db_path}")
        
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        
        logger.info("Database schema created successfully")
    
    def get_or_create_subject(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a subject and return its ID."""
        cursor = conn.execute(
            "INSERT OR IGNORE INTO subjects (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM subjects WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_grade(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a grade and return its ID."""
        # Extract numeric order from grade name
        import re
        level_order = 0
        match = re.search(r'(\d+)', name)
        if match:
            level_order = int(match.group(1))
        elif 'pp1' in name.lower():
            level_order = -2
        elif 'pp2' in name.lower():
            level_order = -1
        
        conn.execute(
            "INSERT OR IGNORE INTO grades (name, level_order) VALUES (?, ?)",
            (name, level_order)
        )
        cursor = conn.execute(
            "SELECT id FROM grades WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_strand(self, conn: sqlite3.Connection, 
                             subject_id: int, name: str) -> int:
        """Get or create a strand and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO strands (subject_id, name) VALUES (?, ?)",
            (subject_id, name)
        )
        cursor = conn.execute(
            "SELECT id FROM strands WHERE subject_id = ? AND name = ?",
            (subject_id, name)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_substrand(self, conn: sqlite3.Connection,
                                strand_id: int, name: str) -> int:
        """Get or create a substrand and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO substrands (strand_id, name) VALUES (?, ?)",
            (strand_id, name)
        )
        cursor = conn.execute(
            "SELECT id FROM substrands WHERE strand_id = ? AND name = ?",
            (strand_id, name)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_competency(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a competency and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO competencies (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM competencies WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_value(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a value and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO curriculum_values (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM curriculum_values WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_pci(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a PCI and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO pcis (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM pcis WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_resource(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a resource and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO resources (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM resources WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def get_or_create_assessment(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create an assessment method and return its ID."""
        conn.execute(
            "INSERT OR IGNORE INTO assessment_methods (name) VALUES (?)", (name,)
        )
        cursor = conn.execute(
            "SELECT id FROM assessment_methods WHERE name = ? COLLATE NOCASE", (name,)
        )
        return cursor.fetchone()[0]
    
    def insert_curriculum_record(self, conn: sqlite3.Connection, 
                                  record: CurriculumRecord) -> Optional[int]:
        """Insert a curriculum record into the database.
        
        Args:
            conn: Database connection
            record: CurriculumRecord to insert
            
        Returns:
            ID of inserted learning outcome, or None if duplicate
        """
        # Get/create hierarchical entities
        subject_id = self.get_or_create_subject(conn, record.subject)
        grade_id = self.get_or_create_grade(conn, record.grade)
        strand_id = self.get_or_create_strand(conn, subject_id, record.strand)
        substrand_id = self.get_or_create_substrand(conn, strand_id, record.substrand)
        
        # Insert learning outcome
        cursor = conn.execute("""
            INSERT OR IGNORE INTO learning_outcomes 
            (subject_id, grade_id, strand_id, substrand_id, outcome_text, source_file, page_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, grade_id, strand_id, substrand_id, 
              record.learning_outcome, record.source_file, record.page_number))
        
        # If no row was inserted (duplicate), return None
        if cursor.rowcount == 0:
            return None
        
        outcome_id = cursor.lastrowid
        
        # Insert related data
        self._insert_inquiry_questions(conn, outcome_id, record.key_inquiry_questions)
        self._insert_learning_experiences(conn, outcome_id, record.learning_experiences)
        self._insert_competencies(conn, outcome_id, record.core_competencies)
        self._insert_values(conn, outcome_id, record.values)
        self._insert_pcis(conn, outcome_id, record.pcis)
        self._insert_resources(conn, outcome_id, record.resources)
        self._insert_assessments(conn, outcome_id, record.assessment_methods)
        self._insert_indicators(conn, outcome_id, record.indicators)
        
        return outcome_id
    
    def _insert_inquiry_questions(self, conn: sqlite3.Connection, 
                                   outcome_id: int, questions: list[str]):
        """Insert inquiry questions for a learning outcome."""
        for q in questions:
            if q:
                conn.execute(
                    "INSERT OR IGNORE INTO inquiry_questions (learning_outcome_id, question_text) VALUES (?, ?)",
                    (outcome_id, q)
                )
    
    def _insert_learning_experiences(self, conn: sqlite3.Connection,
                                      outcome_id: int, experiences: list[str]):
        """Insert learning experiences for a learning outcome."""
        for exp in experiences:
            if exp:
                conn.execute(
                    "INSERT OR IGNORE INTO learning_experiences (learning_outcome_id, experience_text) VALUES (?, ?)",
                    (outcome_id, exp)
                )
    
    def _insert_competencies(self, conn: sqlite3.Connection,
                              outcome_id: int, competencies: list[str]):
        """Insert competencies linked to a learning outcome."""
        for comp in competencies:
            if comp:
                comp_id = self.get_or_create_competency(conn, comp)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_competencies (learning_outcome_id, competency_id) VALUES (?, ?)",
                    (outcome_id, comp_id)
                )
    
    def _insert_values(self, conn: sqlite3.Connection,
                        outcome_id: int, values: list[str]):
        """Insert values linked to a learning outcome."""
        for val in values:
            if val:
                val_id = self.get_or_create_value(conn, val)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_values (learning_outcome_id, value_id) VALUES (?, ?)",
                    (outcome_id, val_id)
                )
    
    def _insert_pcis(self, conn: sqlite3.Connection,
                      outcome_id: int, pcis: list[str]):
        """Insert PCIs linked to a learning outcome."""
        for pci in pcis:
            if pci:
                pci_id = self.get_or_create_pci(conn, pci)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_pcis (learning_outcome_id, pci_id) VALUES (?, ?)",
                    (outcome_id, pci_id)
                )
    
    def _insert_resources(self, conn: sqlite3.Connection,
                           outcome_id: int, resources: list[str]):
        """Insert resources linked to a learning outcome."""
        for res in resources:
            if res:
                res_id = self.get_or_create_resource(conn, res)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_resources (learning_outcome_id, resource_id) VALUES (?, ?)",
                    (outcome_id, res_id)
                )
    
    def _insert_assessments(self, conn: sqlite3.Connection,
                             outcome_id: int, assessments: list[str]):
        """Insert assessment methods linked to a learning outcome."""
        for ass in assessments:
            if ass:
                ass_id = self.get_or_create_assessment(conn, ass)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_assessments (learning_outcome_id, assessment_id) VALUES (?, ?)",
                    (outcome_id, ass_id)
                )
    
    def _insert_indicators(self, conn: sqlite3.Connection,
                            outcome_id: int, indicators: list[str]):
        """Insert achievement indicators for a learning outcome."""
        for ind in indicators:
            if ind:
                conn.execute(
                    "INSERT OR IGNORE INTO indicators (learning_outcome_id, indicator_text) VALUES (?, ?)",
                    (outcome_id, ind)
                )
    
    def bulk_insert_records(self, records: list[CurriculumRecord], 
                            source_file: str = "") -> dict:
        """Insert multiple curriculum records in a single transaction.
        
        Args:
            records: List of CurriculumRecord objects
            source_file: Source filename for tracking
            
        Returns:
            Dict with insertion statistics
        """
        stats = {
            'total': len(records),
            'inserted': 0,
            'duplicates': 0,
            'errors': 0,
        }
        
        with self.get_connection() as conn:
            for record in records:
                try:
                    result = self.insert_curriculum_record(conn, record)
                    if result:
                        stats['inserted'] += 1
                    else:
                        stats['duplicates'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error inserting record: {e}")
            
            # Record parse history
            conn.execute("""
                INSERT INTO parse_history 
                (filename, subject, grade, rows_extracted, rows_inserted, parse_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                source_file,
                records[0].subject if records else None,
                records[0].grade if records else None,
                stats['total'],
                stats['inserted'],
                'completed' if stats['errors'] == 0 else 'partial'
            ))
            
            conn.commit()
        
        return stats
    
    def get_curriculum_summary(self) -> dict:
        """Get summary statistics of the curriculum database."""
        with self.get_connection() as conn:
            stats = {}
            
            # Count entities
            tables = ['subjects', 'grades', 'strands', 'substrands', 
                      'learning_outcomes', 'competencies', 'curriculum_values', 'pcis']
            
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            return stats
    
    def export_to_json(self, output_path: str):
        """Export curriculum data to JSON format.
        
        Args:
            output_path: Path for the JSON output file
        """
        logger.info(f"Exporting curriculum data to {output_path}")
        
        with self.get_connection() as conn:
            # Query all learning outcomes with related data
            cursor = conn.execute("""
                SELECT 
                    lo.id,
                    s.name as subject,
                    g.name as grade,
                    st.name as strand,
                    ss.name as substrand,
                    lo.outcome_text,
                    lo.source_file,
                    lo.page_number
                FROM learning_outcomes lo
                JOIN subjects s ON lo.subject_id = s.id
                JOIN grades g ON lo.grade_id = g.id
                JOIN strands st ON lo.strand_id = st.id
                JOIN substrands ss ON lo.substrand_id = ss.id
                ORDER BY s.name, g.level_order, st.name, ss.name
            """)
            
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                outcome_id = record.pop('id')
                
                # Get related data
                record['key_inquiry_questions'] = self._get_inquiry_questions(conn, outcome_id)
                record['learning_experiences'] = self._get_learning_experiences(conn, outcome_id)
                record['core_competencies'] = self._get_competencies(conn, outcome_id)
                record['values'] = self._get_values(conn, outcome_id)
                record['pcis'] = self._get_pcis(conn, outcome_id)
                record['resources'] = self._get_resources(conn, outcome_id)
                record['assessment_methods'] = self._get_assessments(conn, outcome_id)
                
                records.append(record)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(records)} curriculum records to JSON")
    
    def _get_inquiry_questions(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute(
            "SELECT question_text FROM inquiry_questions WHERE learning_outcome_id = ?",
            (outcome_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    
    def _get_learning_experiences(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute(
            "SELECT experience_text FROM learning_experiences WHERE learning_outcome_id = ?",
            (outcome_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    
    def _get_competencies(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute("""
            SELECT c.name FROM competencies c
            JOIN outcome_competencies oc ON c.id = oc.competency_id
            WHERE oc.learning_outcome_id = ?
        """, (outcome_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_values(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute("""
            SELECT v.name FROM curriculum_values v
            JOIN outcome_values ov ON v.id = ov.value_id
            WHERE ov.learning_outcome_id = ?
        """, (outcome_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_pcis(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute("""
            SELECT p.name FROM pcis p
            JOIN outcome_pcis op ON p.id = op.pci_id
            WHERE op.learning_outcome_id = ?
        """, (outcome_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_resources(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute("""
            SELECT r.name FROM resources r
            JOIN outcome_resources ore ON r.id = ore.resource_id
            WHERE ore.learning_outcome_id = ?
        """, (outcome_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def _get_assessments(self, conn: sqlite3.Connection, outcome_id: int) -> list[str]:
        cursor = conn.execute("""
            SELECT a.name FROM assessment_methods a
            JOIN outcome_assessments oa ON a.id = oa.assessment_id
            WHERE oa.learning_outcome_id = ?
        """, (outcome_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def clear_all_data(self):
        """Clear all data from the database (for re-parsing)."""
        logger.warning("Clearing all curriculum data from database")
        
        with self.get_connection() as conn:
            # Delete in order respecting foreign keys
            tables = [
                'outcome_assessments', 'outcome_resources', 'outcome_pcis',
                'outcome_values', 'outcome_competencies', 'learning_experiences',
                'inquiry_questions', 'indicators', 'learning_outcomes',
                'substrands', 'strands', 'assessment_methods', 'resources',
                'pcis', 'curriculum_values', 'competencies', 'grades', 'subjects',
                'parse_history'
            ]
            
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
            
            conn.commit()
        
        logger.info("All curriculum data cleared")
