from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
import json

from schemas.intake import IntakeCreate
from database import Intake, StatusHistory
from services.drug_interaction_service import check_drug_interactions, generate_counseling_points

ALLOWED_STATUSES = [
    "new",
    "triage",
    "waiting_info",
    "ready_to_fill",
    "filled",
    "dispensed",
    "completed"
]

ALLOWED_TRANSITIONS = {
    "new": ["triage"],
    "triage": ["waiting_info", "ready_to_fill"],
    "waiting_info": ["ready_to_fill"],
    "ready_to_fill": ["filled"],
    "filled": ["dispensed"],
    "dispensed": ["completed"],
    "completed": []
}


def create_intake(db: Session, data: IntakeCreate) -> Intake:
    interactions = check_drug_interactions(
        data.medications,
        data.current_medications
    )
    counseling = generate_counseling_points(data.medications, interactions)
    interactions_json = json.dumps(interactions) if interactions else None

    intake = Intake(
        patient_name=data.patient_name,
        patient_age=data.patient_age,
        patient_allergies=data.patient_allergies,
        medications=data.medications,
        current_medications=data.current_medications,
        notes=data.notes,
        counseling_points=counseling,
        drug_interactions=interactions_json,
        status="new"
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)

    _record_status_history(db, intake.id, from_status=None, to_status="new")
    return intake


def list_intakes(
    db: Session,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Intake]:
    query = db.query(Intake)
    if status:
        query = query.filter(Intake.status == status)
    if assigned_to:
        query = query.filter(Intake.assigned_to == assigned_to)
    if search:
        query = query.filter(Intake.patient_name.ilike(f"%{search}%"))
    return query.order_by(Intake.created_at.desc()).offset(skip).limit(limit).all()


def get_intake_by_id(db: Session, intake_id: int) -> Optional[Intake]:
    return db.query(Intake).filter(Intake.id == intake_id).first()


def update_status(db: Session, intake_id: int, new_status: str, changed_by: Optional[str] = None) -> Optional[Intake]:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None

    current_status = intake.status
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, []):
        raise ValueError(
            f"Invalid transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {ALLOWED_TRANSITIONS.get(current_status, [])}"
        )

    intake.status = new_status
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)

    _record_status_history(db, intake_id, from_status=current_status, to_status=new_status, changed_by=changed_by)
    return intake


def cancel_intake(db: Session, intake_id: int) -> bool:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return False
    db.delete(intake)
    db.commit()
    return True


def assign_intake(db: Session, intake_id: int, user: str) -> Optional[Intake]:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None
    intake.assigned_to = user
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)
    return intake


def update_counseling_points(db: Session, intake_id: int, counseling_points: str) -> Optional[Intake]:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None
    intake.counseling_points = counseling_points
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)
    return intake


def update_pharmacist_notes(db: Session, intake_id: int, pharmacist_notes: str) -> Optional[Intake]:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None
    intake.pharmacist_notes = pharmacist_notes
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)
    return intake


def dispense_medication(db: Session, intake_id: int, dispensed: str) -> Optional[Intake]:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None
    intake.dispensed = dispensed
    if dispensed == "yes":
        intake.dispensed_at = datetime.now(timezone.utc)
        if intake.status == "filled":
            old_status = intake.status
            intake.status = "dispensed"
            db.commit()
            db.refresh(intake)
            _record_status_history(db, intake_id, from_status=old_status, to_status="dispensed")
            return intake
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)
    return intake


def check_interactions_for_intake(db: Session, intake_id: int) -> dict:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None

    interactions = check_drug_interactions(
        intake.medications,
        intake.current_medications
    )
    intake.drug_interactions = json.dumps(interactions) if interactions else None
    intake.counseling_points = generate_counseling_points(intake.medications, interactions)
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)

    return {
        "interactions": interactions,
        "counseling_points": intake.counseling_points
    }


def get_status_history(db: Session, intake_id: int) -> List[StatusHistory]:
    return (
        db.query(StatusHistory)
        .filter(StatusHistory.intake_id == intake_id)
        .order_by(StatusHistory.changed_at.asc())
        .all()
    )


def get_statistics(db: Session) -> dict:
    total = db.query(Intake).count()
    by_status = {status: db.query(Intake).filter(Intake.status == status).count() for status in ALLOWED_STATUSES}
    dispensed_count = db.query(Intake).filter(Intake.dispensed == "yes").count()
    return {
        "total": total,
        "by_status": by_status,
        "dispensed_count": dispensed_count
    }


def _record_status_history(
    db: Session,
    intake_id: int,
    from_status: Optional[str],
    to_status: str,
    changed_by: Optional[str] = None,
) -> None:
    entry = StatusHistory(
        intake_id=intake_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
    )
    db.add(entry)
    db.commit()
