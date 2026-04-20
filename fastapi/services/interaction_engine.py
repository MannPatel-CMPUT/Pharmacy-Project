"""Deterministic pairwise drug interaction engine."""

from __future__ import annotations

from itertools import combinations
from typing import Optional

from sqlalchemy.orm import Session

from database import Drug, DrugInteraction
from services.normalization_service import normalize_and_match


def _ordered_names(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _load_interaction_map(db: Session) -> dict[tuple[str, str], DrugInteraction]:
    drugs = {d.id: d.generic_name for d in db.query(Drug).all()}
    interactions = db.query(DrugInteraction).all()

    interaction_map: dict[tuple[str, str], DrugInteraction] = {}
    for row in interactions:
        left = drugs.get(row.drug_a_id)
        right = drugs.get(row.drug_b_id)
        if not left or not right:
            continue
        key = _ordered_names(left, right)
        interaction_map[key] = row
    return interaction_map


def detect_interactions(
    db: Session,
    new_medications: str,
    current_medications: Optional[str] = None,
) -> list[dict]:
    new_meds = normalize_and_match(new_medications, db)
    current_meds = normalize_and_match(current_medications, db)

    interaction_map = _load_interaction_map(db)
    seen_pairs: set[tuple[str, str]] = set()
    findings: list[dict] = []

    if current_meds:
        candidate_pairs = ((a, b) for a in new_meds for b in current_meds if a != b)
    else:
        candidate_pairs = combinations(new_meds, 2)

    for med_a, med_b in candidate_pairs:
        left, right = _ordered_names(med_a, med_b)
        pair = (left, right)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        interaction = interaction_map.get(pair)
        if not interaction:
            continue

        findings.append(
            {
                "drug1": med_a,
                "drug2": med_b,
                "normalized_pair": [left, right],
                "severity": interaction.severity.capitalize(),
                "description": interaction.clinical_effect or interaction.description,
                "mechanism": interaction.mechanism,
                "monitoring": interaction.monitoring,
                "source": interaction.source,
            }
        )

    return findings
