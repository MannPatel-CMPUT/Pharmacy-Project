from datetime import datetime, timezone
from typing import Optional

from schemas.intake import IntakeCreate

ALLOWED_STATUSES = [
    "new",
    "triage",
    "waiting_info",
    "ready_to_fill",
]

ALLOWED_TRANSITIONS = {
    "new": ["triage"],
    "triage": ["waiting_info"],
    "waiting_info": ["ready_to_fill"],
    "ready_to_fill": []

}

_intakes: list[dict] = []
_next_id: int = 1

def create_intake(data: IntakeCreate) -> dict:
    global _next_id

    intake = {
        "id": _next_id,
        "patient_name": data.patient_name,
        "medications": data.medications,
        "notes": data.notes,
        "status": "new",
        "assigned_to": None,
        "created_at": datetime.now(timezone.utc),

            }
    _intakes.append(intake)
    _next_id +=1
    return intake

def list_intakes() -> list[dict]:
    return _intakes

def get_intake_by_id(intake_id:int) -> Optional[dict]:
    for intake in _intakes:
        if intake["id"] == intake_id:
            return intake
    return None

def update_status(intake_id: int, new_status: str) -> dict|None:
    intake = get_intake_by_id(intake_id)
    if not intake:
        return None
    
    current_status = intake["status"]

    if new_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(
            f"Invalid transition from '{current_status}' to '{new_status}'"
        )
    intake["status"] = new_status
    return intake

def assign_intake(intake_id: int, user:str) -> dict |None:
    intake = get_intake_by_id(intake_id)
    if not intake:
        return None
    
    intake["assigned_to"] = user
    return intake