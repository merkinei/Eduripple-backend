"""Template-based lesson, scheme, and rubric generator using curriculum database."""

import re
import math
from datetime import datetime, timedelta
from curriculum_db import get_curriculum


def query_curriculum(subject, grade):
    """Query curriculum database for subject and grade."""
    # Normalize grade
    grade_normalized = f"Grade {grade}" if grade and not grade.startswith("Grade") else grade
    
    all_curriculum = get_curriculum()
    
    if not all_curriculum:
        return None
    
    # Map common subject name variations
    subject_map = {
        "mathematics": "maths",
        "math": "maths",
        "science": "intergrated_science",
        "integrated science": "intergrated_science",
        "social studies": "social_studies",
        "creative arts": "creative_arts",
        "agriculture": "agriculture_and_nutrition",
        "agriculture and nutrition": "agriculture_and_nutrition",
        "creative arts and sports": "creative_arts_and_sports",
        "pre-technical studies": "pre_technical_studies",
        "pre technical studies": "pre_technical_studies",
        "indigenous languages": "indigenious_languages",
        "indigenous language": "indigenious_languages",
    }
    
    subject_normalized = subject.lower()
    if subject_normalized in subject_map:
        subject_normalized = subject_map[subject_normalized]
    
    # Try exact match (with underscores)
    subject_with_underscore = subject_normalized.replace(" ", "_")
    for entry in all_curriculum:
        if (entry['subject'].lower() == subject_with_underscore and 
            entry['grade'].lower() == grade_normalized.lower()):
            return entry
    
    # Try without underscores
    for entry in all_curriculum:
        if (entry['subject'].lower().replace("_", " ") == subject_normalized and 
            entry['grade'].lower() == grade_normalized.lower()):
            return entry
    
    # Try partial match (checks if subject keywords are in database subject)
    for entry in all_curriculum:
        entry_subject = entry['subject'].lower().replace("_", " ")
        # Check if any key words match
        if (any(word in entry_subject for word in subject_normalized.split()) and
            entry['grade'].lower() == grade_normalized.lower()):
            return entry
    
    return None


def _extract_lesson_count(strand_text):
    """
    Extract the number of required lessons from the strand field.
    
    CBC strand fields often contain lesson counts like:
      '1.3 Fractions (9 lessons)'
      '1.2 Netball (25 lessons)'
      '1.2 Computer Hardware (11 lessons)'
    
    Returns the lesson count (int), defaulting to 1 if not found.
    """
    if not strand_text:
        return 1
    # Handle variations like (9 lessons), ( 25 lessons), (6 Lessons), (8  lessons)
    match = re.search(r'\(\s*(\d+)\s*lessons?\s*\)', strand_text, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    return 0  # Return 0 to signal "not specified" (caller will estimate)


def _extract_strand_topic(strand_text):
    """
    Extract the clean topic name from the strand field.
    
    '1.3 Fractions (9 lessons)' -> 'Fractions'
    '1.2 Water Harvesting and Storage (9 lessons)' -> 'Water Harvesting and Storage'
    """
    if not strand_text:
        return ""
    # Remove lesson count suffix
    cleaned = re.sub(r'\s*\(\d+\s*lessons?\)\s*', '', strand_text, flags=re.IGNORECASE)
    # Remove leading numbering like '1.3 ', '1.3.1 ', '2.1 '
    cleaned = re.sub(r'^[\d]+(?:\.[\d]+)*\s*', '', cleaned).strip()
    return cleaned


def _classify_competency_items(items):
    """
    The CBC PDF parser sometimes mixes values, links-to-other-subjects,
    and pertinent/contemporary issues (PCIs) into the competencies field.
    
    This function separates them into four clean lists:
      - competencies  (actual core competencies)
      - values        (responsibility, respect, unity, love, etc.)
      - links         (link to other subjects)
      - pcis          (pertinent and contemporary issues)
    """
    competencies = []
    values = []
    links = []
    pcis = []
    
    for item in items:
        if not item or not isinstance(item, str) or len(item.strip()) < 4:
            continue
        text = item.strip()
        lowered = text.lower()
        
        # Detect "Link to other subjects/learning areas"
        if re.match(r'^links?\s+to\s+(other\s+)?(subject|learning)', lowered):
            # Clean the prefix
            cleaned = re.sub(r'^links?\s+to\s+(?:other\s+)?(?:subjects?|learning\s+areas?)\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
            if cleaned:
                links.append(cleaned)
            continue
        
        # Detect embedded "Link to other subjects" in middle of text
        if 'link to other' in lowered or 'links to other' in lowered:
            links.append(text)
            continue
        
        # Detect "Pertinent and Contemporary Issues" / PCIs
        if re.match(r'^pertinent\s+(and\s+)?contemporary\s+issues', lowered) or lowered.startswith('pci'):
            cleaned = re.sub(r'^pertinent\s+(?:and\s+)?contemporary\s+issues\s*(?:\(?pcis?\)?)?\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
            if cleaned:
                pcis.append(cleaned)
            continue
        
        # Detect items that START with "Values" (e.g. "Values Responsibility: ...")
        if re.match(r'^values?\s*:?\s+', lowered):
            cleaned = re.sub(r'^values?\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
            if cleaned:
                values.append(cleaned)
            continue
        
        # Items containing value keywords are likely values
        value_keywords = ['respect', 'responsibility', 'unity', 'love', 'patriotism',
                          'integrity', 'peace', 'social justice', 'humility', 'cooperation',
                          'self-esteem', 'self-confidence', 'sharing', 'caring']
        if any(vk in lowered for vk in value_keywords) and len(text) < 200:
            values.append(text)
            continue
        
        # Detect orphaned subject-name fragments that are link continuations
        # These are short items that are just subject names (from split "Link to other subjects" lists)
        subject_names = ['kiswahili', 'french', 'german', 'arabic', 'indigenous languages',
                         'english', 'mathematics', 'integrated science', 'social studies',
                         'pre-technical', 'pre technical', 'creative arts', 'agriculture',
                         'nutrition', 'cre', 'ire', 'hre']
        if len(text) < 80 and any(sn in lowered for sn in subject_names):
            # If it mentions a subject name and talks about teaching/learning, it's a link
            teach_words = ['teach', 'learnt', 'learn', 'relate', 'use ', 'used in',
                           'apply', 'language', 'skills']
            if any(tw in lowered for tw in teach_words) or len(text) < 30:
                links.append(text)
                continue
        
        # Everything else is a genuine competency
        competencies.append(text)
    
    # Deduplicate while preserving order
    competencies = list(dict.fromkeys(competencies))
    values = list(dict.fromkeys(values))
    links = list(dict.fromkeys(links))
    pcis = list(dict.fromkeys(pcis))
    
    return competencies, values, links, pcis


def _distribute_items(items, num_buckets):
    """
    Distribute a list of items evenly across num_buckets.
    Returns a list of lists.
    """
    if not items or num_buckets <= 0:
        return [[] for _ in range(max(1, num_buckets))]
    
    buckets = [[] for _ in range(num_buckets)]
    for i, item in enumerate(items):
        buckets[i % num_buckets].append(item)
    return buckets


def _build_single_lesson_plan(
    lesson_number, total_lessons, subject, grade, topic, strand, substrand,
    outcomes, questions, experiences, competencies, values, duration, date_str,
    links=None, pcis=None
):
    """Build a single lesson plan string for one lesson in a series."""
    current_year = datetime.today().year
    
    # Determine lesson focus description
    if total_lessons > 1:
        lesson_title = f"Lesson {lesson_number} of {total_lessons}"
        if lesson_number == 1:
            focus = "Introduction and foundation concepts"
        elif lesson_number == total_lessons:
            focus = "Consolidation, assessment and review"
        else:
            focus = f"Development and practice (continued)"
    else:
        lesson_title = "Lesson 1 of 1"
        focus = "Complete lesson"
    
    # Format learning outcomes
    if outcomes:
        slo_list = "\n".join([f"- {item}" for item in outcomes])
    else:
        slo_list = "- (Continued from previous lesson)"
    
    # Format key inquiry questions
    if questions:
        kiq_list = "\n".join([f"{i+1}. {item}" for i, item in enumerate(questions)])
    else:
        kiq_list = "- (Refer to key inquiry questions from this strand)"
    
    # Format suggested learning experiences into lesson steps
    lesson_steps = []
    if experiences:
        for exp in experiences[:3]:
            lesson_steps.append(exp)
    
    # Pad with contextual steps if not enough experiences
    step_defaults_intro = [
        f"Introduce key concepts of {topic} through discussion and real-life examples",
        f"Guide learners to explore {topic} through hands-on activities and group work",
        f"Consolidate understanding through practice exercises on {topic}"
    ]
    step_defaults_middle = [
        f"Review previous lesson's concepts on {topic} and address any difficulties",
        f"Deepen understanding through guided practice and problem-solving activities",
        f"Apply concepts to new contexts and real-world situations"
    ]
    step_defaults_end = [
        f"Review all key concepts covered across the {total_lessons} lessons on {topic}",
        f"Assess learner understanding through practical application and peer discussion",
        f"Summarize learning, clarify misconceptions, and extend to real-world connections"
    ]
    
    if lesson_number == 1:
        defaults = step_defaults_intro
    elif lesson_number == total_lessons:
        defaults = step_defaults_end
    else:
        defaults = step_defaults_middle
    
    while len(lesson_steps) < 3:
        lesson_steps.append(defaults[len(lesson_steps)])
    
    # Format competencies (clean — no "Values" or "Link to" prefixes)
    competencies_text = "\n".join([f"- {c}" for c in competencies]) if competencies else "- Critical thinking and problem solving\n- Communication and collaboration\n- Self-efficacy"
    
    # Format values (only actual values like responsibility, respect, etc.)
    values_text = "\n".join([f"- {v}" for v in values]) if values else "- Respect\n- Responsibility\n- Unity"
    
    # Format links to other subjects
    links = links or []
    links_text = "\n".join([f"- {l}" for l in links]) if links else "- (Cross-curricular links as applicable)"
    
    # Format pertinent and contemporary issues (PCIs)
    pcis = pcis or []
    pcis_text = "\n".join([f"- {p}" for p in pcis]) if pcis else "- (Relevant contemporary issues as applicable)"
    
    # Time allocation
    if duration == 35:
        intro_time, dev_time, concl_time = 5, 22, 8
    else:
        intro_time, dev_time, concl_time = 5, 27, 8
    
    # --- Teacher / Learner activities per stage ---

    # Introduction
    if lesson_number == 1:
        teacher_intro = (
            f"Engage learners with a starter activity related to {topic}. "
            f"Assess prior knowledge. "
            f"Relate {topic} to real-life contexts."
        )
        learner_intro = (
            f"Respond to starter questions. "
            f"Share what they already know about {topic}. "
            f"Discuss real-life connections."
        )
    elif lesson_number == total_lessons:
        teacher_intro = (
            f"Quick review of key concepts from previous lessons on {topic}. "
            f"Identify remaining areas of difficulty."
        )
        learner_intro = (
            f"Recall and share key points from previous lessons. "
            f"Ask questions on areas of difficulty."
        )
    else:
        teacher_intro = (
            f"Review key points from Lesson {lesson_number - 1}. "
            f"Address questions from the previous lesson. "
            f"Connect previous learning to today's focus."
        )
        learner_intro = (
            f"Recall previous lesson concepts. "
            f"Answer review questions. "
            f"Listen to today's objectives."
        )
    
    # Lesson Body / Development
    teacher_dev_parts = []
    learner_dev_parts = []
    for i, step in enumerate(lesson_steps[:3]):
        teacher_dev_parts.append(f"Step {i+1}: {step}")
        learner_dev_parts.append(f"Step {i+1}: Participate in guided activities and practice")
    if values:
        teacher_dev_parts.append(f"Emphasize {values[0]}")
    teacher_dev_parts.append("Build critical thinking skills through questioning")
    learner_dev_parts.append("Apply concepts through individual/group tasks")
    learner_dev_parts.append("Collaborate with peers and share findings")
    
    teacher_dev = " ".join(teacher_dev_parts)
    learner_dev = " ".join(learner_dev_parts)
    
    # Conclusion
    if lesson_number < total_lessons:
        teacher_concl = (
            f"Summarize key learning points. "
            f"Preview Lesson {lesson_number + 1}. "
            f"Assign preparatory tasks."
        )
        learner_concl = (
            f"Share what they have learnt. "
            f"Ask questions for clarification. "
            f"Note assignments for next lesson."
        )
    else:
        teacher_concl = (
            f"Summarize all key learning points across the {total_lessons} lessons. "
            f"Celebrate learner progress. "
            f"Connect learning to broader curriculum goals."
        )
        learner_concl = (
            f"Reflect on key takeaways. "
            f"Share achievements and areas of growth. "
            f"Relate learning to everyday life."
        )
    
    resources_cell = "Textbooks, Chalkboard/whiteboard, Learning aids, Reference materials, Student workbooks"
    assessment_intro = "Oral questions, Observation"
    assessment_dev = "Observation, Practical work, Group participation, Oral/written exercises"
    assessment_concl = "Question and answer, Learner self-assessment"
    
    plan = f"""
{'=' * 60}
LESSON PLAN {lesson_number} OF {total_lessons} — {topic.upper()} (TSC-READY)
{focus}
{'=' * 60}

1) ADMINISTRATIVE DETAILS

| School | __________________ | Date | {date_str} |
|--------|-------------------|------|---------|
| Subject | {subject} | Time | {duration} minutes |
| Year | {current_year} | Grade | {grade} |
| Term | __________________ | Lesson | {lesson_title} |
| Roll | __________ | | |

2) STRAND AND SUB-STRAND

Strand: {strand if strand else "__________________"}
Sub-Strand: {substrand if substrand else "__________________"}

3) SPECIFIC LEARNING OUTCOMES (for this lesson)

{slo_list}

4) KEY INQUIRY QUESTIONS (KIQs)

{kiq_list}

5) CORE COMPETENCIES

{competencies_text}

6) VALUES

{values_text}

7) LINK TO OTHER SUBJECTS / LEARNING AREAS

{links_text}

8) PERTINENT AND CONTEMPORARY ISSUES (PCIs)

{pcis_text}

9) ORGANIZATION OF LEARNING

- Whole class discussion
- Group work
- Individual practice
- Pair activities

10) LESSON DEVELOPMENT

| Lesson Stage | Teacher Activities | Learner Activities | Learning Resources | Assessment |
|---|---|---|---|---|
| Introduction ({intro_time} min) | {teacher_intro} | {learner_intro} | {resources_cell} | {assessment_intro} |
| Lesson Body / Development ({dev_time} min) | {teacher_dev} | {learner_dev} | {resources_cell} | {assessment_dev} |
| Conclusion ({concl_time} min) | {teacher_concl} | {learner_concl} | {resources_cell} | {assessment_concl} |

11) EXTENDED ACTIVITIES

- Additional practice for fast learners
- Reinforcement for learners who need support
- Creative application of learning

12) REFLECTION

- What did learners learn today?
- What was challenging?
- How can this be applied in everyday life?
"""
    return plan


def generate_lesson_plan(subject, grade, topic="", duration=40):
    """
    Generate lesson plan(s) from curriculum database.
    
    If the CBC curriculum specifies multiple lessons for a strand/substrand,
    this will generate ALL the required lesson plans with content distributed
    across them.
    """
    curriculum = query_curriculum(subject, grade)
    
    if not curriculum:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }
    
    # Extract curriculum components
    strand = curriculum.get('strand', '')
    substrand = curriculum.get('substrand', '')
    learning_outcomes = curriculum.get('learning_outcomes', [])
    key_questions = curriculum.get('key_inquiry_questions', [])
    experiences = curriculum.get('suggested_learning_experiences', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])
    
    # Clean up empty or stub items
    learning_outcomes = [o for o in learning_outcomes if len(o.strip()) > 10]
    key_questions = [q for q in key_questions if len(q.strip()) > 5]
    experiences = [e for e in experiences if len(e.strip()) > 10]
    
    # The CBC parser mixed values, links, and PCIs into competencies/values fields.
    # Separate them properly.
    competencies, values, links, pcis = _classify_competency_items(
        raw_competencies + raw_values
    )
    
    # Determine how many lessons the curriculum requires
    num_lessons = _extract_lesson_count(strand)
    
    # If no lesson count in strand, estimate from the amount of curriculum content
    if num_lessons == 0:
        # Estimate: ~2 learning outcomes per lesson, minimum 1, maximum 12
        content_items = len(learning_outcomes) + len(experiences)
        if content_items >= 12:
            num_lessons = max(3, min(12, content_items // 3))
        elif content_items >= 6:
            num_lessons = max(2, content_items // 3)
        else:
            num_lessons = 1
    
    strand_topic = _extract_strand_topic(strand) or topic or "the lesson"
    
    # Extract a clean topic from the user's prompt (strip out "generate a grade X ... lesson plan on")
    if topic and len(topic) > 60:
        # Looks like a raw prompt — extract the real topic
        import re as _re
        topic_match = _re.search(r'\bon\s+([a-zA-Z0-9\s\-]{3,120})', topic, _re.IGNORECASE)
        if topic_match:
            extracted = topic_match.group(1)
            # Trim trailing noise like "under the substrand ..."
            extracted = _re.split(r'\b(?:under|for|in|during|term)\b', extracted, maxsplit=1, flags=_re.IGNORECASE)[0]
            extracted = _re.sub(r'\s+', ' ', extracted).strip(' .,-_')
            if len(extracted) > 3:
                topic = extracted.title()
            else:
                topic = strand_topic
        else:
            topic = strand_topic
    elif not topic or topic == subject:
        topic = strand_topic
    
    # Determine lesson duration based on grade
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    if grade_num <= 6:
        duration = 35
    
    # Distribute curriculum content across lessons
    outcomes_per_lesson = _distribute_items(learning_outcomes, num_lessons)
    questions_per_lesson = _distribute_items(key_questions, num_lessons)
    experiences_per_lesson = _distribute_items(experiences, num_lessons)
    
    # Competencies and values are shared across all lessons
    shared_competencies = competencies[:5] if competencies else []
    shared_values = values[:5] if values else []
    shared_links = links[:3] if links else []
    shared_pcis = pcis[:3] if pcis else []
    
    # Generate each lesson plan
    today = datetime.today()
    all_plans = []
    
    for i in range(num_lessons):
        lesson_num = i + 1
        # Stagger dates (one lesson per day, skipping weekends)
        lesson_date = today + timedelta(days=i)
        # Skip weekends
        while lesson_date.weekday() >= 5:
            lesson_date += timedelta(days=1)
        date_str = lesson_date.strftime("%d/%m/%Y")
        
        plan = _build_single_lesson_plan(
            lesson_number=lesson_num,
            total_lessons=num_lessons,
            subject=subject,
            grade=grade,
            topic=topic,
            strand=strand,
            substrand=substrand,
            outcomes=outcomes_per_lesson[i],
            questions=questions_per_lesson[i],
            experiences=experiences_per_lesson[i],
            competencies=shared_competencies,
            values=shared_values,
            duration=duration,
            date_str=date_str,
            links=shared_links,
            pcis=shared_pcis,
        )
        all_plans.append(plan)
    
    # Combine all lesson plans
    header = f"""
{'#' * 60}
  {subject.upper()} — {grade.upper()}
  STRAND: {strand}
  TOPIC: {topic}
  TOTAL LESSONS REQUIRED: {num_lessons}
{'#' * 60}
"""
    
    combined_content = header + "\n".join(all_plans)
    combined_content += f"\n\nGenerated: {datetime.today().strftime('%d/%m/%Y %H:%M')}\n"
    
    return {
        "success": True,
        "content": combined_content,
        "subject": subject,
        "grade": grade,
        "topic": topic,
        "duration": duration,
        "num_lessons": num_lessons,
        "lesson_plans": all_plans,  # Individual plans for separate rendering
    }


def _extract_topic_from_outcome(outcome_text, fallback_items=None):
    """
    Extract a short topic name from a learning outcome string.
    
    e.g. "By the end of the sub-strand the learner should be able to:
          a) explain the importance of conserving leftover foods..."
    -> "Conserving leftover foods"
    
    If outcome_text is just a preamble, tries fallback_items for content.
    """
    candidates = [outcome_text] + (fallback_items or [])
    
    for raw_text in candidates:
        if not raw_text:
            continue
        text = raw_text.strip()
        # Strip common CBC preambles
        # First try to strip "By the end ... the learner should be able to:" as a unit
        text = re.sub(
            r'^by\s+the\s+end\s+of\s+the\s+sub-?\s*strand\b.*?the\s+learner\s+should\s+be\s+able\s+to\s*:\s*',
            '', text, flags=re.IGNORECASE
        ).strip()
        # If that didn't match (no "learner should be able to" in text), strip standalone preamble
        if re.match(r'^by\s+the\s+end\s+of\s+the\s+sub', text, re.IGNORECASE):
            text = ''  # Just a standalone preamble — skip to next candidate
        text = re.sub(
            r'^the\s+learner\s+should\s+be\s+able\s+to\s*:\s*',
            '', text, flags=re.IGNORECASE
        ).strip()
        # Strip leading letter labels like "a) ", "b) "
        text = re.sub(r'^[a-z]\)\s*', '', text, flags=re.IGNORECASE)
        text = text.strip()
        if len(text) < 6:
            continue  # Just a preamble, try next candidate
        # Get the first meaningful clause (up to a period, semicolon, or second label)
        clause = re.split(r'[;.]|\s[b-z]\)', text, maxsplit=1)[0].strip()
        # Try to extract the object of the first verb
        verb_match = re.match(
            r'(?:explain|describe|identify|discuss|carry out|prepare|demonstrate|make|show|manage|grow|use|analyse|recognise|perform|create|indent)\s+(?:the\s+)?(?:importance\s+of\s+)?(.+)',
            clause, re.IGNORECASE
        )
        if verb_match:
            topic = verb_match.group(1).strip(' .,-')
        else:
            topic = clause[:80].strip(' .,-')
        if len(topic) > 5:
            return topic[:60].title()
    
    return None


def _group_outcomes_into_substrands(learning_outcomes):
    """
    CBC data sometimes dumps multiple sub-strands into one record.
    Group outcomes by their preamble ("By the end of the sub-strand..." or
    "the learner should be able to:").
    Each group represents a distinct sub-strand / topic.
    """
    groups = []
    current_group = []
    for outcome in learning_outcomes:
        text = outcome.strip()
        # Detect sub-strand boundary markers
        is_boundary = (
            re.match(r'^by\s+the\s+end\s+of\s+the\s+sub', text, re.IGNORECASE) or
            re.match(r'^the\s+learner\s+should\s+be\s+able\s+to\s*:', text, re.IGNORECASE)
        )
        if is_boundary:
            if current_group:
                groups.append(current_group)
            current_group = [text]
        else:
            current_group.append(text)
    if current_group:
        groups.append(current_group)
    
    # Merge tiny preamble-only groups with the next group
    # e.g. ["By the end of the sub strand"] should merge with ["the learner should be able to: ..."]
    merged = []
    i = 0
    while i < len(groups):
        group = groups[i]
        # If this group is just a short preamble (<30 chars total) and there's a next group, merge
        total_text = sum(len(g) for g in group)
        if total_text < 40 and i + 1 < len(groups):
            merged_group = group + groups[i + 1]
            merged.append(merged_group)
            i += 2
        else:
            merged.append(group)
            i += 1
    
    return merged if merged else [learning_outcomes]


def _group_experiences_into_substrands(experiences):
    """
    Group learning experiences by their preamble ("Learners are guided to:").
    Falls back to returning all experiences in one group if no preamble found.
    """
    groups = []
    current_group = []
    for exp in experiences:
        text = exp.strip()
        if re.match(r'^learners\s+are\s+guided\s+to', text, re.IGNORECASE):
            if current_group:
                groups.append(current_group)
            current_group = [text]
        else:
            current_group.append(text)
    if current_group:
        groups.append(current_group)
    return groups if groups else [experiences]


def generate_scheme_of_work(subject, grade, term="1"):
    """
    Generate a Scheme of Work in the standard Kenyan CBC / TSC tabular format.
    
    Standard columns:
    Wk | Lsn | Strand | Sub-strand | Specific Learning Outcomes |
    Key Inquiry Question(s) | Learning Experiences | Learning Resources |
    Assessment | Reflection
    """
    curriculum = query_curriculum(subject, grade)
    
    if not curriculum:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }
    
    current_year = datetime.today().year
    
    # Extract curriculum components
    strand = curriculum.get('strand', '')
    substrand = curriculum.get('substrand', '')
    learning_outcomes = curriculum.get('learning_outcomes', [])
    key_questions = curriculum.get('key_inquiry_questions', [])
    experiences = curriculum.get('suggested_learning_experiences', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])
    
    # Filter stubs
    learning_outcomes = [o for o in learning_outcomes if len(o.strip()) > 10]
    experiences = [e for e in experiences if len(e.strip()) > 10]
    
    # Clean up contaminated competencies / values
    competencies, values, links, pcis = _classify_competency_items(
        raw_competencies + raw_values
    )
    if not competencies:
        competencies = ["Critical thinking and problem solving",
                        "Communication and collaboration",
                        "Self-efficacy"]
    if not values:
        values = ["Respect", "Responsibility", "Unity"]
    
    # Group learning outcomes and experiences by sub-strand
    outcome_groups = _group_outcomes_into_substrands(learning_outcomes)
    experience_groups = _group_experiences_into_substrands(experiences)
    
    # Determine total lessons from strand text
    total_lessons = _extract_lesson_count(strand)
    if total_lessons == 0:
        content_items = len(learning_outcomes) + len(experiences)
        if content_items >= 12:
            total_lessons = max(3, min(12, content_items // 3))
        elif content_items >= 6:
            total_lessons = max(2, content_items // 3)
        else:
            total_lessons = max(len(outcome_groups), 1)
    
    # Grade-based lesson duration
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    lesson_duration = 35 if grade_num <= 6 else 40
    
    # Determine lessons per week (CBC typically 3-5 lessons per subject per week)
    lessons_per_week = 3 if grade_num <= 6 else 2
    num_weeks = max(1, math.ceil(total_lessons / lessons_per_week))
    num_weeks = min(num_weeks, 13)  # Cap at 13 weeks per term
    
    # Recalculate total lessons if we capped weeks
    if num_weeks * lessons_per_week < total_lessons:
        lessons_per_week = math.ceil(total_lessons / num_weeks)
    
    strand_topic = _extract_strand_topic(strand) or subject
    
    # Distribute questions evenly across all lessons
    questions_per_lesson_count = max(1, math.ceil(len(key_questions) / total_lessons)) if key_questions else 0
    
    # Build the weekly lesson rows
    lesson_counter = 0
    table_rows = []
    
    for week_idx in range(num_weeks):
        # Determine how many lessons this week
        remaining = total_lessons - lesson_counter
        week_lesson_count = min(lessons_per_week, remaining)
        if week_lesson_count <= 0:
            week_lesson_count = 1
        
        # Get outcomes for this week (from grouped substrands)
        if week_idx < len(outcome_groups):
            week_outcomes = outcome_groups[week_idx]
        else:
            week_outcomes = outcome_groups[week_idx % len(outcome_groups)] if outcome_groups else []
        
        # Get experiences for this week
        if week_idx < len(experience_groups):
            week_experiences = experience_groups[week_idx]
        elif experience_groups:
            week_experiences = experience_groups[week_idx % len(experience_groups)]
        else:
            week_experiences = []
        
        # Extract topic for this week
        topic_name = _extract_topic_from_outcome(
            week_outcomes[0] if week_outcomes else None,
            fallback_items=week_outcomes[1:] if len(week_outcomes) > 1 else None
        )
        if not topic_name:
            topic_name = strand_topic
        
        # Clean outcomes text (strip preamble)
        clean_outcomes = []
        for o in week_outcomes:
            cleaned = re.sub(
                r'^by\s+the\s+end\s+of\s+the\s+sub-?\s*strand.*?:\s*',
                '', o, flags=re.IGNORECASE
            ).strip()
            if cleaned:
                clean_outcomes.append(cleaned)
        
        # Clean experiences text (strip "Learners are guided to:" preamble)
        clean_experiences = []
        for e in week_experiences:
            cleaned = re.sub(
                r'^learners\s+are\s+guided\s+to\s*:?\s*',
                '', e, flags=re.IGNORECASE
            ).strip()
            if cleaned and len(cleaned) > 10:
                clean_experiences.append(cleaned)
        
        # Distribute outcomes and experiences across lessons within the week
        outcomes_per_lesson = _distribute_items(clean_outcomes, week_lesson_count)
        experiences_per_lesson = _distribute_items(clean_experiences, week_lesson_count)
        
        for lsn_idx in range(week_lesson_count):
            lesson_counter += 1
            
            # Lesson outcomes
            lsn_outcomes = outcomes_per_lesson[lsn_idx] if lsn_idx < len(outcomes_per_lesson) else []
            outcomes_text = "\n".join([f"• {o}" for o in lsn_outcomes]) if lsn_outcomes else "• (Continuation)"
            
            # Lesson experiences
            lsn_exps = experiences_per_lesson[lsn_idx] if lsn_idx < len(experiences_per_lesson) else []
            if not lsn_exps:
                # Provide contextual defaults
                lsn_exps = [f"Guided exploration of {topic_name.lower()} through discussion and practical activities"]
            exp_text = "\n".join([f"• {e}" for e in lsn_exps])
            
            # Questions for this lesson — distribute across all lessons
            q_start = (lesson_counter - 1) * questions_per_lesson_count
            q_end = q_start + questions_per_lesson_count
            lsn_questions = key_questions[q_start:q_end] if key_questions else []
            if lsn_questions:
                q_text = "\n".join([f"• {q}" for q in lsn_questions])
            else:
                q_text = f"• What have you learnt about {topic_name.lower()}?"
            
            # Resources
            resources = "• Textbooks\n• Charts/visual aids\n• Realia/models\n• Learner workbooks"
            
            # Assessment
            assessment = "• Observation\n• Oral questions\n• Written exercise"
            
            # Reflection
            reflection = "______________________"
            
            table_rows.append({
                "week": week_idx + 1,
                "lesson": lesson_counter,
                "lesson_in_week": lsn_idx + 1,
                "strand": strand if strand else "N/A",
                "substrand": topic_name,
                "outcomes": outcomes_text,
                "questions": q_text,
                "experiences": exp_text,
                "resources": resources,
                "assessment": assessment,
            })
    
    # --- Build the final scheme of work document ---
    
    # Prepare cross-cutting text for table cells
    comp_text = ", ".join(competencies[:5])
    val_text = ", ".join(values[:5])
    links_text = ", ".join(links[:3]) if links else "As applicable"
    pcis_text = ", ".join(pcis[:3]) if pcis else "As applicable"
    
    # Utility: collapse multi-line bullet text into a single table-cell string
    def _cell(text):
        """Escape pipes and collapse newlines so text fits in one markdown cell."""
        return text.replace("|", "/").replace("\n", " ").strip()
    
    # Admin header (above the table)
    header = (
        f"SCHEME OF WORK\n"
        f"{'=' * 80}\n\n"
        f"School: ______________________     "
        f"Teacher: ______________________\n"
        f"Subject: {subject.upper()}     "
        f"Grade: {grade}     "
        f"Term: {term}     "
        f"Year: {current_year}\n"
        f"Approved by HoD: _______________  "
        f"Sign: ___________  Date: ___________\n\n"
    )
    
    # Markdown table header row + separator
    md_table = (
        "| Week | Lesson No. | Strand | Sub-Strand "
        "| Specific Learning Outcomes | Learning Experiences / Activities "
        "| Key Inquiry Question(s) | Learning Resources | Assessment Methods "
        "| Core Competencies | Values | PCIs (Pertinent & Contemporary Issues) "
        "| Remarks |\n"
        "| :--: | :--: | --- | --- "
        "| --- | --- "
        "| --- | --- | --- "
        "| --- | --- | --- "
        "| --- |\n"
    )
    
    # One table row per lesson
    prev_week = None
    for row in table_rows:
        wk = str(row["week"]) if row["week"] != prev_week else ""
        prev_week = row["week"]
        
        md_table += (
            f"| {wk} "
            f"| {row['lesson']} "
            f"| {_cell(row['strand'])} "
            f"| {_cell(row['substrand'])} "
            f"| {_cell(row['outcomes'])} "
            f"| {_cell(row['experiences'])} "
            f"| {_cell(row['questions'])} "
            f"| {_cell(row['resources'])} "
            f"| {_cell(row['assessment'])} "
            f"| {_cell(comp_text)} "
            f"| {_cell(val_text)} "
            f"| {_cell(pcis_text)} "
            f"| |\n"
        )
    
    # Footer notes
    footer = (
        f"\nTotal Lessons: {total_lessons}  |  "
        f"Duration per lesson: {lesson_duration} minutes  |  "
        f"Weeks: {num_weeks}\n\n"
        f"GENERAL NOTES:\n"
        f"- Use learner-centered and competency-based approaches throughout\n"
        f"- Integrate values and core competencies in every lesson\n"
        f"- Differentiate instruction for diverse learner needs\n"
        f"- Relate content to real-world contexts and learner experiences\n"
        f"- Regularly assess and adjust pace based on learner progress\n\n"
        f"Generated: {datetime.today().strftime('%d/%m/%Y %H:%M')}\n"
    )
    
    full_content = header + md_table + footer
    
    return {
        "success": True,
        "content": full_content,
        "subject": subject,
        "grade": grade,
        "term": term
    }


def generate_rubric(subject, grade, assessment_type="performance"):
    """Generate a CBC auto-generated rubric template from curriculum database."""
    curriculum = query_curriculum(subject, grade)
    
    if not curriculum:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }
    
    current_year = datetime.today().year
    date_str = datetime.today().strftime('%d/%m/%Y')
    
    strand = curriculum.get('strand', '')
    substrand = curriculum.get('substrand', '')
    learning_outcomes = curriculum.get('learning_outcomes', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])
    
    # Filter stubs
    learning_outcomes = [o for o in learning_outcomes if len(o.strip()) > 10]
    
    # Classify competency data
    competencies, values, links, pcis = _classify_competency_items(
        raw_competencies + raw_values
    )
    if not competencies:
        competencies = ["Critical thinking and problem solving",
                        "Communication and collaboration",
                        "Self-efficacy"]
    if not values:
        values = ["Respect", "Responsibility", "Unity"]
    if not pcis:
        pcis = ["As applicable"]
    
    # Extract clean strand topic
    strand_topic = _extract_strand_topic(strand) or subject
    
    # Determine grade-based duration
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    lesson_duration = 35 if grade_num <= 6 else 40
    
    # Build clean criteria from learning outcomes (strip preambles)
    criteria = []
    for o in learning_outcomes[:6]:
        cleaned = re.sub(
            r'^by\s+the\s+end\s+of\s+the\s+sub-?\s*strand[^:]*:?\s*',
            '', o, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(
            r'^the\s+learner\s+should\s+be\s+able\s+to\s*:?\s*',
            '', cleaned, flags=re.IGNORECASE
        ).strip()
        if not cleaned or len(cleaned) < 10:
            continue
        # Split compound outcomes  a) ... b) ... c) ...
        parts = re.split(r'\s*[a-z]\)\s+', cleaned)
        for p in parts:
            p = p.strip().rstrip('.')
            # Remove leading letter prefix like "A)" or "b)"
            p = re.sub(r'^[A-Za-z]\)\s*', '', p).strip()
            if len(p) > 10:
                criteria.append(p[0].upper() + p[1:] if p else p)
    criteria = criteria[:4]  # Cap at 4 criteria
    if not criteria:
        criteria = [f"Demonstrate understanding of {strand_topic}"]
    
    # Generate descriptors for each criterion at each level
    def _descriptors(criterion):
        """Generate 4 performance-level descriptors for a criterion."""
        # Extract the main verb (skip leading articles/prepositions)
        words = criterion.split()
        verb = words[0].lower() if words else "demonstrate"
        rest = " ".join(words[1:]) if len(words) > 1 else strand_topic
        
        # Conjugate: add 's' for third-person, handle common endings
        if verb.endswith(('sh', 'ch', 'ss', 'x', 'z')):
            verb_s = verb + "es"
        elif verb.endswith('y') and len(verb) > 1 and verb[-2] not in 'aeiou':
            verb_s = verb[:-1] + "ies"
        else:
            verb_s = verb + "s"
        
        ee = f"Independently and creatively {verb_s} {rest} with exceptional accuracy and originality"
        me = f"Correctly {verb_s} {rest} as required with consistency"
        ae = f"Partially {verb_s} {rest} with teacher guidance and support"
        be = f"Shows minimal ability to {verb} {rest}; requires significant support"
        return ee, me, ae, be
    
    # --- Build the rubric document ---
    
    # Use clean criteria for the info table Learning Outcomes field
    lo_summary = "; ".join(criteria[:3]) if criteria else f"Demonstrate understanding of {strand_topic}"
    
    rubric = f"""CBC AUTO-GENERATED RUBRIC TEMPLATE
{'=' * 60}

LESSON INFORMATION
{'=' * 60}

| Field | Data |
|---|---|
| Subject | {subject.upper()} |
| Grade | {grade} |
| Strand | {strand if strand else 'N/A'} |
| Sub-Strand | {substrand if substrand else strand_topic} |
| Learning Outcome(s) | {lo_summary} |
| Task / Assessment | {assessment_type.title()} assessment |
| Duration | {lesson_duration} minutes |
| Date | {date_str} |

PERFORMANCE LEVELS (CBC Standard)
{'=' * 60}

| Level | Descriptor | Score |
|---|---|---|
| Exceeding Expectation | Demonstrates mastery independently and creatively | 4 |
| Meeting Expectation | Demonstrates required competency correctly | 3 |
| Approaching Expectation | Demonstrates partial understanding with support | 2 |
| Below Expectation | Demonstrates minimal understanding | 1 |

AUTO-GENERATED ASSESSMENT RUBRIC
{'=' * 60}

| Criteria (from Learning Outcomes) | Exceeding Expectation (4) | Meeting Expectation (3) | Approaching Expectation (2) | Below Expectation (1) |
|---|---|---|---|---|"""
    
    for criterion in criteria:
        ee, me, ae, be = _descriptors(criterion)
        rubric += f"\n| {criterion} | {ee} | {me} | {ae} | {be} |"
    
    # Competencies section
    comp_lines = "\n".join([f"- {c}" for c in competencies[:5]])
    
    # Values section
    val_lines = "\n".join([f"- {v}" for v in values[:4]])
    
    # PCIs section
    pci_lines = "\n".join([f"- {p}" for p in pcis[:3]])
    
    rubric += f"""

CORE COMPETENCIES ASSESSED
{'=' * 60}

{comp_lines}

VALUES INTEGRATED
{'=' * 60}

{val_lines}

PCIs INTEGRATED
{'=' * 60}

{pci_lines}

TEACHER FEEDBACK SECTION
{'=' * 60}

Strengths:
___________________________________________________________

Areas for Improvement:
___________________________________________________________

Teacher Comment:
___________________________________________________________

Generated: {datetime.today().strftime('%d/%m/%Y %H:%M')}
"""
    
    return {
        "success": True,
        "content": rubric,
        "subject": subject,
        "grade": grade,
        "assessment_type": assessment_type
    }


if __name__ == "__main__":
    # Test the generators
    print("Testing Lesson Plan Generator...")
    lp = generate_lesson_plan("English", "Grade 7", "Reading Comprehension")
    print(lp["content"][:500] + "...\n")
    
    print("Testing Scheme of Work Generator...")
    sw = generate_scheme_of_work("Mathematics", "Grade 8", "1")
    print(sw["content"][:500] + "...\n")
    
    print("Testing Rubric Generator...")
    rb = generate_rubric("Integrated Science", "Grade 9", "performance")
    print(rb["content"][:500] + "...\n")
