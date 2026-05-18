"""Manually curated curriculum data for high-priority subjects.
This supplements auto-extracted data for subjects where table structures break parsing.
"""

MANUAL_ENHANCEMENTS = {
    "English_Grade_8.pdf": {
        "strand": "LISTENING AND SPEAKING",
        "substrand": "Polite Language in Conversation",
        "key_inquiry_questions": [
            "How do we ensure politeness in telephone conversation?",
            "What strategies help us communicate respectfully?",
            "How can we listen actively to understand others?",
            "Why is polite language important in different contexts?",
            "How do cultural differences affect politeness conventions?",
            "What tone and language choices show respect?",
            "How can we respond politely to difficult conversations?",
            "What non-verbal cues contribute to polite communication?",
            "How do we negotiate disagreements politely?",
            "When is it appropriate to be formal vs. informal?",
        ],
        "suggested_learning_experiences": [
            "The learner listens to recorded telephone conversations and identifies polite language patterns.",
            "The learner participates in role-play activities demonstrating polite responses in various scenarios.",
            "The learner analyzes video clips to observe non-verbal communication and politeness markers.",
            "Pair work: Learners practice telephone etiquette through structured dialogues.",
            "The learner reflects on and compiles a guide of polite expressions for different situations.",
            "Group activity: Learners discuss cultural differences in politeness conventions.",
            "The learner writes and performs dialogues showing polite conflict resolution.",
            "The learner observes and categorizes language that shows respect, courtesy, and empathy.",
            "Interactive role plays where learners practice handling impolite responses gracefully.",
            "The learner creates a portfolio of polite language strategies learned.",
        ],
        "learning_outcomes": [
            "Use grammatical forms to communicate appropriately in different settings",
            "Apply digital literacy skills to enhance proficiency in English",
            "Demonstrate polite language in formal and informal contexts",
        ],
        "core_competencies": [
            "Communication and Collaboration",
            "Critical Thinking and Problem Solving",
        ],
        "values": [
            "Respect",
            "Responsibility",
            "Collaboration",
        ],
    }
}

def enhance_cbc_data(data: dict) -> dict:
    """Merge manual enhancements into parsed CBC data."""
    for key, manual_entry in MANUAL_ENHANCEMENTS.items():
        if key in data:
            # Update with manual data for specific fields
            for field in ["strand", "substrand", "key_inquiry_questions", 
                         "suggested_learning_experiences", "learning_outcomes",
                         "core_competencies", "values"]:
                if field in manual_entry:
                    data[key][field] = manual_entry[field]
    return data
