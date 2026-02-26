import os
import json
import logging
import traceback
import requests
import re
import tempfile
import html
import subprocess
import sys
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory, redirect, url_for, flash, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from manual_curriculum_data import enhance_cbc_data
from admin_curriculum import admin_bp
from curriculum_db import get_curriculum, init_curriculum_db
from lesson_generator import generate_lesson_plan, generate_scheme_of_work, generate_rubric
from gemini_integration import (
    is_gemini_available,
    is_openrouter_available,
    get_active_ai_name,
    get_ai_services_status,
    generate_activities,
    generate_questions,
    generate_outcomes,
    chat as gemini_chat
)
from media_generator import (
    AudioGenerator,
    ElevenLabsAudioGenerator,
    FlashcardGenerator,
    ContentGenerator,
    VideoGenerator,
    generate_reading_passage_audio,
    cleanup_old_media
)

# Lazy imports for heavy libraries
DOCX_AVAILABLE = False
FITZ_AVAILABLE = False
Document = None
fitz = None
HTML = None

def _lazy_import_docx():
    global Document, DOCX_AVAILABLE
    if DOCX_AVAILABLE:
        return
    try:
        from docx import Document as DocxDocument
        Document = DocxDocument
        DOCX_AVAILABLE = True
    except ImportError:
        DOCX_AVAILABLE = False

def _lazy_import_fitz():
    global fitz, FITZ_AVAILABLE
    if FITZ_AVAILABLE or fitz is not None:
        return
    try:
        import fitz as fitz_module
        fitz = fitz_module
        FITZ_AVAILABLE = True
    except Exception as e:
        logging.warning(f"PyMuPDF (fitz) not available: {str(e)}")
        FITZ_AVAILABLE = False

def _lazy_import_weasyprint():
    global HTML
    if HTML is not None:
        return
    try:
        from weasyprint import HTML as WeasyHTML
        HTML = WeasyHTML
    except ImportError as e:
        logging.warning(f"WeasyPrint not available: {str(e)}")

# Load environment variables
load_dotenv()

# Import database and monitoring utilities
try:
    from db_utils import DatabasePool, DatabaseBackup, QueryOptimizer
    from background_tasks import initialize_maintenance_tasks
    DB_UTILS_AVAILABLE = True
except ImportError:
    DB_UTILS_AVAILABLE = False
    logging.warning("Database utilities not available")

# --- Flask App Initialization ---
app = Flask(__name__)

# Load configuration from config factory
from config import get_config
app_config = get_config()
app.config.from_object(app_config)

# Override with explicit env settings
app.secret_key = os.getenv("FLASK_SECRET_KEY", "eduripple-dev-secret-CHANGE-ME")
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Warn if using default secret key in production
if os.getenv("FLASK_ENV") == "production" and app.secret_key == "eduripple-dev-secret-CHANGE-ME":
    logging.critical("SECURITY WARNING: Using default secret key in production! Set FLASK_SECRET_KEY.")

# CORS: Restrict origins in production
_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
CORS(app, origins=_allowed_origins, supports_credentials=True)

# Initialize rate limiter
_rate_storage = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=_rate_storage
)

# Initialize cache
cache = Cache(app, config={
    'CACHE_TYPE': os.getenv('CACHE_TYPE', 'simple'),
    'CACHE_DEFAULT_TIMEOUT': int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300'))
})

# Register admin blueprint
app.register_blueprint(admin_bp)

# --- Security Headers ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if os.getenv("FLASK_ENV") == "production":
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

RESOURCE_DIR = "resources"
os.makedirs(RESOURCE_DIR, exist_ok=True)

# DATA_DIR env var points to a persistent volume on Railway.
# Defaults to app.root_path for local development.
DATA_DIR = os.getenv("DATA_DIR", app.root_path)
os.makedirs(DATA_DIR, exist_ok=True)
TEACHERS_DB = os.path.join(DATA_DIR, "teachers.db")

# Initialize database pool and background tasks
if DB_UTILS_AVAILABLE:
    try:
        db_pool = DatabasePool(TEACHERS_DB, pool_size=5)
        db_scheduler, db_utilities = initialize_maintenance_tasks(db_pool, TEACHERS_DB)
        app.logger.info("Database utilities and background tasks initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize database utilities: {str(e)}")
        db_pool = None
        db_scheduler = None
else:
    db_pool = None
    db_scheduler = None


def init_teachers_db():
    conn = sqlite3.connect(TEACHERS_DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                school TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                subject_area TEXT,
                grade_level TEXT,
                years_experience INTEGER,
                bio TEXT
            )
            """
        )
        
        # Add new columns if they don't exist (for existing databases)
        cursor = conn.execute("PRAGMA table_info(teachers)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "subject_area" not in columns:
            conn.execute("ALTER TABLE teachers ADD COLUMN subject_area TEXT")
        if "grade_level" not in columns:
            conn.execute("ALTER TABLE teachers ADD COLUMN grade_level TEXT")
        if "years_experience" not in columns:
            conn.execute("ALTER TABLE teachers ADD COLUMN years_experience INTEGER")
        if "bio" not in columns:
            conn.execute("ALTER TABLE teachers ADD COLUMN bio TEXT")
            
        conn.commit()
    finally:
        conn.close()


def get_teacher_by_email(email):
    conn = sqlite3.connect(TEACHERS_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, full_name, email, school, password_hash, subject_area, grade_level, years_experience, bio FROM teachers WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_teacher(full_name, email, school, password, subject_area=None, grade_level=None, years_experience=None, bio=None):
    conn = sqlite3.connect(TEACHERS_DB)
    try:
        conn.execute(
            "INSERT INTO teachers (full_name, email, school, password_hash, created_at, subject_area, grade_level, years_experience, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                full_name.strip(),
                email.lower().strip(),
                (school or "").strip(),
                generate_password_hash(password),
                datetime.utcnow().isoformat(),
                (subject_area or "").strip(),
                (grade_level or "").strip(),
                years_experience or None,
                (bio or "").strip(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def login_required_json(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if not session.get("teacher_id"):
            return jsonify({"error": "Authentication required. Please sign in as a teacher."}), 401
        return route_fn(*args, **kwargs)

    return wrapper


def login_required_page(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if not session.get("teacher_id"):
            flash("Please sign in to continue.", "error")
            return redirect(url_for("teacher_signin"))
        return route_fn(*args, **kwargs)

    return wrapper


def is_valid_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """Check password strength and requirements."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not any(char.isupper() for char in password):
        errors.append("Password must contain at least one uppercase letter.")
    if not any(char.isdigit() for char in password):
        errors.append("Password must contain at least one number.")
    return errors


init_teachers_db()

@app.context_processor
def inject_global_template_vars():
    context = {
        "year": datetime.now().year,
        "app_version": "1.0.0",
        "is_teacher_authenticated": bool(session.get("teacher_id")),
        "teacher_name": session.get("teacher_name", ""),
        "teacher_email": session.get("teacher_email", ""),
        "teacher_school": "",
        "teacher_subject_area": "",
        "teacher_grade_level": "",
        "teacher_years_experience": "",
    }
    
    # Fetch full profile if teacher is authenticated
    if context["is_teacher_authenticated"]:
        teacher = get_teacher_by_email(context["teacher_email"])
        if teacher:
            context["teacher_school"] = teacher.get("school", "")
            context["teacher_subject_area"] = teacher.get("subject_area", "")
            context["teacher_grade_level"] = teacher.get("grade_level", "")
            context["teacher_years_experience"] = teacher.get("years_experience", "")
    
    return context
# --- CBC Competency Map ---
COMPETENCY_MAP = {
    "discuss|group work|present|talk": "Communication and Collaboration",
    "analyze|think|solve|inquiry|explore|interpret": "Critical Thinking and Problem Solving",
    "create|imagine|design|draw|model": "Imagination and Creativity",
    "reflect|value|self|responsibility|faith": "Self-Efficacy",
    "community|respect|citizen|values|help|share": "Citizenship",
    "learn to learn|curiosity|discover|growth": "Learning to Learn",
    "digital|ICT|video|online|projector": "Digital Literacy"
}

# --- Load CBC Curriculum PDFs into Memory ---
def extract_all_cbc_text_from_pdfs(directory="cbc_pdfs"):
    cbc_text_data = {}
    candidate_directories = [directory, "cbc pdfs", "cbc_pdfs", "cbc-pdfs"]
    resolved_directory = next((d for d in candidate_directories if os.path.exists(d)), None)

    if not resolved_directory:
        logging.error(f"Directory '{directory}' not found.")
        return cbc_text_data

    if resolved_directory != directory:
        logging.info(f"Using CBC PDFs from '{resolved_directory}'")

    _lazy_import_fitz()
    if not FITZ_AVAILABLE:
        logging.warning("PyMuPDF not available, skipping PDF extraction")
        return cbc_text_data
    
    for filename in os.listdir(resolved_directory):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(resolved_directory, filename)
            try:
                with open(filepath, "rb") as file:
                    doc = fitz.open(stream=file.read(), filetype="pdf")
                    text = "\n".join([page.get_text() for page in doc])
                    name_key = os.path.splitext(filename)[0]
                    cbc_text_data[name_key] = text.strip()
                    print(f"[OK] Extracted: {filename}")
            except Exception as e:
                print(f"[ERROR] Failed to extract {filename}: {e}")
    return cbc_text_data

cbc_curriculum_data = extract_all_cbc_text_from_pdfs()


def load_curriculum_from_db():
    """Load curriculum data from database instead of JSON file."""
    try:
        # Initialize database
        init_curriculum_db()
        # Get all curriculum entries from database
        curriculum_list = get_curriculum()
        # Convert to dict format for backward compatibility
        cbc_data = {}
        for entry in curriculum_list:
            key = f"{entry['subject']}_{entry['grade']}"
            cbc_data[key] = {
                'subject': entry['subject'],
                'grade': entry['grade'],
                'strand': entry['strand'],
                'substrand': entry['substrand'],
                'learning_outcomes': entry['learning_outcomes'],
                'key_inquiry_questions': entry['key_inquiry_questions'],
                'suggested_learning_experiences': entry['suggested_learning_experiences'],
                'core_competencies': entry['core_competencies'],
                'values': entry['values'],
            }
        app.logger.info(f"Loaded {len(cbc_data)} curriculum entries from database")
        return cbc_data
    except Exception as exc:
        app.logger.error(f"Could not load curriculum from database: {exc}")
        return {}


# Load curriculum from database
cbc_parsed_data = load_curriculum_from_db()
# Apply manual enhancements for high-priority subjects if any
if cbc_parsed_data:
    cbc_parsed_data = enhance_cbc_data(cbc_parsed_data)

# --- Classify Prompt Locally ---
def classify_intent(prompt):
    p = prompt.lower()

    explicit_resources_only = (
        "resources only" in p
        or "learning resources only" in p
        or p.startswith("resources:")
    )

    has_grade_subject_context = bool(
        re.search(r"grade\s*\d+", p)
        and re.search(
            r"english|kiswahili|mathematics|math|science|cre|ire|agriculture|nutrition|social studies|integrated science",
            p,
        )
    )

    if "scheme" in p or "scheme of work" in p:
        return "scheme_of_work"
    elif "lesson plan" in p:
        return "lesson_plan"
    elif "rubric" in p or "assessment" in p:
        return "assessment_rubric"
    elif "resource" in p or "materials" in p:
        return "resources"
    elif has_grade_subject_context and not explicit_resources_only:
        return "lesson_plan"
    else:
        return "general"

# --- Structured Logging ---
def log_request(method, endpoint, user_id=None, data=None):
    """Log API requests in structured format"""
    log_data = {
        "event": "api_request",
        "method": method,
        "endpoint": endpoint,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    if data:
        log_data["data_keys"] = list(data.keys()) if isinstance(data, dict) else str(type(data))
    app.logger.info(f"API Request: {json.dumps(log_data)}")

def log_response(method, endpoint, status_code, duration_ms=None, user_id=None):
    """Log API responses in structured format"""
    log_data = {
        "event": "api_response",
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "user_id": user_id,
        "duration_ms": duration_ms,
        "timestamp": datetime.utcnow().isoformat()
    }
    app.logger.info(f"API Response: {json.dumps(log_data)}")

def log_error(method, endpoint, error_msg, error_type=None, user_id=None):
    """Log API errors in structured format"""
    log_data = {
        "event": "api_error",
        "method": method,
        "endpoint": endpoint,
        "error": error_msg,
        "error_type": error_type,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    app.logger.error(f"API Error: {json.dumps(log_data)}")

# --- Input Validation ---
def validate_input(prompt, subject=None, grade=None, max_prompt_length=2000):
    """Validate API input parameters"""
    errors = []
    
    # Validate prompt
    if not prompt:
        errors.append("Prompt cannot be empty")
    elif len(str(prompt)) > max_prompt_length:
        errors.append(f"Prompt exceeds maximum length of {max_prompt_length} characters")
    
    # Validate subject
    valid_subjects = [
        'mathematics', 'math', 'english', 'kiswahili', 'science', 
        'integrated science', 'social studies', 'cre', 'ire',
        'creative arts', 'creative arts and sports', 'agriculture',
        'agriculture and nutrition', 'pre-technical studies'
    ]
    if subject:
        if subject.lower() not in valid_subjects:
            errors.append(f"Invalid subject. Valid subjects: {', '.join(valid_subjects)}")
    
    # Validate grade
    valid_grades = [f"Grade {i}" for i in range(1, 10)]
    if grade:
        if grade not in valid_grades:
            errors.append(f"Invalid grade. Valid grades: {', '.join(valid_grades)}")
    
    return {"valid": len(errors) == 0, "errors": errors}

# --- Subject/Grade Parser ---
def parse_subject_and_grade(prompt):
    grade_match = re.search(r"grade\s*\d+", prompt.lower())
    
    # Exact-match pattern for well-spelled subjects
    subject_pattern = (
        r"\b(agriculture\s+and\s+nutrition|integrated\s+science|social\s+studies|"
        r"creative\s+arts\s+and\s+sports|pre-?technical\s+studies|"
        r"english|kiswahili|mathematics|math|science|cre|ire)\b"
    )
    subject_match = re.search(subject_pattern, prompt.lower())

    subject_text = ""
    if subject_match:
        raw_subject = subject_match.group(1)
        if raw_subject == "math":
            raw_subject = "mathematics"
        subject_text = raw_subject.upper()
    else:
        # Fuzzy fallback: detect subjects even with typos
        subject_text = _fuzzy_match_subject(prompt)

    return grade_match.group(0).title() if grade_match else "", subject_text


def _fuzzy_match_subject(prompt):
    """Match subjects from prompt even when misspelled (e.g. 'agriculuture')."""
    lowered = prompt.lower()
    
    # Each tuple: (keywords that should appear near each other, canonical name)
    fuzzy_subjects = [
        (["agri", "nutr"], "AGRICULTURE AND NUTRITION"),
        (["integr", "sci"], "INTEGRATED SCIENCE"),
        (["social", "stud"], "SOCIAL STUDIES"),
        (["creat", "art"], "CREATIVE ARTS AND SPORTS"),
        (["pre", "tech"], "PRE-TECHNICAL STUDIES"),
        (["indigen", "lang"], "INDIGENOUS LANGUAGES"),
        (["kiswa"], "KISWAHILI"),
        (["math"], "MATHEMATICS"),
        (["engl"], "ENGLISH"),
    ]
    
    for keywords, canonical in fuzzy_subjects:
        if all(kw in lowered for kw in keywords):
            return canonical
    
    # Single-word subject detection (CRE, IRE, Science)
    single_subjects = {
        "cre": "CRE",
        "ire": "IRE",
        "science": "INTEGRATED SCIENCE",
    }
    for keyword, canonical in single_subjects.items():
        if re.search(r'\b' + keyword + r'\b', lowered):
            return canonical
    
    return ""


def parse_grade_number(prompt):
    match = re.search(r"grade\s*(\d+)", (prompt or "").lower())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def get_lesson_duration_minutes(prompt):
    grade_number = parse_grade_number(prompt)
    if grade_number is not None and grade_number <= 6:
        return 35
    return 40


def parse_term(prompt):
    lowered = prompt.lower()
    numeric = re.search(r"term\s*([1-3])", lowered)
    if numeric:
        return f"Term {numeric.group(1)}"

    word = re.search(r"term\s*(one|two|three)", lowered)
    if not word:
        return ""

    mapping = {
        "one": "Term 1",
        "two": "Term 2",
        "three": "Term 3"
    }
    return mapping.get(word.group(1), "")

# --- Preprocess Curriculum Content ---
def preprocess_curriculum_content(text):
    sections = []
    current = {"Strand": "", "Sub-strand": "", "Content": ""}
    for line in text.split('\n'):
        strand_match = re.match(r"^\s*Strand[:\-]?\s*(.+)", line, re.IGNORECASE)
        substrand_match = re.match(r"^\s*Sub[\-\s]?strand[:\-]?\s*(.+)", line, re.IGNORECASE)
        if strand_match:
            if current["Content"]:
                sections.append(current.copy())
                current["Content"] = ""
            current["Strand"] = strand_match.group(1).strip()
        elif substrand_match:
            if current["Content"]:
                sections.append(current.copy())
                current["Content"] = ""
            current["Sub-strand"] = substrand_match.group(1).strip()
        else:
            current["Content"] += line + "\n"
    if current["Content"]:
        sections.append(current.copy())
    return sections


def normalize_subject(subject_text):
    if not subject_text:
        return ""
    return re.sub(r"\s+", " ", subject_text.strip().lower())


def get_structured_info_from_parsed(prompt):
    empty = {
        "Strand": "",
        "Sub-strand": "",
        "Specific Learning Outcomes": [],
        "Key Inquiry Questions": [],
        "Core Competencies": [],
        "Values": [],
        "Suggested Learning Experiences": []
    }

    if not cbc_parsed_data:
        return empty

    grade_number = parse_grade_number(prompt)
    _, subject = parse_subject_and_grade(prompt)
    subject_norm = normalize_subject(subject)

    tokens = re.findall(r"[a-z]{4,}", (prompt or "").lower())
    stop_words = {
        "grade", "term", "lesson", "scheme", "work", "generate", "create", "plan", "rubric",
        "with", "from", "that", "this", "about", "subject"
    }
    keywords = [token for token in tokens if token not in stop_words]

    best_entry = None
    best_score = -1
    for _, entry in cbc_parsed_data.items():
        if not isinstance(entry, dict):
            continue

        score = 0
        entry_grade = entry.get("grade")
        entry_subject = normalize_subject(entry.get("subject", ""))

        if grade_number is not None and entry_grade == grade_number:
            score += 5
        if subject_norm and subject_norm in entry_subject:
            score += 5

        searchable = " ".join([
            entry.get("strand", ""),
            entry.get("substrand", ""),
            " ".join(entry.get("learning_outcomes", []) if isinstance(entry.get("learning_outcomes", []), list) else []),
            " ".join(entry.get("key_inquiry_questions", []) if isinstance(entry.get("key_inquiry_questions", []), list) else []),
        ]).lower()

        score += sum(1 for keyword in keywords[:8] if keyword in searchable)

        if score > best_score:
            best_score = score
            best_entry = entry

    if not best_entry or best_score <= 0:
        return empty

    return {
        "Strand": best_entry.get("strand", "") or "",
        "Sub-strand": best_entry.get("substrand", "") or "",
        "Specific Learning Outcomes": (best_entry.get("learning_outcomes", []) or [])[:6],
        "Key Inquiry Questions": (best_entry.get("key_inquiry_questions", []) or [])[:6],
        "Core Competencies": (best_entry.get("core_competencies", []) or [])[:6],
        "Values": (best_entry.get("values", []) or [])[:6],
        "Suggested Learning Experiences": (best_entry.get("suggested_learning_experiences", []) or [])[:10]
    }

# --- Extract Structured CBC Content ---
@cache.cached(timeout=3600, key_prefix='cbc_content_')
def find_relevant_cbc_content(prompt):
    structured_data = {
        "Strand": "",
        "Sub-strand": "",
        "Specific Learning Outcomes": [],
        "Key Inquiry Questions": [],
        "Core Competencies": [],
        "Values": [],
        "Suggested Learning Experiences": []
    }
    for filename, content in cbc_curriculum_data.items():
        sections = preprocess_curriculum_content(content)
        for section in sections:
            if prompt.lower() in section["Content"].lower() or prompt.lower() in section["Sub-strand"].lower():
                structured_data["Strand"] = section["Strand"]
                structured_data["Sub-strand"] = section["Sub-strand"]
                content = section["Content"]
                slo_match = re.findall(r"\d+\.\s+(.*?)\s*(?=\d+\.|$)", content)
                kiq_match = re.findall(r"Key Inquiry Questions?:\s*(.*?)\n", content, re.IGNORECASE)
                comp_match = re.findall(r"Core Competencies?:\s*(.*?)\n", content, re.IGNORECASE)
                val_match = re.findall(r"Values?:\s*(.*?)\n", content, re.IGNORECASE)
                exp_match = re.findall(r"Suggested Learning Experiences?:\s*(.*?)(?=\n[A-Z]|\n\n|$)", content, re.IGNORECASE | re.DOTALL)
                if slo_match: structured_data["Specific Learning Outcomes"] = [s.strip() for s in slo_match]
                if kiq_match: structured_data["Key Inquiry Questions"] = [k.strip() for k in kiq_match[0].split(",")]
                if comp_match: structured_data["Core Competencies"] = [c.strip() for c in comp_match[0].split(",")]
                if val_match: structured_data["Values"] = [v.strip() for v in val_match[0].split(",")]
                if exp_match:
                    # Extract individual learning experiences from the matched text
                    exp_text = exp_match[0]
                    experiences = re.findall(r"[•\-\*]\s+(.+?)(?=[•\-\*]|$)", exp_text, re.MULTILINE)
                    if experiences:
                        structured_data["Suggested Learning Experiences"] = [e.strip() for e in experiences if len(e.strip()) > 5]
                return structured_data

    parsed_fallback = get_structured_info_from_parsed(prompt)
    if (
        parsed_fallback.get("Strand")
        or parsed_fallback.get("Sub-strand")
        or parsed_fallback.get("Specific Learning Outcomes")
        or parsed_fallback.get("Key Inquiry Questions")
    ):
        if not parsed_fallback.get("Sub-strand"):
            on_match = re.search(r"\bon\s+([a-zA-Z\s\-]{3,60})", prompt, re.IGNORECASE)
            if on_match:
                parsed_fallback["Sub-strand"] = on_match.group(1).strip().title()
        return parsed_fallback

    return structured_data
# --- OpenRouter + YouTube Keys ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
# --- Generate Dynamic Core Competencies ---
def generate_dynamic_competencies(text):
    detected = set()
    text_lower = text.lower()
    for keywords, competency in COMPETENCY_MAP.items():
        if re.search(keywords, text_lower):
            detected.add(competency)
    if not detected:
        detected.update(["Critical Thinking and Problem Solving", "Communication and Collaboration"])
    return "**Core Competencies Addressed:**\n" + "\n".join([f"- {c}" for c in sorted(detected)])


def normalize_filename(text):
    cleaned = re.sub(r"[^a-zA-Z0-9\-_\s]", "", text).strip().lower()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60] if cleaned else "cbc_output"


def as_printable_html(text):
    escaped_lines = [html.escape(line) for line in (text or "").split("\n")]
    parts = []
    i = 0

    def parse_cells(row):
        stripped = row.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        return [cell.strip() for cell in stripped.split("|")]

    while i < len(escaped_lines):
        line = escaped_lines[i]

        is_table_header = (
            "|" in line
            and i + 1 < len(escaped_lines)
            and re.fullmatch(r"\s*\|?\s*[-:]+(?:\s*\|\s*[-:]+)+\s*\|?\s*", escaped_lines[i + 1])
        )

        if is_table_header:
            header_cells = parse_cells(line)
            table_rows = []
            i += 2
            while i < len(escaped_lines) and "|" in escaped_lines[i]:
                candidate = escaped_lines[i].strip()
                if not candidate:
                    break
                table_rows.append(parse_cells(escaped_lines[i]))
                i += 1

            thead_html = "".join([f"<th>{cell}</th>" for cell in header_cells])
            tbody_html = ""
            for row_cells in table_rows:
                row_html = "".join([f"<td>{cell}</td>" for cell in row_cells])
                tbody_html += f"<tr>{row_html}</tr>"

            parts.append(
                "<table style='width:100%; border-collapse:collapse; margin:12px 0;'>"
                f"<thead><tr>{thead_html}</tr></thead>"
                f"<tbody>{tbody_html}</tbody>"
                "</table>"
            )
            continue

        if line.strip():
            parts.append(line + "<br>")
        else:
            parts.append("<br>")
        i += 1

    rendered = "".join(parts)
    return f"""
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <style>
          body {{ font-family: Arial, sans-serif; padding: 24px; line-height: 1.5; }}
          h1, h2, h3 {{ color: #17325f; }}
          hr {{ border: none; border-top: 1px solid #d0d7e5; margin: 16px 0; }}
          table, th, td {{ border: 1px solid #d0d7e5; }}
          th, td {{ padding: 8px; text-align: left; vertical-align: top; }}
          th {{ background: #eef3ff; }}
        </style>
      </head>
      <body>{rendered}</body>
    </html>
    """


def sanitize_generated_text(text):
    cleaned = text or ""
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", cleaned)
    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"__(.+?)__", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 - \2", cleaned)
    cleaned = re.sub(r"\n-{3,}\n", "\n----------------------------------------\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def infer_lesson_strand_substrand(prompt, subject_text):
    lowered = (prompt or "").lower()
    subject_upper = (subject_text or "").upper()

    if "ENGLISH" in subject_upper:
        if "reading" in lowered or "comprehens" in lowered:
            return "Reading and Viewing", "Reading for Comprehension"
        if "writing" in lowered or "composition" in lowered:
            return "Writing", "Writing for Different Purposes"
        if "listening" in lowered or "speaking" in lowered:
            return "Listening and Speaking", "Oral Communication"

    return "", ""


def infer_scheme_strand_substrand(prompt, subject_text):
    lowered = (prompt or "").lower()
    subject_upper = (subject_text or "").upper()

    if "ENGLISH" in subject_upper:
        has_reading = "reading" in lowered or "comprehens" in lowered
        has_writing = "writing" in lowered or "composition" in lowered
        has_oral = "listening" in lowered or "speaking" in lowered or "oral" in lowered

        if has_oral:
            return "LISTENING AND SPEAKING", "Oral Communication"
        if has_writing and not has_reading:
            return "WRITING", "Writing for Different Purposes"
        if has_reading or has_writing:
            return "READING AND VIEWING", "Reading for Comprehension"
        return "LANGUAGE AND COMMUNICATION", "Reading and Viewing"

    if "AGRICULTURE AND NUTRITION" in subject_upper and "soil conservation" in lowered:
        return "CONSERVATION OF RESOURCES", "Soil Conservation"

    return "", ""


def extract_topic_from_prompt(prompt):
    text = (prompt or "").strip()
    match = re.search(r"\bon\s+([a-zA-Z0-9\s\-]{3,120})", text, re.IGNORECASE)
    if not match:
        return ""

    topic = match.group(1)
    topic = re.split(r"\b(term\s*[1-3]|grade\s*\d+)\b", topic, maxsplit=1, flags=re.IGNORECASE)[0]
    topic = re.sub(r"\s+", " ", topic).strip(" .,-_")
    return topic.title()


def build_default_key_inquiry_questions(prompt, strand_text, substrand_text, subject_text):
    topic = extract_topic_from_prompt(prompt)
    anchor = topic if topic else (substrand_text if substrand_text and "_" not in substrand_text else strand_text)
    if not anchor or "_" in anchor:
        anchor = "this topic"

    subject_phrase = subject_text.title() if subject_text and "_" not in subject_text else "this learning area"
    return [
        f"How does {anchor} support learner achievement in {subject_phrase}?",
        f"Which practical classroom activities can help learners understand {anchor}?",
        f"How can learners apply {anchor} in school and at home?",
    ]


def build_default_lesson_steps(prompt, strand_text, substrand_text, learning_experiences=None):
    topic = extract_topic_from_prompt(prompt)
    anchor = topic if topic else (substrand_text if substrand_text and "_" not in substrand_text else "the concept")
    
    # If we have actual learning experiences from CBC, use them as lesson steps
    if learning_experiences and len(learning_experiences) >= 3:
        # Clean up the experiences
        step1 = str(learning_experiences[0]).strip(" -•").strip()
        step2 = str(learning_experiences[1]).strip(" -•").strip()
        step3 = str(learning_experiences[2]).strip(" -•").strip()
        
        return {
            "step_1": step1 if len(step1) > 10 else f"Introduce {anchor} using guided questions, examples, and short teacher demonstration.",
            "step_2": step2 if len(step2) > 10 else f"Guide learners in pair/group activity to explore {anchor} and record key observations.",
            "step_3": step3 if len(step3) > 10 else f"Facilitate presentation, correction, and brief individual task to check understanding of {anchor}.",
        }
    elif learning_experiences and len(learning_experiences) >= 1:
        # If we have at least one experience, use it and extrapolate
        step1 = str(learning_experiences[0]).strip(" -•").strip()
        step2 = str(learning_experiences[1]).strip(" -•").strip() if len(learning_experiences) > 1 else f"Guide learners in pair/group activity to explore {anchor} and record key observations."
        step3 = f"Facilitate presentation, correction, and brief individual task to check understanding of {anchor}."
        
        return {
            "step_1": step1 if len(step1) > 10 else f"Introduce {anchor} using guided questions, examples, and short teacher demonstration.",
            "step_2": step2 if isinstance(step2, str) and len(step2) > 10 else f"Guide learners in pair/group activity to explore {anchor} and record key observations.",
            "step_3": step3,
        }
    else:
        # Fallback to generic steps
        return {
            "step_1": f"Introduce {anchor} using guided questions, examples, and short teacher demonstration.",
            "step_2": f"Guide learners in pair/group activity to explore {anchor} and record key observations.",
            "step_3": f"Facilitate presentation, correction, and brief individual task to check understanding of {anchor}.",
        }


def save_to_word(file_path, content):
    _lazy_import_docx()
    if DOCX_AVAILABLE and Document:
        try:
            doc = Document()
            for line in content.split("\n"):
                if line.strip():
                    doc.add_paragraph(line)
            doc.save(file_path)
            return
        except Exception as e:
            app.logger.error(f"Error creating Word document: {str(e)}")
    
    # Fallback: save as text file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def create_download_files(content, intent, prompt):
    _lazy_import_weasyprint()
    _lazy_import_docx()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = normalize_filename(prompt)
    base_name = f"{intent}_{slug}_{timestamp}"

    pdf_filename = f"{base_name}.pdf"
    word_filename = f"{base_name}.docx" if DOCX_AVAILABLE else f"{base_name}.txt"

    pdf_path = os.path.join(RESOURCE_DIR, pdf_filename)
    word_path = os.path.join(RESOURCE_DIR, word_filename)

    if HTML:
        HTML(string=as_printable_html(content)).write_pdf(pdf_path)
    else:
        # Fallback: save as text file if WeasyPrint not available
        with open(pdf_path.replace('.pdf', '.txt'), 'w', encoding='utf-8') as f:
            f.write(content)
        pdf_path = pdf_path.replace('.pdf', '.txt')
    save_to_word(word_path, content)

    return {
        "pdf": f"/resources/{pdf_filename}",
        "word": f"/resources/{word_filename}",
        "saved_to": RESOURCE_DIR
    }


def get_tsc_structure_prompt(intent, prompt, structured_text):
    base = (
        "You are an expert Kenyan CBC curriculum assistant. "
        "Generate output in clear, TSC-ready structure for Junior Secondary (Grade 7-9). "
        "Use simple teacher-friendly language, accurate headings, bullet points, and classroom-practical steps."
    )

    structures = {
        "lesson_plan": (
            "Use this exact order of headings: "
            "1) Administrative Details (School, Subject, Grade, Term, Date, Time), "
            "2) Strand and Sub-strand, 3) Specific Learning Outcomes, 4) Key Inquiry Questions, "
            "5) Core Competencies, 6) Values, 7) Learning Resources, 8) Organization of Learning, "
            "9) Lesson Introduction, 10) Lesson Development (Step 1, Step 2, Step 3), "
            "11) Assessment for Learning, 12) Conclusion, 13) Reflection. "
            "Use numbering exactly as shown and keep section labels explicit. "
            "Duration rule: Grade 7-9 lessons must be 40 minutes, Grade 1-6 lessons must be 35 minutes."
        ),
        "scheme_of_work": (
            "Use this exact order of headings: "
            "1) Cover block (RATIONALISED SCHEMES OF WORK, Subject, Grade, Term, Teacher's Name, TSC Number, School), "
            "2) Weekly breakdown table with exact columns "
            "(Wk, LSN, Strand, Sub-strand, Specific Learning Outcomes, Key Inquiry Question(s), Learning Experiences, Learning Resources, Assessment Methods, Refl), "
            "3) Teacher Reflection notes at the end. "
            "Do NOT add introductory text, commentary, markdown code fences, or extra headings before section 1."
        ),
        "assessment_rubric": (
            "Use this exact order of headings: "
            "1) Assessment Task, 2) Class/Grade Context, 3) Criteria and Performance Levels "
            "(Exceeds, Meets, Approaches, Below), 4) Scoring Guide, 5) Feedback Notes, 6) Remedial Actions. "
            "Present performance levels in a clear matrix/table style."
        ),
        "resources": (
            "Use this exact order of headings: "
            "1) Topic and Grade, 2) Priority Learning Resources (print, visual, audio, digital), "
            "3) Suggested Classroom Activities, 4) Low-cost/Local Alternatives, 5) Safety and Accessibility Notes."
        ),
        "general": (
            "Respond using headings relevant to CBC planning with clear steps, resources, and assessment ideas."
        )
    }

    selected_structure = structures.get(intent, structures["general"])
    return f"{base}\n\nRequest: {prompt}\n\nCurriculum Context:\n{structured_text}\n\nFormatting Rules:\n{selected_structure}"

# --- Routes ---
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/features")
def features():
    return render_template("features.html")

@app.route("/library")
def library():
    return render_template("library.html")

@app.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/terms")
def terms():
    return render_template("terms.html", last_updated="25 February 2026")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", last_updated="25 February 2026")

@app.route("/ai-disclosure")
def ai_disclosure():
    return render_template("ai_disclosure.html")

@app.route("/robots.txt")
def robots_txt():
    return "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nSitemap: " + request.url_root.rstrip("/") + "/sitemap.xml\n", 200, {"Content-Type": "text/plain"}


@app.route("/contact/submit", methods=["POST"])
def submit_contact():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    inquiry_type = (request.form.get("inquiry_type") or "").strip()
    school = (request.form.get("school") or "").strip()
    message = (request.form.get("message") or "").strip()

    # Validate required fields
    if not name or not email or not message or not inquiry_type:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("contact"))

    # Validate email
    if not is_valid_email(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("contact"))

    # Store contact message
    contact_message = {
        "id": int(datetime.now().timestamp() * 1000),
        "name": name,
        "email": email,
        "phone": phone,
        "inquiry_type": inquiry_type,
        "school": school,
        "message": message,
        "submitted_at": datetime.now().isoformat()
    }

    # Save to JSON file
    messages_file = os.path.join(app.root_path, "data", "contact_messages.json")
    os.makedirs(os.path.dirname(messages_file), exist_ok=True)

    messages = []
    if os.path.exists(messages_file):
        try:
            with open(messages_file, "r") as f:
                messages = json.load(f)
        except:
            messages = []

    messages.append(contact_message)

    with open(messages_file, "w") as f:
        json.dump(messages, f, indent=2)

    # Log the message
    app.logger.info(f"Contact message from {name} ({email}): {inquiry_type}")

    flash("Thank you for reaching out! We'll get back to you soon.", "success")
    return redirect(url_for("contact"))
@login_required_page
def ripple_ai():
    return render_template("ai_chat.html")

@app.route("/ai-chat")
@login_required_page
def ai_chat():
    return render_template("ai_chat.html")


@app.route("/teacher/signup", methods=["GET", "POST"])
def teacher_signup():
    if request.method == "GET":
        if session.get("teacher_id"):
            return redirect(url_for("teacher_dashboard"))
        return render_template("teacher_signup.html")

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    school = (request.form.get("school") or "").strip()
    subject_area = (request.form.get("subject_area") or "").strip()
    grade_level = (request.form.get("grade_level") or "").strip()
    years_exp = request.form.get("years_experience") or None
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""
    agree_terms = request.form.get("agree_terms")

    # Validate terms acceptance
    if not agree_terms:
        flash("You must accept the Terms of Service and Privacy Policy.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Validate required fields
    if not full_name or not email or not password:
        flash("Full name, email, and password are required.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Validate email format
    if not is_valid_email(email):
        flash("Please enter a valid email address.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Validate full name length
    if len(full_name) < 2:
        flash("Full name must be at least 2 characters.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Validate password strength
    password_errors = validate_password(password)
    if password_errors:
        for error in password_errors:
            flash(error, "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Validate password match
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 400

    # Check if email already exists
    existing = get_teacher_by_email(email)
    if existing:
        flash("An account with that email already exists.", "error")
        return render_template("teacher_signup.html", full_name=full_name, email=email, school=school, subject_area=subject_area, grade_level=grade_level, years_experience=years_exp), 409

    try:
        years_exp_int = int(years_exp) if years_exp else None
    except ValueError:
        years_exp_int = None

    create_teacher(full_name, email, school, password, subject_area, grade_level, years_exp_int)
    teacher = get_teacher_by_email(email)
    session["teacher_id"] = teacher["id"]
    session["teacher_name"] = teacher["full_name"]
    session["teacher_email"] = teacher["email"]
    flash("Account created successfully. Welcome!", "success")
    return redirect(url_for("teacher_dashboard"))


@app.route("/teacher/signin", methods=["GET", "POST"])
def teacher_signin():
    if request.method == "GET":
        if session.get("teacher_id"):
            return redirect(url_for("teacher_dashboard"))
        return render_template("teacher_signin.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    teacher = get_teacher_by_email(email)
    if not teacher or not check_password_hash(teacher["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("teacher_signin.html", email=email), 401

    session["teacher_id"] = teacher["id"]
    session["teacher_name"] = teacher["full_name"]
    session["teacher_email"] = teacher["email"]
    flash("Signed in successfully.", "success")
    next_url = request.args.get("next")
    return redirect(next_url or url_for("teacher_dashboard"))


@app.route("/teacher/signout", methods=["POST"])
def teacher_signout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/teacher/dashboard")
@login_required_page
def teacher_dashboard():
    recent_files = []
    total_files = 0
    last_generated = None
    
    if os.path.isdir(RESOURCE_DIR):
        files = [
            item for item in os.listdir(RESOURCE_DIR)
            if os.path.isfile(os.path.join(RESOURCE_DIR, item))
        ]
        total_files = len(files)
        files.sort(
            key=lambda item: os.path.getmtime(os.path.join(RESOURCE_DIR, item)),
            reverse=True,
        )
        
        if files:
            latest_time = os.path.getmtime(os.path.join(RESOURCE_DIR, files[0]))
            last_generated = datetime.fromtimestamp(latest_time).strftime("%Y-%m-%d %H:%M")
        
        recent_files = [
            {
                "name": item,
                "url": f"/resources/{item}",
                "modified": datetime.fromtimestamp(
                    os.path.getmtime(os.path.join(RESOURCE_DIR, item))
                ).strftime("%Y-%m-%d %H:%M"),
            }
            for item in files[:10]
        ]

    return render_template(
        "teacher_dashboard.html",
        recent_files=recent_files,
        total_files=total_files,
        last_generated=last_generated
    )


@app.route("/teacher/account")
@login_required_page
def teacher_account():
    return render_template("teacher_account.html")


@app.route("/teacher/settings")
@login_required_page
def teacher_settings():
    return render_template("teacher_settings.html")


@app.route("/teacher/change-password", methods=["POST"])
@login_required_page
def change_password():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_password or not new_password:
        flash("Current password and new password are required.", "error")
        return redirect(url_for("teacher_settings"))

    if len(new_password) < 8:
        flash("New password must be at least 8 characters.", "error")
        return redirect(url_for("teacher_settings"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("teacher_settings"))

    teacher = get_teacher_by_email(session.get("teacher_email"))
    if not teacher or not check_password_hash(teacher["password_hash"], current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("teacher_settings"))

    conn = sqlite3.connect(TEACHERS_DB)
    try:
        conn.execute(
            "UPDATE teachers SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password), session.get("teacher_id"))
        )
        conn.commit()
        flash("Password updated successfully.", "success")
    finally:
        conn.close()

    return redirect(url_for("teacher_settings"))


@app.route("/teacher/resources")
@login_required_page
def teacher_resources():
    search_query = (request.args.get("search") or "").strip().lower()
    sort_by = request.args.get("sort") or "recent"
    
    resources = []
    if os.path.isdir(RESOURCE_DIR):
        files = [
            item for item in os.listdir(RESOURCE_DIR)
            if os.path.isfile(os.path.join(RESOURCE_DIR, item))
        ]
        
        # Filter by search query
        if search_query:
            files = [f for f in files if search_query in f.lower()]
        
        # Sort files
        file_paths = [(f, os.path.join(RESOURCE_DIR, f)) for f in files]
        
        if sort_by == "oldest":
            file_paths.sort(key=lambda x: os.path.getmtime(x[1]))
        elif sort_by == "name_asc":
            file_paths.sort(key=lambda x: x[0].lower())
        elif sort_by == "name_desc":
            file_paths.sort(key=lambda x: x[0].lower(), reverse=True)
        else:  # recent
            file_paths.sort(key=lambda x: os.path.getmtime(x[1]), reverse=True)
        
        for filename, filepath in file_paths:
            size_bytes = os.path.getsize(filepath)
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f}KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
            
            resources.append({
                "name": filename,
                "url": f"/resources/{filename}",
                "size": size_str,
                "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M"),
            })
    
    return render_template("teacher_resources.html", resources=resources, search_query=search_query)


@app.route("/teacher/delete-resource", methods=["POST"])
@login_required_page
def delete_resource():
    filename = (request.form.get("filename") or "").strip()
    
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("teacher_resources"))
    
    filepath = os.path.join(RESOURCE_DIR, filename)
    
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        flash("File not found.", "error")
        return redirect(url_for("teacher_resources"))
    
    try:
        os.remove(filepath)
        flash(f"Deleted: {filename}", "success")
    except Exception as e:
        flash(f"Could not delete file: {str(e)}", "error")
    
    return redirect(url_for("teacher_resources"))

# --- YouTube Search Helper ---
def search_youtube_videos(query, max_results=5, grade=None, subject=None):
    """Search YouTube for educational videos related to the lesson topic"""
    # Enhance query for educational content
    edu_query = f"{query} lesson Kenya CBC"
    if grade:
        edu_query = f"{grade} {edu_query}"
    if subject:
        edu_query = f"{subject} {edu_query}"
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": edu_query,
        "type": "video",
        "key": YOUTUBE_API_KEY,
        "maxResults": max_results,
        "safeSearch": "strict",
        "videoDuration": "medium",  # 4-20 minutes, good for classroom
        "relevanceLanguage": "en"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            return [
                {
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "channel": item["snippet"]["channelTitle"],
                    "description": item["snippet"]["description"][:150] + "..." if len(item["snippet"]["description"]) > 150 else item["snippet"]["description"]
                } for item in items
            ]
    except Exception as e:
        app.logger.error(f"YouTube search error: {str(e)}")
    return []


# --- Curated Educational Resources ---
def get_curated_resources(subject, grade, topic):
    """Get curated educational resources including videos, audio, and visual aids"""
    resources = {
        "videos": [],
        "audio": [],
        "visual": [],
        "websites": []
    }
    
    # YouTube videos (dynamic)
    youtube_videos = search_youtube_videos(topic, max_results=5, grade=grade, subject=subject)
    resources["videos"] = youtube_videos
    
    # Curated educational websites by subject
    subject_websites = {
        "mathematics": [
            {"title": "Khan Academy - Math", "url": "https://www.khanacademy.org/math", "description": "Free math lessons and practice"},
            {"title": "Math is Fun", "url": "https://www.mathsisfun.com/", "description": "Interactive math explanations"},
            {"title": "GeoGebra", "url": "https://www.geogebra.org/", "description": "Free graphing calculator and geometry tools"}
        ],
        "english": [
            {"title": "BBC Learning English", "url": "https://www.bbc.co.uk/learningenglish", "description": "English lessons with videos and audio"},
            {"title": "ReadWriteThink", "url": "https://www.readwritethink.org/", "description": "Literacy resources for teachers"},
            {"title": "Storyline Online", "url": "https://storylineonline.net/", "description": "Free read-aloud stories by actors"}
        ],
        "science": [
            {"title": "National Geographic Education", "url": "https://education.nationalgeographic.org/", "description": "Science and geography resources"},
            {"title": "NASA for Students", "url": "https://www.nasa.gov/stem/forstudents/", "description": "Space and science education"},
            {"title": "PhET Simulations", "url": "https://phet.colorado.edu/", "description": "Free interactive science simulations"}
        ],
        "kiswahili": [
            {"title": "Kiswahili Lesson Plans", "url": "https://elimutab.co.ke/kiswahili", "description": "Kiswahili teaching resources"},
            {"title": "Kamusi Project", "url": "https://kamusi.org/", "description": "Swahili dictionary and language tools"}
        ],
        "social_studies": [
            {"title": "History for Kids", "url": "https://www.historyforkids.net/", "description": "Kid-friendly history lessons"},
            {"title": "National Geographic Kids", "url": "https://kids.nationalgeographic.com/", "description": "Geography and culture for kids"}
        ],
        "cre": [
            {"title": "Bible Gateway", "url": "https://www.biblegateway.com/", "description": "Bible verses and study tools"},
            {"title": "RE:Quest", "url": "https://request.org.uk/", "description": "Religious education resources"}
        ]
    }
    
    # Get subject-specific websites
    subject_key = subject.lower().replace(" ", "_") if subject else "english"
    resources["websites"] = subject_websites.get(subject_key, subject_websites.get("english", []))
    
    # Curated audio resources (podcasts, songs)
    audio_resources = {
        "mathematics": [
            {"title": "Math Songs by NUMBEROCK", "url": "https://www.youtube.com/c/NUMBEROCK", "type": "song", "description": "Catchy math songs for learning"},
            {"title": "Times Tables Songs", "url": "https://www.timestables.com/songs/", "type": "song", "description": "Multiplication table songs"}
        ],
        "english": [
            {"title": "Storynory - Audio Stories", "url": "https://www.storynory.com/", "type": "podcast", "description": "Free audio stories for children"},
            {"title": "Grammar Girl Podcast", "url": "https://www.quickanddirtytips.com/grammar-girl", "type": "podcast", "description": "Grammar tips and explanations"}
        ],
        "science": [
            {"title": "Brains On! Podcast", "url": "https://www.brainson.org/", "type": "podcast", "description": "Science podcast for kids"},
            {"title": "Tumble Science Podcast", "url": "https://www.sciencepodcastforkids.com/", "type": "podcast", "description": "Science stories for curious kids"}
        ],
        "kiswahili": [
            {"title": "Kiswahili Songs for Kids", "url": "https://www.youtube.com/results?search_query=kiswahili+songs+for+kids", "type": "song", "description": "Educational Kiswahili songs"}
        ]
    }
    resources["audio"] = audio_resources.get(subject_key, [])
    
    # Visual resources (printables, diagrams)
    visual_resources = {
        "mathematics": [
            {"title": "Math Printables", "url": "https://www.math-drills.com/", "type": "worksheet", "description": "Free math worksheets"},
            {"title": "Visual Fractions", "url": "https://www.visualfractions.com/", "type": "interactive", "description": "Visual fraction tools"}
        ],
        "english": [
            {"title": "ReadWriteThink Printouts", "url": "https://www.readwritethink.org/classroom-resources/printouts", "type": "worksheet", "description": "Literacy printables"},
            {"title": "Graphic Organizers", "url": "https://www.eduplace.com/graphicorganizer/", "type": "organizer", "description": "Writing graphic organizers"}
        ],
        "science": [
            {"title": "Science Diagrams", "url": "https://www.sciencekids.co.nz/pictures.html", "type": "diagram", "description": "Science pictures and diagrams"},
            {"title": "Periodic Table", "url": "https://ptable.com/", "type": "interactive", "description": "Interactive periodic table"}
        ]
    }
    resources["visual"] = visual_resources.get(subject_key, [])
    
    return resources

# --- Format Lesson Plan ---
def format_lesson_plan(response, structured_info=None, prompt=""):
    dynamic_competencies = generate_dynamic_competencies(response)

    today = datetime.today().strftime("%d/%m/%Y")
    current_year = datetime.today().year
    grade, subject = parse_subject_and_grade(prompt)
    term = parse_term(prompt)
    subject_text = subject.title() if subject else "__________________"
    grade_text = grade if grade else "__________________"
    term_text = term if term else "___"

    strand = structured_info.get("Strand", "") if structured_info else ""
    substrand = structured_info.get("Sub-strand", "") if structured_info else ""

    raw_slos = structured_info.get("Specific Learning Outcomes", []) if structured_info else []
    clean_slos = []
    for item in raw_slos:
        cleaned = re.sub(r"\s+", " ", str(item)).strip(" -,:;")
        if len(cleaned) < 20:
            continue
        if len(cleaned.split()) < 4:
            continue
        clean_slos.append(cleaned)
    clean_slos = clean_slos[:6]

    raw_kiq = structured_info.get("Key Inquiry Questions", []) if structured_info else []
    clean_kiq = []
    for item in raw_kiq:
        cleaned = re.sub(r"\s+", " ", str(item)).strip(" -,:;")
        if len(cleaned.split()) < 4:
            continue
        if "?" not in cleaned:
            if re.match(r"^(how|what|why|which|can|do|should|who|when|where)\b", cleaned, re.IGNORECASE):
                cleaned += "?"
            else:
                continue
        if len(cleaned) < 14:
            continue
        clean_kiq.append(cleaned)
    clean_kiq = clean_kiq[:6]

    slo = "\n- " + "\n- ".join(clean_slos) if clean_slos else ""
    kiq = "\n1. " + "\n2. ".join(clean_kiq) if clean_kiq else ""
    learning_resources = "Bible, chalkboard, textbook, projector (if available)"
    org_learning = "Whole class discussion, group dramatization, creative writing"
    inferred_strand, inferred_substrand = infer_lesson_strand_substrand(prompt, subject)

    strand_text = strand if strand else (inferred_strand if inferred_strand else "__________________")
    substrand_text = substrand if substrand else (inferred_substrand if inferred_substrand else "__________________")

    if inferred_strand:
        prompt_lower = (prompt or "").lower()
        if (
            ("reading" in prompt_lower and "reading" not in strand_text.lower())
            or ("writing" in prompt_lower and "writing" not in strand_text.lower())
            or ("listening" in prompt_lower and "listening" not in strand_text.lower())
            or ("speaking" in prompt_lower and "speaking" not in strand_text.lower())
        ):
            strand_text = inferred_strand

    if inferred_substrand:
        prompt_lower = (prompt or "").lower()
        if (
            ("comprehens" in prompt_lower and "comprehens" not in substrand_text.lower())
            or ("oral" in prompt_lower and "oral" not in substrand_text.lower())
            or ("writing" in prompt_lower and "writing" not in substrand_text.lower())
        ):
            substrand_text = inferred_substrand

    if not clean_kiq and "comprehens" in (prompt or "").lower():
        clean_kiq = [
            "How do learners identify the main idea in a text?",
            "Which strategies help learners answer comprehension questions accurately?",
        ]

    if not clean_kiq:
        clean_kiq = build_default_key_inquiry_questions(prompt, strand_text, substrand_text, subject_text)

    kiq = "\n" + "\n".join([f"{index + 1}. {item}" for index, item in enumerate(clean_kiq[:3])])

    # Get learning experiences from structured info if available
    learning_experiences = structured_info.get("Suggested Learning Experiences", []) if structured_info else []
    lesson_steps = build_default_lesson_steps(prompt, strand_text, substrand_text, learning_experiences)
    slo_text = slo if slo.strip() else "\n- __________________\n- __________________\n- __________________"
    kiq_text = kiq if kiq.strip() else "\n1. __________________\n2. __________________"
    lesson_minutes = get_lesson_duration_minutes(prompt)

    if lesson_minutes == 35:
        time_allocation = [
            "- Introduction: 5 mins",
            "- Step 1: 7 mins",
            "- Step 2 (Competencies/Values): 9 mins",
            "- Step 3: 6 mins",
            "- Extended Activities: 4 mins",
            "- Conclusion: 2 mins",
            "- Reflection: 2 mins",
        ]
    else:
        time_allocation = [
            "- Introduction: 5 mins",
            "- Step 1: 8 mins",
            "- Step 2 (Competencies/Values): 10 mins",
            "- Step 3: 7 mins",
            "- Extended Activities: 5 mins",
            "- Conclusion: 3 mins",
            "- Reflection: 2 mins",
        ]

    time_allocation_text = "\n".join(time_allocation)

    return f"""
LESSON PLAN (TSC-READY)
1) Administrative Details

| **School** | __________________ | **Date** | {today} |
|------------|--------------------|----------|--------------------|
| **Subject** | {subject_text} | **Time** | {lesson_minutes} minutes |
| **Year** | {current_year} | **Grade**| {grade_text} |
| **Term** | {term_text} | **Roll** | ___________ |

2) Strand and Sub-strand
Strand: {strand_text}
Sub Strand: {substrand_text}

3) Specific Learning Outcomes:{slo_text}
4) Key Inquiry Questions:{kiq_text}
5) Core Competencies
{dynamic_competencies.replace('**Core Competencies Addressed:**', '').strip()}
6) Values
- Respect
- Responsibility
- Collaboration
7) Learning Resources
- {learning_resources}
8) Organization of Learning
- {org_learning}
- Lesson Duration: {lesson_minutes} minutes

9) Lesson Introduction
- Engage learners with starter activity and prior knowledge check.

10) Lesson Development
Step 1:
- {lesson_steps['step_1']}
Step 2:
- {lesson_steps['step_2']}
Step 3:
- {lesson_steps['step_3']}

11) Assessment for Learning
- Observation checklist
- Oral questions
- Short written task

12) Conclusion
- Recap key learning points and assign follow-up activity.

13) Reflection
- What worked well?
- What needs improvement next lesson?

TIME ALLOCATION
{time_allocation_text}
"""


def format_scheme_of_work(response, structured_info=None, prompt=""):
    strand = structured_info.get("Strand", "") if structured_info else ""
    substrand = structured_info.get("Sub-strand", "") if structured_info else ""
    grade, subject = parse_subject_and_grade(prompt)
    term = parse_term(prompt)
    current_year = datetime.today().year

    subject_text = subject if subject else "__________________"
    grade_text = grade if grade else "__________________"
    term_text = term if term else "__________________"
    term_cover = term_text.upper() if term_text != "__________________" else term_text
    strand_text = strand if strand else "__________________"
    substrand_text = substrand if substrand else "__________________"

    inferred_scheme_strand, inferred_scheme_substrand = infer_scheme_strand_substrand(prompt, subject_text)
    prompt_lower = (prompt or "").lower()
    is_english = "ENGLISH" in subject_text.upper()
    has_english_topic = any(token in prompt_lower for token in ["reading", "comprehens", "writing", "listening", "speaking", "oral"])
    inconsistent_pair = (
        strand_text.strip().upper() == "LISTENING AND SPEAKING"
        and any(token in substrand_text.strip().lower() for token in ["reading", "writing"])
    )

    if inferred_scheme_strand:
        english_default_needed = is_english and not has_english_topic

        english_strand_mismatch = (
            is_english
            and strand_text.strip().upper() == "LISTENING AND SPEAKING"
            and not any(token in prompt_lower for token in ["listening", "speaking", "oral"])
        )

        if (
            "__________________" in strand_text
            or ("listening" in strand_text.lower() and "reading" in prompt_lower)
            or ("reading" in strand_text.lower() and "writing" in prompt_lower)
            or english_default_needed
            or english_strand_mismatch
            or inconsistent_pair
        ):
            strand_text = inferred_scheme_strand

    if inferred_scheme_substrand:
        if (
            "__________________" in substrand_text
            or ("comprehens" in prompt_lower and "comprehens" not in substrand_text.lower())
            or (
                is_english
                and not has_english_topic
            )
            or (
                strand_text.strip().upper() == "LANGUAGE AND COMMUNICATION"
                and substrand_text.strip().lower() in {"reading and writing", "listening and speaking"}
            )
            or inconsistent_pair
        ):
            substrand_text = inferred_scheme_substrand

    if is_english and inconsistent_pair:
        strand_text = inferred_scheme_strand
        substrand_text = inferred_scheme_substrand

    return f"""
RATIONALISED SCHEMES OF WORK
{subject_text}
{grade_text}
{term_cover} {current_year}
TEACHER'S NAME: _________________________________
TSC NUMBER: _____________________________________
SCHOOL: _________________________________________

| Wk | LSN | Strand | Sub-strand | Specific Learning Outcomes | Key Inquiry Question(s) | Learning Experiences | Learning Resources | Assessment Methods | Refl |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) __________________ b) __________________ c) __________________ | __________________ | Learners are guided to: • __________________ • __________________ | Learner's Book, Teacher's Guide, charts, digital/print resources | Observation; Written tests; Assignments; Oral assessment | ___ |
| 1 | 2 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) __________________ b) __________________ c) __________________ | __________________ | Learners are guided to: • __________________ • __________________ | Learner's Book, Teacher's Guide, locally available materials | Observation; Projects; Oral assessment | ___ |
| 1 | 3 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) __________________ b) __________________ c) __________________ | __________________ | Learners are guided to: • __________________ • __________________ | Textbook, board, worksheets, reference materials | Written tests; Assignments; Practical task | ___ |

Teacher Reflection Notes:
- What was achieved this week?
- Which learners need support/remediation?
"""


def format_assessment_rubric(response, prompt=""):
    grade, subject = parse_subject_and_grade(prompt)
    term = parse_term(prompt)
    current_year = datetime.today().year

    subject_text = subject.title() if subject else "__________________"
    grade_text = grade if grade else "__________________"
    term_text = term if term else "__________________"

    normalized = response.lower()
    heading_hits = [
        "assessment task" in normalized,
        "class/grade context" in normalized or "class context" in normalized,
        "performance levels" in normalized or "criteria" in normalized,
        "scoring guide" in normalized,
        "feedback notes" in normalized,
        "remedial actions" in normalized,
    ]
    if sum(heading_hits) >= 5:
        return response

    return f"""
ASSESSMENT RUBRIC (TSC-READY)
1) Assessment Task
- Task Title: __________________
- Subject Focus: {subject_text}

2) Class/Grade Context
- Grade: {grade_text}
- Term: {term_text}
- Year: {current_year}
- Learning Area Context: __________________

3) Criteria and Performance Levels
| Criteria | Exceeds Expectation | Meets Expectation | Approaches Expectation | Below Expectation |
|---|---|---|---|---|
| Content Accuracy | Complete and accurate evidence | Mostly accurate evidence | Partial accuracy with gaps | Limited/incorrect evidence |
| Application of Skill | Applies skill confidently and independently | Applies skill correctly with minimal support | Applies skill with support | Unable to apply skill adequately |
| Communication/Presentation | Clear, logical, and well-organized | Clear with minor gaps | Basic clarity with frequent gaps | Unclear and disorganized |

4) Scoring Guide
- 4 = Exceeds Expectation
- 3 = Meets Expectation
- 2 = Approaches Expectation
- 1 = Below Expectation
- Total Score: __________________

5) Feedback Notes
- Strengths: __________________
- Areas for Improvement: __________________

6) Remedial Actions
- Support Plan: __________________
- Enrichment Plan: __________________

---
AI Draft Notes:
{response}
"""


def build_offline_scheme_of_work(prompt, structured_info):
    strand = structured_info.get("Strand", "") if structured_info else ""
    substrand = structured_info.get("Sub-strand", "") if structured_info else ""
    grade, subject = parse_subject_and_grade(prompt)
    term = parse_term(prompt)
    current_year = datetime.today().year
    prompt_lower = (prompt or "").lower()

    inferred_scheme_strand, inferred_scheme_substrand = infer_scheme_strand_substrand(prompt, subject)
    inconsistent_pair = (
        strand.strip().upper() == "LISTENING AND SPEAKING"
        and any(token in substrand.strip().lower() for token in ["reading", "writing"])
    )

    if inferred_scheme_strand:
        english_default_needed = (
            "english" in prompt_lower
            and not strand
            and inferred_scheme_strand.upper() == "LANGUAGE AND COMMUNICATION"
        )
        english_strand_mismatch = (
            "english" in prompt_lower
            and strand.strip().upper() == "LISTENING AND SPEAKING"
            and not any(token in prompt_lower for token in ["listening", "speaking", "oral"])
        )
        if (
            not strand
            or strand.strip().upper() in {"language skills", "language", "english"}
            or strand.strip().lower() in {"strand", "topic", "main strand"}
            or english_default_needed
            or english_strand_mismatch
            or inconsistent_pair
        ):
            strand = inferred_scheme_strand

    if inferred_scheme_substrand:
        if (
            not substrand
            or substrand.strip().lower() in {
                "sub strand",
                "sub-strand",
                "reading and writing",
                "generic",
                "n/a",
                "none",
                "not specified",
            }
            or inconsistent_pair
        ):
            substrand = inferred_scheme_substrand

    if "english" in prompt_lower and inconsistent_pair:
        strand = inferred_scheme_strand
        substrand = inferred_scheme_substrand

    strand_text = strand if strand else "Language Skills"
    substrand_text = substrand if substrand else "Reading and Writing"
    subject_text = subject if subject else "__________________"
    grade_text = grade if grade else "__________________"
    term_text = term if term else "__________________"
    term_cover = term_text.upper() if term_text != "__________________" else term_text

    weekly_rows = [
        f"| 1 | 1 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) describe key concepts in {substrand_text}; b) identify practical applications; c) apply learning in class task. | How can this topic improve classroom and community practice? | Learners are guided to: • discuss key ideas in groups • complete guided practical activity | Sample materials, Teacher's Guide, Learner's Book | Observation; Written tests and assignments; Oral assessment | ___ |",
        f"| 1 | 2 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) explain class activity steps; b) use available resources effectively; c) demonstrate learned skill. | What steps are needed to complete the task successfully? | Learners are guided to: • research using digital/print resources • present findings in pairs | Charts, textbook, local resources | Observation; Projects; Oral assessment | ___ |",
        f"| 1 | 3 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) perform task independently; b) evaluate outcomes; c) suggest improvements. | How can we improve outcomes using local resources? | Learners are guided to: • perform practical class task • reflect on results and improvements | Worksheets, board, reference notes | Written tests; Assignments; Practical task | ___ |",
        f"| 2 | 1 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) extend prior knowledge; b) collaborate in teams; c) apply correct procedures. | Which methods are most effective for this topic? | Learners are guided to: • complete pair activity • document outcomes in exercise books | Learner's Book, teacher notes, sample tools | Observation; Oral assessment | ___ |",
        f"| 2 | 2 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) solve task-based challenges; b) interpret findings; c) report results clearly. | How do we measure success in this learning area? | Learners are guided to: • analyze outcomes • share reports and receive feedback | Charts, worksheets, digital resources | Written tests and assignments; Projects | ___ |",
        f"| 2 | 3 | {strand_text} | {substrand_text} | By the end of the lesson, the learner should be able to: a) consolidate the week's learning; b) demonstrate competence; c) reflect on strengths and gaps. | What should we improve in the next lessons? | Learners are guided to: • do recap tasks • complete reflection questions | Revision materials, board, textbook | Observation; Oral assessment; Short test | ___ |"
    ]

    return (
        "RATIONALISED SCHEMES OF WORK\n"
        f"{subject_text}\n"
        f"{grade_text}\n"
        f"{term_cover} {current_year}\n"
        "TEACHER'S NAME: _________________________________\n"
        "TSC NUMBER: _____________________________________\n"
        "SCHOOL: _________________________________________\n\n"
        "| Wk | LSN | Strand | Sub-strand | Specific Learning Outcomes | Key Inquiry Question(s) | Learning Experiences | Learning Resources | Assessment Methods | Refl |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(weekly_rows)
        + "\n\nTeacher Reflection Notes\n"
        "- Which activities improved participation most?\n"
        "- Which learners need targeted support next week?\n"
    )


def build_unavailable_fallback(intent, prompt, structured_info, reason):
    fallback_body = (
        f"Request: {prompt}\n"
        f"Strand: {structured_info.get('Strand', '')}\n"
        f"Sub-strand: {structured_info.get('Sub-strand', '')}"
    )

    if intent == "lesson_plan":
        return format_lesson_plan(fallback_body, structured_info, prompt)
    if intent == "scheme_of_work":
        return build_offline_scheme_of_work(prompt, structured_info)
    if intent == "assessment_rubric":
        return format_assessment_rubric(fallback_body, prompt)
    if intent == "resources":
        return (
            "Teaching Resources (Offline Draft)\n"
            f"Topic/Request: {prompt}\n"
            f"Strand: {structured_info.get('Strand', '__________________')}\n"
            f"Sub-strand: {structured_info.get('Sub-strand', '__________________')}\n\n"
            "Priority Learning Resources:\n"
            "- Learner's Book and Teacher's Guide\n"
            "- Charts, pictures, and locally available materials\n"
            "- Short videos/audio where available\n\n"
            "Suggested Classroom Activities:\n"
            "- Guided discussion and demonstration\n"
            "- Group task with reporting\n"
            "- Short assessment task and feedback\n"
        )
    return format_lesson_plan(fallback_body, structured_info, prompt)

# --- AI Chat Prompt ---
def chat_openrouter(prompt, model="mistralai/mistral-7b-instruct"):
    if not OPENROUTER_API_KEY:
        return {"ok": False, "error": "OPENROUTER_API_KEY is missing"}

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://eduripple.ai",
                "X-Title": "EduRipple CBC Assistant"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        response.raise_for_status()
        return {
            "ok": True,
            "content": response.json()["choices"][0]["message"]["content"].strip()
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "HTTPError"
        app.logger.error(f"OpenRouter HTTP error: {status_code}")
        return {"ok": False, "error": f"OpenRouter HTTP {status_code}"}
    except requests.exceptions.RequestException as e:
        app.logger.error(f"OpenRouter request failed: {str(e)}")
        return {"ok": False, "error": "Network/API request error"}
    except Exception as e:
        app.logger.error(f"OpenRouter unknown error: {str(e)}")
        return {"ok": False, "error": "Unexpected AI service error"}

@app.route("/api/cbc", methods=["POST"])
@login_required_json
def cbc_assistant():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid request format"}), 400
        
        prompt = data.get('prompt', '').strip()
        
        # Validate input
        validation = validate_input(prompt)
        if not validation["valid"]:
            return jsonify({"success": False, "error": "; ".join(validation["errors"])}), 400
        
        intent = classify_intent(prompt)
        
        # Parse subject and grade from prompt
        grade_match, subject_match = parse_subject_and_grade(prompt)
        
        # Get curated resources for the topic
        curated_resources = get_curated_resources(subject_match or "English", grade_match or "Grade 7", prompt)
        
        # Generate using templates based on intent
        if intent == "lesson_plan":
            result = generate_lesson_plan(subject_match or "English", grade_match or "Grade 7", prompt)
            answer = result["content"] if result["success"] else f"Error: {result['error']}'"
            # If multi-lesson, include structured data for frontend tabs
            if result.get("success") and result.get("num_lessons", 1) > 1:
                num_lessons = result["num_lessons"]
                lesson_plans_list = result.get("lesson_plans", [])
            else:
                num_lessons = 1
                lesson_plans_list = []
        elif intent == "scheme_of_work":
            term = parse_term(prompt).split()[-1] if parse_term(prompt) else "1"
            result = generate_scheme_of_work(subject_match or "Mathematics", grade_match or "Grade 7", term)
            answer = result["content"] if result["success"] else f"Error: {result['error']}"
        elif intent == "assessment_rubric":
            result = generate_rubric(subject_match or "Science", grade_match or "Grade 7", "performance")
            answer = result["content"] if result["success"] else f"Error: {result['error']}"
        else:
            # For general queries, use database to provide context
            structured_info = find_relevant_cbc_content(prompt)
            outcomes = structured_info.get('Specific Learning Outcomes', [])
            questions = structured_info.get('Key Inquiry Questions', [])
            competencies = structured_info.get('Core Competencies', [])
            experiences = structured_info.get('Suggested Learning Experiences', [])
            
            answer = f"""CURRICULAR GUIDANCE

Strand: {structured_info.get('Strand', 'N/A')}
Sub-strand: {structured_info.get('Sub-strand', 'N/A')}

Specific Learning Outcomes:
{chr(10).join([f'- {o}' for o in outcomes])}

Key Inquiry Questions:
{chr(10).join([f'- {q}' for q in questions])}

Core Competencies:
{chr(10).join([f'- {c}' for c in competencies])}

Suggested Learning Experiences:
{chr(10).join([f'- {e}' for e in experiences])}
"""

        # Add YouTube videos to all responses
        if curated_resources["videos"]:
            video_section = "\n\n📺 RECOMMENDED YOUTUBE VIDEOS:\n"
            for v in curated_resources["videos"][:5]:
                video_section += f"• {v['title']}\n  Channel: {v['channel']}\n  Watch: {v['url']}\n\n"
            answer += video_section
        
        # Add curated websites
        if curated_resources["websites"]:
            website_section = "\n🌐 EDUCATIONAL WEBSITES:\n"
            for w in curated_resources["websites"]:
                website_section += f"• {w['title']}: {w['url']}\n  {w['description']}\n\n"
            answer += website_section
        
        # Add audio resources
        if curated_resources["audio"]:
            audio_section = "\n🎧 AUDIO RESOURCES:\n"
            for a in curated_resources["audio"]:
                audio_section += f"• {a['title']} ({a['type']})\n  {a['url']}\n  {a['description']}\n\n"
            answer += audio_section
        
        # Add visual resources
        if curated_resources["visual"]:
            visual_section = "\n🖼️ VISUAL & PRINTABLE RESOURCES:\n"
            for v in curated_resources["visual"]:
                visual_section += f"• {v['title']} ({v['type']})\n  {v['url']}\n  {v['description']}\n\n"
            answer += visual_section

        answer = sanitize_generated_text(answer)
        downloads = create_download_files(answer, intent, prompt)

        response_data = {
            "success": True,
            "response": answer,
            "downloads": downloads,
            "curated_resources": curated_resources,
            "resources": [
                {"name": item, "url": f"/resources/{item}"}
                for item in sorted(os.listdir(RESOURCE_DIR), reverse=True)
                if os.path.isfile(os.path.join(RESOURCE_DIR, item))
            ][:20]
        }
        
        # Include multi-lesson data if applicable
        if intent == "lesson_plan":
            n = num_lessons if 'num_lessons' in dir() else 1
            response_data["num_lessons"] = n
            response_data["topic"] = result.get("topic", "")
            response_data["subject"] = result.get("subject", "")
            response_data["grade"] = result.get("grade", "")
            if lesson_plans_list:
                response_data["lesson_plans"] = [
                    sanitize_generated_text(lp) for lp in lesson_plans_list
                ]
        
        return jsonify(response_data)
    
    except Exception as e:
        app.logger.error(f"Error in cbc_assistant: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An error occurred while processing your request. Please try again."
        }), 500


@app.route('/resources/<path:filename>', methods=['GET'])
def download_resource(filename):
    return send_from_directory(RESOURCE_DIR, filename, as_attachment=True)


@app.route('/api/resources', methods=['GET'])
def list_resources():
    files = []
    for item in os.listdir(RESOURCE_DIR):
        path = os.path.join(RESOURCE_DIR, item)
        if os.path.isfile(path):
            files.append({
                "name": item,
                "url": f"/resources/{item}",
                "date": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                "size": os.path.getsize(path)
            })
    files.sort(key=lambda item: item["date"], reverse=True)
    return jsonify({"resources": files})


# ===== AI MEDIA GENERATION ENDPOINTS =====

@app.route('/api/audio/voices', methods=['GET'])
def get_available_voices():
    """Get list of available ElevenLabs voices"""
    return jsonify({
        "success": True,
        "voices": ElevenLabsAudioGenerator.get_available_voices(),
        "recommended": {
            "lesson": "rachel",
            "story": "matthew", 
            "young_learners": "emily",
            "professional": "paul"
        }
    })


@app.route('/api/generate/audio', methods=['POST'])
@login_required_json
def generate_audio():
    """
    Generate high-quality audio using ElevenLabs (with gTTS fallback).
    Supports any subject content - lessons, stories, vocabulary, exercises.
    
    Request JSON:
    {
        "text": "The content to convert to speech...",
        "voice": "rachel" | "adam" | "matthew" | etc (optional),
        "content_type": "lesson" | "story" | "vocabulary" | "exercise",
        "subject": "english" | "mathematics" | etc (optional, for auto voice selection)
    }
    
    Free tier voices: rachel, sarah, emily, adam, josh, thomas, matthew, dave, charlie, paul
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        text = data.get('text', '').strip()
        voice = data.get('voice', 'rachel')
        content_type = data.get('content_type', 'lesson')
        subject = data.get('subject')
        
        if not text:
            return jsonify({"success": False, "error": "Text is required"}), 400
        
        # Free tier recommendation: keep under 5000 chars to conserve quota
        if len(text) > 10000:
            return jsonify({"success": False, "error": "Text too long (max 10,000 characters). Consider splitting into parts."}), 400
        
        # Generate audio using ElevenLabs (with fallback)
        result = ElevenLabsAudioGenerator.generate_audio(
            text=text,
            voice=voice,
            subject=subject,
            content_type=content_type
        )
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating audio: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate audio"}), 500


@app.route('/api/generate/lesson-audio', methods=['POST'])
@login_required_json
def generate_lesson_audio():
    """
    Generate audio narration for a complete lesson.
    Auto-selects best voice based on subject.
    
    Request JSON:
    {
        "lesson_content": "The full lesson text...",
        "title": "Introduction to Fractions",
        "subject": "mathematics",
        "voice": "thomas" (optional)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        lesson_content = data.get('lesson_content', '').strip()
        title = data.get('title', 'Lesson')
        subject = data.get('subject')
        voice = data.get('voice')
        
        if not lesson_content:
            return jsonify({"success": False, "error": "Lesson content is required"}), 400
        
        result = ElevenLabsAudioGenerator.generate_lesson_audio(
            lesson_content=lesson_content,
            title=title,
            subject=subject,
            voice=voice
        )
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating lesson audio: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate lesson audio"}), 500


@app.route('/api/generate/story-audio', methods=['POST'])
@login_required_json  
def generate_story_audio():
    """
    Generate narrated story/reading passage audio.
    Perfect for reading comprehension exercises.
    
    Request JSON:
    {
        "story_text": "Once upon a time...",
        "title": "The Clever Hare",
        "voice": "matthew" (optional, good for stories)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        story_text = data.get('story_text', '').strip()
        title = data.get('title', 'Story')
        voice = data.get('voice', 'matthew')
        
        if not story_text:
            return jsonify({"success": False, "error": "Story text is required"}), 400
        
        result = ElevenLabsAudioGenerator.generate_story_audio(
            story_text=story_text,
            title=title,
            voice=voice
        )
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating story audio: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate story audio"}), 500


@app.route('/api/generate/audio-comparison', methods=['POST'])
@login_required_json
def generate_audio_comparison():
    """
    Generate audio at multiple speeds for comparison exercises.
    Students can listen to slow vs normal to practice listening skills.
    
    Request JSON:
    {
        "text": "The passage to read...",
        "speeds": ["slow", "normal"],
        "language": "english"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        text = data.get('text', '').strip()
        speeds = data.get('speeds', ['slow', 'normal'])
        language = data.get('language', 'english')
        
        if not text:
            return jsonify({"success": False, "error": "Text is required"}), 400
        
        result = generate_reading_passage_audio(text, speeds=speeds)
        result['language'] = language
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating audio comparison: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate audio"}), 500


@app.route('/api/generate/flashcards', methods=['POST'])
@login_required_json
def generate_flashcards():
    """
    Generate interactive flashcards for vocabulary, concepts, or Q&A.
    
    Request JSON:
    {
        "topic": "Fractions",
        "type": "vocabulary" | "concept" | "question",
        "subject": "Mathematics",
        "grade": "Grade 7",
        "items": [
            {"front": "Term", "back": "Definition"},
            ...
        ]
    }
    
    OR for auto-generation:
    {
        "topic": "Fractions",
        "subject": "Mathematics", 
        "grade": "Grade 7",
        "auto_generate": true,
        "count": 10
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        topic = data.get('topic', 'General')
        card_type = data.get('type', 'vocabulary')
        subject = data.get('subject', 'English')
        grade = data.get('grade', 'Grade 7')
        
        # Auto-generate flashcards
        if data.get('auto_generate'):
            count = min(data.get('count', 10), 20)
            result = ContentGenerator.generate_vocabulary_flashcards(
                subject=subject,
                grade=grade,
                topic=topic,
                count=count
            )
            return jsonify(result)
        
        # Manual flashcard creation
        items = data.get('items', [])
        if not items:
            return jsonify({"success": False, "error": "No flashcard items provided"}), 400
        
        # Validate items format
        for item in items:
            if 'front' not in item or 'back' not in item:
                return jsonify({"success": False, "error": "Each item must have 'front' and 'back' fields"}), 400
        
        result = FlashcardGenerator.generate_flashcards(
            topic=f"{grade} {subject} - {topic}",
            items=items,
            card_type=card_type
        )
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating flashcards: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate flashcards"}), 500


@app.route('/api/generate/vocabulary-audio', methods=['POST'])
@login_required_json
def generate_vocabulary_audio():
    """
    Generate audio for vocabulary words with their definitions.
    Perfect for vocabulary drilling and pronunciation practice.
    
    Request JSON:
    {
        "words": [
            {"word": "Comprehension", "definition": "The ability to understand"},
            ...
        ],
        "language": "english"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        words = data.get('words', [])
        language = data.get('language', 'english')
        
        if not words:
            return jsonify({"success": False, "error": "No words provided"}), 400
        
        result = AudioGenerator.generate_vocabulary_audio(words, language=language)
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating vocabulary audio: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate audio"}), 500


# ── Fallback educational content when AI is unavailable ──
# This provides real educational content for common topics so videos
# are still useful even when the AI quota is exhausted.

_FALLBACK_VOCABULARY = {
    "fractions": [
        {"word": "Fraction", "definition": "A number that represents a part of a whole, written with a numerator and denominator like 1/2."},
        {"word": "Numerator", "definition": "The top number in a fraction. It tells how many parts we have."},
        {"word": "Denominator", "definition": "The bottom number in a fraction. It tells how many equal parts the whole is divided into."},
        {"word": "Proper Fraction", "definition": "A fraction where the numerator is smaller than the denominator, like 3/4."},
        {"word": "Improper Fraction", "definition": "A fraction where the numerator is larger than or equal to the denominator, like 5/3."},
        {"word": "Mixed Number", "definition": "A whole number combined with a fraction, like 2 and 1/2."},
        {"word": "Equivalent Fractions", "definition": "Different fractions that represent the same amount, like 1/2 and 2/4."},
        {"word": "Simplify", "definition": "To reduce a fraction to its smallest form by dividing both numbers by their greatest common factor."},
        {"word": "Common Denominator", "definition": "A shared denominator used when adding or subtracting fractions with different denominators."},
        {"word": "Unit Fraction", "definition": "A fraction with 1 as the numerator, like 1/3 or 1/5."},
    ],
    "decimals": [
        {"word": "Decimal", "definition": "A number that uses a decimal point to show tenths, hundredths, and smaller parts."},
        {"word": "Decimal Point", "definition": "The dot in a decimal number that separates whole numbers from fractional parts."},
        {"word": "Tenths", "definition": "The first place after the decimal point. 0.1 means one tenth."},
        {"word": "Hundredths", "definition": "The second place after the decimal point. 0.01 means one hundredth."},
        {"word": "Place Value", "definition": "The value of a digit based on its position in a number."},
        {"word": "Rounding", "definition": "Adjusting a decimal to the nearest whole number or decimal place."},
        {"word": "Terminating Decimal", "definition": "A decimal that ends after a certain number of digits, like 0.25."},
        {"word": "Recurring Decimal", "definition": "A decimal in which one or more digits repeat forever, like 0.333..."},
    ],
    "percentages": [
        {"word": "Percentage", "definition": "A number expressed as a fraction of 100, shown with the % symbol."},
        {"word": "Percent", "definition": "Per hundred. 50% means 50 out of every 100."},
        {"word": "Discount", "definition": "A reduction in price, often given as a percentage."},
        {"word": "Increase", "definition": "When a value goes up. A percentage increase shows how much it grew."},
        {"word": "Decrease", "definition": "When a value goes down. A percentage decrease shows how much it shrunk."},
        {"word": "Convert", "definition": "To change from one form to another, like turning a fraction into a percentage."},
        {"word": "Profit", "definition": "The money gained when selling price is higher than buying price, often shown as a percentage."},
        {"word": "Loss", "definition": "The money lost when selling price is lower than buying price."},
    ],
    "multiplication": [
        {"word": "Multiply", "definition": "To add a number to itself a certain number of times. 3 times 4 means 3 + 3 + 3 + 3."},
        {"word": "Product", "definition": "The answer you get when you multiply two or more numbers together."},
        {"word": "Factor", "definition": "A number that divides evenly into another number. 3 and 4 are factors of 12."},
        {"word": "Multiple", "definition": "The result of multiplying a number by a whole number. 6, 9, 12 are multiples of 3."},
        {"word": "Times Table", "definition": "A list of multiples of a number, used to help with quick multiplication."},
        {"word": "Array", "definition": "Objects arranged in equal rows and columns to show multiplication."},
        {"word": "Commutative", "definition": "The order of multiplication does not change the answer. 3 x 4 = 4 x 3."},
        {"word": "Distributive", "definition": "Breaking a multiplication into simpler parts. 6 x 14 = 6 x 10 + 6 x 4."},
    ],
    "division": [
        {"word": "Divide", "definition": "To split a number into equal groups or parts."},
        {"word": "Dividend", "definition": "The number being divided. In 12 ÷ 3, the dividend is 12."},
        {"word": "Divisor", "definition": "The number you divide by. In 12 ÷ 3, the divisor is 3."},
        {"word": "Quotient", "definition": "The answer when you divide one number by another."},
        {"word": "Remainder", "definition": "The amount left over after dividing. 13 ÷ 4 = 3 remainder 1."},
        {"word": "Long Division", "definition": "A method for dividing large numbers step by step."},
        {"word": "Divisible", "definition": "A number that can be divided exactly with no remainder."},
        {"word": "Inverse", "definition": "Division is the inverse (opposite) of multiplication."},
    ],
    "geometry": [
        {"word": "Geometry", "definition": "The branch of mathematics that deals with shapes, sizes, and positions."},
        {"word": "Angle", "definition": "The space between two lines that meet at a point, measured in degrees."},
        {"word": "Triangle", "definition": "A shape with three sides and three angles."},
        {"word": "Rectangle", "definition": "A shape with four sides and four right angles (90 degrees)."},
        {"word": "Perimeter", "definition": "The total distance around the outside of a shape."},
        {"word": "Area", "definition": "The amount of space inside a flat shape, measured in square units."},
        {"word": "Parallel", "definition": "Lines that run side by side and never meet, like train tracks."},
        {"word": "Symmetry", "definition": "When one half of a shape is a mirror image of the other half."},
    ],
    "water cycle": [
        {"word": "Evaporation", "definition": "When water heats up and turns from liquid into water vapor (gas)."},
        {"word": "Condensation", "definition": "When water vapor cools down and turns back into tiny water droplets, forming clouds."},
        {"word": "Precipitation", "definition": "Water that falls from clouds as rain, snow, sleet, or hail."},
        {"word": "Collection", "definition": "When water gathers in rivers, lakes, and oceans after precipitation."},
        {"word": "Water Vapor", "definition": "The invisible gas form of water found in the air."},
        {"word": "Transpiration", "definition": "When plants release water vapor through their leaves into the air."},
        {"word": "Groundwater", "definition": "Water that seeps underground and is stored in rocks and soil."},
        {"word": "Runoff", "definition": "Water that flows over the land surface into streams and rivers."},
    ],
    "plants": [
        {"word": "Photosynthesis", "definition": "The process plants use to make food from sunlight, water, and carbon dioxide."},
        {"word": "Chlorophyll", "definition": "The green pigment in leaves that captures sunlight for photosynthesis."},
        {"word": "Root", "definition": "The part of a plant that grows underground and absorbs water and nutrients."},
        {"word": "Stem", "definition": "The main body of a plant that supports leaves and carries water and food."},
        {"word": "Pollination", "definition": "The transfer of pollen from one flower to another, allowing plants to make seeds."},
        {"word": "Germination", "definition": "When a seed begins to grow and sprout into a new plant."},
        {"word": "Nutrients", "definition": "Substances in the soil that plants need to grow healthy and strong."},
        {"word": "Carbon Dioxide", "definition": "A gas in the air that plants take in and use to make food."},
    ],
    "human body": [
        {"word": "Skeleton", "definition": "The framework of bones that supports and protects the body."},
        {"word": "Muscles", "definition": "Body tissues that contract and relax to produce movement."},
        {"word": "Heart", "definition": "The organ that pumps blood throughout the body."},
        {"word": "Lungs", "definition": "Organs that take in oxygen and release carbon dioxide when we breathe."},
        {"word": "Digestion", "definition": "The process of breaking down food into nutrients the body can use."},
        {"word": "Brain", "definition": "The organ that controls thinking, feeling, and all body functions."},
        {"word": "Blood", "definition": "The liquid that carries oxygen and nutrients to all parts of the body."},
        {"word": "Organs", "definition": "Parts of the body that have specific important jobs, like the heart or lungs."},
    ],
}

_FALLBACK_SLIDES = {
    "fractions": [
        {"title": "What Are Fractions?", "content": "A fraction represents a part of a whole. When we cut a pizza into 4 equal slices and eat 1 slice, we have eaten 1/4 of the pizza. Fractions help us describe parts of things."},
        {"title": "Parts of a Fraction", "content": "Every fraction has two numbers. The top number is called the numerator - it tells how many parts we have. The bottom number is called the denominator - it tells how many equal parts the whole is divided into."},
        {"title": "Types of Fractions", "content": "A proper fraction has a smaller numerator than denominator, like 2/5. An improper fraction has a larger numerator, like 7/4. A mixed number combines a whole number with a fraction, like 1 and 3/4."},
        {"title": "Equivalent Fractions", "content": "Equivalent fractions look different but have the same value. For example, 1/2 is the same as 2/4 or 3/6. You can find equivalent fractions by multiplying or dividing both the numerator and denominator by the same number."},
        {"title": "Adding Fractions", "content": "To add fractions with the same denominator, just add the numerators: 1/5 + 2/5 = 3/5. If denominators are different, first find a common denominator, then add."},
        {"title": "Fractions in Daily Life", "content": "We use fractions every day! Sharing food equally, measuring ingredients for cooking, telling time (half past, quarter to), and measuring distances all involve fractions."},
    ],
}

_FALLBACK_READING = {
    "fractions": "Fractions are numbers that show parts of a whole. When you divide something into equal pieces, each piece is a fraction. The top number is called the numerator and it tells us how many pieces we have. The bottom number is called the denominator and it tells us how many total equal pieces there are. For example, if a cake is cut into 8 slices and you eat 3, you have eaten three-eighths or 3/8 of the cake. Fractions are used every day when we share things equally, tell time, or measure ingredients for cooking.",
}


def _get_fallback_vocabulary(topic, subject):
    """Get topic-specific vocabulary fallback when AI is unavailable"""
    topic_lower = topic.lower().strip()
    
    # Try exact match first
    if topic_lower in _FALLBACK_VOCABULARY:
        return _FALLBACK_VOCABULARY[topic_lower]
    
    # Try partial match (e.g. "adding fractions" matches "fractions")
    for key, words in _FALLBACK_VOCABULARY.items():
        if key in topic_lower or topic_lower in key:
            return words
    
    # Generic fallback about the topic itself
    return [
        {"word": topic, "definition": f"This is an important concept in {subject} that students learn about."},
        {"word": f"Understanding {topic}", "definition": f"{topic} involves learning key ideas and applying them to solve problems."},
        {"word": f"Exploring {topic}", "definition": f"We study {topic} to build knowledge and skills that help us in everyday life."},
        {"word": f"Applying {topic}", "definition": f"We can use what we learn about {topic} in real-world situations."},
        {"word": f"Key Ideas in {topic}", "definition": f"Every topic has important ideas. Ask your teacher about the key concepts of {topic}."},
        {"word": f"Practice", "definition": f"Practice helps us get better at {topic}. Try exercises and ask questions."},
    ]


def _get_fallback_slides(topic, subject):
    """Get topic-specific slides fallback when AI is unavailable"""
    topic_lower = topic.lower().strip()
    
    # Try exact or partial match
    for key, slides in _FALLBACK_SLIDES.items():
        if key in topic_lower or topic_lower in key:
            return slides
    
    # Generic but educational fallback
    return [
        {"title": f"What is {topic}?", "content": f"{topic} is an important topic in {subject}. Understanding {topic} helps us make sense of the world around us and solve real problems."},
        {"title": f"Why Learn {topic}?", "content": f"Learning about {topic} builds important skills. It connects to many other subjects and helps us think critically about everyday situations."},
        {"title": f"Key Concepts of {topic}", "content": f"Every topic has key concepts to master. When studying {topic}, focus on understanding the main ideas first, then practice with examples."},
        {"title": f"Real Life and {topic}", "content": f"We can see {topic} in action in our daily lives. Look around you and think about where {topic} applies - you might be surprised!"},
        {"title": f"Practice Makes Perfect", "content": f"The best way to master {topic} is through practice. Try different exercises, ask questions, and work with classmates to deepen your understanding."},
    ]


def _get_fallback_reading(topic, subject):
    """Get topic-specific reading passage fallback when AI is unavailable"""
    topic_lower = topic.lower().strip()
    
    # Try exact or partial match
    for key, text in _FALLBACK_READING.items():
        if key in topic_lower or topic_lower in key:
            return text
    
    # Generic educational passage
    return f"{topic} is a fascinating area of study in {subject}. Students learn about {topic} because it helps them understand important ideas and develop useful skills. When studying {topic}, it is helpful to start with the basic concepts and build up to more complex ideas step by step. Practicing with examples and exercises is one of the best ways to get better. Real-world connections make {topic} more interesting and easier to remember. Keep asking questions and exploring - that is how great learners grow!"


@app.route('/api/generate/video', methods=['POST'])
@login_required_json
def generate_video():
    """
    Generate educational videos with ElevenLabs AI narration.
    
    Auto-generate from topic:
    {
        "topic": "Water Cycle",
        "type": "vocabulary" | "slideshow" | "reading",
        "video_type": "vocabulary" | "slideshow" | "reading",  // alternative key
        "subject": "Science",
        "grade": "Grade 7",
        "voice": "rachel",
        "color_scheme": "ocean"
    }
    
    OR manual content:
    {
        "type": "vocabulary",
        "title": "Week 5 Vocabulary",
        "words": [{"word": "...", "definition": "..."}],
        "voice": "rachel"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        video_type = data.get('type') or data.get('video_type', 'vocabulary')
        title = data.get('title', data.get('topic', 'Educational Video'))
        with_audio = data.get('with_audio', True)
        color_scheme = data.get('color_scheme', 'default')
        voice = data.get('voice', 'rachel')
        topic = data.get('topic')
        subject = data.get('subject', 'English')
        grade = data.get('grade', 'Grade 7')
        
        # Clean topic: strip common prefixes like "create a video about..."
        # so the AI focuses on the actual subject matter
        if topic:
            import re as _re
            # Remove phrases like "create/make/generate a/an video/slideshow/reading about/on/for"
            cleaned = _re.sub(
                r'^(?:(?:create|make|generate|build|produce)\s+)?'
                r'(?:a\s+|an\s+)?'
                r'(?:vocabulary\s+)?(?:video|slideshow|reading\s+video|animation)?\s*'
                r'(?:about|on|for|regarding|of|explaining)?\s*',
                '', topic, flags=_re.IGNORECASE
            ).strip()
            if cleaned:
                topic = cleaned
        
        # Auto-generate content from topic using AI
        if topic and not data.get('words') and not data.get('slides') and not data.get('text'):
            from gemini_integration import chat as ai_chat
            
            if video_type == 'vocabulary':
                # Generate vocabulary words from topic
                prompt = f"""Generate 8-10 vocabulary words directly related to the topic "{topic}" for a {grade} {subject} class.

IMPORTANT: The words must be actual terms/concepts about {topic} itself, NOT about videos or media.
For example, if the topic is "Fractions", generate words like "Numerator", "Denominator", "Improper Fraction", etc.

Return ONLY a valid JSON array of objects with 'word' and 'definition' keys.
Example format:
[
    {{"word": "Term1", "definition": "Brief definition for young students"}},
    {{"word": "Term2", "definition": "Another brief definition"}}
]

Keep definitions simple (1-2 sentences) for young learners.
Return ONLY the JSON array, no other text."""

                try:
                    content_result = ai_chat(prompt)
                    app.logger.info(f"AI vocab result for '{topic}': success={content_result.get('success') if content_result else 'None'}")
                    if content_result and content_result.get('success'):
                        import json, re
                        content = content_result.get('response', '')
                        # Extract JSON from response
                        json_match = re.search(r'\[[\s\S]*\]', content)
                        if json_match:
                            words = json.loads(json_match.group())
                            app.logger.info(f"AI generated {len(words)} vocabulary words for '{topic}'")
                            result = VideoGenerator.generate_vocabulary_video(
                                words=words,
                                title=f"{grade} {subject}: {topic}",
                                with_audio=with_audio,
                                color_scheme=color_scheme,
                                voice=voice
                            )
                            return jsonify(result)
                        else:
                            app.logger.warning(f"No JSON array found in AI response for '{topic}': {content[:200]}")
                    else:
                        app.logger.warning(f"AI failed for vocab '{topic}': {content_result.get('error', 'unknown') if content_result else 'None'}")
                except Exception as e:
                    app.logger.warning(f"AI generation failed, using fallback: {e}")
                
                # Rich fallback: topic-specific vocabulary when AI is unavailable
                words = _get_fallback_vocabulary(topic, subject)
                
            elif video_type == 'slideshow':
                # Generate slides from topic
                prompt = f"""Create 5-6 educational slides that TEACH the topic "{topic}" to {grade} {subject} students.

IMPORTANT: The slides must explain {topic} itself with actual educational content. Do NOT write about creating videos or media.
For example, if the topic is "Fractions", create slides explaining what fractions are, types of fractions, how to add them, etc.

Return ONLY a valid JSON array of objects with 'title' and 'content' keys.
Example format:
[
    {{"title": "Introduction", "content": "Brief introduction text (2-3 sentences)"}},
    {{"title": "Key Concept", "content": "Main explanation (2-3 sentences)"}}
]

Make content simple for young learners. Return ONLY the JSON array."""

                try:
                    content_result = ai_chat(prompt)
                    app.logger.info(f"AI slideshow result for '{topic}': success={content_result.get('success') if content_result else 'None'}")
                    if content_result and content_result.get('success'):
                        import json, re
                        content = content_result.get('response', '')
                        json_match = re.search(r'\[[\s\S]*\]', content)
                        if json_match:
                            slides = json.loads(json_match.group())
                            app.logger.info(f"AI generated {len(slides)} slides for '{topic}'")
                            result = VideoGenerator.generate_slideshow_video(
                                slides=slides,
                                title=f"{grade} {subject}: {topic}",
                                with_audio=with_audio,
                                color_scheme=color_scheme,
                                voice=voice
                            )
                            return jsonify(result)
                        else:
                            app.logger.warning(f"No JSON array found in AI response for slides '{topic}': {content[:200]}")
                    else:
                        app.logger.warning(f"AI failed for slides '{topic}': {content_result.get('error', 'unknown') if content_result else 'None'}")
                except Exception as e:
                    app.logger.warning(f"AI generation failed, using fallback: {e}")
                
                # Rich fallback slides
                slides = _get_fallback_slides(topic, subject)
                
            elif video_type == 'reading':
                # Generate reading text from topic
                prompt = f"""Write a short educational passage (4-6 sentences) that TEACHES {grade} students about "{topic}" in {subject}.

IMPORTANT: Write actual educational content about {topic} itself. Do NOT write about creating videos or media.
For example, if the topic is "Fractions", write a passage explaining what fractions are and how they are used.

Write ONLY the passage text, suitable for a reading exercise. Use simple vocabulary appropriate for young learners.
Do not include any titles or formatting, just the plain text passage."""

                try:
                    content_result = ai_chat(prompt)
                    app.logger.info(f"AI reading result for '{topic}': success={content_result.get('success') if content_result else 'None'}")
                    if content_result and content_result.get('success'):
                        text = content_result.get('response', '').strip()
                        if text:
                            result = VideoGenerator.generate_reading_video(
                                text=text,
                                title=f"Reading: {topic}",
                                speed=data.get('speed', 'normal'),
                                color_scheme=color_scheme,
                                voice=voice
                            )
                            return jsonify(result)
                    else:
                        app.logger.warning(f"AI failed for reading '{topic}': {content_result.get('error', 'unknown') if content_result else 'None'}")
                except Exception as e:
                    app.logger.warning(f"AI generation failed, using fallback: {e}")
                
                # Rich fallback text
                text = _get_fallback_reading(topic, subject)
            
            # Generate based on type
            if video_type == 'vocabulary':
                result = VideoGenerator.generate_vocabulary_video(
                    words=words,
                    title=f"{grade} {subject}: {topic}",
                    with_audio=with_audio,
                    color_scheme=color_scheme,
                    voice=voice
                )
            elif video_type == 'slideshow':
                result = VideoGenerator.generate_slideshow_video(
                    slides=slides,
                    title=f"{grade} {subject}: {topic}",
                    with_audio=with_audio,
                    color_scheme=color_scheme,
                    voice=voice
                )
            else:
                result = VideoGenerator.generate_reading_video(
                    text=text,
                    title=f"Reading: {topic}",
                    speed=data.get('speed', 'normal'),
                    color_scheme=color_scheme,
                    voice=voice
                )
            return jsonify(result)
        
        # Manual content provided
        if video_type == 'vocabulary':
            words = data.get('words', [])
            if not words:
                return jsonify({"success": False, "error": "No words provided for vocabulary video"}), 400
            
            result = VideoGenerator.generate_vocabulary_video(
                words=words,
                title=title,
                with_audio=with_audio,
                color_scheme=color_scheme,
                voice=voice
            )
            
        elif video_type == 'slideshow':
            slides = data.get('slides', [])
            if not slides:
                return jsonify({"success": False, "error": "No slides provided"}), 400
            
            result = VideoGenerator.generate_slideshow_video(
                slides=slides,
                title=title,
                with_audio=with_audio,
                color_scheme=color_scheme,
                voice=voice
            )
            
        elif video_type == 'reading':
            text = data.get('text', '')
            if not text:
                return jsonify({"success": False, "error": "No text provided for reading video"}), 400
            
            speed = data.get('speed', 'normal')
            result = VideoGenerator.generate_reading_video(
                text=text,
                title=title,
                speed=speed,
                color_scheme=color_scheme,
                voice=voice
            )
            
        else:
            return jsonify({"success": False, "error": f"Unknown video type: {video_type}"}), 400
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error generating video: {str(e)}")
        return jsonify({"success": False, "error": f"Failed to generate video: {str(e)}"}), 500


@app.route('/api/regenerate-cbc', methods=['POST'])
def regenerate_cbc_parsed_json():
    parser_script = os.path.join(app.root_path, "cbc_parser.py")
    if not os.path.exists(parser_script):
        return jsonify({
            "ok": False,
            "message": "cbc_parser.py was not found in the project root."
        }), 404

    try:
        result = subprocess.run(
            [sys.executable, parser_script],
            cwd=app.root_path,
            capture_output=True,
            text=True,
            timeout=300,
            check=False
        )

        if result.returncode != 0:
            return jsonify({
                "ok": False,
                "message": "CBC parsing failed.",
                "stderr": (result.stderr or "").strip(),
                "stdout": (result.stdout or "").strip()
            }), 500

        return jsonify({
            "ok": True,
            "message": "CBC parsed JSON regenerated successfully.",
            "stdout": (result.stdout or "").strip()
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "ok": False,
            "message": "CBC parsing timed out. Please try again."
        }), 504

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    _lazy_import_weasyprint()
    content = request.json.get("html", "")
    if not HTML:
        return jsonify({"error": "PDF export not available - WeasyPrint not installed"}), 503
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        HTML(string=content).write_pdf(tmp_pdf.name)
        return send_file(tmp_pdf.name, as_attachment=True, download_name="lesson_plan.pdf")


# --- GEMINI AI ENDPOINTS ---

@app.route('/api/gemini/status', methods=['GET'])
def gemini_status():
    """Check AI services availability and status (Gemini with OpenRouter fallback)"""
    services_status = get_ai_services_status()
    active_service = get_active_ai_name()
    
    # Determine overall status
    is_available = is_gemini_available() or is_openrouter_available()
    
    return jsonify({
        "available": is_available,
        "active_service": active_service,
        "services": {
            "gemini": {
                "available": is_gemini_available(),
                "status": "Ready" if is_gemini_available() else "Not initialized"
            },
            "openrouter": {
                "available": is_openrouter_available(),
                "status": "Ready (Fallback)" if is_openrouter_available() else "Not initialized"
            }
        },
        "fallback_chain": "Gemini → OpenRouter",
        "message": f"AI services ready. Using: {active_service}" if is_available else "No AI services available. Some features will be limited."
    })


@app.route('/api/gemini/activities', methods=['POST'])
@limiter.limit("10 per hour")
@login_required_json
def gemini_activities():
    """Generate starter activities using AI (Gemini or OpenRouter fallback)"""
    try:
        data = request.get_json()
        subject = data.get('subject', 'Mathematics')
        grade = data.get('grade', 'Grade 7')
        topic = data.get('topic', 'General Topic')
        count = data.get('count', 3)
        
        if not (is_gemini_available() or is_openrouter_available()):
            return jsonify({
                "success": False,
                "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
            }), 503
        
        result = generate_activities(subject, grade, topic, count)
        
        if result and result.get("success"):
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Failed to generate activities")}), 400
            
    except Exception as e:
        app.logger.error(f"Error in gemini_activities: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/gemini/questions', methods=['POST'])
@limiter.limit("10 per hour")
@login_required_json
def gemini_questions():
    """Generate assessment questions using AI (Gemini or OpenRouter fallback)"""
    try:
        data = request.get_json()
        subject = data.get('subject', 'Mathematics')
        grade = data.get('grade', 'Grade 7')
        topic = data.get('topic', 'General Topic')
        count = data.get('count', 5)
        
        if not (is_gemini_available() or is_openrouter_available()):
            return jsonify({
                "success": False,
                "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
            }), 503
        
        result = generate_questions(subject, grade, topic, count)
        
        if result and result.get("success"):
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Failed to generate questions")}), 400
            
    except Exception as e:
        app.logger.error(f"Error in gemini_questions: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/gemini/learning-outcomes', methods=['POST'])
@limiter.limit("10 per hour")
@login_required_json
def gemini_learning_outcomes():
    """Generate learning outcomes using AI (Gemini or OpenRouter fallback)"""
    try:
        data = request.get_json()
        subject = data.get('subject', 'Mathematics')
        grade = data.get('grade', 'Grade 7')
        topic = data.get('topic', 'General Topic')
        
        if not (is_gemini_available() or is_openrouter_available()):
            return jsonify({
                "success": False,
                "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
            }), 503
        
        result = generate_outcomes(subject, grade, topic)
        
        if result and result.get("success"):
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Failed to generate learning outcomes")}), 400
            
    except Exception as e:
        app.logger.error(f"Error in gemini_learning_outcomes: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/gemini/chat', methods=['POST'])
@limiter.limit("10 per hour")
@login_required_json
def gemini_chat_endpoint():
    """Chat with AI about educational topics (Gemini or OpenRouter fallback)"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', None)
        
        if not message:
            return jsonify({"success": False, "error": "Message is required"}), 400
        
        if not (is_gemini_available() or is_openrouter_available()):
            return jsonify({
                "success": False,
                "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
            }), 503
        
        result = gemini_chat(message, context)
        
        if result and result.get("success"):
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Chat failed")}), 400
            
    except Exception as e:
        app.logger.error(f"Error in gemini_chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/gemini/enhance-lesson', methods=['POST'])
@limiter.limit("10 per hour")
@login_required_json
def enhance_lesson_with_gemini():
    """Enhance lesson plan with AI suggestions (Gemini or OpenRouter fallback)"""
    try:
        data = request.get_json()
        subject = data.get('subject', 'Mathematics')
        grade = data.get('grade', 'Grade 7')
        topic = data.get('topic', 'General Topic')
        duration = data.get('duration', 40)
        base_lesson = data.get('base_lesson', '')
        
        if not (is_gemini_available() or is_openrouter_available()):
            return jsonify({
                "success": False,
                "error": "No AI service available. Please configure Gemini or OpenRouter API keys."
            }), 503
        
        from gemini_integration import enhance_lesson_plan
        enhanced = enhance_lesson_plan(subject, grade, topic, duration, base_lesson)
        
        return jsonify({
            "success": True,
            "enhanced_content": enhanced,
            "original_content": base_lesson
        })
            
    except Exception as e:
        app.logger.error(f"Error in enhance_lesson: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# --- Monitoring and System Health Endpoints ---

def _is_admin():
    """Check if current user has admin privileges (authenticated teacher with admin email)."""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    return session.get("teacher_email") == admin_email


@app.route('/api/system/health', methods=['GET'])
def system_health():
    """Get system health status. Basic status is public; detailed stats require admin."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "unknown",
                "cache": "operational",
                "ai_service": get_active_ai_name() if is_gemini_available() or is_openrouter_available() else "unavailable"
            }
        }
        
        # Check database health if available
        if DB_UTILS_AVAILABLE and db_utilities:
            try:
                if db_utilities["db_health"].check_integrity():
                    health_status["services"]["database"] = "operational"
                    health_status["database_stats"] = db_utilities["db_health"].get_database_stats()
                else:
                    health_status["services"]["database"] = "compromised"
                    health_status["status"] = "warning"
            except:
                health_status["services"]["database"] = "error"
                health_status["status"] = "warning"
        
        return jsonify(health_status)
    except Exception as e:
        app.logger.error(f"Error in system_health: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/system/monitoring', methods=['GET'])
@login_required_json
def get_monitoring_data():
    """Get monitoring data including rate limit breaches and alerts. Admin only."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Admin access required"}), 403
    if not DB_UTILS_AVAILABLE or not db_utilities:
        return jsonify({"success": False, "error": "Monitoring not available"}), 503
    
    try:
        rate_limit_monitor = db_utilities.get("rate_limit_monitor")
        alert_system = db_utilities.get("alert_system")
        
        monitoring_data = {
            "rate_limit_breaches": rate_limit_monitor.get_breach_summary(hours=24) if rate_limit_monitor else {},
            "recent_alerts": alert_system.get_recent_alerts(limit=10) if alert_system else [],
            "top_violators": rate_limit_monitor.get_top_violators(limit=5) if rate_limit_monitor else {}
        }
        
        return jsonify({"success": True, "data": monitoring_data})
    except Exception as e:
        app.logger.error(f"Error in get_monitoring_data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/system/backup', methods=['POST'])
@login_required_json
@limiter.limit("5 per day")
def trigger_backup():
    """Manually trigger a database backup. Admin only."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Admin access required"}), 403
    if not DB_UTILS_AVAILABLE or not db_utilities:
        return jsonify({"success": False, "error": "Backup not available"}), 503
    
    try:
        db_backup = db_utilities.get("db_backup")
        backup_file = db_backup.create_backup()
        
        return jsonify({
            "success": True,
            "message": "Database backup created successfully",
            "backup_file": backup_file
        })
    except Exception as e:
        app.logger.error(f"Error in trigger_backup: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(error):
    app.logger.warning(f"Page not found: {request.url}")
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Resource not found"}), 404
    return render_template("error_404.html"), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.error(f"Server error on {request.url}: {str(error)}")
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Internal server error. Please try again later."}), 500
    return render_template("error_500.html"), 500


@app.errorhandler(403)
def forbidden(error):
    app.logger.warning(f"Forbidden access to {request.url}")
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Forbidden"}), 403
    flash("You don't have permission to access this resource.", "error")
    return redirect(url_for("home")), 403


@app.errorhandler(429)
def rate_limit_exceeded(error):
    app.logger.warning(f"Rate limit exceeded: {request.remote_addr} on {request.url}")
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Too many requests. Please slow down and try again later."}), 429
    flash("You've made too many requests. Please wait a moment and try again.", "error")
    return redirect(url_for("home")), 429


@app.errorhandler(413)
def request_too_large(error):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Request too large. Maximum size is 16MB."}), 413
    flash("The uploaded file is too large.", "error")
    return redirect(url_for("home")), 413


# --- Run App ---
if __name__ == "__main__":
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=5)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('RippleAI startup')
    
    try:
        port = int(os.getenv("PORT", "5000"))
        is_debug = os.getenv("FLASK_ENV", "development").lower() != "production"
        app.run(host="0.0.0.0", port=port, debug=is_debug, use_reloader=is_debug)
    except KeyboardInterrupt:
        app.logger.info("Shutdown signal received")
    finally:
        # Cleanup background tasks
        if db_scheduler:
            db_scheduler.stop()
            app.logger.info("Background tasks stopped")
