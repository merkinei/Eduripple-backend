"""Template-based lesson, scheme, and rubric generator using curriculum database."""

import re
import math
from datetime import datetime, timedelta
from curriculum_db import get_curriculum

# ---------------------------------------------------------------------------
# Approved CBC Core Competencies (CBC Policy 2017) — Rule 4
# ---------------------------------------------------------------------------
_APPROVED_COMPETENCIES = [
    ("communication",     "Communication and Collaboration"),
    ("critical",          "Critical Thinking and Problem Solving"),
    ("creat",             "Creativity and Imagination"),
    ("citizen",           "Citizenship"),
    ("digital",           "Digital Literacy"),
    ("learning to learn", "Learning to Learn"),
    ("self-efficac",      "Self-Efficacy"),
    ("efficac",           "Self-Efficacy"),
]

# Approved CBC Values (CBC Policy 2017) — Rule 4
_APPROVED_VALUES = [
    "Respect", "Responsibility", "Integrity", "Unity",
    "Peace", "Love", "Patriotism", "Social Justice",
]


def _filter_to_approved_competencies(raw_list):
    """Map raw DB competency strings to only the 7 approved CBC core competencies."""
    seen = set()
    result = []
    for raw in (raw_list or []):
        lowered = raw.lower()
        for keyword, canonical in _APPROVED_COMPETENCIES:
            if keyword in lowered and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
                break
    return result or ["Communication and Collaboration", "Critical Thinking and Problem Solving", "Self-Efficacy"]


def _filter_to_approved_values(raw_list):
    """Filter raw value strings to only the 8 approved CBC values."""
    seen = set()
    result = []
    for raw in (raw_list or []):
        lowered = raw.lower()
        for canonical in _APPROVED_VALUES:
            if canonical.lower() in lowered and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
                break
    return result or ["Respect", "Responsibility"]


def query_curriculum(subject, grade, substrand_hint=None):
    """Query curriculum database for subject and grade.
    Returns the best-matching entry (by substrand_hint if provided,
    otherwise the first match). Never returns on the first loop —
    always collects ALL matches first."""
    # Normalize grade: handle "10", "grade10", "Grade 10", "grade 10"
    if not grade:
        return None
    
    grade_str = str(grade).strip()
    # Remove "Grade " prefix if present, extract just the number
    grade_num = grade_str.lower().replace("grade", "").strip()
    # Rebuild as "Grade N"
    grade_normalized = f"Grade {grade_num}" if grade_num else grade_str

    all_curriculum = get_curriculum()
    if not all_curriculum:
        return None

    # Map common subject name variations to actual DB subject names
    subject_map = {
        "english": "english",
        "history": "history and government",
        "history and government": "history and government",
        "gov": "history and government",
        "government": "history and government",
        "mathematics": "maths",
        "math": "maths",
        "maths": "maths",
        "science": "intergrated science",
        "integrated science": "intergrated science",
        "intergrated science": "intergrated science",
        "social studies": "social studies",
        "creative arts": "creative arts",
        "creative arts and sports": "creative arts and sports",
        "agriculture": "agriculture and nutrition",
        "agriculture and nutrition": "agriculture and nutrition",
        "agriculture and nutrion": "agriculture and nutrion",  # DB typo Grade 8
        "pre-technical studies": "pre technical studies",
        "pre technical studies": "pre technical studies",
        "kiswahili": "kiswahili",
        "indigenous languages": "indigenious languages",
        "indigenous language": "indigenious languages",
        "indigenious languages": "indigenious languages",
        "cre": "cre",
        "christian religious education": "cre",
        "ire": "ire",
        "islamic religious education": "ire",
    }

    subject_normalized = subject.lower()
    if subject_normalized in subject_map:
        subject_normalized = subject_map[subject_normalized]
    subject_with_underscore = subject_normalized.replace(" ", "_")
    grade_lower = grade_normalized.lower()

    # Collect ALL entries that match subject + grade
    matches = []
    for entry in all_curriculum:
        entry_subject = entry['subject'].lower().replace("_", " ")
        entry_grade = entry['grade'].lower()
        subject_match = (
            entry_subject == subject_normalized
            or entry['subject'].lower() == subject_with_underscore
            or any(w in entry_subject for w in subject_normalized.split() if len(w) > 3)
        )
        if subject_match and entry_grade == grade_lower:
            matches.append(entry)

    if not matches:
        return None

    # If a substrand hint is given, return the best-matching entry
    if substrand_hint:
        return _find_best_curriculum_entry(matches, substrand_hint)
    return matches[0]


def _get_all_matching_entries(subject, grade):
    """Return ALL curriculum entries for a subject+grade using the same fuzzy
    normalization as query_curriculum().  Used by generate_scheme_of_work()."""
    grade_normalized = f"Grade {grade}" if grade and not grade.startswith("Grade") else grade
    all_curriculum = get_curriculum()
    if not all_curriculum:
        return []

    subject_map = {
        "mathematics": "maths", "math": "maths",
        "science": "intergrated science",
        "integrated science": "intergrated science",
        "intergrated science": "intergrated science",
        "social studies": "social studies",
        "creative arts": "creative arts",
        "creative arts and sports": "creative arts and sports",
        "agriculture": "agriculture and nutrition",
        "agriculture and nutrition": "agriculture and nutrition",
        "agriculture and nutrion": "agriculture and nutrion",
        "pre-technical studies": "pre technical studies",
        "pre technical studies": "pre technical studies",
        "indigenous languages": "indigenious languages",
        "indigenous language": "indigenious languages",
        "indigenious languages": "indigenious languages",
        "cre": "cre",
        "christian religious education": "cre",
        "ire": "ire",
        "islamic religious education": "ire",
    }

    subject_normalized = subject.lower()
    if subject_normalized in subject_map:
        subject_normalized = subject_map[subject_normalized]
    subject_with_underscore = subject_normalized.replace(" ", "_")
    grade_lower = grade_normalized.lower()

    matches = []
    for entry in all_curriculum:
        entry_subject = entry['subject'].lower().replace("_", " ")
        entry_grade   = entry['grade'].lower()
        subject_match = (
            entry_subject == subject_normalized
            or entry['subject'].lower() == subject_with_underscore
            or any(w in entry_subject for w in subject_normalized.split() if len(w) > 3)
        )
        if subject_match and entry_grade == grade_lower:
            matches.append(entry)
    return matches


def _combine_substrand(num, name):
    """Combine substrand_number + substrand name, avoiding double prefixes.

    DB quirk: some subjects store the section number in substrand_number ('4.2')
    and the sub-section fragment in substrand name ('.1 Intensive Reading').
    In that case join them as '4.2.1 Intensive Reading' (no extra space before dot).
    """
    num = (num or '').strip()
    name = (name or '').strip()
    if not num:
        return name
    # If the name starts with a dot-fragment like '.1 ...' combine directly onto num
    if name.startswith('.'):
        return f"{num}{name}"
    # If name already starts with the same numeric prefix, don't duplicate
    if name.startswith(num):
        return name
    return f"{num} {name}".strip()


def _find_best_curriculum_entry(all_entries, substrand_hint):
    """Given a list of entries (all same subject+grade), pick the one whose
    substrand best matches the substrand_hint.  Falls back to first entry."""
    if not all_entries:
        return None
    if not substrand_hint:
        return all_entries[0]

    # Synonym expansion: CBC topic words → related DB keywords
    _SYNONYMS: dict[str, list[str]] = {
        'play':           ['drama', 'story', 'reader', 'oral', 'narrative', 'literature'],
        'drama':          ['play', 'oral', 'narrative', 'literature', 'reader'],
        'poem':           ['poetry', 'poem', 'oral', 'literature'],
        'character':      ['character'],
        'comprehension':  ['reading', 'intensive', 'extensive', 'information'],
        'composition':    ['writing', 'creative', 'narrative', 'composition'],
        'grammar':        ['grammar', 'verb', 'tense', 'word', 'sentence'],
        'fraction':       ['fraction', 'number', 'ratio', 'proportion'],
        'algebra':        ['algebra', 'expression', 'equation', 'algebraic'],
        'geometry':       ['geometry', 'shape', 'angle', 'triangle', 'circle'],
        'crop':           ['crop', 'plant', 'soil', 'farm', 'agriculture'],
        'animal':         ['animal', 'livestock', 'poultry', 'pest'],
    }

    hint_lower = substrand_hint.lower()
    hint_words = [w for w in hint_lower.split() if len(w) > 3]

    # Expand hints with synonyms
    expanded_words = list(hint_words)
    for hw in hint_words:
        for key, syns in _SYNONYMS.items():
            if hw.startswith(key[:4]):
                expanded_words.extend(syns)
        # Add stem (first 6 chars) for fuzzy prefix matching
        if len(hw) > 6:
            expanded_words.append(hw[:6])

    best, best_score = all_entries[0], 0
    for entry in all_entries:
        sub = entry.get('substrand', '').lower()
        # Exact word containment + stem prefix match
        score = sum(
            1 for w in expanded_words
            if w in sub or any(sw.startswith(w[:6]) for sw in sub.split() if len(sw) > 4)
        )
        if score > best_score:
            best, best_score = entry, score
    return best


def _clean_slo(text):
    """Strip PDF-parser preamble headers that leaked into SLO text."""
    # Partial fragment: 'By the end of the sub' (split across list items by PDF parser)
    t = re.sub(
        r'^by\s+the\s+end\s+of\s+the\s+sub[-\s]*$',
        '', text, flags=re.IGNORECASE
    ).strip()
    # Partial fragment with hyphenated 'sub-strand': 'By the end of the-sub strand'
    t = re.sub(
        r'^by\s+the\s+end\s+of\s+the[-\s]+sub[-\s]*strand[^:]*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Full preamble: 'By the end of the sub-strand / sub strand ...'
    t = re.sub(
        r'^by\s+the\s+end\s+of\s+the\s+sub[\s\-]*strand[^:]*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    t = re.sub(
        r'^by\s+the\s+end\s+of\s+the\s+strand[^:]*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Any remaining 'By the end of the...' catch-all
    t = re.sub(
        r'^by\s+the\s+end\s+of\s+the\s+\S+\s*[,.]?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    t = re.sub(
        r'^the\s+learner\s+should\s+be\s+able\s+to\s*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Continuation fragment: 'strand, the learner should be able to:'
    t = re.sub(
        r'^strand[,\s]+the\s+learner\s+should\s+be\s+able\s+to\s*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    t = re.sub(
        r'^learner\s+should\s+be\s+able\s+to\s*:?\s*',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Strip leading punctuation artifacts left after stripping preamble
    return t.lstrip(':;,. ').strip()


# Matches items that clearly end mid-thought (truncated PDF extraction)
_SLO_ENDS_INCOMPLETE = re.compile(
    r'\b(of|a|an|the|in|on|to|by|from|for|and|or|but)\s*$', re.IGNORECASE
)
_SLO_HYPHEN_ARTIFACT = re.compile(r'\bto-day\b', re.IGNORECASE)


def _is_valid_slo(text):
    """Return True if the SLO text is a genuine, complete outcome statement."""
    t = text.strip()
    if len(t) < 15:
        return False
    if _SLO_ENDS_INCOMPLETE.search(t):
        return False
    if _SLO_HYPHEN_ARTIFACT.search(t):
        return False
    return True


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


# ---------------------------------------------------------------------------
# Topic-aware generators for PCIs, cross-curricular links, resources
# ---------------------------------------------------------------------------

_STUB_ACTIVITY = re.compile(
    r'^(learners?\s+are\s+guided\s+to\s*:?|the\s+learner\s+is\s+guided\s+to\s*:?'
    r'|learners?\s+guided\s+to\s*:?)$',
    re.IGNORECASE,
)


def _generate_lesson_resources(subject, grade, topic, substrand):
    """Return topic-specific learning resources (max 7)."""
    g = re.search(r'\d+', grade)
    grade_num = g.group() if g else '8'
    subj_title = re.sub(r'\s+and\s+', ' & ', subject, flags=re.IGNORECASE).title()
    combined = (topic or substrand or '').lower()

    resources = [
        f"KICD {subj_title} Learner's Book Grade {grade_num}",
        f"KICD {subj_title} Teacher's Guide Grade {grade_num}",
    ]

    topic_extras = [
        (['soil conserv', 'soil erosion', 'conservation of resourc'], [
            'Soil samples from different environments',
            'Cardboard/cartons for farm model construction',
            'Photos comparing eroded vs conserved land',
            'Water for soil erosion simulation',
        ]),
        (['water harvest', 'water storage', 'irrigation'], [
            'Rain gauge and measuring cylinders',
            'Water harvesting model or equipment',
            'Diagrams of water storage structures',
        ]),
        (['crop produc', 'kitchen garden', 'seed', 'planting', 'backyard garden'], [
            'Seed samples and seedling trays',
            'Soil and compost samples',
            'Gardening tools (hoe, trowel)',
            'Photos of different crop varieties',
        ]),
        (['poultry', 'livestock', 'animal'], [
            'Photos/diagrams of poultry housing types',
            'Feed and water trough samples',
            'Animal health management charts',
        ]),
        (['pest', 'disease control', 'weed'], [
            'Pest and disease identification photo charts',
            'Empty pesticide containers (labelled)',
            'Diseased vs healthy crop specimen photos',
        ]),
        (['fraction', 'decimal', 'percent', 'ratio'], [
            'Fraction tiles and number lines',
            'Pie charts and fraction diagrams',
        ]),
        (['algebra', 'equation', 'linear', 'quadratic'], [
            'Algebra tiles and graph paper',
            'Worked examples chart',
        ]),
        (['geometr', 'angle', 'shape', 'area', 'volume'], [
            'Geometric shape models (3D)',
            'Compass, ruler and protractor',
        ]),
        (['cell', 'microscop', 'organism'], [
            'Microscope and prepared slides',
            'Cell structure diagrams/charts',
        ]),
        (['ecosystem', 'biodiversit'], [
            'Ecosystem charts and diagrams',
            'Local plant/animal specimens or photos',
        ]),
        (['photosynthes', 'respiration', 'plant biologe'], [
            'Potted plants and green leaves',
            'Iodine solution and test tubes',
        ]),
        (['reading', 'comprehension', 'intensive reading'], [
            'Printed reading passages',
            'Comprehension question worksheets',
            'Dictionary and thesaurus',
        ]),
        (['writing', 'essay', 'composition', 'grammar'], [
            'Sample essays and writing prompt cards',
            'Writing rubric checklist',
        ]),
        (['map', 'topograph', 'map reading'], [
            'Topographic and political maps',
            'Atlas and compass',
            'Map reading worksheets',
        ]),
        (['conservation', 'environment', 'climate change'], [
            'Environmental conservation charts and posters',
            'Photos of natural resources (before/after degradation)',
        ]),
    ]

    for keywords, extras in topic_extras:
        if any(kw in combined for kw in keywords):
            resources.extend(extras)
            break

    resources.extend(['Chalkboard/whiteboard and chalk/markers', 'Learner exercise books'])
    return list(dict.fromkeys(resources))[:7]


def _generate_pcis(strand, substrand, topic, pcis_raw):
    """Expand bare DB PCI keywords or generate topic-specific PCIs."""
    combined = (strand + ' ' + substrand + ' ' + (topic or '')).lower()

    pci_topics = [
        (['soil conserv', 'soil erosion', 'conservation of resourc'], [
            'Environmental Education — effects of soil erosion on agricultural productivity',
            'Climate Change — relationship between deforestation and soil degradation',
            'Food Security — soil conservation as a foundation for sustainable agriculture',
        ]),
        (['water harvest', 'water storage', 'irrigation'], [
            'Environmental Education — sustainable water use and conservation',
            'Climate Change — water scarcity and shifting rainfall patterns',
            'Food Security — water harvesting to ensure reliable crop production',
        ]),
        (['crop produc', 'kitchen garden', 'food produc'], [
            'Food Security — importance of crop production for household and national food supply',
            'Environmental Education — organic farming and reduction of agrochemical use',
            'Health Education — nutritional benefits of home-grown vegetables',
        ]),
        (['poultry', 'livestock'], [
            'Food Security — poultry and livestock as sources of protein and household income',
            'Health Education — hygiene in handling and consuming animal products',
            'Financial Literacy — small-scale animal farming as an income-generating activity',
        ]),
        (['pest', 'disease control'], [
            'Health Education — safe and responsible use of pesticides',
            'Environmental Education — effects of pesticides on soil health and biodiversity',
            'Food Security — managing crop losses caused by pests and diseases',
        ]),
        (['environment', 'conservation', 'climate', 'ecosystem', 'biodiversit'], [
            'Environmental Education — importance of natural resource conservation',
            'Climate Change — human activities and their impact on the environment',
            'Citizenship — personal and community responsibility for environmental stewardship',
        ]),
        (['fraction', 'algebra', 'geometr', 'statistic', 'mathemat'], [
            'Financial Literacy — applying mathematics in everyday budgeting and trade',
            'Digital Literacy — use of calculators and digital tools in mathematical problem solving',
            'Life Skills — logical and numerical thinking in daily decision making',
        ]),
        (['reading', 'writing', 'grammar', 'composition', 'english', 'language'], [
            'Digital Literacy — using digital platforms for reading and written communication',
            'Life Skills — effective communication across personal and professional contexts',
            'Citizenship — responsible and respectful use of language in public discourse',
        ]),
        (['health', 'nutrition', 'diet', 'hygiene'], [
            'Health Education — balanced diet, hygiene and disease prevention',
            'Life Skills — personal health management and informed decision making',
            'Social Justice — equitable access to food and health services',
        ]),
        (['cre', 'ire', 'creation', 'faith', 'religion', 'moral'], [
            'Moral and Spiritual Values — integrity, honesty and care for others',
            'Citizenship — role of faith communities in social service and cohesion',
            'Life Skills — applying moral values in everyday situations',
        ]),
    ]

    expanded = [p for p in (pcis_raw or []) if len(p.strip()) > 25]
    if len(expanded) < 2:
        for keywords, statements in pci_topics:
            if any(kw in combined for kw in keywords):
                for stmt in statements:
                    if stmt not in expanded:
                        expanded.append(stmt)
                if len(expanded) >= 3:
                    break
    if not expanded:
        expanded = [
            'Life Skills — applying academic knowledge to solve real-life challenges',
            'Citizenship — contributing positively to community and the environment',
        ]
    return list(dict.fromkeys(expanded))[:4]


def _generate_cross_links(subject, strand, substrand, topic, links_raw):
    """Generate cross-curricular subject links when DB has none or incomplete data."""
    good_raw = [l for l in (links_raw or []) if len(l.strip()) > 20]
    if len(good_raw) >= 2:
        return good_raw[:4]

    combined = (subject + ' ' + strand + ' ' + substrand + ' ' + (topic or '')).lower()

    links_pool = [
        (['soil conserv', 'crop', 'farm', 'water harvest', 'livestock', 'poultry', 'agri'], [
            'Integrated Science — soil composition, water cycle and plant biology',
            'Social Studies — land use, environmental conservation and food security',
            'Mathematics — calculating land area, crop yields and farm budgets',
        ]),
        (['nutrition', 'food', 'diet'], [
            'Integrated Science — digestion and role of nutrients in the body',
            'Health Education — balanced diet and disease prevention',
            'Mathematics — calculating dietary portions and caloric values',
        ]),
        (['fraction', 'decimal', 'ratio', 'algebra', 'geometr', 'statistic', 'mathemat'], [
            'Integrated Science — measurement, scientific data collection and analysis',
            'Social Studies — interpreting population statistics and geographic data',
            'English — reading and interpreting mathematical word problems',
        ]),
        (['reading', 'writing', 'grammar', 'comprehension', 'composition', 'english'], [
            'Social Studies — using literacy to access historical and civic content',
            'Integrated Science — reading and interpreting scientific texts',
            'Kiswahili — comparing language structures and written expression',
        ]),
        (['science', 'ecosystem', 'cell', 'photosynthes', 'chemical', 'force', 'energy'], [
            'Mathematics — measurements, calculations and scientific data analysis',
            'Agriculture and Nutrition — scientific principles applied in food production',
            'Social Studies — human impact on the natural environment',
        ]),
        (['map', 'geograph', 'population', 'history', 'civic', 'social studies'], [
            'Integrated Science — physical environment and natural resources',
            'Mathematics — reading maps, graphs and statistical data',
            'English — research skills and structured report writing',
        ]),
        (['cre', 'christian', 'leisure', 'faith', 'ire', 'islamic', 'religion', 'moral', 'religious'], [
            'Social Studies — civic responsibility, community values and ethical decision-making',
            'English — reading religious texts; written reflection and structured oral expression',
            'Health Education — responsible lifestyle choices and their impact on personal wellbeing',
        ]),
    ]

    result = []
    for keywords, link_list in links_pool:
        if any(kw in combined for kw in keywords):
            result.extend(link_list)
            break
    if not result:
        result = [
            'English — communication, reading and writing skills',
            'Mathematics — numerical reasoning and quantitative analysis',
        ]
    return list(dict.fromkeys(result))[:4]


def _supplement_competencies(approved, subject, topic, minimum=3):
    """Supplement approved CBC competencies to reach minimum count.
    All additions are drawn from the 7 approved CBC competencies only."""
    if len(approved) >= minimum:
        return approved[:5]

    combined = (subject + ' ' + (topic or '')).lower()

    if any(k in combined for k in ['cre', 'ire', 'christian', 'islamic', 'religion', 'moral',
                                        'faith', 'christian living', 'leisure', 'bible', 'quran']):
        pool = [
            'Critical Thinking and Problem Solving — evaluating moral dilemmas and forming faith-based ethical judgements',
            'Communication and Collaboration — respectfully sharing personal values and faith perspectives in group discussion',
            'Self-Efficacy — applying Christian/moral values confidently in personal decision-making',
            'Citizenship — contributing positively to community through values-based action',
        ]
    elif any(k in combined for k in ['soil', 'farm', 'crop', 'conserv', 'agri', 'water', 'poultry', 'livestock']):
        pool = [
            'Critical Thinking and Problem Solving — evaluating different soil and land conservation methods',
            'Communication and Collaboration — presenting group project findings to the class',
            'Citizenship — taking responsibility for environmental and agricultural conservation',
            'Learning to Learn — researching conservation techniques using digital and print media',
        ]
    elif any(k in combined for k in ['math', 'algebra', 'fraction', 'geometr', 'statistic']):
        pool = [
            'Critical Thinking and Problem Solving — applying mathematical reasoning to real-world problems',
            'Communication and Collaboration — explaining mathematical solutions clearly to peers',
            'Digital Literacy — using calculators and technology in mathematical computation',
            'Learning to Learn — developing personal strategies for problem solving',
        ]
    elif any(k in combined for k in ['reading', 'writing', 'english', 'language', 'grammar', 'comprehension',
                                        'character', 'story', 'narrative', 'poem', 'poetry', 'oral',
                                        'literature', 'drama', 'play', 'class reader', 'reader']):
        pool = [
            'Communication and Collaboration — expressing ideas clearly in speech and written analysis',
            'Critical Thinking and Problem Solving — analysing character motivation, plot and narrative techniques',
            'Creativity and Imagination — creative writing and imaginative response to literary texts',
            'Digital Literacy — using digital platforms for reading, writing and literary research',
        ]
    elif any(k in combined for k in ['science', 'biology', 'chemistry', 'physics', 'ecosystem', 'cell']):
        pool = [
            'Critical Thinking and Problem Solving — designing, conducting and interpreting experiments',
            'Communication and Collaboration — documenting and presenting scientific findings',
            'Digital Literacy — using technology for research and data collection',
            'Learning to Learn — developing scientific enquiry and investigation skills',
        ]
    else:
        pool = [
            'Critical Thinking and Problem Solving — analysing and evaluating real-world issues',
            'Communication and Collaboration — sharing ideas effectively in group settings',
            'Learning to Learn — developing study strategies and applying knowledge to new contexts',
            'Citizenship — contributing responsibly to community and the environment',
        ]

    result = list(approved)
    seen = {c.split(' — ')[0].strip() for c in result}
    for candidate in pool:
        base = candidate.split(' — ')[0].strip()
        if base not in seen and len(result) < minimum:
            result.append(candidate)
            seen.add(base)
    return result[:5]


def _generate_step_learner_mirror(step_text, topic):
    """Convert a teacher-instruction step into the corresponding specific learner activity."""
    text = re.sub(r'^step\s*\d+\s*:\s*', '', step_text, flags=re.IGNORECASE).strip()
    tl = text.lower()

    if re.search(r'search\s+and\s+share', tl):
        obj = re.search(r'information\s+on\s+(.+?)(?:\s+using|\s+from|\s+in|$)', tl)
        what = obj.group(1).strip() if obj else topic
        return f"Search for information on {what} using digital devices and textbooks; share findings with the class"

    if re.search(r'conduct\s+(an?\s+)?project|construct|papier', tl):
        obj = re.search(r'(?:construct|conduct\s+project\s*:?\s*)(.{3,50}?)(?:\s+using|\s+in\s+group|$)', tl)
        what = obj.group(1).strip() if obj else f"the model related to {topic}"
        return f"Work in groups to construct {what}; assign roles and complete the task collaboratively"

    if re.search(r'\bbuild\b|\bmake\s+a\b|\bcreate\s+a\b|\bdesign\s+a\b', tl):
        obj = re.search(r'(?:build|make|create|design)\s+(a\s+.{3,40}?)(?:\s+using|\s+in\s+group|$)', tl)
        what = obj.group(1).strip() if obj else f"model related to {topic}"
        return f"Work in groups to {obj.group(0).strip() if obj else 'build the model'}; collaborate and complete all steps"

    if re.search(r'conduct\s+(an?\s+)?experiment|set\s+up', tl):
        return "Follow the experimental procedure step by step; record all observations in exercise book"

    if re.search(r'observe\s+and\s+record|observe\s+', tl):
        return "Carefully observe and record findings in exercise book; compare results with partner"

    if re.search(r'discuss\s+in\s+groups?|group\s+discuss|guide\s+.*discuss', tl):
        return "Discuss in groups; agree on key points and nominate a spokesperson to share with the class"

    if re.search(r'\bpresent\b|\bdisplay\s+work\b', tl):
        return "Present group findings to the class; listen to and give feedback on other groups' presentations"

    if re.search(r'\bdraw\b|\bsketch\b|\bdiagram\b', tl):
        return "Draw and label the required diagram neatly in exercise book"

    if re.search(r'\bidentif\b|\blist\s+the\b|\bname\s+the\b', tl):
        return "Identify and write down the required items in exercise book; compare answers with a partner"

    if re.search(r'read\s+and|read\s+the|\breading\b', tl):
        return "Read the assigned passage carefully; answer comprehension questions in full sentences"

    if re.search(r'\bsolv\b|\bcalculat\b|\bcomput\b', tl):
        return "Solve the given problems independently; compare working with a partner and correct errors"

    if re.search(r'plot\s+a\s+graph|draw\s+a\s+graph|number\s+line', tl):
        return "Plot the data on graph paper; label axes correctly and verify with a partner"

    if re.search(r'role\s+play|dramatiz|act\s+out', tl):
        return "Participate actively in the role play; reflect on the experience and share key lessons"

    if re.search(r'write\s+a|compose\s+a|draft\s+a', tl):
        return "Write the required piece independently; peer-edit for clarity and correctness"

    # Stub-step defaults generated when DB experiences is empty
    if re.search(r'\bintroduce\s+key\s+concepts\b|\bintroduction\s+to\b', tl):
        return f"Share prior knowledge of {topic}; listen to the introduction and write down three key points in exercise book"

    if re.search(r'\bexplore\b.{0,30}\bhands[- ]on\b|\bexplore\b.{0,30}\bgroup\s+work\b', tl):
        return f"Take part in hands-on activities exploring {topic}; record observations and share findings with the group"

    if re.search(r'\bconsolidat\b', tl):
        return f"Complete the practice exercises on {topic} independently; check answers with a partner and correct any errors"

    # Fallback: strip teacher-instruction prefixes, then mirror the action directly
    cleaned = re.sub(
        r'^(the\s+learner\s+is\s+guided\s+to\s*:?|learners?\s+are\s+guided\s+to\s*:?'
        r'|guide\s+learners?\s+to\s*:?|ask\s+learners?\s+to\s*:?'
        r'|introduce\s+key\s+concepts\s+of\s+\S+\s+through\s+)',
        '', text, flags=re.IGNORECASE
    ).strip()

    verb_match = re.match(
        r'^(identify|list|name|describe|explain|compare|discuss|analyse|analyze|write|'
        r'read|draw|solve|calculate|measure|observe|record|present|research|'
        r'complete|create|design|construct|perform|demonstrate|evaluate|brainstorm|'
        r'explore|investigate|examine|outline|reflect|apply|use|practise|practice|'
        r'consolidate|develop|introduce)',
        cleaned, re.IGNORECASE
    )
    if verb_match:
        return f"{cleaned.rstrip('.')}; record findings in exercise book and share with the class"

    return f"Actively participate in the activity on {topic}; record findings and discuss outcomes with peers"


def _generate_extended_activities(subject, topic, substrand, experiences=None):
    """Return (fast_learner_activity, support_activity) specific to topic."""
    combined = (topic + ' ' + (substrand or '') + ' ' + subject).lower()

    ext_map = [
        (['soil conserv', 'soil erosion'],
         f"Fast learners: Research two soil conservation techniques not covered in the lesson (e.g. terracing, gabions); draw labelled diagrams and explain where each is best applied",
         f"Need support: Match provided picture cards showing effects of soil erosion to the correct conservation method from a given list"),
        (['water harvest', 'water storage', 'irrigation'],
         f"Fast learners: Design a labelled rainwater harvesting system for a school farm; state the function of each component",
         f"Need support: Label the parts of a simple water harvesting structure using a provided diagram and word bank"),
        (['crop produc', 'kitchen garden', 'backyard garden', 'seed', 'planting'],
         f"Fast learners: Plan a seasonal crop calendar for a kitchen garden in your county, showing rainfall patterns and planting windows",
         f"Need support: Sort provided seed picture cards into food crops and cash crops using the textbook as reference"),
        (['poultry', 'livestock', 'animal'],
         f"Fast learners: Compare two commercial poultry or livestock breeds; present findings as a labelled comparison table",
         f"Need support: Label the main parts of a poultry house or livestock pen using a given diagram and word bank"),
        (['pest', 'disease control', 'weed'],
         f"Fast learners: Create a one-month pest/disease monitoring diary for one crop grown in your area; include control measures",
         f"Need support: Match pictures of crop diseases to their names and symptoms using provided photo cards"),
        (['fraction', 'decimal', 'ratio', 'percent'],
         f"Fast learners: Write and solve three real-life word problems involving {topic} (e.g. shopping, cooking, farming); show full working",
         f"Need support: Use fraction strips or a number line to model each problem before solving"),
        (['algebra', 'equation', 'linear', 'quadratic'],
         f"Fast learners: Write a two-variable real-life equation from a personal scenario; solve and verify the solution",
         f"Need support: Use a balance diagram template provided by the teacher to model and solve simple one-variable equations"),
        (['geometr', 'shape', 'area', 'volume', 'angle'],
         f"Fast learners: Measure and calculate the area and perimeter of three different spaces in school; present all working",
         f"Need support: Use square grid paper to count units for area before applying the formula"),
        (['statistic', 'data', 'probabilit', 'graph'],
         f"Fast learners: Collect real data from classmates (e.g. heights, travel times) and draw the most appropriate statistical graph",
         f"Need support: Complete a frequency table from given data with guided prompts before drawing a bar chart"),
        (['reading', 'comprehension', 'intensive reading'],
         f"Fast learners: Write a critical review of the passage, identifying the central theme and supporting it with textual evidence",
         f"Need support: Use provided sentence starters to answer comprehension questions in full sentences"),
        (['writing', 'essay', 'composition', 'creative writing'],
         f"Fast learners: Write an extended piece incorporating figurative language, a structured argument and a memorable conclusion",
         f"Need support: Use the provided paragraph frame to write one structured body paragraph with a topic sentence"),
        (['grammar', 'tense', 'punctuation', 'sentence'],
         f"Fast learners: Write ten original sentences each demonstrating a different grammatical structure covered this week",
         f"Need support: Identify and correct grammatical errors in a provided paragraph using a grammar reference card"),
        (['ecosystem', 'biodiversit', 'environment', 'conservation', 'climate'],
         f"Fast learners: Research a locally threatened species; present a three-point conservation action plan with justification",
         f"Need support: Sort pictures of living organisms into their correct ecosystems using a provided classification key"),
        (['cell', 'microscop', 'organism', 'photosynthes', 'respiration'],
         f"Fast learners: Create an annotated diagram showing the stages of {topic} at the cellular level",
         f"Need support: Label a given diagram using a word bank; answer three short questions from the textbook"),
        (['map', 'topograph', 'map reading'],
         f"Fast learners: Draw a sketch map of the school environment with a key showing at least five features",
         f"Need support: Identify three physical and three human features on a provided map using the legend"),
        (['history', 'civic', 'constitution', 'government', 'rights', 'duties'],
         f"Fast learners: Research how one historical event shaped a right or duty in Kenya's constitution; write a short structured report",
         f"Need support: Complete a structured timeline placing key historical events in correct chronological order"),
        (['health', 'nutrition', 'diet', 'hygiene'],
         f"Fast learners: Plan a one-week balanced meal plan for a family of four; justify each day's food group choices",
         f"Need support: Sort food picture cards into correct food groups using a food pyramid reference chart"),
        (['cre', 'christian', 'leisure', 'ire', 'islamic', 'religion', 'faith', 'moral', 'religious'],
         f"Fast learners: Research a biblical or religious teaching on {topic}; write a short structured reflection (150 words) explaining how its values apply to modern youth life",
         f"Need support: Use a provided scripture or text extract to answer three guided questions about the values and lessons taught in relation to {topic}; use the sentence starters provided"),
    ]

    for keywords, fast, support in ext_map:
        if any(kw in combined for kw in keywords):
            return fast, support

    fast = f"Fast learners: Research an advanced aspect of {topic} not covered in today's lesson; create a written or visual summary to share with the class"
    support = f"Need support: Complete a structured activity sheet on {topic} with guided questions, a word bank and visual prompts"
    return fast, support


def _generate_values_with_context(values_raw, subject, topic, substrand):
    """Return 2–3 value statements each with a lesson-specific contextual explanation."""
    combined = (topic + ' ' + (substrand or '') + ' ' + subject).lower()

    _is_literary = any(k in combined for k in [
        'character', 'story', 'narrative', 'poem', 'poetry', 'oral',
        'literature', 'drama', 'play', 'reader', 'reading', 'writing',
        'english', 'language', 'grammar', 'comprehension',
    ])
    _is_science = any(k in combined for k in [
        'science', 'biology', 'chemistry', 'physics', 'ecosystem', 'cell',
        'experiment', 'observ',
    ])

    if _is_literary:
        context_map = {
            'respect':        f"learners appreciate diverse character perspectives and value the experiences of others encountered in {topic}",
            'integrity':      f"learners analyse characters' moral choices honestly and form evidence-based personal opinions about {topic}",
            'love':           f"learners show empathy for characters' experiences and demonstrate compassion for diverse human situations in {topic}",
            'unity':          f"learners collaborate in group discussions and dramatisations, combining insights to understand {topic}",
            'responsibility': f"learners take ownership of their reading, written responses and contributions to class discussion on {topic}",
            'peace':          f"learners resolve differing literary interpretations respectfully during group work on {topic}",
            'patriotism':     f"learners appreciate how texts on {topic} reflect Kenyan culture, identity and national values",
            'social justice': f"learners consider themes of fairness, equality and justice as represented in texts about {topic}",
        }
    elif _is_science:
        context_map = {
            'integrity':      f"learners record and report experimental observations honestly without falsifying results during {topic}",
            'responsibility': f"learners handle apparatus safely and take ownership of fair testing during {topic}",
            'respect':        f"learners value peers' experimental findings and consider different scientific explanations for {topic}",
            'unity':          f"learners collaborate in practicals, sharing roles and expertise when investigating {topic}",
            'love':           f"learners show curiosity and care for the natural world through their investigation of {topic}",
            'patriotism':     f"learners appreciate how scientific knowledge about {topic} contributes to Kenya's development",
            'peace':          f"learners engage in respectful scientific debate and collaborative problem solving during {topic}",
            'social justice': f"learners consider equitable access to science and technology in the context of {topic}",
        }
    else:
        context_map = {
            'unity':          f"learners collaborate in groups during {topic} activities, combining individual strengths to achieve a shared goal",
            'responsibility': f"learners take ownership of their tasks and handle all materials carefully during {topic}",
            'integrity':      f"learners engage honestly and ethically in all tasks and discussions related to {topic}",
            'respect':        f"learners listen attentively to peers' contributions and value diverse approaches to {topic}",
            'peace':          f"learners resolve group disagreements calmly and maintain a harmonious working environment during {topic}",
            'love':           f"learners show care for the environment, community and peers through their engagement with {topic}",
            'patriotism':     f"learners appreciate how {topic} contributes to national development and the well-being of Kenya",
            'social justice': f"learners consider equitable access to resources and fair opportunities related to {topic}",
        }

    working = list(values_raw) if values_raw else []

    # Supplement to at least 2 values using topic-appropriate defaults
    if any(k in combined for k in ['soil', 'farm', 'crop', 'agri', 'water harvest', 'livestock', 'poultry']):
        defaults = ['Unity', 'Responsibility', 'Patriotism']
    elif any(k in combined for k in ['math', 'algebra', 'fraction', 'geometr', 'statistic']):
        defaults = ['Integrity', 'Responsibility', 'Respect']
    elif any(k in combined for k in ['reading', 'writing', 'grammar', 'english', 'language',
                                       'character', 'story', 'narrative', 'poem', 'poetry',
                                       'oral', 'literature', 'drama', 'play', 'reader']):
        defaults = ['Respect', 'Integrity', 'Love']
    elif any(k in combined for k in ['science', 'ecosystem', 'cell', 'biology', 'chemistry']):
        defaults = ['Responsibility', 'Integrity', 'Love']
    elif any(k in combined for k in ['social studies', 'history', 'civic', 'geography']):
        defaults = ['Patriotism', 'Unity', 'Social Justice']
    else:
        defaults = ['Responsibility', 'Respect', 'Unity']

    existing_lower = {v.lower() for v in working}
    for d in defaults:
        if len(working) >= 3:
            break
        if d.lower() not in existing_lower:
            working.append(d)
            existing_lower.add(d.lower())

    result = []
    for v in working[:3]:
        key = v.lower().strip()
        context = context_map.get(key, f"demonstrated through thoughtful and active participation in {topic} activities")
        result.append(f"{v} — {context}")
    return result


def _generate_extension_activity(topic, substrand, subject, prev_experiences):
    """Return a NEW activity that applies or extends what was done in Lesson 1."""
    combined = (topic + ' ' + (substrand or '') + ' ' + subject).lower()

    ext_map = [
        (['soil conserv', 'soil erosion'],
         (f"Guide learners to evaluate the farm model constructed in Lesson 1: identify weaknesses, "
          f"suggest improvements, and record two additional soil conservation measures not used in the model",
          f"Evaluate the Lesson 1 farm model; add two improvements and record findings with labelled sketches")),
        (['water harvest', 'water storage', 'irrigation'],
         (f"Guide learners to calculate the water harvesting capacity of a proposed structure using given dimensions",
          f"Calculate the water storage volume using the formula V = l × w × h; compare answers with a partner")),
        (['crop produc', 'kitchen garden', 'seed', 'planting', 'backyard garden'],
         (f"Guide learners to plan a planting calendar for a kitchen garden, selecting crops suitable for local seasons",
          f"Use provided rainfall and temperature data to select two crops and justify the planting dates chosen")),
        (['poultry', 'livestock', 'animal'],
         (f"Guide learners to calculate the cost-benefit analysis of a small-scale {topic.lower()} enterprise "
          f"using provided unit costs",
          f"Complete the cost-benefit worksheet; identify which variable most affects profitability")),
        (['pest', 'disease control', 'weed'],
         (f"Guide learners to develop a one-week integrated pest management (IPM) schedule for a specific crop",
          f"Draft an IPM weekly schedule; include at least one biological, cultural and chemical control measure")),
        (['fraction', 'decimal', 'ratio', 'percent'],
         (f"Guide learners to solve three multi-step real-life problems applying {topic.lower()} "
          f"(e.g. shopping, cooking, farming contexts)",
          f"Solve the three word problems showing full working; underline the final answer for each")),
        (['algebra', 'equation', 'linear', 'quadratic'],
         (f"Guide learners to formulate and solve their own real-life equation based on a scenario they create",
          f"Write a personal scenario, form the equation, solve and verify the solution by substituting back")),
        (['geometr', 'shape', 'area', 'volume', 'angle'],
         (f"Guide learners to measure classroom/school spaces and apply {topic.lower()} formulae to real measurements",
          f"Measure and record three dimensions; calculate using the appropriate formula and compare with estimates")),
        (['statistic', 'data', 'graph', 'probabilit'],
         (f"Guide learners to collect real data from the class (e.g. travel time, shoe size) "
          f"and draw the most appropriate graph",
          f"Collect data, complete the frequency table and draw the graph; write two observations from the graph")),
        (['reading', 'comprehension', 'intensive reading'],
         (f"Guide learners to compare the Lesson 1 passage to a second shorter text on the same theme; "
          f"identify similarities and differences in purpose and tone",
          f"Read the second passage; complete a two-column comparison table (Passage 1 vs Passage 2) in exercise book")),
        (['writing', 'essay', 'composition', 'creative writing'],
         (f"Guide learners to peer-edit their Lesson 1 draft using a provided checklist; then write a revised final copy",
          f"Use the editing checklist to improve the Lesson 1 draft; write the final polished version")),
        (['grammar', 'tense', 'punctuation', 'sentence'],
         (f"Guide learners to apply the grammar rule from Lesson 1 in original sentences, "
          f"then analyse a paragraph for correct/incorrect usage",
          f"Write five original sentences applying the rule; mark and correct the errors in the provided paragraph")),
        (['ecosystem', 'biodiversit', 'environment', 'conservation', 'climate'],
         (f"Guide learners to analyse a before/after photo of a degraded vs restored ecosystem; "
          f"identify causes and suggest restoration actions",
          f"Study the two photos; list three causes of degradation and propose two restoration actions with justification")),
        (['cell', 'microscop', 'organism', 'photosynthes', 'respiration'],
         (f"Guide learners to create an annotated flow diagram summarising the process studied in Lesson 1",
          f"Draw the flow diagram with at least four labelled stages; write one sentence explaining each stage")),
        (['map', 'topograph', 'map reading'],
         (f"Guide learners to apply map reading skills to interpret a real local map and answer structured questions",
          f"Use the provided local map to answer five structured questions on distance, direction and features")),
        (['history', 'civic', 'constitution', 'government', 'rights', 'duties'],
         (f"Guide learners to create a case study of one right or duty from Lesson 1 as it applies in their community",
          f"Write a short case study (8–10 sentences) giving a real example of the right/duty in community life")),
        (['health', 'nutrition', 'diet', 'hygiene'],
         (f"Guide learners to evaluate a sample meal for nutritional balance using the food groups chart from Lesson 1",
          f"Analyse the sample meal; identify any missing food groups and suggest a corrected balanced version")),
    ]

    for keywords, (teacher_act, learner_act) in ext_map:
        if any(kw in combined for kw in keywords):
            return teacher_act, learner_act

    # Generic fallback
    teacher = (f"Guide learners to apply the key concepts from Lesson 1 to a new scenario: "
               f"present a case study or problem related to {topic} and ask learners to propose solutions in groups")
    learner = (f"Analyse the new scenario in groups; apply Lesson 1 concepts to propose and justify a solution; "
               f"record the group response in exercise book")
    return teacher, learner


def _generate_assessment_criteria(outcomes, topic):
    """Return a list of assessment criteria statements derived from SLOs."""
    if not outcomes:
        return [
            f"Learner can explain key concepts of {topic} accurately",
            f"Learner demonstrates understanding through practical application",
            f"Learner participates actively and communicates ideas clearly",
        ]
    criteria = []
    for out in outcomes:
        # Convert outcome to criterion: "describe X" → "Learner can describe X with accuracy"
        out_clean = out.strip().rstrip('.')
        first_word = out_clean.split()[0].lower() if out_clean else ''
        if first_word in ('describe', 'explain', 'define', 'state', 'identify', 'name', 'list'):
            criteria.append(f"Learner can {out_clean} correctly and in own words")
        elif first_word in ('demonstrate', 'carry out', 'perform', 'conduct', 'apply', 'use'):
            criteria.append(f"Learner {out_clean} accurately and safely during the practical task")
        elif first_word in ('calculate', 'solve', 'compute', 'measure', 'draw', 'plot'):
            criteria.append(f"Learner can {out_clean}, showing all working and with correct result")
        else:
            criteria.append(f"Learner can {out_clean} as evidenced by their written/practical work")
    return criteria[:4]


def _build_single_lesson_plan(
    lesson_number, total_lessons, subject, grade, topic, strand, substrand,
    outcomes, questions, experiences, competencies, values, duration, date_str,
    links=None, pcis=None, all_experiences=None
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
    
    # Format key inquiry questions — strictly 2-3, directly related to strand (Rule 5)
    questions = questions[:3]
    # Pad to at least 2 if the DB only supplied 1
    if len(questions) < 2:
        combined_kiq = (topic + ' ' + (substrand or '')).lower()
        if any(k in combined_kiq for k in ['soil', 'conserv', 'agri', 'farm', 'crop', 'poultry', 'livestock']):
            questions.append("How can we protect our soil and natural resources to ensure food security for future generations?")
        elif any(k in combined_kiq for k in ['reading', 'comprehension', 'poetry', 'narrative', 'prose', 'intensive']):
            questions.append("How does reading widely improve your ability to communicate effectively?")
        elif any(k in combined_kiq for k in ['grammar', 'phrasal', 'tense', 'punctuation', 'sentence', 'writing', 'composition']):
            questions.append("How does correct use of grammar and language help you communicate more clearly?")
        elif any(k in combined_kiq for k in ['cre', 'christian', 'creation', 'leisure', 'faith', 'ire', 'islamic', 'religion']):
            questions.append("How can the values and teachings from this lesson guide your decisions in everyday life?")
        elif any(k in combined_kiq for k in ['math', 'algebra', 'fraction', 'geometr', 'statistic', 'equation']):
            questions.append("Where do you encounter this mathematical concept in your daily life or community?")
        elif any(k in combined_kiq for k in ['science', 'ecosystem', 'cell', 'photosynthes', 'organism', 'energy', 'force']):
            questions.append("How does understanding this scientific concept help you solve real-world problems?")
        elif any(k in combined_kiq for k in ['map', 'geograph', 'history', 'civic', 'social', 'population']):
            questions.append("How does the knowledge from this lesson help you become a more responsible citizen?")
        elif any(k in combined_kiq for k in ['health', 'nutrition', 'diet', 'hygiene']):
            questions.append("How can you apply what you learn about health and nutrition to improve your daily life?")
        else:
            questions.append(f"How can you apply what you learn about {substrand or topic} to benefit your community?")
    if questions:
        kiq_list = "\n".join([f"{i+1}. {item}" for i, item in enumerate(questions)])
    else:
        kiq_list = f"1. What are the key concepts in {substrand or topic}?\n2. How does this knowledge apply in daily life?"
    
    # -----------------------------------------------------------------------
    # Build lesson steps — Lesson 1 uses DB activities; Lesson 2+ is NEW and
    # distinctly different: review → extension → assessment
    # -----------------------------------------------------------------------
    if lesson_number == 1:
        lesson_steps = list(experiences[:3]) if experiences else []
        step_defaults = [
            f"Introduce key concepts of {topic} through discussion and real-life examples",
            f"Guide learners to explore {topic} through hands-on activities and group work",
            f"Consolidate understanding of {topic} through practice exercises",
        ]
        while len(lesson_steps) < 3:
            lesson_steps.append(step_defaults[len(lesson_steps)])
    else:
        # Use ALL DB activities (all_experiences) as the reference for what Lesson 1 covered
        l1_ref = (all_experiences or experiences or [])
        l1_activity_summary = (
            l1_ref[0] if l1_ref else f"activities introduced during Lesson 1 on {topic}"
        )
        ext_teacher, _ext_learner_inline = _generate_extension_activity(
            topic, substrand, subject, l1_ref
        )
        lesson_steps = [
            # Step 1 — review / presentation of Lesson 1 work
            f"Invite groups to present or display their completed work from Lesson 1 "
            f"({l1_activity_summary[:80].rstrip()}); facilitate brief peer feedback",
            # Step 2 — NEW applying/extending activity
            ext_teacher,
            # Step 3 — assessment activity
            f"Administer a short written or practical assessment on {topic}: "
            f"learners answer three targeted questions covering all SLOs independently",
        ]
    
    # Format competencies (clean — no "Values" or "Link to" prefixes)
    competencies_text = "\n".join([f"- {c}" for c in competencies]) if competencies else "- Critical thinking and problem solving\n- Communication and collaboration\n- Self-efficacy"
    
    # Format values with lesson-specific explanations (2–3 entries minimum)
    values_entries = _generate_values_with_context(values, subject, topic, substrand)
    values_text = "\n".join([f"- {v}" for v in values_entries])
    
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
            f"Assess prior knowledge through brief questioning. "
            f"Relate {topic} to real-life contexts and state today's learning objectives."
        )
        learner_intro = (
            f"Respond to starter questions about {topic}. "
            f"Share prior knowledge and real-life connections. "
            f"Listen to and write down today's learning outcomes."
        )
    else:
        # Lesson 2+: open with presentation/review of Lesson 1 work
        teacher_intro = (
            f"Direct learners to display or prepare their Lesson 1 work for presentation. "
            f"Call on two or three groups to briefly present their key findings on {topic}. "
            f"Clarify any misconceptions identified during the review."
        )
        learner_intro = (
            f"Display or prepare Lesson 1 work for presentation. "
            f"Listen to peers' presentations; note one similarity and one difference "
            f"from their own Lesson 1 work. "
            f"Ask clarifying questions about any misconceptions."
        )

    # Lesson Body / Development
    teacher_dev_parts = []
    learner_dev_parts = []
    if lesson_number == 1:
        # Normal DB-driven steps for Lesson 1
        for i, step in enumerate(lesson_steps[:3]):
            teacher_dev_parts.append(f"Step {i+1}: {step}")
            learner_dev_parts.append(f"Step {i+1}: {_generate_step_learner_mirror(step, topic)}")
        teacher_dev_parts.append(
            "Circulate and monitor progress; ask probing questions to deepen understanding"
        )
        learner_dev_parts.append(
            "Record all findings in exercise book; discuss conclusions with peers"
        )
    else:
        # Lesson 2+: Step 1 = review presentation, Step 2 = new extension, Step 3 = assessment
        # Step 1 — Facilitate Lesson 1 review/presentation
        teacher_dev_parts.append(f"Step 1: {lesson_steps[0]}")
        learner_dev_parts.append(
            f"Step 1: Present Lesson 1 work to the class or in groups; "
            f"take brief notes on peer feedback and record one improvement to make"
        )
        # Step 2 — NEW extension activity
        teacher_dev_parts.append(f"Step 2: {lesson_steps[1]}")
        # Mirror the extension activity specifically
        _l1_ref_inner = (all_experiences or experiences or [])
        _, _ext_learner_step2 = _generate_extension_activity(topic, substrand, subject, _l1_ref_inner)
        learner_dev_parts.append(f"Step 2: {_ext_learner_step2}")
        # Step 3 — Assessment activity
        teacher_dev_parts.append(
            f"Step 3: {lesson_steps[2]} "
            f"Circulate and note individual performance against each SLO."
        )
        learner_dev_parts.append(
            f"Step 3: Attempt all assessment questions individually without assistance; "
            f"show all working where applicable; submit on completion"
        )

    teacher_dev = " ".join(teacher_dev_parts)
    learner_dev = " ".join(learner_dev_parts)

    # Conclusion
    if lesson_number == 1 and total_lessons > 1:
        teacher_concl = (
            f"Summarize key learning points from Lesson 1. "
            f"Preview Lesson 2: inform learners they will present their work and complete "
            f"an extension task. Assign: learners to review and finalize their Lesson 1 work."
        )
        learner_concl = (
            f"Share two key things learned today about {topic}. "
            f"Record the Lesson 2 preview and assignment in exercise book. "
            f"Begin reviewing/finalizing Lesson 1 work for presentation."
        )
    elif lesson_number > 1:
        # Individual written reflection + assessment criteria
        criteria = _generate_assessment_criteria(outcomes, topic)
        criteria_str = " | ".join([f"({j+1}) {c}" for j, c in enumerate(criteria)])
        teacher_concl = (
            f"Read out the assessment criteria for this lesson: {criteria_str}. "
            f"Direct learners to complete an individual written reflection in exercise book. "
            f"Collect assessment work; provide formative feedback before the next lesson."
        )
        learner_concl = (
            f"Self-assess against each criterion read by the teacher. "
            f"Write individual reflection: (1) I can now... (2) I found challenging... "
            f"(3) I will apply this by... Submit assessment work to the teacher."
        )
    else:
        # Single lesson or final lesson in multi-lesson set
        teacher_concl = (
            f"Summarize all key learning points on {topic}. "
            f"Celebrate learner progress. "
            f"Connect learning to broader curriculum goals."
        )
        learner_concl = (
            f"Reflect on key takeaways from {topic}. "
            f"Share achievements and areas of growth. "
            f"Relate learning to everyday life."
        )
    
    _all_res = _generate_lesson_resources(subject, grade, topic, substrand)
    # Introduction: KICD books + first topic-specific item only
    if lesson_number == 1:
        res_intro = ", ".join(_all_res[:2] + ([_all_res[2]] if len(_all_res) > 2 else ['Chalkboard/whiteboard and chalk/markers']))
    else:
        # Lesson 2+ intro: learner work from Lesson 1 + KICD book
        res_intro = f"{_all_res[0]}, Lesson 1 completed work (group models/notes/worksheets), Chalkboard/whiteboard and chalk/markers"
    # Development: all resources for Lesson 1; assessment sheet added for Lesson 2+
    if lesson_number == 1:
        res_dev = ", ".join(_all_res)
    else:
        res_dev = ", ".join(_all_res) + ", Short assessment worksheet/question card"
    # Conclusion: reference book + exercise books + assessment rubric
    res_concl = ", ".join([_all_res[0], 'Learner exercise books', 'Assessment rubric/checklist'])

    if lesson_number == 1:
        assessment_intro = "Oral questions, Observation"
        assessment_dev = "Observation, Practical work, Group participation, Oral/written exercises"
        assessment_concl = "Question and answer, Learner self-assessment"
    else:
        assessment_intro = "Peer feedback observation, Presentation checklist"
        assessment_dev = "Written assessment, Observation of extension task, Individual performance"
        assessment_concl = "Self-assessment against criteria, Written reflection, Formative feedback"

    # Extended activities (topic-specific)
    _ext_fast_raw, _ext_support_raw = _generate_extended_activities(subject, topic, substrand, all_experiences or experiences)
    ext_fast = f"- {_ext_fast_raw}"
    ext_support = f"- {_ext_support_raw}"

    # Reflection / assessment criteria block — lesson-specific
    if lesson_number == 1 and total_lessons > 1:
        reflection_block = (
            f"- What key concepts about {topic} did learners understand today?\n"
            f"- Which learners may need additional support before Lesson 2?\n"
            f"- Was the group activity completed as intended?\n"
            f"- Reminder: ensure all groups finalize their work for Lesson 2 presentation."
        )
    elif lesson_number > 1:
        criteria = _generate_assessment_criteria(outcomes, topic)
        crit_lines = "\n".join([f"  {j+1}. {c}" for j, c in enumerate(criteria)])
        reflection_block = (
            f"Assessment Criteria (tied to SLOs):\n{crit_lines}\n\n"
            f"Learner Written Reflection prompts:\n"
            f"  - I can now: ___________________________\n"
            f"  - I found challenging: _________________\n"
            f"  - I will apply this by: ________________\n\n"
            f"Teacher Reflection:\n"
            f"- Did all learners meet the assessment criteria?\n"
            f"- Which criteria require re-teaching before the next lesson?\n"
            f"- How will individual written reflections inform planning?"
        )
    else:
        reflection_block = (
            f"- What did learners learn about {topic} today?\n"
            f"- What was challenging for most learners?\n"
            f"- How can this knowledge be applied in everyday life?"
        )

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
| Introduction ({intro_time} min) | {teacher_intro} | {learner_intro} | {res_intro} | {assessment_intro} |
| Lesson Body / Development ({dev_time} min) | {teacher_dev} | {learner_dev} | {res_dev} | {assessment_dev} |
| Conclusion ({concl_time} min) | {teacher_concl} | {learner_concl} | {res_concl} | {assessment_concl} |

11) EXTENDED ACTIVITIES

{ext_fast}
{ext_support}

12) REFLECTION AND ASSESSMENT CRITERIA

{reflection_block}

---
⚠️ AI-generated — verify against KICD curriculum design before classroom use.
"""
    return plan


def generate_lesson_plan(subject, grade, topic="", duration=40):
    """
    Generate lesson plan(s) from curriculum database.
    
    If the CBC curriculum specifies multiple lessons for a strand/substrand,
    this will generate ALL the required lesson plans with content distributed
    across them.
    """
    # Step 1: find any matching entry to confirm subject+grade exists
    curriculum = query_curriculum(subject, grade)
    if not curriculum:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }

    # Step 2: get ALL entries for this subject+grade and pick the one whose
    # substrand best matches the topic/prompt hint — Rule 2
    from curriculum_db import get_curriculum as _get_all
    all_for_grade = _get_all(subject=curriculum['subject'], grade=curriculum['grade'])
    if isinstance(all_for_grade, list) and len(all_for_grade) > 1 and topic:
        curriculum = _find_best_curriculum_entry(all_for_grade, topic)
    elif isinstance(all_for_grade, list) and len(all_for_grade) >= 1:
        curriculum = all_for_grade[0]
    
    # Extract curriculum components
    strand = curriculum.get('strand', '')
    _sub_num = curriculum.get('substrand_number', '').strip()
    _sub_name = curriculum.get('substrand', '').strip()
    substrand = _combine_substrand(_sub_num, _sub_name)
    learning_outcomes = curriculum.get('learning_outcomes', [])
    key_questions = curriculum.get('key_inquiry_questions', [])
    experiences = curriculum.get('suggested_learning_experiences', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])
    raw_pcis = curriculum.get('pcis', [])
    raw_link_subjects = curriculum.get('link_subjects', [])
    
    # Clean up empty or stub items — strip PDF preamble headers from SLOs
    learning_outcomes = [_clean_slo(o) for o in learning_outcomes]
    learning_outcomes = [o for o in learning_outcomes if _is_valid_slo(o)]
    key_questions = [q for q in key_questions if len(q.strip()) > 5]
    # Filter preamble stubs like "Learners are guided to:" — Issue 4
    experiences = [
        e for e in experiences
        if len(e.strip()) > 10 and not _STUB_ACTIVITY.match(e.strip())
    ]
    
    # The CBC parser mixed values, links, and PCIs into competencies/values fields.
    # Separate them properly.
    competencies, values, links, pcis = _classify_competency_items(
        raw_competencies + raw_values
    )
    
    # Determine how many lessons the curriculum requires
    # First, try to get from database field (most reliable)
    num_lessons = curriculum.get('num_lessons', 0)
    
    # Ensure it's an integer
    try:
        num_lessons = int(num_lessons) if num_lessons else 0
    except (ValueError, TypeError):
        num_lessons = 0
    
    # If database doesn't have it, try extracting from strand text
    if num_lessons == 0 or num_lessons is None:
        num_lessons = _extract_lesson_count(strand)
    
    # If still no lesson count, estimate from the amount of curriculum content
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
    
    # Extract a clean topic from the user's prompt (strip noise like "generate a grade X lesson plan on")
    if topic and len(topic) > 60:
        import re as _re
        topic_match = _re.search(r'\bon\s+([a-zA-Z0-9\s\-]{3,120})', topic, _re.IGNORECASE)
        if topic_match:
            extracted = topic_match.group(1)
            # Strip leading "the strand / substrand / topic / unit" prefix — Rule 1
            extracted = _re.sub(
                r'^(?:the\s+)?(?:strand|sub-?strand|topic|unit)\s+',
                '', extracted, flags=_re.IGNORECASE
            )
            # Trim trailing noise like "under the substrand ..."
            extracted = _re.split(
                r'\b(?:under|for|in|during|term)\b', extracted,
                maxsplit=1, flags=_re.IGNORECASE
            )[0]
            extracted = _re.sub(r'\s+', ' ', extracted).strip(' .,-_')
            if len(extracted) > 3:
                topic = extracted.title()
            else:
                topic = strand_topic
        else:
            topic = strand_topic
    elif not topic or topic == subject:
        topic = strand_topic
    # Prefer the substrand's clean name as the topic title when it's more specific
    if substrand and len(substrand.strip()) > 3:
        clean_sub = re.sub(r'^[\.\d\s]+', '', substrand).strip()
        if len(clean_sub) > 3:
            topic = clean_sub.title()
    
    # Determine lesson duration based on grade
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    if grade_num <= 6:
        duration = 35
    
    # Distribute experiences across lessons; SLOs shown in full every lesson — Issue 6
    outcomes_per_lesson = [learning_outcomes for _ in range(num_lessons)]
    questions_per_lesson = _distribute_items(key_questions, num_lessons)
    experiences_per_lesson = _distribute_items(experiences, num_lessons)
    
    # Approved competencies, supplemented to minimum 3 — Issues 3 & 4
    approved_competencies = _filter_to_approved_competencies(competencies + raw_competencies)
    shared_competencies = _supplement_competencies(approved_competencies, subject, topic, minimum=3)
    shared_values = _filter_to_approved_values(values + raw_values)
    # Topic-aware PCIs and cross-curricular links — Issues 1 & 2
    shared_pcis = _generate_pcis(strand, substrand, topic, raw_pcis + pcis)
    shared_links = _generate_cross_links(subject, strand, substrand, topic, raw_link_subjects + links)
    
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
            all_experiences=experiences,  # full list so Lesson 2+ knows what Lesson 1 covered
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


def _clean_strand_name(text):
    """Fix PDF line-break artifacts in strand names, e.g. 'Christia n Living' → 'Christian Living'."""
    if not text:
        return text
    # Strip leading dots/punctuation (e.g. '. Reading' → 'Reading')
    text = re.sub(r'^[\s.,:;\-]+', '', text).strip()
    # Remove lesson-count suffixes like '(9 lessons)' from strand display
    text = re.sub(r'\s*\(\s*\d+\s*lessons?\s*\)', '', text, flags=re.IGNORECASE).strip()
    # Rejoin single letters/fragments that were split by a line-break in the PDF
    # e.g. 'Christia n' → 'Christian', 'Livi ng' → 'Living'
    text = re.sub(
        r'([A-Za-z]{3,})\s+([a-z]{1,3})(?=\s|$)',
        lambda m: m.group(1) + m.group(2)
            if not m.group(2) in ('in', 'on', 'of', 'to', 'by', 'at', 'is', 'an', 'and', 'the', 'or')
            else m.group(0),
        text
    )
    return text.strip()


def generate_scheme_of_work(subject, grade, term="1"):
    """
    Generate a Scheme of Work in the standard Kenyan CBC / TSC tabular format.
    Iterates through ALL sub-strands for the subject/grade so every week
    covers a different topic — not the same one repeated.

    Columns: Wk | Lsn | Strand | Sub-strand | Specific Learning Outcomes |
    Learning Experiences | Key Inquiry Question(s) | Learning Resources |
    Assessment | Core Competencies | Values | PCIs | Remarks
    """
    from curriculum_db import get_curriculum as _get_all_curriculum  # noqa (kept for compat)

    # ── Fetch EVERY sub-strand entry for this subject + grade ────────────────
    all_entries = _get_all_matching_entries(subject, grade)
    if not all_entries:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }

    valid_entries = [
        e for e in all_entries
        if e.get('substrand') and len(e.get('substrand', '').strip()) > 3
    ]
    if not valid_entries:
        valid_entries = all_entries

    current_year = datetime.today().year
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    lesson_duration = 35 if grade_num <= 6 else 40
    lessons_per_week = 3 if grade_num <= 6 else 2

    MIN_TERM_WEEKS = 12
    MAX_TERM_WEEKS = 14

    # ── Build one lesson-row per lesson across all sub-strands ───────────────
    table_rows = []
    global_lesson = 0
    week_num = 1
    lessons_in_current_week = 0

    for entry in valid_entries:
        raw_strand = entry.get('strand', '') or subject
        strand = _clean_strand_name(raw_strand)

        _sub_num = entry.get('substrand_number', '').strip()
        _sub_name = entry.get('substrand', '').strip()
        substrand = _combine_substrand(_sub_num, _sub_name)

        learning_outcomes = entry.get('learning_outcomes', [])
        key_questions     = entry.get('key_inquiry_questions', []) or []
        experiences       = entry.get('suggested_learning_experiences', []) or []
        raw_competencies  = entry.get('core_competencies', []) or []
        raw_values        = entry.get('values', []) or []

        # Clean SLOs
        learning_outcomes = [_clean_slo(o) for o in learning_outcomes]
        learning_outcomes = [o for o in learning_outcomes if _is_valid_slo(o)]

        # Clean experiences (strip preamble stubs)
        experiences = [
            re.sub(r'^learners?\s+are\s+guided\s+to\s*:?\s*', '', e, flags=re.IGNORECASE).strip()
            for e in experiences
        ]
        experiences = [e for e in experiences if len(e) > 10 and not _STUB_ACTIVITY.match(e)]

        # Competencies / values for this entry
        comps, vals, links, pcis_raw = _classify_competency_items(raw_competencies + raw_values)
        if not comps:
            comps = ["Critical thinking and problem solving",
                     "Communication and collaboration", "Self-efficacy"]
        if not vals:
            vals = ["Respect", "Responsibility", "Unity"]

        # Topic-aware PCIs
        pcis_list = _generate_pcis(strand, substrand, substrand, pcis_raw)
        pcis_str = "; ".join(pcis_list[:2]) if pcis_list else _generate_pcis(subject, substrand, substrand, [])
        if isinstance(pcis_str, list):
            pcis_str = "; ".join(pcis_str[:2])

        comp_str = ", ".join(comps[:3])
        val_str  = ", ".join(vals[:3])

        # Determine how many lessons this sub-strand needs
        num_lessons = _extract_lesson_count(raw_strand)
        if num_lessons <= 0:
            # Estimate from number of outcomes or experiences
            num_lessons = max(len(learning_outcomes), len(experiences), 2)
        num_lessons = max(1, min(num_lessons, 8))  # cap 1–8 per sub-strand

        # KIQ fallback — topic-specific, not "What have you learnt"
        _combined_kiq = (substrand + ' ' + subject).lower()
        if key_questions:
            kiq_pool = [q for q in key_questions if len(q.strip()) > 10]
        else:
            kiq_pool = []
        if not kiq_pool:
            if any(k in _combined_kiq for k in ['cre', 'christian', 'leisure', 'ire', 'islamic', 'religion', 'faith', 'moral']):
                kiq_pool = [f"How do Christian/moral values help young people make responsible decisions about {substrand.lower()}?"]
            elif any(k in _combined_kiq for k in ['soil', 'conserv', 'agri', 'farm', 'crop', 'livestock', 'poultry']):
                kiq_pool = [f"How does proper management of {substrand.lower()} contribute to food security?"]
            elif any(k in _combined_kiq for k in ['fraction', 'algebra', 'geometr', 'statistic', 'mathemat']):
                kiq_pool = [f"Where do you encounter {substrand.lower()} in your daily life?"]
            elif any(k in _combined_kiq for k in ['reading', 'writing', 'grammar', 'english', 'language']):
                kiq_pool = [f"How does mastering {substrand.lower()} improve your communication skills?"]
            elif any(k in _combined_kiq for k in ['science', 'ecosystem', 'cell', 'photosynthes', 'energy', 'force']):
                kiq_pool = [f"How does understanding {substrand.lower()} help explain the world around you?"]
            else:
                kiq_pool = [f"Why is it important to learn about {substrand.lower()}?"]

        # Distribute outcomes and experiences across lessons for this sub-strand
        for lsn_idx in range(num_lessons):
            # Stop if we've exceeded MAX_TERM_WEEKS
            if week_num > MAX_TERM_WEEKS:
                break

            global_lesson += 1
            lessons_in_current_week += 1

            # SLO for this lesson
            if learning_outcomes:
                slo = learning_outcomes[lsn_idx % len(learning_outcomes)]
            else:
                slo = f"Apply knowledge and skills related to {substrand}"

            # Experience/activity for this lesson
            if experiences:
                exp = experiences[lsn_idx % len(experiences)]
            elif lsn_idx == 0:
                exp = f"Introduction to {substrand}: discussion of real-life examples and prior knowledge elicitation"
            elif lsn_idx == num_lessons - 1:
                exp = f"Assessment and consolidation on {substrand}: oral questions and written exercise"
            else:
                exp = f"Guided investigation of {substrand} through group work, observation and class discussion"

            # KIQ for this lesson
            kiq = kiq_pool[lsn_idx % len(kiq_pool)]

            table_rows.append({
                "week":      week_num,
                "lesson":    global_lesson,
                "strand":    strand or subject,
                "substrand": substrand,
                "outcomes":  f"• {slo}",
                "experiences": f"• {exp}",
                "questions": f"• {kiq}",
                "resources": "• Textbook\n• Charts/visual aids\n• Realia/models\n• Learner workbooks",
                "assessment": "• Observation\n• Oral questions\n• Written exercise",
                "comp_str":  comp_str,
                "val_str":   val_str,
                "pcis_str":  pcis_str,
            })

            if lessons_in_current_week >= lessons_per_week:
                week_num += 1
                lessons_in_current_week = 0

        if week_num > MAX_TERM_WEEKS:
            break

    # If we ran out of entries before MIN_TERM_WEEKS, note the actual count
    num_weeks    = week_num - (1 if lessons_in_current_week == 0 else 0)
    total_lessons = global_lesson
    
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
            f"| {_cell(row['comp_str'])} "
            f"| {_cell(row['val_str'])} "
            f"| {_cell(row['pcis_str'])} "
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


def generate_rubric(subject, grade, assessment_type="performance", topic=None):
    """Generate a CBC auto-generated rubric template from curriculum database.
    topic: optional sub-strand/topic hint to find the best-matching curriculum entry.
    """
    curriculum = query_curriculum(subject, grade, substrand_hint=topic or None)
    
    if not curriculum:
        return {
            "success": False,
            "error": f"Curriculum not found for {subject} {grade}",
            "content": ""
        }
    
    current_year = datetime.today().year
    date_str = datetime.today().strftime('%d/%m/%Y')
    
    strand = _clean_strand_name(curriculum.get('strand', '') or '')
    _sub_num = curriculum.get('substrand_number', '').strip()
    _sub_name = curriculum.get('substrand', '').strip()
    substrand = _clean_strand_name(_combine_substrand(_sub_num, _sub_name))
    learning_outcomes = curriculum.get('learning_outcomes', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])

    # Filter stubs — strip PDF preamble headers from SLOs
    learning_outcomes = [_clean_slo(o) for o in learning_outcomes]
    learning_outcomes = [o for o in learning_outcomes if _is_valid_slo(o)]

    # Classify competency data
    competencies, values, links, pcis = _classify_competency_items(
        raw_competencies + raw_values
    )
    if not competencies:
        competencies = ["Critical Thinking and Problem Solving",
                        "Communication and Collaboration",
                        "Self-Efficacy"]
    if not values:
        values = ["Respect", "Responsibility", "Unity"]
    if not pcis:
        pcis = _generate_pcis(strand, substrand, subject, [])
        if not pcis:
            pcis = ["As applicable"]

    # Extract clean strand topic
    strand_topic = _extract_strand_topic(strand) or subject

    # Enhance competencies and values with subject/topic context
    # Strip leading substrand numbers (e.g. '6.3 Alcohol...' → 'Alcohol...') for clean topic text
    _comp_topic = re.sub(
        r'^\d+(?:\.\d+)*\s*',
        '',
        (topic or substrand or strand_topic)
    ).strip() or strand_topic
    # Always rebuild from the contextual pool so every rubric shows explanatory context
    competencies = _supplement_competencies([], subject, _comp_topic, minimum=3)
    values = _generate_values_with_context(values, subject, _comp_topic, substrand)
    
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

    # Supplement if DB yielded fewer than 3 criteria
    if len(criteria) < 3:
        # Strip leading substrand number (e.g. "6.3 Alcohol..." → "Alcohol...")
        _sub_plain = re.sub(r'^\d+(?:\.\d+)*\s*', '', substrand).strip() or substrand
        combined_topic = (substrand + ' ' + subject).lower()
        supplement_pool: list[str] = []
        if any(k in combined_topic for k in ['cre', 'christian', 'ire', 'islamic', 'religion', 'moral', 'faith']):
            supplement_pool = [
                f"Explain the Christian/moral teaching on {_sub_plain}",
                f"Analyse the consequences of {_sub_plain.lower()} and suggest responsible alternatives",
                f"Apply Christian/moral values to make informed decisions regarding {_sub_plain.lower()}",
            ]
        elif any(k in combined_topic for k in ['agri', 'farm', 'crop', 'soil', 'livestock', 'poultry', 'nutrition']):
            supplement_pool = [
                f"Describe the importance of {_sub_plain.lower()} in sustainable farming",
                f"Demonstrate correct procedures for {_sub_plain.lower()}",
                f"Evaluate the impact of {_sub_plain.lower()} on community food security",
            ]
        elif any(k in combined_topic for k in ['math', 'mathemat', 'algebra', 'geometry', 'number', 'fraction', 'statistic']):
            supplement_pool = [
                f"Solve practical problems involving {_sub_plain.lower()}",
                f"Apply properties of {_sub_plain.lower()} to real-world contexts",
                f"Communicate mathematical reasoning about {_sub_plain.lower()} clearly",
            ]
        elif any(k in combined_topic for k in ['english', 'read', 'writ', 'grammar', 'listening', 'speaking']):
            supplement_pool = [
                f"Apply language skills to comprehend texts on {_sub_plain.lower()}",
                f"Produce structured written work demonstrating understanding of {_sub_plain.lower()}",
                f"Communicate ideas about {_sub_plain.lower()} accurately and coherently",
            ]
        elif any(k in combined_topic for k in ['science', 'biology', 'physics', 'chemistry', 'environment']):
            supplement_pool = [
                f"Conduct simple experiments/observations related to {_sub_plain.lower()}",
                f"Explain scientific principles underlying {_sub_plain.lower()}",
                f"Evaluate real-world applications of knowledge about {_sub_plain.lower()}",
            ]
        else:
            supplement_pool = [
                f"Demonstrate understanding of key concepts in {_sub_plain.lower()}",
                f"Apply knowledge of {_sub_plain.lower()} to practical situations",
                f"Evaluate the relevance of {_sub_plain.lower()} in everyday life",
            ]
        for s in supplement_pool:
            if len(criteria) >= 3:
                break
            if s not in criteria:
                criteria.append(s)
    
    # Generate descriptors for each criterion at each level
    _ATTITUDINAL_VERBS = {
        'appreciate', 'value', 'respect', 'acknowledge', 'recognise', 'recognize',
        'accept', 'embrace', 'demonstrate', 'show', 'exhibit', 'display',
        'care', 'support', 'believe', 'commit', 'advocate',
    }

    def _descriptors(criterion):
        """Generate 4 performance-level descriptors for a criterion."""
        subject_lower = subject.lower()
        is_religious = any(k in subject_lower for k in ['cre', 'ire', 'christian', 'islamic', 'religion', 'moral'])
        # Extract the main verb (skip leading articles/prepositions)
        words = criterion.split()
        verb = words[0].lower() if words else "demonstrate"
        rest = " ".join(words[1:]) if len(words) > 1 else strand_topic

        # Attitudinal / affective verbs — accuracy language makes no sense;
        # use frequency/consistency language instead
        if verb in _ATTITUDINAL_VERBS:
            if is_religious:
                ee = (f"Consistently and enthusiastically demonstrates {rest} through independent actions "
                      f"and reflective writing, clearly grounded in personal faith and conviction")
                me = (f"Regularly demonstrates {rest} in class activities and interactions, "
                      f"connecting it appropriately to Christian/moral principles")
                ae = (f"Sometimes demonstrates {rest} when prompted or guided by the teacher; "
                      f"basic understanding of the value is evident")
                be = (f"Rarely demonstrates {rest}; requires significant encouragement, "
                      f"scaffolding and teacher support")
            else:
                ee = (f"Consistently and enthusiastically demonstrates {rest} "
                      f"through independent and creative expression in all tasks")
                me = (f"Regularly demonstrates {rest} in own work and interactions with peers")
                ae = (f"Sometimes demonstrates {rest} when prompted or guided by the teacher")
                be = (f"Rarely demonstrates {rest}; requires significant encouragement and support")
            return ee, me, ae, be

        # Conjugate: add 's' for third-person, handle common endings
        if verb.endswith(('sh', 'ch', 'ss', 'x', 'z')):
            verb_s = verb + "es"
        elif verb.endswith('y') and len(verb) > 1 and verb[-2] not in 'aeiou':
            verb_s = verb[:-1] + "ies"
        else:
            verb_s = verb + "s"

        if is_religious:
            ee = (f"Independently {verb_s} {rest} and applies Christian/moral values in daily life "
                  f"with clear evidence of personal reflection and conviction")
            me = (f"Correctly {verb_s} {rest} and demonstrates understanding of the relevant "
                  f"moral/Christian principle with appropriate examples")
            ae = (f"Partially {verb_s} {rest} with teacher guidance; basic moral understanding "
                  f"evident but lacking depth")
            be = (f"Shows minimal ability to {verb} {rest}; requires significant guidance "
                  f"and scaffolding to engage with the topic")
        else:
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

    # Build subject-specific KICD resources line
    subj_lower = subject.lower()
    if any(k in subj_lower for k in ['cre', 'christian']):
        kicd_resource = f"KICD CRE Learner's Book {grade}, KICD CRE Teacher's Guide {grade}"
    elif any(k in subj_lower for k in ['ire', 'islamic']):
        kicd_resource = f"KICD IRE Learner's Book {grade}, KICD IRE Teacher's Guide {grade}"
    elif 'math' in subj_lower:
        kicd_resource = f"KICD Mathematics Learner's Book {grade}, KICD Mathematics Teacher's Guide {grade}"
    elif 'english' in subj_lower:
        kicd_resource = f"KICD English Learner's Book {grade}, KICD English Teacher's Guide {grade}"
    elif 'science' in subj_lower:
        kicd_resource = f"KICD Integrated Science Learner's Book {grade}, KICD Integrated Science Teacher's Guide {grade}"
    elif 'social' in subj_lower:
        kicd_resource = f"KICD Social Studies Learner's Book {grade}, KICD Social Studies Teacher's Guide {grade}"
    elif 'agri' in subj_lower:
        kicd_resource = f"KICD Agriculture & Nutrition Learner's Book {grade}, KICD Agriculture & Nutrition Teacher's Guide {grade}"
    else:
        kicd_resource = f"KICD {subject} Learner's Book {grade}, KICD {subject} Teacher's Guide {grade}"

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

KICD APPROVED RESOURCES
{'=' * 60}

- {kicd_resource}
- Kenya Institute of Curriculum Development (KICD) website: www.kicd.ac.ke
- Relevant support materials approved by KICD for {subject} {grade}

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
