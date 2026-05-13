"""Counseling orchestration: deterministic template generation only."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from services.normalization_service import split_medications
from services.template_service import (
    counseling_json_to_text,
    generate_counseling_template,
    log_generated_counseling,
)

logger = logging.getLogger(__name__)


def generate_counseling(
    db: Session,
    *,
    patient_name: str,
    medications: str,
    interactions: list[dict],
    patient_age: Optional[int] = None,
    intake_id: Optional[int] = None,
    patient_allergies: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    normalized_meds = split_medications(medications)
    template_payload = generate_counseling_template(
        patient_name=patient_name,
        medications=normalized_meds,
        interactions=interactions,
        age=patient_age,
    )
    log_generated_counseling(
        db,
        intake_id,
        patient_name,
        normalized_meds,
        template_payload,
        generator="template",
    )
    return {
        "source": "template",
        "payload": template_payload,
        "text": counseling_json_to_text(template_payload),
    }
