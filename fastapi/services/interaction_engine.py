"""Deterministic pairwise drug interaction engine."""

from __future__ import annotations

import logging
from itertools import combinations
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Drug, DrugInteraction
from services.knowledge_repository import ordered_pair
from services.normalization_service import expanded_terms_for_matching, normalize_and_match

logger = logging.getLogger(__name__)


def _ordered_names(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _get_drug_by_canonical_name(db: Session, name: str) -> Optional[Drug]:
    if not name:
        return None
    token = name.strip().lower()
    row = db.query(Drug).filter(Drug.generic_name == token).first()
    if row:
        return row
    return db.query(Drug).filter(func.lower(Drug.generic_name) == token).first()


def _fetch_interaction_for_name_pair(
    db: Session, name_a: str, name_b: str
) -> Optional[DrugInteraction]:
    """Resolve two canonical drug names to a single DrugInteraction row, if any."""
    d1 = _get_drug_by_canonical_name(db, name_a)
    d2 = _get_drug_by_canonical_name(db, name_b)
    if not d1 or not d2 or d1.id == d2.id:
        return None
    a_id, b_id = ordered_pair(d1.id, d2.id)
    return (
        db.query(DrugInteraction)
        .filter(
            DrugInteraction.drug_a_id == a_id,
            DrugInteraction.drug_b_id == b_id,
        )
        .first()
    )


def _lookup_interaction_for_medication_pair(
    db: Session, med_a: str, med_b: str
) -> tuple[Optional[DrugInteraction], tuple[str, str], str, list[tuple[str, str]]]:
    """
    Match using ordered names, then class/synonym expansion.
    Returns (row, matched_pair, match_reason, searched_pairs).
    """
    left, right = _ordered_names(med_a, med_b)
    pair = (left, right)
    searched_pairs: list[tuple[str, str]] = [pair]

    interaction = _fetch_interaction_for_name_pair(db, left, right)
    if interaction:
        return interaction, pair, "exact", searched_pairs

    for left_option in expanded_terms_for_matching(left):
        for right_option in expanded_terms_for_matching(right):
            candidate = _ordered_names(left_option, right_option)
            if candidate in searched_pairs:
                continue
            searched_pairs.append(candidate)
            interaction = _fetch_interaction_for_name_pair(db, left_option, right_option)
            if interaction:
                return interaction, candidate, "class_expansion", searched_pairs

    return None, pair, "none", searched_pairs


def detect_interactions(
    db: Session,
    new_medications: str,
    current_medications: Optional[str] = None,
) -> list[dict]:
    new_meds = normalize_and_match(new_medications, db)
    current_meds = normalize_and_match(current_medications, db)
    logger.info(
        "interaction intake_normalized new=%s current=%s",
        new_meds,
        current_meds,
    )

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

        interaction, matched_pair, match_reason, searched_pairs = (
            _lookup_interaction_for_medication_pair(db, med_a, med_b)
        )

        logger.info(
            "interaction pair_eval input_pair=%s searched_pairs=%s matched_pair=%s match_reason=%s matched=%s",
            pair,
            searched_pairs[:8],
            matched_pair if interaction else None,
            match_reason if interaction else "none",
            bool(interaction),
        )
        if not interaction:
            continue

        findings.append(
            {
                "drug1": med_a,
                "drug2": med_b,
                "normalized_pair": [matched_pair[0], matched_pair[1]],
                "severity": interaction.severity.capitalize(),
                "description": interaction.clinical_effect or interaction.description,
                "mechanism": interaction.mechanism,
                "monitoring": interaction.monitoring,
                "source": interaction.source,
            }
        )
        logger.info(
            "interaction matched input_pair=%s stored_pair=%s source=%s",
            pair,
            matched_pair,
            interaction.source,
        )

    return findings
