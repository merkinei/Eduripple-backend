"""Improved CBC PDF parser using pdfplumber table detection."""

import pdfplumber
import json
import re
from pathlib import Path
from curriculum_db import init_curriculum_db, insert_curriculum

PDF_DIR = Path("cbc pdfs")
OUT_TABLE = "cbc_parsed.json"  # Keep for backward compat

def extract_tables_from_pdf(pdf_path):
    """Extract structured tables from PDF."""
    tables_data = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Scan pages 12-60 for curriculum tables (covers most content, faster)
            for page_idx in range(11, min(len(pdf.pages), 60)):
                page = pdf.pages[page_idx]
                tables = page.extract_tables()
                
                if tables:
                    for table in tables:
                        # Convert table (list of lists) to structured format
                        if len(table) > 1:
                            headers = table[0]
                            rows = table[1:]
                            
                            for row in rows:
                                # Create dict with headers as keys
                                row_dict = {}
                                for i, header in enumerate(headers):
                                    if i < len(row):
                                        row_dict[normalize_header(header)] = row[i]
                                
                                if any(row_dict.values()):  # Skip empty rows
                                    tables_data.append(row_dict)
    except Exception as e:
        print(f"Error extracting tables from {pdf_path}: {e}")
    
    return tables_data


def normalize_header(header):
    """Normalize table header names."""
    if not header:
        return ""
    h = str(header).strip().lower()
    # Map common header variations
    mappings = {
        'strand': ['strand', 'strands'],
        'substrand': ['sub-strand', 'sub strand', 'substrand', 'sub-strands'],
        'learning_outcomes': ['specific learning outcomes', 'learning outcomes', 'slo', 'outcomes'],
        'key_inquiry': ['key inquiry questions', 'inquiry questions', 'kiq', 'key inquiry'],
        'learning_experiences': ['suggested learning experiences', 'learning experiences', 'sle'],
        'competencies': ['core competencies', 'competencies'],
        'values': ['values', 'national values'],
    }
    
    for canonical, variants in mappings.items():
        if any(v in h for v in variants):
            return canonical
    
    return h


def parse_table_row(row_dict):
    """Parse a curriculum table row into structured data."""
    data = {
        'strand': clean_text(row_dict.get('strand', '')),
        'substrand': clean_text(row_dict.get('substrand', '')),
        'learning_outcomes': split_field(row_dict.get('learning_outcomes', '')),
        'key_inquiry_questions': split_field(row_dict.get('key_inquiry', '')),
        'suggested_learning_experiences': split_field(row_dict.get('learning_experiences', '')),
        'core_competencies': split_field(row_dict.get('competencies', '')),
        'values': split_field(row_dict.get('values', '')),
    }
    return data


def clean_text(text):
    """Clean extracted text."""
    if not text:
        return ""
    text = str(text).strip()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove common artifacts
    text = text.replace('\n', ' ')
    return text


def split_field(text):
    """Split comma/semicolon separated values into list."""
    if not text:
        return []
    
    text = str(text).strip()
    # Split by common separators
    items = re.split(r'[,;]\s*|\n\s*[•\-]\s*', text)
    
    # Clean and filter each item
    result = []
    for item in items:
        item = clean_text(item)
        if len(item) > 5:  # Minimum length
            result.append(item)
    
    return result[:15]  # Limit to 15 items


def parse_pdf(pdf_path):
    """Parse a single PDF using table extraction."""
    subject, grade = parse_subject_grade(pdf_path.stem)
    
    # Extract tables
    tables = extract_tables_from_pdf(pdf_path)
    
    if not tables:
        print(f"  [WARN] No tables found in {pdf_path.name}")
        return {
            'subject': subject,
            'grade': grade,
            'strand': '',
            'substrand': '',
            'learning_outcomes': [],
            'key_inquiry_questions': [],
            'suggested_learning_experiences': [],
            'core_competencies': [],
            'values': [],
        }
    
    # Merge all table rows
    merged = {
        'strand': '',
        'substrand': '',
        'learning_outcomes': [],
        'key_inquiry_questions': [],
        'suggested_learning_experiences': [],
        'core_competencies': [],
        'values': [],
    }
    
    for row in tables:
        parsed = parse_table_row(row)
        
        # Update merged data
        if not merged['strand'] and parsed['strand']:
            merged['strand'] = parsed['strand']
        if not merged['substrand'] and parsed['substrand']:
            merged['substrand'] = parsed['substrand']
        
        # Extend lists (avoid duplicates)
        for field in ['learning_outcomes', 'key_inquiry_questions', 
                      'suggested_learning_experiences', 'core_competencies', 'values']:
            for item in parsed[field]:
                if item not in merged[field]:
                    merged[field].append(item)
    
    # Trim to reasonable sizes
    for field in ['learning_outcomes', 'key_inquiry_questions',
                  'suggested_learning_experiences', 'core_competencies', 'values']:
        merged[field] = merged[field][:15]
    
    merged['subject'] = subject
    merged['grade'] = grade
    
    return merged


def parse_subject_grade(filename):
    """Extract subject and grade from PDF filename."""
    name = str(filename).replace('.pdf', '')
    
    # Look for grade pattern (Grade_N or _NP or _N)
    grade_match = re.search(r'Grade[_\s]?(\d+|[A-Z]P)', name, re.IGNORECASE)
    grade = f"Grade {grade_match.group(1)}" if grade_match else "Unknown"
    
    # Subject is everything before grade
    subject = re.sub(r'Grade.*', '', name, flags=re.IGNORECASE).strip('_').strip()
    
    return subject, grade


def main():
    """Parse all PDFs and populate database."""
    if not PDF_DIR.exists():
        print(f"PDF directory not found: {PDF_DIR}")
        return
    
    print("Initializing curriculum database...")
    init_curriculum_db()
    
    print(f"Parsing PDFs from {PDF_DIR}...")
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    
    parsed_all = {}
    success_count = 0
    
    for pdf in pdfs:
        try:
            print(f"  Parsing {pdf.name}...", end='')
            data = parse_pdf(pdf)
            parsed_all[pdf.stem] = data
            
            # Insert into database
            insert_curriculum(data['subject'], data['grade'], data)
            
            # Count fields populated
            fields_count = sum([
                len(data.get('learning_outcomes', [])),
                len(data.get('key_inquiry_questions', [])),
                len(data.get('suggested_learning_experiences', [])),
            ])
            
            status = "[OK]" if fields_count >= 5 else "[WARN]"
            print(f" {status} ({fields_count} fields)")
            success_count += 1
            
        except Exception as e:
            print(f" [ERROR] {e}")
    
    # Save JSON backup
    with open(OUT_TABLE, 'w', encoding='utf-8') as f:
        json.dump(parsed_all, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Parsed {success_count}/{len(pdfs)} PDFs")
    print(f"[OK] Database saved to curriculum.db")
    print(f"[OK] JSON backup saved to {OUT_TABLE}")


if __name__ == "__main__":
    main()
