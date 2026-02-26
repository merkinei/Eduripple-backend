import json
import re
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "cbc pdfs"
OUT_FILE = ROOT / "cbc_parsed.json"


def normalize_text(text: str) -> str:
    replacements = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€\x9d": '"',
        "â€“": "-",
        "â€”": "-",
        "Â": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def meaningful_line(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned:
        return False
    if re.fullmatch(r"[ivxlcdm]+", cleaned.lower()):
        return False
    if re.fullmatch(r"\d+", cleaned):
        return False
    if len(cleaned) < 2:
        return False
    return True


def clean_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if meaningful_line(line)]
    lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
    return lines


def parse_subject_grade(stem: str) -> tuple[str, int | None]:
    stem = re.sub(r"\.pdf$", "", stem, flags=re.IGNORECASE)
    normalized = stem.replace("-", "_")
    grade_match = re.search(r"_grade_(\d+)", normalized, re.IGNORECASE)
    grade = int(grade_match.group(1)) if grade_match else None
    subject = re.sub(r"_grade_\d+", "", normalized, flags=re.IGNORECASE)
    subject = subject.replace("_", " ").strip().title()
    return subject, grade


def extract_first_field(lines: list[str], field: str) -> str:
    pattern = re.compile(rf"^{re.escape(field)}\s*[:\-]?\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip(" .:-")
        normalized = value.strip(" ,:-").lower()
        if len(value) < 3:
            continue
        if normalized in {"the", "the learner", "learner", "sub strand", "strand"}:
            continue
        if normalized.startswith("the learner"):
            continue
        if re.search(r"summary of|sub strands|grade\s*\d|\.\.\.", value, re.IGNORECASE):
            continue
        return value
    return ""


def looks_like_heading(line: str) -> bool:
    text = line.strip()
    if len(text) < 6 or len(text) > 120:
        return False
    if re.search(r"learner|suggested|assessment|question|experience", text, re.IGNORECASE):
        return False
    return bool(re.match(r"^\d+\.\d+(?:\.\d+)?\s+", text))


def extract_strand_substrand(lines: list[str]) -> tuple[str, str]:
    strand = extract_first_field(lines, "Strand")
    substrand = extract_first_field(lines, "Sub-strand")

    headings = [line for line in lines if looks_like_heading(line)]

    if not strand:
        for line in headings:
            if re.match(r"^\d+\.\d+\s+", line):
                strand = line
                break

    if not substrand and strand:
        parent = re.match(r"^(\d+\.\d+)\b", strand)
        if parent:
            prefix = parent.group(1) + "."
            for line in headings:
                if line.startswith(prefix):
                    substrand = line
                    break

    return strand, substrand


def extract_question_lines(lines: list[str], full_text: str = "") -> list[str]:
    """Extract Key Inquiry Questions from text.
    Searches for complete question patterns, including partial word matches."""
    questions = []
    
    # Pattern 1: explicit "Key Inquiry Question" sections
    kiq_pattern = r"(?:Key\s+Inquiry\s+Questions?|Inquiry\s+Questions?)\s*[:\-]?\s*([^?\n]*\?[^\n]*(?:\n[^?\n]*\?[^\n]*)*)"
    matches = re.findall(kiq_pattern, full_text, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        items = re.split(r"\n|;", match)
        for item in items:
            item = item.strip(" -•").strip()
            if 8 <= len(item) <= 300 and "?" in item:
                questions.append(item)
    
    # Pattern 2: Look for questions directly in text (lines ending with ?)
    # But be more aggressive - accept partial lines that look like questions
    for line in lines:
        line = line.strip()
        if "?" not in line:
            continue
        
        # Skip metadata/boilerplate
        if re.search(r"table|contents|page \d|grade|subject|strand", line, re.IGNORECASE):
            continue
        
        # Accept if it looks like a question (8-300 chars, has ?)
        if 8 <= len(line) <= 300:
            questions.append(line)
    
    # Pattern 3: Search full text for sentences ending with ?
    sentence_pattern = r"[A-Z][^?]*\?"
    matches = re.findall(sentence_pattern, full_text)
    for match in matches:
        match = match.strip()
        if 8 <= len(match) <= 300 and not re.search(r"table|page|grade|subject", match, re.IGNORECASE):
            questions.append(match)
    
    # Deduplicate and clean
    unique = []
    seen = set()
    for q in questions:
        # Normalize: remove extra spaces, ensure ends with ?
        q_clean = re.sub(r"\s+", " ", q).strip()
        if not q_clean.endswith("?"):
            q_clean += "?"
        key = q_clean.lower()
        if key not in seen and len(q_clean) >= 8:
            unique.append(q_clean)
            seen.add(key)
    
    return unique[:15]


def extract_block_items(text: str, heading_regex: str, stop_regex: str) -> list[str]:
    heading = re.search(heading_regex, text, re.IGNORECASE)
    if not heading:
        return []

    start = heading.end()
    block = text[start:]
    stop = re.search(stop_regex, block, re.IGNORECASE)
    if stop:
        block = block[: stop.start()]

    candidates = []
    for raw in re.split(r"\n|\r", block):
        line = re.sub(r"\s+", " ", raw).strip(" -•\t")
        if len(line) < 6:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if re.search(r"^strand$|^sub[- ]?strand$", line, re.IGNORECASE):
            continue
        candidates.append(line)

    unique = []
    seen = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique[:40]


def extract_competencies(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        if re.search(r"core competencies?\s*:", line, re.IGNORECASE):
            value = re.split(r":", line, maxsplit=1)[-1].strip()
            if value:
                found.append(value)
        elif re.search(
            r"critical thinking|communication and collaboration|digital literacy|self-efficacy|learning to learn|citizenship|creativity",
            line,
            re.IGNORECASE,
        ):
            found.append(line)

    unique = []
    seen = set()
    for item in found:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:20]


def extract_values(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        if re.search(r"values?\s*:", line, re.IGNORECASE):
            value = re.split(r":", line, maxsplit=1)[-1].strip()
            if value:
                found.append(value)
        elif re.search(r"respect|integrity|unity|responsibility|honesty|perseverance|patriotism", line, re.IGNORECASE):
            found.append(line)

    unique = []
    seen = set()
    for item in found:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:20]


def extract_suggested_learning_experiences(text: str) -> list[str]:
    """Extract Suggested Learning Experiences from text.
    Uses multiple patterns to find learning activities."""
    if not isinstance(text, str):
        return []
    
    experiences = []
    
    # Pattern 1: Explicit "Suggested Learning Experiences" section
    sle_pattern = r"(?:Suggested\s+Learning\s+Experiences?|Learning\s+Experiences?)\s*[:\-]?\s*([^?]*?)(?=\n(?:Key\s+Inquiry|Core\s+Competencies|Values|Assessment|Specific\s+Learning|Strand|$))"
    matches = re.findall(sle_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if matches:
        for match in matches:
            # Split by common separators
            items = re.split(r"\n\s*[•\-\*]\s+|\n\s*\d+\)[:\s]+|\n(?=[A-Z])", match)
            for item in items:
                item = re.sub(r"\s+", " ", item).strip()
                # Remove numbering patterns
                item = re.sub(r"^\d+\.\d+\.?\d*\s*", "", item)
                item = re.sub(r"^\(\d+\s+lessons?\)\s*", "", item)
                item = re.sub(r"^•\s*", "", item)
                
                if 15 <= len(item) <= 300:
                    # Must look like a learning activity
                    if any(verb in item.lower() for verb in ["learner", "listen", "read", "write", "discuss", "present", "create", "practice", "observe", "identify", "demonstrate", "group", "pair", "engage"]):
                        experiences.append(item)
    
    # Pattern 2: Look for lines that start with action verbs related to learning
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if 15 <= len(line) <= 300:
            # Check for activity-related keywords
            lower = line.lower()
            if any(phrase in lower for phrase in ["the learner", "learners", "listen to", "read", "write", "discuss", "group activity", "pair work", "engage", "observe", "reflect", "role play"]):
                # Skip metadata
                if not re.search(r"strand|page|assessment|rubric|grade|subject|table", lower):
                    experiences.append(line)
    
    # Pattern 3: Look for bulleted/numbered items that look like activities
    activity_pattern = r"(?:^|\n)\s*[•\-\*]\s+([A-Z][^?\n]{15,300})"
    matches = re.findall(activity_pattern, text, re.MULTILINE)
    for match in matches:
        if any(verb in match.lower() for verb in ["listen", "read", "write", "discuss", "practice", "observe", "identify", "learner"]):
            experiences.append(match.strip())
    
    # Deduplicate
    unique = []
    seen = set()
    for exp in experiences:
        exp = re.sub(r"\s+", " ", exp).strip()
        if len(exp) >= 15:
            key = exp.lower()[:80]  # Use first 80 chars for dedup
            if key not in seen:
                unique.append(exp)
                seen.add(key)
    
    return unique[:15]


def extract_learning_outcomes(text: str, lines: list[str]) -> list[str]:
    from_heading = extract_block_items(
        text,
        r"specific\s+learning\s+outcomes?\s*[:\-]?",
        r"key\s+inquiry\s+questions?|suggested\s+learning\s+experiences|core\s+competencies|values",
    )
    if from_heading:
        return from_heading

    by_end_blocks = re.findall(
        r"By\s+the\s+end[^\n:]{0,120}:\s*(.+?)(?=\n\s*(?:Core competencies|Values|Key Inquiry|Suggested Learning|Strand|Sub Strand|$))",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if by_end_blocks:
        captured = []
        for block in by_end_blocks:
            pieces = re.split(r"\n|\r|\d+\.\s+|[•\-]\s+", block)
            for part in pieces:
                line = re.sub(r"\s+", " ", part).strip(" .:-")
                if len(line) < 10 or len(line) > 220:
                    continue
                if re.search(r"suggested learning|core competencies|key inquiry", line, re.IGNORECASE):
                    continue
                if re.search(r"^(identify|explain|describe|demonstrate|apply|discuss|use|analyse|analyze|construct|create|differentiate|outline|state|classify|compare)\b", line, re.IGNORECASE):
                    captured.append(line)

        if captured:
            unique = []
            seen = set()
            for item in captured:
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                unique.append(item)
            return unique[:30]

    # Fallback: sentence-like lines that start with action verbs and are not boilerplate
    candidates = []
    for line in lines:
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        if len(line) < 20 or len(line) > 220:
            continue
        if re.search(r"table of contents|summary of strands|lesson allocation|general learning outcomes", line, re.IGNORECASE):
            continue
        if re.match(r"^(Identify|Explain|Describe|Demonstrate|Apply|Discuss|Use|Analyse|Analyze|Construct|Create|Differentiate)\b", line):
            candidates.append(line)

    unique = []
    seen = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:30]


def is_relevant_page(page_text: str) -> bool:
    """Identify if a page contains curriculum content (not TOC, cover, blank, etc)."""
    text_lower = page_text.lower()
    
    # Skip pages that are clearly not curriculum content
    if re.search(r"table of contents|contents|acknowledgements|introduction|disclaimer", text_lower):
        return False
    if len(page_text.strip()) < 100:  # Skip mostly blank pages
        return False
    if page_text.count("\n") < 3:  # Skip pages with very few lines
        return False
        
    # Keep pages with curriculum keywords
    curriculum_keywords = [
        "strand", "sub strand", "substrand", "learning outcome", "key inquiry",
        "core competency", "value", "suggested learning", "assessment",
        "specific learning outcome", "competencies"
    ]
    
    has_curriculum = any(keyword in text_lower for keyword in curriculum_keywords)
    return has_curriculum


def extract_relevant_pages(doc) -> list[str]:
    """Extract from pages 12+ to capture all curriculum content.
    Skip only cover/TOC pages (1-11) and heavily process all remaining pages."""
    relevant_texts = []
    
    # Scan pages 12+ (indices 11+) - these have the curriculum content
    # Don't limit to 100 pages - get everything
    try:
        for idx in range(11, len(doc)):
            try:
                text = doc[idx].get_text()
                normalized = normalize_text(text)
                # Keep all non-blank pages - we'll filter during extraction
                if normalized.strip():
                    relevant_texts.append(normalized)
            except:
                # Skip problematic pages
                continue
    except:
        pass
    
    return relevant_texts


def parse_pdf(path: Path) -> dict:
    with path.open("rb") as file_obj:
        doc = fitz.open(stream=file_obj.read(), filetype="pdf")
        
        # Extract only from relevant pages
        relevant_pages = extract_relevant_pages(doc)
        if not relevant_pages:
            # Fallback: use all pages if none marked as relevant
            relevant_pages = [normalize_text(page.get_text()) for page in doc]
        
        full_text = "\n".join(relevant_pages)

    full_text = normalize_text(full_text)
    lines = clean_lines(full_text)

    subject, grade = parse_subject_grade(path.stem)
    strand, substrand = extract_strand_substrand(lines)

    learning_outcomes = extract_learning_outcomes(full_text, lines)
    key_inquiry_questions = extract_question_lines(lines, full_text)
    core_competencies = extract_competencies(lines)
    values = extract_values(lines)
    suggested_learning_experiences = extract_suggested_learning_experiences(full_text)

    return {
        "subject": subject,
        "grade": grade,
        "strand": strand,
        "substrand": substrand,
        "learning_outcomes": learning_outcomes,
        "key_inquiry_questions": key_inquiry_questions,
        "core_competencies": core_competencies,
        "values": values,
        "suggested_learning_experiences": suggested_learning_experiences,
        "source_file": path.stem,
    }


def main() -> None:
    if not PDF_DIR.exists():
        raise FileNotFoundError(f"PDF directory not found: {PDF_DIR}")

    parsed = {}
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    for pdf in pdfs:
        parsed[pdf.stem] = parse_pdf(pdf)

    OUT_FILE.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(parsed)} files -> {OUT_FILE}")


if __name__ == "__main__":
    main()
