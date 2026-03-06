"""Text cleaning and normalization utilities for CBC PDF extraction.

This module handles:
- Whitespace normalization
- Bullet character removal
- Line break cleanup
- PDF extraction artifact removal
"""

import re
import unicodedata
from typing import Optional


# Common PDF artifacts to remove
PDF_ARTIFACTS = [
    '\x00', '\x01', '\x02', '\x03',  # Control characters
    '\uf0b7', '\uf0a7', '\uf0d8',    # PDF bullet symbols
    '\ufffd',                         # Replacement character
    '�',                              # Mojibake
]

# Bullet patterns to normalize
BULLET_PATTERNS = [
    r'^\s*[•●○◦▪▫‣⁃]\s*',           # Standard bullets
    r'^\s*[\-–—]\s+',                # Dashes as bullets
    r'^\s*\d+\.\s+',                 # Numbered lists
    r'^\s*[a-z]\)\s+',               # Letter lists (a) b) c)
    r'^\s*[ivxIVX]+\.\s+',           # Roman numerals
]


def clean_text(text: Optional[str], preserve_newlines: bool = False) -> str:
    """Clean and normalize extracted text.
    
    Args:
        text: Raw text from PDF extraction
        preserve_newlines: If True, keeps newlines; otherwise converts to spaces
        
    Returns:
        Cleaned text string
    """
    if not text:
        return ""
    
    text = str(text)
    
    # Remove PDF artifacts
    for artifact in PDF_ARTIFACTS:
        text = text.replace(artifact, '')
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Handle newlines
    if preserve_newlines:
        # Normalize different newline types
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Remove multiple consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
    else:
        # Convert newlines to spaces
        text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)  # Trim lines
    
    # Remove leading/trailing whitespace from entire string
    text = text.strip()
    
    return text


def remove_bullets(text: str) -> str:
    """Remove bullet characters and list markers from text.
    
    Args:
        text: Text potentially containing bullet markers
        
    Returns:
        Text with bullets removed
    """
    if not text:
        return ""
    
    # Remove bullet patterns
    for pattern in BULLET_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    
    return text.strip()


def split_on_bullets(text: str) -> list[str]:
    """Split text into items based on bullet markers.
    
    Args:
        text: Text with bullet-separated items
        
    Returns:
        List of individual items
    """
    if not text:
        return []
    
    # First try to split by newlines with bullets
    bullet_pattern = r'[\n\r]+\s*[•●○◦▪▫‣⁃\-–—]\s*'
    items = re.split(bullet_pattern, text)
    
    # If no bullet splits, try semicolons and commas for short lists
    if len(items) <= 1:
        # Only split on these if items are reasonably short (likely a list)
        if ';' in text:
            items = text.split(';')
        elif ',' in text and text.count(',') >= 2:
            # Only split commas if there are multiple and average segment is short
            potential_items = text.split(',')
            avg_len = sum(len(p) for p in potential_items) / len(potential_items)
            if avg_len < 100:  # Short segments likely mean it's a list
                items = potential_items
    
    # Clean each item
    result = []
    for item in items:
        cleaned = clean_text(remove_bullets(item))
        if cleaned and len(cleaned) >= 3:  # Minimum meaningful length
            result.append(cleaned)
    
    return result


def normalize_field_value(text: Optional[str]) -> str:
    """Normalize a single field value.
    
    Args:
        text: Raw field value
        
    Returns:
        Normalized value
    """
    if not text:
        return ""
    
    text = clean_text(text)
    text = remove_bullets(text)
    
    # Remove common PDF table artifacts
    text = re.sub(r'\s*\|\s*', ' ', text)  # Pipe characters
    text = re.sub(r'\s*\[\s*\]\s*', '', text)  # Empty brackets
    
    return text.strip()


def extract_list_items(text: Optional[str], min_length: int = 5, max_items: int = 50) -> list[str]:
    """Extract list items from text that may contain bullet points or separators.
    
    Args:
        text: Text containing list items
        min_length: Minimum character length for valid items
        max_items: Maximum number of items to return
        
    Returns:
        List of extracted items
    """
    if not text:
        return []
    
    # Split on bullets first
    items = split_on_bullets(text)
    
    # If no splits, return as single item
    if not items:
        cleaned = normalize_field_value(text)
        if cleaned and len(cleaned) >= min_length:
            return [cleaned]
        return []
    
    # Filter and clean items
    result = []
    seen = set()
    
    for item in items:
        normalized = normalize_field_value(item)
        
        # Skip if too short or already seen
        if len(normalized) < min_length:
            continue
        
        # Create normalized key for deduplication
        dedup_key = normalized.lower().strip()
        if dedup_key in seen:
            continue
        
        seen.add(dedup_key)
        result.append(normalized)
        
        if len(result) >= max_items:
            break
    
    return result


def is_garbage_text(text: str) -> bool:
    """Check if text is likely garbage/artifacts rather than real content.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be garbage
    """
    if not text:
        return True
    
    # Too short
    if len(text) < 3:
        return True
    
    # Mostly non-alphanumeric
    alpha_ratio = sum(1 for c in text if c.isalnum()) / len(text)
    if alpha_ratio < 0.3:
        return True
    
    # Common garbage patterns
    garbage_patterns = [
        r'^[\d\s\.\-]+$',           # Only numbers and punctuation
        r'^[_\-\s]+$',              # Only underscores/dashes
        r'^page\s*\d+$',            # Page numbers
        r'^\d+\s*$',                # Just a number
        r'^[A-Z]\s*$',              # Single letter
    ]
    
    for pattern in garbage_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False
