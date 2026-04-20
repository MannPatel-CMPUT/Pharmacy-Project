"""Shared persistence helpers for drug knowledge services."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Drug, DrugAlias, DrugInteraction
from services.normalization_service import normalize_token


def get_or_create_drug(db: Session, generic_name: str, brand_name: str | None = None) -> Drug:
    token = normalize_token(generic_name)
    if not token:
        token = (generic_name or "").strip().lower()

    drug = db.query(Drug).filter(func.lower(Drug.generic_name) == token.lower()).first()
    if drug:
        if brand_name and not drug.brand_name:
            drug.brand_name = brand_name
        return drug

    drug = Drug(generic_name=token, brand_name=brand_name)
    db.add(drug)
    db.flush()
    return drug


def ensure_alias(db: Session, drug: Drug, alias: str, known_aliases: set[str] | None = None) -> None:
    if known_aliases is not None and alias in known_aliases:
        return

    for pending in db.new:
        if isinstance(pending, DrugAlias) and pending.alias == alias:
            return

    existing = db.query(DrugAlias).filter(DrugAlias.alias == alias).first()
    if existing:
        if known_aliases is not None:
            known_aliases.add(alias)
        return

    db.add(DrugAlias(drug_id=drug.id, alias=alias))
    if known_aliases is not None:
        known_aliases.add(alias)


def ordered_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def interaction_exists(db: Session, drug_a_id: int, drug_b_id: int) -> bool:
    pair = ordered_pair(drug_a_id, drug_b_id)
    return (
        db.query(DrugInteraction)
        .filter(DrugInteraction.drug_a_id == pair[0], DrugInteraction.drug_b_id == pair[1])
        .first()
        is not None
    )
