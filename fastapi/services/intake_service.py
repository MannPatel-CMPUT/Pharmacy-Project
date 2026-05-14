from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
import json
import logging

from core.constants import ALLOWED_STATUSES, ALLOWED_TRANSITIONS
from core.workflow import STAGE_DISPLAY, is_pickup_ready, next_stage_hint
from schemas.intake import IntakeCreate, EvaluateIntakeRequest, IntakeOut
from database import Intake, StatusHistory
from services.counseling_service import generate_counseling
from services.drug_interaction_service import check_drug_interactions, generate_counseling_points
from services.normalization_service import normalize_and_match
from services.clinical_context_service import build_allergy_warnings, build_lifestyle_warnings

_SEVERITY_TO_RISK = {
    "contraindicated": "Very High",
    "major": "High",
    "moderate": "Moderate",
    "minor": "Low",
    "unknown": "Unknown",
}

_SEVERITY_RANK = {
    "contraindicated": 0,
    "major": 1,
    "moderate": 2,
    "minor": 3,
    "unknown": 4,
}


def _sort_interactions_by_severity(interactions: list) -> list:
    """Sort interactions by clinical severity (most dangerous first)."""
    if not interactions:
        return interactions
    return sorted(
        interactions,
        key=lambda ix: _SEVERITY_RANK.get((ix.get("severity") or "unknown").lower(), 99),
    )

_SEVERITY_TO_RECOMMENDATION = {
    "contraindicated": "Avoid this combination. Seek immediate medical advice.",
    "major": "Avoid unless specifically directed by your doctor. Requires close monitoring.",
    "moderate": "Use with caution. Monitor closely and consult your pharmacist or doctor.",
    "minor": "Generally safe, but monitor for minor side effects. Ask pharmacist if unsure.",
    "unknown": "Insufficient data — consult your pharmacist or doctor.",
}

_RISK_ORDER = ["None", "Low", "Moderate", "High", "Very High"]

logger = logging.getLogger(__name__)


def enrich_intake_out(intake: Intake) -> IntakeOut:
    """Add workflow labels for UI / browser notifications (pickup-ready, stage name)."""
    base = IntakeOut.model_validate(intake)
    return base.model_copy(
        update={
            "stage_display": STAGE_DISPLAY.get(intake.status, intake.status.replace("_", " ").title()),
            "pickup_ready": is_pickup_ready(intake.status),
            "workflow_hint": next_stage_hint(intake.status),
        }
    )


def create_intake(db: Session, data: IntakeCreate) -> Intake:
    logger.info(
        "intake create normalized_medications new=%s current=%s",
        normalize_and_match(data.medications, db),
        normalize_and_match(data.current_medications, db),
    )
    interactions = check_drug_interactions(
        db,
        data.medications,
        data.current_medications,
        patient_age=data.patient_age,
        patient_gender=data.patient_gender,
    )
    interactions = _sort_interactions_by_severity(interactions)
    interactions_json = json.dumps(interactions) if interactions else None

    intake = Intake(
        patient_name=data.patient_name,
        patient_age=data.patient_age,
        patient_gender=data.patient_gender,
        patient_phone=((data.patient_phone or "").strip() or None),
        patient_allergies=data.patient_allergies,
        medications=data.medications,
        current_medications=data.current_medications,
        notes=data.notes,
        drug_interactions=interactions_json,
        status="new"
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)

    counseling = generate_counseling_points(
        db,
        patient_name=data.patient_name,
        medications=data.medications,
        interactions=interactions,
        patient_age=data.patient_age,
        intake_id=intake.id,
        patient_allergies=data.patient_allergies,
        notes=data.notes,
    )
    intake.counseling_points = counseling
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


def dispense_medication(db: Session, intake_id: int, dispensed: str, changed_by: Optional[str] = None) -> Optional[Intake]:
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
            _record_status_history(db, intake_id, from_status=old_status, to_status="dispensed", changed_by=changed_by)
            return intake
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)
    return intake


def _recompute_intake_interactions(db: Session, intake: Intake) -> dict:
    logger.info(
        "intake recheck normalized_medications intake_id=%s new=%s current=%s",
        intake.id,
        normalize_and_match(intake.medications, db),
        normalize_and_match(intake.current_medications, db),
    )
    interactions = check_drug_interactions(
        db,
        intake.medications,
        intake.current_medications,
        patient_age=intake.patient_age,
        patient_gender=intake.patient_gender,
    )
    interactions = _sort_interactions_by_severity(interactions)
    intake.drug_interactions = json.dumps(interactions) if interactions else None
    counseling_result = generate_counseling(
        db,
        patient_name=intake.patient_name,
        medications=intake.medications,
        interactions=interactions,
        patient_age=intake.patient_age,
        intake_id=intake.id,
        patient_allergies=intake.patient_allergies,
        notes=intake.notes,
    )
    intake.counseling_points = counseling_result["text"]
    intake.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(intake)

    return {
        "interactions": interactions,
        "counseling_points": intake.counseling_points,
        "counseling_source": counseling_result["source"],
    }


def check_interactions_for_intake(db: Session, intake_id: int) -> dict:
    intake = get_intake_by_id(db, intake_id)
    if not intake:
        return None
    return _recompute_intake_interactions(db, intake)


def evaluate_intake_interactions(db: Session, data: EvaluateIntakeRequest) -> dict:
    """
    Evaluate drug interactions, allergy warnings, and lifestyle cautions without saving an intake.
    Uses the local drug_interactions table (from configured CSV / seed data).
    """
    try:
        raw_interactions = check_drug_interactions(
            db,
            data.medications,
            data.current_medications,
            patient_age=data.patient_age,
            patient_gender=data.patient_gender,
        )
        raw_interactions = _sort_interactions_by_severity(raw_interactions)
    except Exception:
        logger.exception("evaluate_intake: interaction detection failed")
        return {
            "success": False,
            "interactions": [],
            "allergyWarnings": [],
            "lifestyleWarnings": [],
            "overallRisk": "Unknown",
            "error": "Interaction analysis temporarily unavailable. See your intake card for details.",
        }

    structured: list[dict] = []
    highest_risk_idx = 0

    for ix in raw_interactions:
        sev_key = (ix.get("severity") or "unknown").lower()
        risk = _SEVERITY_TO_RISK.get(sev_key, "Unknown")
        rec = _SEVERITY_TO_RECOMMENDATION.get(sev_key, _SEVERITY_TO_RECOMMENDATION["unknown"])
        structured.append({
            "drug1": ix.get("drug1", ""),
            "drug2": ix.get("drug2", ""),
            "severity": ix.get("severity", "Unknown"),
            "riskFactor": risk,
            "explanation": ix.get("description") or "Interaction identified; details unavailable.",
            "recommendation": rec,
            "source": ix.get("source"),
        })
        idx = _RISK_ORDER.index(risk) if risk in _RISK_ORDER else 0
        highest_risk_idx = max(highest_risk_idx, idx)

    allergy_warnings = build_allergy_warnings(
        data.patient_allergies,
        data.medications,
        data.current_medications,
    )

    lifestyle_warnings = build_lifestyle_warnings(
        smoking=data.smoking,
        alcohol_use=data.alcohol_use,
        renal_status=data.renal_status,
        hepatic_status=data.hepatic_status,
        pregnancy=data.pregnancy,
        patient_gender=data.patient_gender,
        medications=data.medications,
        current_medications=data.current_medications,
    )

    if not structured and (allergy_warnings or lifestyle_warnings):
        highest_risk_idx = max(highest_risk_idx, 1)

    return {
        "success": True,
        "interactions": structured,
        "allergyWarnings": allergy_warnings,
        "lifestyleWarnings": lifestyle_warnings,
        "overallRisk": _RISK_ORDER[highest_risk_idx],
    }


def refresh_all_intake_interaction_snapshots(db: Session) -> dict[str, int]:
    """Re-run interaction detection and counseling for every intake."""
    updated = 0
    for intake in db.query(Intake).all():
        try:
            _recompute_intake_interactions(db, intake)
            updated += 1
        except Exception:
            logger.exception("refresh snapshot failed intake_id=%s", intake.id)
    return {"intakes_updated": updated}


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
    ready_for_pickup = db.query(Intake).filter(Intake.status == "filled").count()
    return {
        "total": total,
        "by_status": by_status,
        "dispensed_count": dispensed_count,
        "ready_for_pickup": ready_for_pickup,
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
