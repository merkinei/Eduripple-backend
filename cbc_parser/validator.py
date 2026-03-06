"""Validation logic for CBC curriculum data.

This module validates curriculum rows and tables to ensure
data quality before database insertion.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .cleaner import is_garbage_text, clean_text
from .header_normalizer import get_required_fields, get_optional_fields

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a curriculum row."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


# Minimum lengths for required fields
MIN_FIELD_LENGTHS = {
    'strand': 2,
    'substrand': 2,
    'learning_outcome': 10,
}

# Maximum lengths (for sanity checking)
MAX_FIELD_LENGTHS = {
    'strand': 200,
    'substrand': 300,
    'learning_outcome': 1000,
    'key_inquiry_question': 500,
    'learning_experience': 1000,
    'core_competency': 200,
    'value': 200,
    'pci': 500,
    'assessment': 500,
    'resource': 500,
}


def validate_row(row: dict) -> ValidationResult:
    """Validate a single curriculum row.
    
    Args:
        row: Dictionary with curriculum fields
        
    Returns:
        ValidationResult indicating validity and any issues
    """
    errors = []
    warnings = []
    
    required_fields = get_required_fields()
    
    # Check required fields exist and are not empty
    for field in required_fields:
        value = row.get(field, '')
        
        if not value:
            errors.append(f"Missing required field: {field}")
            continue
            
        # Check minimum length
        min_len = MIN_FIELD_LENGTHS.get(field, 2)
        if len(str(value)) < min_len:
            errors.append(f"Field '{field}' is too short (min {min_len} chars)")
            continue
        
        # Check for garbage text
        if isinstance(value, str) and is_garbage_text(value):
            errors.append(f"Field '{field}' appears to contain invalid content")
    
    # Check optional fields for quality
    optional_fields = get_optional_fields()
    for field in optional_fields:
        value = row.get(field)
        if not value:
            continue
            
        # Handle both string and list values
        if isinstance(value, list):
            for item in value:
                if is_garbage_text(str(item)):
                    warnings.append(f"Field '{field}' contains potentially invalid items")
                    break
        elif isinstance(value, str):
            if is_garbage_text(value):
                warnings.append(f"Field '{field}' appears to contain invalid content")
    
    # Check field lengths don't exceed maximums
    for field, max_len in MAX_FIELD_LENGTHS.items():
        value = row.get(field, '')
        if isinstance(value, str) and len(value) > max_len:
            warnings.append(f"Field '{field}' exceeds maximum length ({max_len})")
    
    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_learning_outcome(outcome: str) -> bool:
    """Validate a single learning outcome string.
    
    Args:
        outcome: Learning outcome text
        
    Returns:
        True if outcome appears valid
    """
    if not outcome:
        return False
    
    outcome = clean_text(outcome)
    
    # Too short
    if len(outcome) < 10:
        return False
    
    # Contains garbage
    if is_garbage_text(outcome):
        return False
    
    # Should contain some action verbs typically found in learning outcomes
    action_indicators = [
        'identify', 'describe', 'explain', 'demonstrate', 'apply',
        'analyze', 'evaluate', 'create', 'develop', 'use', 'recognize',
        'understand', 'know', 'list', 'name', 'define', 'compare',
        'distinguish', 'interpret', 'illustrate', 'solve', 'practice',
        'perform', 'appreciate', 'explore', 'discuss', 'write', 'read',
    ]
    
    outcome_lower = outcome.lower()
    has_action = any(verb in outcome_lower for verb in action_indicators)
    
    # If very long, it's probably valid content even without action verbs
    if len(outcome) > 50:
        return True
    
    return has_action


def validate_table_structure(headers: list) -> ValidationResult:
    """Validate that a table has the expected structure for curriculum data.
    
    Args:
        headers: List of header strings from the table
        
    Returns:
        ValidationResult indicating if table structure is valid
    """
    errors = []
    warnings = []
    
    if not headers:
        errors.append("Table has no headers")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
    
    # Clean headers
    cleaned_headers = [str(h).strip().lower() if h else '' for h in headers]
    
    # Check for minimum columns
    if len(cleaned_headers) < 2:
        errors.append("Table has fewer than 2 columns")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
    
    # Check for empty headers
    empty_count = sum(1 for h in cleaned_headers if not h)
    if empty_count > len(cleaned_headers) / 2:
        warnings.append("More than half of headers are empty")
    
    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_subject_grade(subject: str, grade: str) -> ValidationResult:
    """Validate subject and grade extraction.
    
    Args:
        subject: Extracted subject name
        grade: Extracted grade level
        
    Returns:
        ValidationResult for subject/grade
    """
    errors = []
    warnings = []
    
    if not subject or subject.lower() == 'unknown':
        errors.append("Could not extract subject from filename")
    elif len(subject) < 2:
        errors.append("Subject name is too short")
    
    if not grade or grade.lower() == 'unknown':
        warnings.append("Could not extract grade from filename")
    
    # Validate grade format
    if grade:
        import re
        grade_pattern = r'grade\s*\d+|pp[12]|pre-primary\s*[12]'
        if not re.search(grade_pattern, grade.lower()):
            warnings.append(f"Grade format may be incorrect: {grade}")
    
    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def filter_valid_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Filter a list of rows into valid and invalid sets.
    
    Args:
        rows: List of curriculum row dictionaries
        
    Returns:
        Tuple of (valid_rows, invalid_rows)
    """
    valid = []
    invalid = []
    
    for row in rows:
        result = validate_row(row)
        if result.is_valid:
            valid.append(row)
        else:
            invalid.append({
                'row': row,
                'errors': result.errors,
                'warnings': result.warnings,
            })
            logger.debug(f"Invalid row: {result.errors}")
    
    return valid, invalid


class ValidationStats:
    """Track validation statistics during parsing."""
    
    def __init__(self):
        self.total_rows = 0
        self.valid_rows = 0
        self.invalid_rows = 0
        self.tables_processed = 0
        self.tables_skipped = 0
        self.warnings_count = 0
        self.errors_by_type: dict[str, int] = {}
    
    def record_valid(self):
        """Record a valid row."""
        self.total_rows += 1
        self.valid_rows += 1
    
    def record_invalid(self, errors: list[str]):
        """Record an invalid row with its errors."""
        self.total_rows += 1
        self.invalid_rows += 1
        for error in errors:
            # Categorize error
            error_type = error.split(':')[0] if ':' in error else error
            self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
    
    def record_table_processed(self):
        """Record a table that was processed."""
        self.tables_processed += 1
    
    def record_table_skipped(self, reason: str = ""):
        """Record a table that was skipped."""
        self.tables_skipped += 1
        if reason:
            logger.debug(f"Table skipped: {reason}")
    
    def record_warning(self):
        """Record a warning."""
        self.warnings_count += 1
    
    def get_summary(self) -> dict:
        """Get validation statistics summary."""
        return {
            'total_rows': self.total_rows,
            'valid_rows': self.valid_rows,
            'invalid_rows': self.invalid_rows,
            'validity_rate': self.valid_rows / self.total_rows if self.total_rows > 0 else 0,
            'tables_processed': self.tables_processed,
            'tables_skipped': self.tables_skipped,
            'warnings_count': self.warnings_count,
            'errors_by_type': self.errors_by_type,
        }
    
    def log_summary(self):
        """Log a summary of validation statistics."""
        summary = self.get_summary()
        logger.info(f"Validation Summary:")
        logger.info(f"  Total rows: {summary['total_rows']}")
        logger.info(f"  Valid rows: {summary['valid_rows']} ({summary['validity_rate']:.1%})")
        logger.info(f"  Invalid rows: {summary['invalid_rows']}")
        logger.info(f"  Tables processed: {summary['tables_processed']}")
        logger.info(f"  Tables skipped: {summary['tables_skipped']}")
        if summary['errors_by_type']:
            logger.info(f"  Top error types:")
            for error_type, count in sorted(summary['errors_by_type'].items(), 
                                           key=lambda x: -x[1])[:5]:
                logger.info(f"    - {error_type}: {count}")
