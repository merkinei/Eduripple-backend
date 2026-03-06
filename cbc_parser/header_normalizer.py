"""Header normalization for CBC curriculum tables.

This module maps various header name variations found in CBC PDFs
to canonical field names used throughout the system.
"""

import re
from typing import Optional

# Canonical field names -> list of variations (patterns)
HEADER_MAPPINGS = {
    'strand': [
        r'\bstrand\b',
        r'\bstrands\b',
        r'\btheme\b',
        r'\bthemes\b',
    ],
    'substrand': [
        r'\bsub[\s\-]?strand\b',
        r'\bsub[\s\-]?strands\b',
        r'\bsubtopic\b',
        r'\bsub[\s\-]?topic\b',
        r'\bsub[\s\-]?theme\b',
    ],
    'learning_outcome': [
        r'\bspecific\s+learning\s+outcomes?\b',
        r'\blearning\s+outcomes?\b',
        r'\bexpected\s+learning\s+outcomes?\b',
        r'\boutcomes?\b',
        r'\bslo\b',
        r'\bobjectives?\b',
        r'\blearning\s+objectives?\b',
    ],
    'key_inquiry_question': [
        r'\bkey\s+inquiry\s+questions?\b',
        r'\binquiry\s+questions?\b',
        r'\bkey\s+questions?\b',
        r'\bkiq\b',
        r'\bguiding\s+questions?\b',
    ],
    'learning_experience': [
        r'\bsuggested\s+learning\s+experiences?\b',
        r'\blearning\s+experiences?\b',
        r'\bsle\b',
        r'\bsuggested\s+activities\b',
        r'\blearning\s+activities\b',
        r'\bactivities\b',
    ],
    'core_competency': [
        r'\bcore\s+competenc(y|ies)\b',
        r'\bcompetenc(y|ies)\s+to\s+be\s+developed\b',
        r'\bcompetenc(y|ies)\b',
        r'\bcc\b',
    ],
    'value': [
        r'\bvalues?\s+to\s+be\s+developed\b',
        r'\bnational\s+values?\b',
        r'\bcore\s+values?\b',
        r'\bvalues?\b',
    ],
    'pci': [
        r'\bpertinent\s+and\s+contemporary\s+issues?\b',
        r'\bpcis?\b',
        r'\bcontemporary\s+issues?\b',
        r'\bcross[\s\-]?cutting\s+issues?\b',
    ],
    'assessment': [
        r'\bassessment\s+approach(es)?\b',
        r'\bassessment\s+methods?\b',
        r'\bassessment\s+criteria\b',
        r'\bevaluation\s+methods?\b',
        r'\bassessment\b',
    ],
    'resource': [
        r'\bsuggested\s+resources?\b',
        r'\blearning\s+resources?\b',
        r'\bresources?\b',
        r'\bmaterials?\b',
        r'\bteaching[\s\/]learning\s+resources?\b',
    ],
    'indicator': [
        r'\bindicators?\s+of\s+achievement\b',
        r'\bachievement\s+indicators?\b',
        r'\bindicators?\b',
        r'\bperformance\s+indicators?\b',
    ],
    'content': [
        r'\bcontent\b',
        r'\bknowledge\b',
        r'\btopic\s+content\b',
    ],
    'time': [
        r'\btime\b',
        r'\bduration\b',
        r'\blesson\s+duration\b',
        r'\bperiods?\b',
        r'\bhours?\b',
    ],
}

# Headers that indicate a curriculum table (for filtering)
CURRICULUM_INDICATOR_HEADERS = {
    'strand': 10,
    'substrand': 10,
    'learning_outcome': 8,
    'key_inquiry_question': 6,
    'learning_experience': 5,
    'core_competency': 5,
    'value': 3,
    'indicator': 4,
}

# Minimum score to consider a table as curriculum-related
MIN_CURRICULUM_SCORE = 15


def normalize_header(header: Optional[str]) -> str:
    """Map a header string to its canonical name.
    
    Args:
        header: Raw header text from PDF table
        
    Returns:
        Canonical field name, or original header if no mapping found
    """
    if not header:
        return ""
    
    # Clean and lowercase the header
    h = str(header).strip().lower()
    h = re.sub(r'\s+', ' ', h)
    h = re.sub(r'[^\w\s\-]', '', h)  # Remove special chars except hyphen
    
    # Try to match against known patterns
    for canonical, patterns in HEADER_MAPPINGS.items():
        for pattern in patterns:
            if re.search(pattern, h, re.IGNORECASE):
                return canonical
    
    # Return cleaned original if no match
    return h.replace(' ', '_').replace('-', '_')


def normalize_headers(headers: list[str]) -> dict[int, str]:
    """Normalize a list of headers and return index mapping.
    
    Args:
        headers: List of raw header strings
        
    Returns:
        Dict mapping column index to canonical header name
    """
    mapping = {}
    
    for idx, header in enumerate(headers):
        if header:
            canonical = normalize_header(header)
            if canonical:
                mapping[idx] = canonical
    
    return mapping


def calculate_curriculum_score(headers: list[str]) -> int:
    """Calculate how likely this table is curriculum-related based on headers.
    
    Args:
        headers: List of header strings
        
    Returns:
        Score indicating curriculum relevance (higher = more likely)
    """
    score = 0
    normalized = [normalize_header(h) for h in headers if h]
    
    for header in normalized:
        if header in CURRICULUM_INDICATOR_HEADERS:
            score += CURRICULUM_INDICATOR_HEADERS[header]
    
    return score


def is_curriculum_table(headers: list[str]) -> bool:
    """Determine if a table is likely a curriculum content table.
    
    Args:
        headers: List of header strings from the table
        
    Returns:
        True if table appears to be curriculum-related
    """
    score = calculate_curriculum_score(headers)
    return score >= MIN_CURRICULUM_SCORE


def get_required_fields() -> set[str]:
    """Get set of fields required for a valid curriculum row.
    
    Returns:
        Set of canonical field names that are required
    """
    return {'strand', 'substrand', 'learning_outcome'}


def get_optional_fields() -> set[str]:
    """Get set of optional curriculum fields.
    
    Returns:
        Set of canonical field names that are optional
    """
    return {
        'key_inquiry_question',
        'learning_experience',
        'core_competency',
        'value',
        'pci',
        'assessment',
        'resource',
        'indicator',
        'content',
        'time',
    }


def get_list_fields() -> set[str]:
    """Get fields that typically contain multiple items (lists).
    
    Returns:
        Set of canonical field names that are list-type
    """
    return {
        'learning_outcome',
        'key_inquiry_question',
        'learning_experience',
        'core_competency',
        'value',
        'pci',
        'assessment',
        'resource',
        'indicator',
    }
