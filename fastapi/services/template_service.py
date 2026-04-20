"""Template-based counseling generator (no LLM)."""

from __future__ import annotations

from typing import Optional
import json

from sqlalchemy.orm import Session

from database import GeneratedCounselingLog


def generate_counseling_template(
    patient_name: str,
    medications: list[str],
    interactions: list[dict],
    age: Optional[int] = None,
) -> dict:
    bullets = []
    reminders = [
        "Take medications exactly as prescribed.",
        "Do not stop medications abruptly without clinician guidance.",
        "Keep an updated medication list and share it at each visit.",
    ]

    if age is not None and age >= 65:
        reminders.append("Use extra caution for dizziness and fall risk.")

    med_set = {med.lower() for med in medications}
    if "warfarin" in med_set:
        bullets.extend(
            [
                "Maintain consistent vitamin K intake.",
                "Report unusual bruising or bleeding immediately.",
            ]
        )
    if "lisinopril" in med_set:
        bullets.append("Monitor blood pressure and watch for persistent cough.")
    if "atorvastatin" in med_set:
        bullets.append("Report unexplained muscle pain promptly.")

    interaction_bullets = [
        f"{row['severity']}: {row['drug1']} + {row['drug2']} — {row['description']}"
        for row in interactions
    ]

    return {
        "patient_name": patient_name,
        "medications": medications,
        "interaction_warnings": interaction_bullets,
        "counseling_points": bullets or reminders,
        "general_reminders": reminders,
        "disclaimer": "Educational prototype only. Not for diagnosis or prescribing.",
    }


def counseling_json_to_text(counseling_payload: dict) -> str:
    lines = []
    for item in counseling_payload.get("counseling_points", []):
        lines.append(f"• {item}")

    warnings = counseling_payload.get("interaction_warnings", [])
    if warnings:
        lines.append("\n⚠️ DRUG INTERACTION WARNINGS:")
        for warning in warnings:
            lines.append(f"• {warning}")

    lines.append(f"\n{counseling_payload['disclaimer']}")
    return "\n".join(lines)


def log_generated_counseling(
    db: Session,
    intake_id: Optional[int],
    patient_name: str,
    medications: list[str],
    counseling_payload: dict,
    generator: str = "template_service",
) -> None:
    log = GeneratedCounselingLog(
        intake_id=intake_id,
        patient_name=patient_name,
        medications=", ".join(medications),
        counseling_json=json.dumps(counseling_payload),
        generator=generator,
    )
    db.add(log)
    db.commit()
