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
    """Query curriculum database for subject and grade."""
    # Normalize grade
    grade_normalized = f"Grade {grade}" if grade and not grade.startswith("Grade") else grade
    
    all_curriculum = get_curriculum()
    
    if not all_curriculum:
        return None
    
    # Map common subject name variations to actual DB subject names (with spaces, as stored)
    subject_map = {
        "mathematics": "maths",
        "math": "maths",
        "science": "intergrated science",
        "integrated science": "intergrated science",
        "intergrated science": "intergrated science",
        "social studies": "social studies",
        "creative arts": "creative arts",
        "creative arts and sports": "creative arts and sports",
        "agriculture": "agriculture and nutrition",
        "agriculture and nutrition": "agriculture and nutrition",
        "agriculture and nutrion": "agriculture and nutrion",  # DB typo for Grade 8
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


def _find_best_curriculum_entry(all_entries, substrand_hint):
    """Given a list of entries (all same subject+grade), pick the one whose
    substrand best matches the substrand_hint.  Falls back to first entry."""
    if not all_entries:
        return None
    if not substrand_hint:
        return all_entries[0]
    hint_lower = substrand_hint.lower()
    hint_words = [w for w in hint_lower.split() if len(w) > 3]
    best, best_score = all_entries[0], 0
    for entry in all_entries:
        sub = entry.get('substrand', '').lower()
        score = sum(1 for w in hint_words if w in sub)
        if score > best_score:
            best, best_score = entry, score
    return best


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

    if any(k in combined for k in ['soil', 'farm', 'crop', 'conserv', 'agri', 'water', 'poultry', 'livestock']):
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
    elif any(k in combined for k in ['reading', 'writing', 'english', 'language', 'grammar', 'comprehension']):
        pool = [
            'Communication and Collaboration — expressing ideas clearly in speech and writing',
            'Critical Thinking and Problem Solving — analysing and drawing meaning from texts',
            'Creativity and Imagination — creative writing and storytelling',
            'Digital Literacy — using digital platforms for reading, writing and research',
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

    # Fallback: derive first verb phrase from step text
    action = re.match(r'^([A-Z][a-z]+(?:\s+[a-z]+){0,4})', text)
    if action:
        return f"Participate by {action.group(1).lower()}; record findings and share outcomes with peers"
    return "Actively engage with the activity; record findings and discuss outcomes with the class"


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

    context_map = {
        'unity': f"learners collaborate in groups during {topic} activities, combining individual strengths to achieve a shared goal",
        'responsibility': f"learners take ownership of their tasks and handle all materials carefully during {topic}",
        'integrity': f"learners report observations and findings honestly without falsifying results during {topic}",
        'respect': f"learners listen attentively to peers' contributions and value diverse approaches to {topic}",
        'peace': f"learners resolve group disagreements calmly and maintain a harmonious working environment during {topic}",
        'love': f"learners show care for the environment, community and peers through their engagement with {topic}",
        'patriotism': f"learners appreciate how {topic} contributes to national development and the well-being of Kenya",
        'social justice': f"learners consider equitable access to resources and fair opportunities related to {topic}",
    }

    working = list(values_raw) if values_raw else []

    # Supplement to at least 2 values using topic-appropriate defaults
    if any(k in combined for k in ['soil', 'farm', 'crop', 'agri', 'water harvest', 'livestock', 'poultry']):
        defaults = ['Unity', 'Responsibility', 'Patriotism']
    elif any(k in combined for k in ['math', 'algebra', 'fraction', 'geometr', 'statistic']):
        defaults = ['Integrity', 'Responsibility', 'Respect']
    elif any(k in combined for k in ['reading', 'writing', 'grammar', 'english', 'language']):
        defaults = ['Respect', 'Integrity', 'Responsibility']
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
    
    # Format key inquiry questions — strictly 2-3, directly related to strand (Rule 5)
    questions = questions[:3]
    # Pad to at least 2 if the DB only supplied 1
    if len(questions) < 2:
        questions.append(f"How does knowledge of {substrand or topic} apply in everyday life?")
    if questions:
        kiq_list = "\n".join([f"{i+1}. {item}" for i, item in enumerate(questions)])
    else:
        kiq_list = f"1. What are the key concepts in {substrand or topic}?\n2. How does this knowledge apply in daily life?"
    
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
        learner_dev_parts.append(f"Step {i+1}: {_generate_step_learner_mirror(step, topic)}")
    teacher_dev_parts.append("Circulate and monitor progress; ask probing questions to deepen understanding")
    learner_dev_parts.append("Record all findings in exercise book; discuss conclusions with peers")

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
    
    _all_res = _generate_lesson_resources(subject, grade, topic, substrand)
    # Introduction: KICD books + first topic-specific item only (starter activity resources)
    res_intro = ", ".join(_all_res[:2] + ([_all_res[2]] if len(_all_res) > 2 else ['Chalkboard/whiteboard and chalk/markers']))
    # Development: all resources
    res_dev = ", ".join(_all_res)
    # Conclusion: main reference + exercise books + assessment checklist
    res_concl = ", ".join([_all_res[0], 'Learner exercise books', 'Assessment rubric/checklist'])
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
| Introduction ({intro_time} min) | {teacher_intro} | {learner_intro} | {res_intro} | {assessment_intro} |
| Lesson Body / Development ({dev_time} min) | {teacher_dev} | {learner_dev} | {res_dev} | {assessment_dev} |
| Conclusion ({concl_time} min) | {teacher_concl} | {learner_concl} | {res_concl} | {assessment_concl} |

11) EXTENDED ACTIVITIES

{{ext_fast}}
{{ext_support}}

12) REFLECTION

- What did learners learn today?
- What was challenging?
- How can this be applied in everyday life?

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
    substrand = curriculum.get('substrand', '')
    learning_outcomes = curriculum.get('learning_outcomes', [])
    key_questions = curriculum.get('key_inquiry_questions', [])
    experiences = curriculum.get('suggested_learning_experiences', [])
    raw_competencies = curriculum.get('core_competencies', [])
    raw_values = curriculum.get('values', [])
    raw_pcis = curriculum.get('pcis', [])
    raw_link_subjects = curriculum.get('link_subjects', [])
    
    # Clean up empty or stub items
    learning_outcomes = [o for o in learning_outcomes if len(o.strip()) > 10]
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
    
    # Grade-based lesson duration and lessons per week
    grade_num = int(re.search(r'\d+', grade).group()) if re.search(r'\d+', grade) else 7
    lesson_duration = 35 if grade_num <= 6 else 40
    lessons_per_week = 3 if grade_num <= 6 else 2
    
    # A Kenyan school term is typically 12-14 weeks
    # Set minimum 12 weeks for a complete term scheme of work
    MIN_TERM_WEEKS = 12
    MAX_TERM_WEEKS = 14
    
    # Determine total lessons from strand text (if specified)
    extracted_lessons = _extract_lesson_count(strand)
    
    # Calculate weeks based on extracted lessons or default to full term
    if extracted_lessons > 0:
        num_weeks = max(MIN_TERM_WEEKS, math.ceil(extracted_lessons / lessons_per_week))
        num_weeks = min(num_weeks, MAX_TERM_WEEKS)
        total_lessons = num_weeks * lessons_per_week
    else:
        # Default to full 12-week term
        num_weeks = MIN_TERM_WEEKS
        total_lessons = num_weeks * lessons_per_week
    
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
