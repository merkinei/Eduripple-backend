"""Row parser for CBC curriculum tables.

This module converts raw table rows into structured CurriculumRecord objects.
Handles:
- Context carryover for blank strand/substrand cells
- Field extraction and normalization
- Multiple learning outcomes per row
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .cleaner import normalize_field_value, extract_list_items, clean_text
from .header_normalizer import normalize_headers, get_list_fields
from .database import CurriculumRecord
from .validator import validate_learning_outcome

logger = logging.getLogger(__name__)


@dataclass
class ParsingContext:
    """Maintains parsing context across table rows.
    
    Used to carry forward strand/substrand when cells are blank.
    """
    current_strand: str = ""
    current_substrand: str = ""
    subject: str = ""
    grade: str = ""
    source_file: str = ""
    page_number: int = 0
    
    def update_strand(self, strand: str):
        """Update current strand and reset substrand."""
        if strand:
            self.current_strand = strand
            # Don't reset substrand automatically - let it carry over too
    
    def update_substrand(self, substrand: str):
        """Update current substrand."""
        if substrand:
            self.current_substrand = substrand
    
    def reset(self):
        """Reset context (for new table or PDF)."""
        self.current_strand = ""
        self.current_substrand = ""


class RowParser:
    """Parses curriculum table rows into structured records."""
    
    def __init__(self, context: Optional[ParsingContext] = None):
        """Initialize row parser.
        
        Args:
            context: Parsing context for carryover. Created if not provided.
        """
        self.context = context or ParsingContext()
        self.list_fields = get_list_fields()
    
    def parse_table(self, table: list[list], headers: list[str],
                    page_number: int = 0) -> list[CurriculumRecord]:
        """Parse an entire table into curriculum records.
        
        Args:
            table: List of rows (each row is a list of cell values)
            headers: Header row (already extracted)
            page_number: PDF page number for tracking
            
        Returns:
            List of CurriculumRecord objects
        """
        records = []
        
        # Normalize headers to get column mapping
        header_mapping = normalize_headers(headers)
        
        if not header_mapping:
            logger.warning("No recognized headers found in table")
            return records
        
        self.context.page_number = page_number
        
        # Process each data row
        for row_idx, row in enumerate(table):
            try:
                row_records = self.parse_row(row, header_mapping)
                records.extend(row_records)
            except Exception as e:
                logger.debug(f"Error parsing row {row_idx}: {e}")
        
        return records
    
    def parse_row(self, row: list, header_mapping: dict[int, str]) -> list[CurriculumRecord]:
        """Parse a single table row into curriculum records.
        
        One row may produce multiple CurriculumRecord objects if it contains
        multiple learning outcomes.
        
        Args:
            row: List of cell values
            header_mapping: Dict mapping column index to canonical field name
            
        Returns:
            List of CurriculumRecord objects
        """
        # Extract all fields from row
        fields = self._extract_fields(row, header_mapping)
        
        # Handle strand carryover
        strand = fields.get('strand', '')
        if strand:
            self.context.update_strand(strand)
        else:
            strand = self.context.current_strand
        
        # Handle substrand carryover
        substrand = fields.get('substrand', '')
        if substrand:
            self.context.update_substrand(substrand)
        else:
            substrand = self.context.current_substrand
        
        # Get learning outcomes - may be multiple
        learning_outcomes = fields.get('learning_outcome', [])
        if isinstance(learning_outcomes, str):
            learning_outcomes = extract_list_items(learning_outcomes)
        
        # If no outcomes, check for outcomes in wrong column
        if not learning_outcomes:
            # Sometimes outcomes are in 'indicator' or 'content' columns
            for alt_field in ['indicator', 'content']:
                alt_value = fields.get(alt_field, [])
                if isinstance(alt_value, str):
                    alt_value = extract_list_items(alt_value)
                if alt_value:
                    learning_outcomes = alt_value
                    break
        
        # Create records for each learning outcome
        records = []
        
        # Extract other fields (shared across all outcomes in this row)
        shared_fields = {
            'key_inquiry_questions': self._ensure_list(fields.get('key_inquiry_question', [])),
            'learning_experiences': self._ensure_list(fields.get('learning_experience', [])),
            'core_competencies': self._ensure_list(fields.get('core_competency', [])),
            'values': self._ensure_list(fields.get('value', [])),
            'pcis': self._ensure_list(fields.get('pci', [])),
            'assessment_methods': self._ensure_list(fields.get('assessment', [])),
            'resources': self._ensure_list(fields.get('resource', [])),
            'indicators': self._ensure_list(fields.get('indicator', [])),
        }
        
        for outcome in learning_outcomes:
            # Validate the learning outcome
            if not validate_learning_outcome(outcome):
                continue
            
            record = CurriculumRecord(
                subject=self.context.subject,
                grade=self.context.grade,
                strand=strand,
                substrand=substrand,
                learning_outcome=outcome,
                source_file=self.context.source_file,
                page_number=self.context.page_number,
                **shared_fields
            )
            records.append(record)
        
        return records
    
    def _extract_fields(self, row: list, header_mapping: dict[int, str]) -> dict:
        """Extract and normalize fields from a row.
        
        Args:
            row: List of cell values
            header_mapping: Column index to field name mapping
            
        Returns:
            Dict with field names and their values
        """
        fields = {}
        
        for col_idx, field_name in header_mapping.items():
            if col_idx >= len(row):
                continue
            
            raw_value = row[col_idx]
            
            if not raw_value:
                continue
            
            # Check if this is a list-type field
            if field_name in self.list_fields:
                # Extract as list
                value = extract_list_items(str(raw_value))
            else:
                # Extract as single value
                value = normalize_field_value(str(raw_value))
            
            if value:
                fields[field_name] = value
        
        return fields
    
    def _ensure_list(self, value) -> list:
        """Ensure value is a list.
        
        Args:
            value: String or list
            
        Returns:
            List of strings
        """
        if not value:
            return []
        if isinstance(value, str):
            return extract_list_items(value)
        return value
    
    def set_context(self, subject: str, grade: str, source_file: str = ""):
        """Set parsing context for a new document.
        
        Args:
            subject: Subject name
            grade: Grade level
            source_file: Source filename
        """
        self.context.subject = subject
        self.context.grade = grade
        self.context.source_file = source_file
        self.context.reset()


def parse_subject_grade(filename: str) -> tuple[str, str]:
    """Extract subject and grade from PDF filename.
    
    Args:
        filename: PDF filename (with or without extension)
        
    Returns:
        Tuple of (subject, grade)
    """
    import re
    
    # Remove extension
    name = str(filename).replace('.pdf', '').replace('.PDF', '')
    
    # Common grade patterns
    grade_patterns = [
        r'Grade[_\s]?(\d+)',           # Grade_7, Grade 7, Grade7
        r'_(\d+)$',                     # trailing _7
        r'_([A-Z]P\d?)$',               # PP1, PP2
        r'(PP[12])',                    # Pre-primary
        r'Pre[_\s]?Primary[_\s]?(\d)',  # Pre-Primary 1
    ]
    
    grade = "Unknown"
    grade_match_pos = len(name)
    
    for pattern in grade_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            grade_num = match.group(1)
            if grade_num.upper().startswith('PP'):
                grade = grade_num.upper()
            elif grade_num.isdigit():
                grade = f"Grade {grade_num}"
            else:
                grade = grade_num
            grade_match_pos = match.start()
            break
    
    # Subject is everything before the grade
    subject_part = name[:grade_match_pos].strip('_- ')
    
    # Clean up subject name
    subject = subject_part.replace('_', ' ').strip()
    
    # Handle special cases
    if not subject:
        subject = "Unknown"
    
    # Fix common variations
    subject_fixes = {
        'CRE': 'Christian Religious Education',
        'IRE': 'Islamic Religious Education',
        'HRE': 'Hindu Religious Education',
        'PHE': 'Physical and Health Education',
        'Agri': 'Agriculture',
    }
    
    for abbrev, full_name in subject_fixes.items():
        if subject.upper() == abbrev:
            subject = full_name
            break
    
    return subject, grade


class TableRowIterator:
    """Iterator that handles context carryover across table rows."""
    
    def __init__(self, table: list[list], headers: list[str]):
        """Initialize iterator.
        
        Args:
            table: Raw table data (list of rows)
            headers: Header row
        """
        self.table = table
        self.headers = headers
        self.header_mapping = normalize_headers(headers)
        self.current_strand = ""
        self.current_substrand = ""
        self.row_index = 0
    
    def __iter__(self):
        return self
    
    def __next__(self) -> dict:
        """Get next row with context carryover applied.
        
        Returns:
            Dict with all fields, including carried-over strand/substrand
        """
        if self.row_index >= len(self.table):
            raise StopIteration
        
        row = self.table[self.row_index]
        self.row_index += 1
        
        # Build row dict with carryover
        row_dict = {}
        
        for col_idx, field_name in self.header_mapping.items():
            if col_idx < len(row) and row[col_idx]:
                row_dict[field_name] = row[col_idx]
        
        # Apply carryover for strand
        if 'strand' in row_dict and row_dict['strand']:
            self.current_strand = clean_text(row_dict['strand'])
        row_dict['strand'] = self.current_strand
        
        # Apply carryover for substrand
        if 'substrand' in row_dict and row_dict['substrand']:
            self.current_substrand = clean_text(row_dict['substrand'])
        row_dict['substrand'] = self.current_substrand
        
        return row_dict
