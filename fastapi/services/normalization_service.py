"""Deterministic medication normalization and alias matching."""

from __future__ import annotations

import re
from typing import Optional
from sqlalchemy.orm import Session

from database import DrugAlias

_SPLIT_PATTERN = re.compile(r"[,;\n]")
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s-]")

CLASS_TO_DRUGS: dict[str, list[str]] = {
    "nsaids": ["ibuprofen", "naproxen", "aspirin"],
    "nsaid": ["ibuprofen", "naproxen", "aspirin"],
    "opioids": ["hydrocodone", "oxycodone", "morphine"],
    "opioid": ["hydrocodone", "oxycodone", "morphine"],
    "benzodiazepines": ["alprazolam", "lorazepam", "diazepam"],
    "benzodiazepine": ["alprazolam", "lorazepam", "diazepam"],
}

_DRUG_TO_CLASSES: dict[str, set[str]] = {}
for class_name, members in CLASS_TO_DRUGS.items():
    for member in members:
        _DRUG_TO_CLASSES.setdefault(member, set()).add(class_name)


def normalize_token(value: str) -> str:
    cleaned = _NON_ALNUM_PATTERN.sub("", (value or "").strip().lower())
    return " ".join(cleaned.split())


def split_medications(raw_medications: Optional[str]) -> list[str]:
    if not raw_medications:
        return []
    parts = _SPLIT_PATTERN.split(raw_medications)
    return [normalize_token(part) for part in parts if normalize_token(part)]


def resolve_alias(db: Session, token: str) -> str:
    if not token:
        return token
    alias = db.query(DrugAlias).filter(DrugAlias.alias == token).first()
    if alias and alias.drug:
        return alias.drug.generic_name
    return token


def normalize_and_match(raw_medications: Optional[str], db: Session) -> list[str]:
    normalized = split_medications(raw_medications)
    return [resolve_alias(db, token) for token in normalized]


def expanded_terms_for_matching(term: str) -> list[str]:
    """Expand class/member names for deterministic matching fallbacks."""
    token = normalize_token(term)
    if not token:
        return []

    expanded: set[str] = {token}
    if token in CLASS_TO_DRUGS:
        expanded.update(CLASS_TO_DRUGS[token])
    expanded.update(_DRUG_TO_CLASSES.get(token, set()))
    return sorted(expanded)
