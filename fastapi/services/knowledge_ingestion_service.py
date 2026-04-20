"""Manual knowledge dataset ingestion (CSV/JSON)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy.orm import Session

from database import DrugAlias, DrugInteraction
from services.knowledge_repository import (
    ensure_alias,
    get_or_create_drug,
    interaction_exists,
    ordered_pair,
)

ALLOWED_SEVERITIES = {"contraindicated", "major", "moderate", "minor"}
REQUIRED_FIELDS = ["drug_a", "drug_b", "severity", "clinical_effect", "mechanism", "monitoring"]


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_json(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _validate_row(row: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    normalized: dict[str, str] = {}
    for field in REQUIRED_FIELDS:
        value = str(row.get(field, "")).strip()
        if not value:
            return False, {}
        normalized[field] = value

    normalized["drug_a"] = _normalize(normalized["drug_a"])
    normalized["drug_b"] = _normalize(normalized["drug_b"])
    normalized["severity"] = _normalize(normalized["severity"])

    if normalized["drug_a"] == normalized["drug_b"]:
        return False, {}
    if normalized["severity"] not in ALLOWED_SEVERITIES:
        return False, {}

    return True, normalized


def ingest_knowledge_dataset(filename: str, content: bytes, db: Session) -> dict[str, int]:
    stats = {"total_rows": 0, "inserted": 0, "skipped": 0, "failed": 0}

    try:
        text = content.decode("utf-8")
    except Exception:
        stats["failed"] = 1
        return stats

    try:
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            rows = _parse_csv(text)
        elif lower_name.endswith(".json"):
            rows = _parse_json(text)
        else:
            stats["failed"] = 1
            return stats
    except Exception:
        stats["failed"] = 1
        return stats

    stats["total_rows"] = len(rows)
    known_aliases = {row.alias for row in db.query(DrugAlias.alias).all()}
    known_pairs = {
        ordered_pair(row.drug_a_id, row.drug_b_id)
        for row in db.query(DrugInteraction.drug_a_id, DrugInteraction.drug_b_id).all()
    }

    for row in rows:
        try:
            valid, normalized = _validate_row(row)
            if not valid:
                stats["skipped"] += 1
                continue

            drug_a = get_or_create_drug(db, normalized["drug_a"])
            drug_b = get_or_create_drug(db, normalized["drug_b"])
            ensure_alias(db, drug_a, normalized["drug_a"], known_aliases)
            ensure_alias(db, drug_b, normalized["drug_b"], known_aliases)

            pair = ordered_pair(drug_a.id, drug_b.id)
            if pair in known_pairs or interaction_exists(db, drug_a.id, drug_b.id):
                stats["skipped"] += 1
                continue

            db.add(
                DrugInteraction(
                    drug_a_id=pair[0],
                    drug_b_id=pair[1],
                    severity=normalized["severity"],
                    description=normalized["clinical_effect"],
                    clinical_effect=normalized["clinical_effect"],
                    mechanism=normalized["mechanism"],
                    monitoring=normalized["monitoring"],
                    source="upload",
                )
            )
            known_pairs.add(pair)
            stats["inserted"] += 1
        except Exception:
            db.rollback()
            stats["failed"] += 1

    db.commit()
    return stats
