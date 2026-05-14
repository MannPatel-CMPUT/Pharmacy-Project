"""Ingest large DrugBank-style CSV files: Drug 1, Drug 2, Interaction Description."""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from typing import Any, TextIO

from sqlalchemy.orm import Session

from database import DrugInteraction
from services.ddi_severity_classifier import (
    ALLOWED_SEVERITIES,
    classify_ddii_interaction_severity,
    parse_explicit_ddii_severity,
)
from services.knowledge_repository import ensure_alias, get_or_create_drug, ordered_pair

logger = logging.getLogger(__name__)

SOURCE_TAG = "db_drug_interactions_csv"

_DDII_DRUG1 = ("drug 1", "drug1", "drug_a", "drug a")
_DDII_DRUG2 = ("drug 2", "drug2", "drug_b", "drug b")
_DDII_DESC = ("interaction description", "description", "clinical_effect", "clinical effect")
_DDII_RISK = ("risk severity", "interaction severity", "clinical severity")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _map_ddii_row(raw: dict[str, str]) -> dict[str, str] | None:
    lower_map = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
    d1 = next((lower_map[a] for a in _DDII_DRUG1 if a in lower_map and lower_map[a]), None)
    d2 = next((lower_map[a] for a in _DDII_DRUG2 if a in lower_map and lower_map[a]), None)
    desc = next((lower_map[a] for a in _DDII_DESC if a in lower_map and lower_map[a]), None)
    if not d1 or not d2 or d1.lower() == d2.lower():
        return None
    if not desc:
        return None
    risk_cell = next((lower_map[a] for a in _DDII_RISK if a in lower_map and lower_map[a]), None)
    return {
        "drug_a": d1.lower(),
        "drug_b": d2.lower(),
        "description": desc,
        "explicit_severity": parse_explicit_ddii_severity(risk_cell),
    }


def _severity_from_ddii_description(description: str) -> str:
    """Backward-compatible alias for :func:`classify_ddii_interaction_severity`."""
    return classify_ddii_interaction_severity(description)


def is_ddii_csv_headers(fieldnames: list[str] | None) -> bool:
    """
    True for DrugBank-style exports: ``Drug 1``, ``Drug 2``, ``Interaction Description``.

    Excludes the app's six-column upload format (drug_a, drug_b, severity, …) which also
    contains drug_a / clinical_effect but is not the DDII file.
    """
    if not fieldnames:
        return False
    keys = {_norm_header(x) for x in fieldnames}
    # Legacy app CSV always includes explicit severity + mechanism columns
    if "severity" in keys and "mechanism" in keys:
        return False
    has_ddii_titles = "drug 1" in keys and "drug 2" in keys
    has_desc = "interaction description" in keys
    if has_ddii_titles and has_desc:
        return True
    return False


def ingest_ddii_csv_stream(
    db: Session,
    text_stream: TextIO,
    *,
    max_rows: int | None = None,
    commit_every: int = 2000,
) -> dict[str, Any]:
    """
    Stream-parse a UTF-8 CSV with headers Drug 1, Drug 2, Interaction Description.
    Loads existing interaction pairs into memory once for fast dedup.
    """
    stats: dict[str, Any] = {
        "total_rows": 0,
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "format": "db_drug_interactions_csv",
    }

    reader = csv.DictReader(text_stream)
    if not is_ddii_csv_headers(reader.fieldnames):
        stats["fatal"] = True
        stats["failed"] = 1
        stats["error"] = (
            "CSV must have columns like 'Drug 1', 'Drug 2', 'Interaction Description'"
        )
        return stats

    pair_rows = db.query(DrugInteraction.drug_a_id, DrugInteraction.drug_b_id).all()
    known_pairs: set[tuple[int, int]] = {
        (min(a, b), max(a, b)) for a, b in pair_rows
    }

    commit_every = max(100, min(commit_every, 20000))
    pending_commits = 0

    for raw in reader:
        if max_rows is not None and stats["total_rows"] >= max_rows:
            break

        mapped = _map_ddii_row({k: v or "" for k, v in raw.items()})
        if not mapped:
            stats["skipped"] += 1
            continue

        stats["total_rows"] += 1
        d1 = mapped["drug_a"]
        d2 = mapped["drug_b"]
        desc = mapped["description"][:8000]
        explicit = mapped.get("explicit_severity")
        if explicit in ALLOWED_SEVERITIES:
            severity = explicit
        else:
            severity = classify_ddii_interaction_severity(desc)
        if severity not in ALLOWED_SEVERITIES:
            severity = "moderate"

        try:
            drug_a = get_or_create_drug(db, d1)
            drug_b = get_or_create_drug(db, d2)
            ensure_alias(db, drug_a, d1)
            ensure_alias(db, drug_b, d2)

            pair = ordered_pair(drug_a.id, drug_b.id)
            if pair in known_pairs:
                stats["skipped"] += 1
                continue

            db.add(
                DrugInteraction(
                    drug_a_id=pair[0],
                    drug_b_id=pair[1],
                    severity=severity,
                    description=desc,
                    clinical_effect=desc[:2000],
                    mechanism=None,
                    monitoring=None,
                    source=SOURCE_TAG,
                )
            )
            known_pairs.add(pair)
            stats["inserted"] += 1
            pending_commits += 1

            if pending_commits >= commit_every:
                db.commit()
                pending_commits = 0
        except Exception as exc:
            stats["failed"] += 1
            db.rollback()
            logger.exception("ddi_csv row failed: %s", exc)
            if stats["failed"] > 100:
                stats["fatal"] = True
                stats["error"] = "Too many row failures; aborted"
                return stats

    db.commit()
    logger.info(
        "ddi_csv done total_rows=%s inserted=%s skipped=%s failed=%s",
        stats["total_rows"],
        stats["inserted"],
        stats["skipped"],
        stats["failed"],
    )
    return stats


def ingest_ddii_csv_bytes(db: Session, content: bytes, **kwargs: Any) -> dict[str, Any]:
    text = content.decode("utf-8-sig")
    return ingest_ddii_csv_stream(db, io.StringIO(text), **kwargs)


def ingest_ddii_csv_file(
    db: Session,
    file_path: str,
    *,
    max_rows: int | None = None,
    commit_every: int | None = None,
) -> dict[str, Any]:
    ce = commit_every if commit_every is not None else int(os.getenv("DDI_CSV_COMMIT_EVERY", "2000"))
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        return ingest_ddii_csv_stream(db, f, max_rows=max_rows, commit_every=ce)
