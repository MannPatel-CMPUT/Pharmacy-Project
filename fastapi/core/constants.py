"""Core constants for workflow and clinical scoring."""

ALLOWED_STATUSES = [
    "new",
    "triage",
    "waiting_info",
    "ready_to_fill",
    "filled",
    "dispensed",
    "completed",
]

ALLOWED_TRANSITIONS = {
    "new": ["triage"],
    "triage": ["waiting_info", "ready_to_fill"],
    "waiting_info": ["ready_to_fill"],
    "ready_to_fill": ["filled"],
    "filled": ["dispensed"],
    "dispensed": ["completed"],
    "completed": [],
}

SEVERITY_SCORES = {
    "contraindicated": 100,
    "major": 80,
    "moderate": 50,
    "minor": 20,
    "unknown": 10,
}
