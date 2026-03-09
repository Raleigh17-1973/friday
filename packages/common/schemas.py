"""JSON-schema-like contracts used across Friday components."""

PLANNER_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "problem_statement",
        "missing_information",
        "domains_involved",
        "recommended_specialists",
        "required_tools",
        "risk_level",
        "output_format",
    ],
}

SPECIALIST_MEMO_SCHEMA = {
    "type": "object",
    "required": [
        "specialist_id",
        "analysis",
        "recommendation",
        "assumptions",
        "risks",
        "evidence",
        "confidence",
        "questions",
    ],
}

CRITIC_REPORT_SCHEMA = {
    "type": "object",
    "required": ["blind_spots", "challenged_assumptions", "alternative_path", "residual_risks"],
}

FINAL_ANSWER_PACKAGE_SCHEMA = {
    "type": "object",
    "required": [
        "direct_answer",
        "executive_summary",
        "key_assumptions",
        "major_risks",
        "recommended_next_steps",
    ],
}

MEMORY_CANDIDATE_SCHEMA = {
    "type": "object",
    "required": ["candidate_id", "run_id", "candidate_type", "content", "risk_level", "auto_accepted"],
}
