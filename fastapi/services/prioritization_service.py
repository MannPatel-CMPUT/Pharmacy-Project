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


def prioritize_interactions(
    interactions: list[dict],
    age: Optional[int] = None,
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

        if medication_count is not None and medication_count >= 5:
            score += 10
        if medication_count is not None and medication_count >= 8:
            score += 5

        enriched = dict(item)
        enriched["priority_score"] = score
        scored.append(enriched)

    return sorted(scored, key=lambda row: row["priority_score"], reverse=True)
