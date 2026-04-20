"""High-level API for deterministic interaction + counseling generation."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from services.interaction_engine import detect_interactions
from services.normalization_service import split_medications
from services.prioritization_service import prioritize_interactions
from services.counseling_service import generate_counseling


def check_drug_interactions(
    db: Session,
    new_medications: str,
    current_medications: Optional[str] = None,
    *,
    patient_age: Optional[int] = None,
    renal_status: Optional[str] = None,
    hepatic_status: Optional[str] = None,
) -> list[dict]:
    findings = detect_interactions(db, new_medications, current_medications)
    total_meds = len(split_medications(new_medications)) + len(split_medications(current_medications))
    return prioritize_interactions(
        findings,
        age=patient_age,
        renal_status=renal_status,
        hepatic_status=hepatic_status,
        medication_count=total_meds,
    )


def generate_counseling_points(
    db: Session,
    *,
    patient_name: str,
    medications: str,
    interactions: Optional[list[dict]] = None,
    patient_age: Optional[int] = None,
    intake_id: Optional[int] = None,
) -> str:
    result = generate_counseling(
        db,
        patient_name=patient_name,
        medications=medications,
        interactions=interactions or [],
        patient_age=patient_age,
        intake_id=intake_id,
    )
    return result["text"]
