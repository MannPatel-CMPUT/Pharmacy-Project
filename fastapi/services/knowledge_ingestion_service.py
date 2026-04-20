"""Manual knowledge dataset ingestion (CSV/JSON) and openFDA label JSON bundles."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from database import DrugAlias, DrugInteraction
from services.knowledge_repository import (
    ensure_alias,
    get_or_create_drug,
    interaction_exists,
    ordered_pair,
)
from services.openfda_ingestion_service import (
    ingest_openfda_label_json_stream,
    ingest_openfda_label_results,
    is_openfda_label_bundle,
)

_UPLOAD_CHUNK = 1024 * 1024

ALLOWED_SEVERITIES = {"contraindicated", "major", "moderate", "minor"}


def is_seed_interactions_bundle(payload: Any) -> bool:
    """True for repo `drug_interactions.json` shape: interactions{} and optional categories{}."""
    if not isinstance(payload, dict):
        return False
    rows = payload.get("rows")
    if isinstance(rows, list) and len(rows) > 0:
        return False
    inter = payload.get("interactions")
    if not isinstance(inter, dict):
        return False
    cats = payload.get("categories", None)
    if cats is not None and not isinstance(cats, dict):
        return False
    return True


def _norm_seed_name(value: str) -> str:
    return (value or "").strip().lower()


def _severity_from_seed_description(description: str) -> str:
    normalized_description = (description or "").strip()
    lower_desc = normalized_description.lower()
    if "major" in lower_desc:
        return "major"
    if "moderate" in lower_desc:
        return "moderate"
    if "minor" in lower_desc:
        return "minor"
    return "unknown"


def ingest_seed_interactions_bundle(
    db: Session,
    payload: dict[str, Any],
    *,
    interaction_source: str,
) -> dict[str, Any]:
    """
    Merge drugs, aliases, and pairwise interactions from seed-shaped JSON.
    Idempotent: skips existing interaction pairs. Does not commit.
    """
    stats: dict[str, Any] = {
        "total_rows": 0,
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "format": "drug_interactions_seed",
    }

    interactions = payload.get("interactions") or {}
    if not isinstance(interactions, dict):
        stats["failed"] = 1
        stats["fatal"] = True
        stats["error"] = "Invalid seed bundle: interactions must be an object"
        return stats

    names: set[str] = set()
    for left, rights in interactions.items():
        if not isinstance(rights, dict):
            continue
        names.add(_norm_seed_name(str(left)))
        for right in rights.keys():
            names.add(_norm_seed_name(str(right)))

    categories = payload.get("categories") or {}
    if isinstance(categories, dict):
        for drug_list in categories.values():
            if not isinstance(drug_list, list):
                continue
            for item in drug_list:
                names.add(_norm_seed_name(str(item)))

    names.discard("")
    if not names:
        stats["error"] = "Seed bundle contained no drug names"
        stats["fatal"] = True
        stats["failed"] = 1
        return stats

    known_aliases = {row.alias for row in db.query(DrugAlias.alias).all()}

    for name in sorted(names):
        try:
            drug = get_or_create_drug(db, name)
            ensure_alias(db, drug, name, known_aliases)
        except Exception as exc:
            db.rollback()
            stats["failed"] += 1
            stats["fatal"] = True
            stats["error"] = f"Drug bootstrap failed: {exc}"
            return stats

    pair_count = 0
    for left, rights in interactions.items():
        if not isinstance(rights, dict):
            continue
        left_norm = _norm_seed_name(str(left))
        if not left_norm:
            continue
        for right, description in rights.items():
            right_norm = _norm_seed_name(str(right))
            if not right_norm or left_norm == right_norm:
                stats["skipped"] += 1
                continue
            pair_count += 1
            stats["total_rows"] += 1
            try:
                if not isinstance(description, str):
                    description = str(description)
                drug_a = get_or_create_drug(db, left_norm)
                drug_b = get_or_create_drug(db, right_norm)
                ensure_alias(db, drug_a, left_norm, known_aliases)
                ensure_alias(db, drug_b, right_norm, known_aliases)

                pair_ids = ordered_pair(drug_a.id, drug_b.id)
                if interaction_exists(db, pair_ids[0], pair_ids[1]):
                    stats["skipped"] += 1
                    continue

                normalized_description = description.strip()
                severity = _severity_from_seed_description(normalized_description)
                db.add(
                    DrugInteraction(
                        drug_a_id=pair_ids[0],
                        drug_b_id=pair_ids[1],
                        severity=severity,
                        description=normalized_description,
                        clinical_effect=normalized_description,
                        mechanism=None,
                        monitoring=None,
                        source=interaction_source,
                    )
                )
                stats["inserted"] += 1
            except Exception as exc:
                db.rollback()
                stats["failed"] += 1
                stats["fatal"] = True
                stats["error"] = f"Interaction row failed: {exc}"
                return stats

    stats["pairs_seen"] = pair_count
    return stats


REQUIRED_FIELDS = ["drug_a", "drug_b", "severity", "clinical_effect", "mechanism", "monitoring"]


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_json_payload(payload: Any) -> list[dict[str, Any]]:
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


def ingest_knowledge_dataset(filename: str, content: bytes, db: Session) -> dict[str, Any]:
    lower_name = filename.lower()
    if not (lower_name.endswith(".csv") or lower_name.endswith(".json")):
        return {
            "total_rows": 0,
            "inserted": 0,
            "skipped": 0,
            "failed": 1,
            "fatal": True,
            "error": "Unsupported file type. Use .csv or .json",
        }

    try:
        text = content.decode("utf-8")
    except Exception:
        return {
            "total_rows": 0,
            "inserted": 0,
            "skipped": 0,
            "failed": 1,
            "fatal": True,
            "error": "File is not valid UTF-8 text",
        }

    if lower_name.endswith(".json"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return {
                "total_rows": 0,
                "inserted": 0,
                "skipped": 0,
                "failed": 1,
                "fatal": True,
                "error": f"Invalid JSON: {exc}",
            }

        if is_openfda_label_bundle(payload):
            stats = ingest_openfda_label_results(db, payload["results"])
            stats["format"] = "openfda_label_json"
            return stats

        if is_seed_interactions_bundle(payload):
            stats = ingest_seed_interactions_bundle(db, payload, interaction_source="upload")
            if stats.get("fatal"):
                return stats
            db.commit()
            return stats

        try:
            rows = _parse_json_payload(payload)
        except Exception:
            return {
                "total_rows": 0,
                "inserted": 0,
                "skipped": 0,
                "failed": 1,
                "fatal": True,
                "error": "Could not parse JSON rows",
            }

        if not rows:
            return {
                "total_rows": 0,
                "inserted": 0,
                "skipped": 0,
                "failed": 1,
                "fatal": True,
                "error": (
                    "Unrecognized JSON shape. Expected either openFDA label export "
                    '{"meta":..., "results":[...]} or a list / {"rows":[...]} of objects with '
                    f"fields: {', '.join(REQUIRED_FIELDS)}"
                ),
            }
    else:
        try:
            rows = _parse_csv(text)
        except Exception:
            return {
                "total_rows": 0,
                "inserted": 0,
                "skipped": 0,
                "failed": 1,
                "fatal": True,
                "error": "Could not parse CSV",
            }

    stats: dict[str, Any] = {
        "total_rows": len(rows),
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "format": "dataset_rows",
    }

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


def _large_json_bytes() -> int:
    """JSON files larger than this are stream-parsed (openFDA ``results[]`` only)."""
    raw = os.getenv("KNOWLEDGE_LARGE_JSON_BYTES", str(8 * 1024 * 1024)).strip()
    try:
        return max(512 * 1024, int(raw))
    except ValueError:
        return 8 * 1024 * 1024


def _sniff_large_file_is_openfda_export(path: str) -> bool:
    with open(path, "rb") as f:
        head = f.read(1024 * 1024)
    if b'"results"' not in head:
        return False
    return b'"meta"' in head or b'"openfda"' in head


def ingest_knowledge_large_json_file(db: Session, filename: str, path: str) -> dict[str, Any]:
    """
    Ingest a huge openFDA label JSON file from disk using a streaming parser.
    Other JSON shapes must stay under ``KNOWLEDGE_LARGE_JSON_BYTES`` (use normal upload).
    """
    if not _sniff_large_file_is_openfda_export(path):
        return {
            "total_fetched": 0,
            "parsed": 0,
            "inserted": 0,
            "skipped": 0,
            "failed": 1,
            "fatal": True,
            "format": "openfda_label_json",
            "error": (
                "Large JSON uploads must be an openFDA human drug label export "
                "(top-level meta + results[]). For the bundled seed file, keep it under "
                "KNOWLEDGE_LARGE_JSON_BYTES or upload drug_interactions.json (small)."
            ),
        }
    stats = ingest_openfda_label_json_stream(db, path)
    stats["format"] = "openfda_label_json"
    return stats


async def _spool_upload_to_tempfile(upload: UploadFile) -> tuple[str, int]:
    fd, path = tempfile.mkstemp(suffix=".json-upload")
    os.close(fd)
    total = 0
    try:
        with open(path, "wb") as w:
            while True:
                chunk = await upload.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                w.write(chunk)
                total += len(chunk)
        return path, total
    except Exception:
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass
        raise


async def ingest_knowledge_upload(file: UploadFile, db: Session) -> dict[str, Any]:
    """
    Accept multipart uploads: JSON is spooled to disk first so multi-hundred-MB openFDA
    exports do not load entirely into RAM. Large JSON is stream-ingested when it looks
    like an openFDA label bundle.
    """
    filename = (file.filename or "upload.bin").strip() or "upload.bin"
    lower = filename.lower()

    if lower.endswith(".json"):
        path, size = await _spool_upload_to_tempfile(file)
        try:
            if size <= _large_json_bytes():
                with open(path, "rb") as f:
                    content = f.read()
                return ingest_knowledge_dataset(filename, content, db)
            return ingest_knowledge_large_json_file(db, filename, path)
        finally:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    content = await file.read()
    return ingest_knowledge_dataset(filename, content, db)
