import re
import json
import sqlite3
import sys
import pdfplumber
from pathlib import Path

PDF_DIR = Path("cbc pdfs")
DB_PATH = Path("curriculum.db")
OUT_JSON = Path("curriculum_parsed.json")


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS curriculum (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            subject             TEXT NOT NULL,
            grade               TEXT NOT NULL,
            strand              TEXT,
            strand_number       TEXT,
            substrand           TEXT,
            substrand_number    TEXT,
            num_lessons         TEXT,
            learning_outcomes   TEXT,   -- JSON array
            key_inquiry         TEXT,   -- JSON array
            activities          TEXT,   -- JSON array
            competencies        TEXT,   -- JSON array
            values_             TEXT,   -- JSON array
            pcis                TEXT,   -- JSON array
            assessment          TEXT,   -- JSON array
            link_subjects       TEXT,   -- JSON array
            raw_text            TEXT
        )
    """)
    # Index for fast lookup
    c.execute("CREATE INDEX IF NOT EXISTS idx_subject_grade ON curriculum(subject, grade)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_strand ON curriculum(strand)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_substrand ON curriculum(substrand)")
    conn.commit()
    conn.close()


def insert_substrand(record: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO curriculum (
            subject, grade, strand, strand_number, substrand, substrand_number,
            num_lessons, learning_outcomes, key_inquiry, activities,
            competencies, values_, pcis, assessment, link_subjects, raw_text
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        record.get("subject", ""),
        record.get("grade", ""),
        record.get("strand", ""),
        record.get("strand_number", ""),
        record.get("substrand", ""),
        record.get("substrand_number", ""),
        record.get("num_lessons", ""),
        json.dumps(record.get("learning_outcomes", [])),
        json.dumps(record.get("key_inquiry", [])),
        json.dumps(record.get("activities", [])),
        json.dumps(record.get("competencies", [])),
        json.dumps(record.get("values_", [])),
        json.dumps(record.get("pcis", [])),
        json.dumps(record.get("assessment", [])),
        json.dumps(record.get("link_subjects", [])),
        record.get("raw_text", ""),
    ))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# TEXT HELPERS
# ─────────────────────────────────────────────

def clean(text) -> str:
    if not text:
        return ""
    text = str(text).strip()
    # Remove newlines and normalize whitespace
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_items(text) -> list:
    """Split bullet/numbered list text into clean items."""
    if not text:
        return []
    text = str(text)
    
    # Remove common CBC prefixes
    text = re.sub(r'^By\s+the\s+end\s+of\s+the\s+sub[\-\s]?strand.*?:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^The\s+learner\s+should\s+be\s+able\s+to:', '', text, flags=re.IGNORECASE)
    
    # Replace bullet characters with standard delimiter
    text = text.replace('\uf0b7', '|||')  # PDF bullet character
    text = re.sub(r'[•\-\*]\s+', '|||', text)
    
    # Split on lettered lists a), b), c) - these can appear inline without newlines
    # Pattern matches: ", a)" or " a)" or newline+a) at word boundaries
    text = re.sub(r'(?:,\s*|\s+)([a-z])\)\s+', r'|||', text)
    
    # Split on numbered lists: 1. or 1) or i. ii. iii.
    text = re.sub(r'(?:,\s*|\s+)(\d+)[\.\)]\s+', r'|||', text)
    text = re.sub(r'(?:,\s*|\s+)(i{1,3}|iv|v|vi{0,3})[\.\)]\s+', r'|||', text, flags=re.IGNORECASE)
    
    # Split on double newlines
    text = re.sub(r'\n{2,}', '|||', text)
    
    # Now split by delimiter
    items = text.split('|||')
    
    result = []
    for item in items:
        item = clean(item)
        # Remove leading bullet/letter/number characters that might remain
        item = re.sub(r'^[•\-\*\d\.\)]+\s*', '', item)
        item = re.sub(r'^[a-z]\)\s*', '', item)
        item = re.sub(r'^(i{1,3}|iv|v|vi{0,3})[\.\)]\s*', '', item, flags=re.IGNORECASE)
        # Remove trailing commas/periods
        item = item.rstrip(',.;')
        if len(item) > 8:
            result.append(item)
    return result[:30]


def extract_lesson_count(text: str) -> str:
    """Extract number of lessons from text like '(9 lessons)'."""
    if not text:
        return ""
    m = re.search(r'\((\d+)\s*lessons?\)', text, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


# Known CBC competencies, values, and PCIs
KNOWN_COMPETENCIES = [
    'critical thinking', 'creativity', 'communication', 'collaboration',
    'problem solving', 'self-efficacy', 'digital literacy', 'learning to learn',
    'citizenship', 'imagination', 'curiosity'
]

KNOWN_VALUES = [
    'unity', 'peace', 'love', 'respect', 'responsibility', 'honesty',
    'patriotism', 'social justice', 'integrity', 'care', 'compassion',
    'cooperation', 'tolerance', 'humility', 'sharing', 'national unity'
]

KNOWN_PCIS = [
    'environmental', 'citizenship', 'health', 'life skills', 'gender',
    'human rights', 'disaster risk', 'financial literacy', 'safety',
    'peace education', 'drug abuse', 'child abuse', 'terrorism',
    'road safety', 'food security', 'animal welfare'
]


def extract_embedded_fields(text: str) -> dict:
    """
    Extract competencies, values, and PCIs embedded in learning experiences text.
    CBC documents often include these at the end of activities like:
    "critical thinking skills as learners..., value of unity as they work together,
    environmental awareness as learners explore..."
    """
    if not text:
        return {'competencies': [], 'values_': [], 'pcis': []}
    
    text_lower = text.lower()
    
    competencies = []
    values = []
    pcis = []
    
    # Extract competencies
    for comp in KNOWN_COMPETENCIES:
        if comp in text_lower:
            competencies.append(comp.title())
    
    # Extract values - look for patterns like "value of X" or just the value name
    for val in KNOWN_VALUES:
        if f'value of {val}' in text_lower or f'values of {val}' in text_lower or f'{val} as' in text_lower:
            values.append(val.title())
    
    # Extract PCIs - look for "awareness", "education" patterns and known terms
    for pci in KNOWN_PCIS:
        if pci in text_lower:
            pcis.append(pci.title())
    
    return {
        'competencies': list(set(competencies))[:10],
        'values_': list(set(values))[:10],
        'pcis': list(set(pcis))[:10]
    }


def parse_filename(stem: str):
    """Extract subject and grade from filename like 'English_Grade7'."""
    name = str(stem)
    # Remove .pdf if still present
    name = re.sub(r'\.pdf$', '', name, flags=re.IGNORECASE)
    
    grade_match = re.search(r'Grade[_\s]?(\w+)', name, re.IGNORECASE)
    grade = f"Grade {grade_match.group(1)}" if grade_match else "Unknown"
    subject = re.sub(r'[_\s]?Grade.*', '', name, flags=re.IGNORECASE)
    subject = subject.replace('_', ' ').strip()
    return subject, grade


# ─────────────────────────────────────────────
# HEADER NORMALIZER
# ─────────────────────────────────────────────

# Order matters - more specific patterns first
HEADER_PATTERNS = [
    # Kiswahili headers (must come before English to match "Mada Ndogo" before "Mada")
    ('substrand', [r'\bmada ndogo\b', r'\bsub[\-\s]?strand', r'\bsub strand']),
    ('strand', [r'\bmada\b', r'^strand$', r'\bstrand\b']),
    # Kiswahili: "Matokeo Maalum Yanayotarajiwa" = Learning Outcomes
    ('learning_outcomes', [r'matokeo maalum', r'matokeo ya ujifunzaji', r'specific learning', r'learning outcomes?', r'\bslo\b']),
    # Kiswahili: "Maswali Dadisi" or "Swali Dadisi" = Key Inquiry
    ('key_inquiry', [r'maswali dadisi', r'swali dadisi', r'maswali ya uchunguzi', r'key inquiry', r'inquiry question', r'\bkiq\b']),
    # Kiswahili: "Shughuli za Ujifunzaji" = Activities  
    ('activities', [r'shughuli za ujifunzaji', r'suggested learning experience', r'learning experience', r'\bsle\b', r'activities']),
    # English headers
    ('num_lessons', [r'idadi ya vipindi', r'\bno\.', r'no of lessons', r'lessons', r'number of lessons']),
    ('competencies', [r'core competenc', r'\bcompetencies']),
    ('values_', [r'\bvalues\b', r'national values']),
    ('pcis', [r'pertinent', r'contemporary', r'\bpci\b']),
    ('assessment', [r'assessment']),
    ('link_subjects', [r'link to', r'other subjects', r'learning areas']),
]


def normalize_header(header: str) -> str:
    if not header:
        return ""
    # Remove newlines and normalize whitespace
    h = str(header).replace('\n', ' ').strip().lower()
    h = re.sub(r'\s+', ' ', h)
    
    # Check patterns in order
    for canonical, patterns in HEADER_PATTERNS:
        for patt in patterns:
            if re.search(patt, h, re.IGNORECASE):
                return canonical
    
    return h.replace(' ', '_')


# ─────────────────────────────────────────────
# STRAND NUMBER DETECTOR
# ─────────────────────────────────────────────

def extract_strand_number(text: str):
    """Extract strand number like '1.0', '2.3' from text."""
    if not text:
        return "", ""
    m = re.match(r'^(\d+\.\d+)\s*(.*)', str(text).strip())
    if m:
        return m.group(1), m.group(2).strip()
    return "", str(text).strip()


# ─────────────────────────────────────────────
# CORE PARSER — ONE ROW PER SUB-STRAND
# ─────────────────────────────────────────────

# Known problematic PDFs that cause pdfplumber to hang or crash
SKIP_PDFS = set()  # No longer skipping Kiswahili - now supported

def parse_pdf(pdf_path: Path, subject: str, grade: str, debug: bool = False) -> list:
    """
    Parse a CBC curriculum PDF.
    Returns a list of dicts — one dict per sub-strand.
    """
    # Skip known problematic PDFs
    if pdf_path.name in SKIP_PDFS:
        return []
    
    records = []
    page_errors = 0
    max_page_errors = 5  # Skip PDF after this many page errors

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            # Start from page 8 (index 7) - curriculum tables appear around pages 10-14
            for page_idx in range(min(7, total_pages), total_pages):
                if page_errors >= max_page_errors:
                    if debug:
                        print(f"    [Skipping rest of PDF - too many errors]")
                    break
                    
                try:
                    page = pdf.pages[page_idx]
                except (Exception, KeyboardInterrupt) as e:
                    page_errors += 1
                    if debug:
                        print(f"    [Page {page_idx} load error: {e}]")
                    continue
                
                try:
                    tables = page.extract_tables()
                except (Exception, KeyboardInterrupt) as page_err:
                    page_errors += 1
                    if debug:
                        print(f"    [Page {page_idx} extract error ({page_errors}/{max_page_errors}): {page_err}]")
                    continue

                if not tables:
                    continue

                for table in tables:
                    try:
                        if not table or len(table) < 2:
                            continue

                        # Normalize headers
                        raw_headers = table[0]
                        headers = [normalize_header(h) for h in raw_headers]

                        if debug:
                            print(f"    Page {page_idx} headers: {raw_headers}")
                            print(f"    Normalized: {headers}")

                        # Skip tables with no useful headers
                        useful = {'strand', 'substrand', 'learning_outcomes',
                                  'key_inquiry', 'activities'}
                        if not useful.intersection(set(headers)):
                            continue

                        current_strand = ""
                        current_strand_num = ""

                        for raw_row in table[1:]:
                            # Pad row to header length
                            row = list(raw_row) + [''] * (len(headers) - len(raw_row))

                            row_dict = {}
                            for i, h in enumerate(headers):
                                if h:
                                    row_dict[h] = clean(row[i])

                            # Skip completely empty rows
                            if not any(row_dict.values()):
                                continue

                            # ── Strand carry-forward ──────────────────────────
                            # CBC tables often have strand in first column only
                            # on the first row, then blank for sub-rows
                            if row_dict.get('strand'):
                                strand_num, strand_name = extract_strand_number(
                                    row_dict['strand'])
                                current_strand = strand_name or row_dict['strand']
                                current_strand_num = strand_num

                            substrand_raw = row_dict.get('substrand', '')
                            if not substrand_raw:
                                continue  # Skip rows with no sub-strand

                            # Extract lesson count from substrand (e.g., "(9 lessons)")
                            num_lessons = extract_lesson_count(substrand_raw) or row_dict.get('num_lessons', '')
                            
                            # Remove lesson count from substrand text
                            substrand_clean = re.sub(r'\s*\(\d+\s*lessons?\)', '', substrand_raw, flags=re.IGNORECASE)
                            
                            substrand_num, substrand_name = extract_strand_number(substrand_clean)

                            # ── Build one clean record per sub-strand ─────────
                            
                            # Get raw activities text for embedded field extraction
                            activities_raw = row_dict.get('activities', '')
                            
                            # Extract embedded competencies, values, and PCIs from activities text
                            embedded = extract_embedded_fields(activities_raw)
                            
                            # Get explicit values from columns if present
                            explicit_competencies = split_items(row_dict.get('competencies', ''))
                            explicit_values = split_items(row_dict.get('values_', ''))
                            explicit_pcis = split_items(row_dict.get('pcis', ''))
                            
                            # Merge explicit and embedded, prioritize explicit
                            all_competencies = explicit_competencies + [c for c in embedded['competencies'] if c not in explicit_competencies]
                            all_values = explicit_values + [v for v in embedded['values_'] if v not in explicit_values]
                            all_pcis = explicit_pcis + [p for p in embedded['pcis'] if p not in explicit_pcis]
                            
                            record = {
                                'subject':           subject,
                                'grade':             grade,
                                'strand':            current_strand,
                                'strand_number':     current_strand_num,
                                'substrand':         substrand_name or substrand_clean,
                                'substrand_number':  substrand_num,
                                'num_lessons':       num_lessons,
                                'learning_outcomes': split_items(row_dict.get('learning_outcomes', '')),
                                'key_inquiry':       split_items(row_dict.get('key_inquiry', '')),
                                'activities':        split_items(activities_raw),
                                'competencies':      all_competencies[:10],
                                'values_':           all_values[:10],
                                'pcis':              all_pcis[:10],
                                'assessment':        split_items(row_dict.get('assessment', '')),
                                'link_subjects':     split_items(row_dict.get('link_subjects', '')),
                                'raw_text':          str(raw_row),
                            }

                            # Only save if it has at least SLOs or activities
                            if record['learning_outcomes'] or record['activities']:
                                records.append(record)
                            
                    except Exception as table_err:
                        if debug:
                            print(f"    [Table error on page {page_idx}: {table_err}]")
                        continue

    except Exception as e:
        print(f"  [ERROR] {pdf_path.name}: {e}")

    return records


# ─────────────────────────────────────────────
# QUERY HELPER (used by your app at runtime)
# ─────────────────────────────────────────────

def get_curriculum(subject: str, grade: str, substrand: str = "") -> list:
    """
    Fetch curriculum records from DB for injection into Claude prompt.
    Call this BEFORE every Claude API call.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if substrand:
        c.execute("""
            SELECT * FROM curriculum
            WHERE subject LIKE ? AND grade LIKE ? AND substrand LIKE ?
            LIMIT 3
        """, (f"%{subject}%", f"%{grade}%", f"%{substrand}%"))
    else:
        c.execute("""
            SELECT * FROM curriculum
            WHERE subject LIKE ? AND grade LIKE ?
            LIMIT 10
        """, (f"%{subject}%", f"%{grade}%"))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def format_for_prompt(records: list) -> str:
    """
    Format DB records into clean text for Claude system prompt injection.
    """
    if not records:
        return "No curriculum data found. Use general CBC guidelines."

    parts = []
    for r in records:
        slos = json.loads(r.get('learning_outcomes', '[]'))
        kiqs = json.loads(r.get('key_inquiry', '[]'))
        acts = json.loads(r.get('activities', '[]'))
        vals = json.loads(r.get('values_', '[]'))
        pcis = json.loads(r.get('pcis', '[]'))

        part = f"""
STRAND: {r['strand_number']} {r['strand']}
SUB-STRAND: {r['substrand_number']} {r['substrand']}
LESSONS: {r['num_lessons']}

SPECIFIC LEARNING OUTCOMES:
{chr(10).join(f'- {s}' for s in slos)}

KEY INQUIRY QUESTIONS:
{chr(10).join(f'- {q}' for q in kiqs)}

SUGGESTED LEARNING EXPERIENCES:
{chr(10).join(f'- {a}' for a in acts)}

VALUES: {', '.join(vals)}
PCIs: {', '.join(pcis)}
"""
        parts.append(part.strip())

    return "\n\n" + "="*50 + "\n\n".join(parts)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if not PDF_DIR.exists():
        print(f"[ERROR] PDF directory not found: {PDF_DIR}")
        return

    debug = "--debug" in sys.argv

    print("Initializing database...")
    init_db()

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs\n")

    all_records = []
    total_substrands = 0

    for pdf in pdfs:
        subject, grade = parse_filename(pdf.stem)
        print(f"Parsing: {pdf.name} -> {subject} {grade}", end=" ")

        records = parse_pdf(pdf, subject, grade, debug=debug)

        for r in records:
            insert_substrand(r)

        total_substrands += len(records)
        status = "[OK]" if records else "[WARN - no sub-strands found]"
        print(f"{status} ({len(records)} sub-strands)")

        all_records.extend(records)

    # Save JSON backup
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Total PDFs parsed:     {len(pdfs)}")
    print(f"Total sub-strands:     {total_substrands}")
    print(f"Database:              {DB_PATH}")
    print(f"JSON backup:           {OUT_JSON}")
    print(f"\nRun diagnostic:")
    print(f"  python cbc_parser.py --check")


def diagnostic():
    """Check what's in the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM curriculum")
    total = c.fetchone()[0]
    print(f"\nTotal rows: {total}")

    c.execute("""
        SELECT subject, grade, COUNT(*) as count 
        FROM curriculum 
        GROUP BY subject, grade 
        ORDER BY subject, grade
    """)
    print("\nSub-strands per subject/grade:")
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]}: {row[2]} sub-strands")

    c.execute("SELECT subject, grade, strand, substrand FROM curriculum LIMIT 5")
    print("\nSample records:")
    for row in c.fetchall():
        print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]}")

    conn.close()


if __name__ == "__main__":
    if "--check" in sys.argv:
        diagnostic()
    else:
        main()
