"""Deterministic prioritization for interaction findings."""

from __future__ import annotations

from typing import Optional

from core.constants import SEVERITY_SCORES


def _risk_multiplier(flag: Optional[str]) -> int:
    value = (flag or "").strip().lower()
    if value in {"severe", "impaired", "poor"}:
        return 20
    if value in {"mild", "moderate"}:
        return 10
    return 0


_FEMALE_INDICATORS = frozenset({"female", "f", "woman", "girl"})
_MALE_INDICATORS = frozenset({"male", "m", "man", "boy"})

# Medications with notable sex-specific risks (e.g. QT-prolongation more common in females,
# teratogenicity for females of childbearing potential, specific male/female dosing cautions).
_FEMALE_RISK_KEYWORDS = frozenset({
    "methotrexate", "isotretinoin", "leflunomide", "thalidomide",
    "azathioprine", "warfarin", "amiodarone", "quinidine",
    "clarithromycin", "erythromycin", "azithromycin",
    "haloperidol", "quetiapine", "olanzapine",
})
_MALE_RISK_KEYWORDS = frozenset({
    "sildenafil", "tadalafil", "vardenafil", "finasteride", "dutasteride",
    "testosterone", "tamsulosin", "alfuzosin",
})


def _gender_score_boost(patient_gender: Optional[str], description: str) -> int:
    g = (patient_gender or "").strip().lower()
    if not g or g in ("unknown", "unspecified", "prefer not to say", "other"):
        return 0
    desc_lower = description.lower()
    boost = 0
    if g in _FEMALE_INDICATORS:
        if any(k in desc_lower for k in _FEMALE_RISK_KEYWORDS):
            boost += 12
    if g in _MALE_INDICATORS:
        if any(k in desc_lower for k in _MALE_RISK_KEYWORDS):
            boost += 8
    return boost


def prioritize_interactions(
    interactions: list[dict],
    age: Optional[int] = None,
    patient_gender: Optional[str] = None,
    renal_status: Optional[str] = None,
    hepatic_status: Optional[str] = None,
    medication_count: Optional[int] = None,
) -> list[dict]:
    scored = []
    for item in interactions:
        severity_key = str(item.get("severity", "unknown")).lower()
        score = SEVERITY_SCORES.get(severity_key, SEVERITY_SCORES["unknown"])

        if age is not None and age >= 65:
            score += 15

        score += _risk_multiplier(renal_status)
        score += _risk_multiplier(hepatic_status)

        description = item.get("description") or ""
        score += _gender_score_boost(patient_gender, description)

        if medication_count is not None and medication_count >= 5:
            score += 10
        if medication_count is not None and medication_count >= 8:
            score += 5

        enriched = dict(item)
        enriched["priority_score"] = score
        scored.append(enriched)

    return sorted(scored, key=lambda row: row["priority_score"], reverse=True)
