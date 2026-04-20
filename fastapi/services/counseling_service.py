"""Counseling orchestration service.

Tries Ollama first for personalization, then falls back to template generation.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from services.normalization_service import split_medications
from services.ollama_service import generate_personalized_counseling
from services.template_service import (
    counseling_json_to_text,
    generate_counseling_template,
    log_generated_counseling,
)


def _ollama_json_to_text(payload: dict) -> str:
    lines: list[str] = []

    if payload.get("interaction_summary"):
        lines.append(f"Interaction summary: {payload['interaction_summary']}")
    if payload.get("patient_specific_risk"):
        lines.append(f"Patient-specific risk: {payload['patient_specific_risk']}")

    def add_section(title: str, key: str):
        values = payload.get(key) or []
        if not values:
            return
        lines.append(f"\n{title}:")
        for item in values:
            lines.append(f"• {item}")

    add_section("Top counseling points", "top_counseling_points")
    add_section("Monitoring points", "monitoring_points")
    add_section("Red flags", "red_flags")
    add_section("When to contact clinician", "when_to_contact_clinician")
    add_section("Evidence used", "evidence_used")

    lines.append(f"\n{payload.get('disclaimer', 'Educational prototype only. Not for diagnosis or prescribing.')}")
    return "\n".join(lines)


def generate_counseling(
    db: Session,
    *,
    patient_name: str,
    medications: str,
    interactions: list[dict],
    patient_age: Optional[int] = None,
    intake_id: Optional[int] = None,
) -> dict:
    normalized_meds = split_medications(medications)
    patient_context = {
        "patient_name": patient_name,
        "patient_age": patient_age,
        "medications": normalized_meds,
    }

    try:
        ollama_payload = generate_personalized_counseling(interactions, patient_context)
        log_generated_counseling(
            db,
            intake_id,
            patient_name,
            normalized_meds,
            ollama_payload,
            generator="ollama",
        )
        return {
            "source": "ollama",
            "payload": ollama_payload,
            "text": _ollama_json_to_text(ollama_payload),
        }
    except Exception:
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
            generator="template_fallback",
        )
        return {
            "source": "template_fallback",
            "payload": template_payload,
            "text": counseling_json_to_text(template_payload),
        }
