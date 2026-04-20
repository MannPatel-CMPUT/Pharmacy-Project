"""Per-intake openFDA label fetch to improve interaction coverage (free API; optional OPENFDA_API_KEY)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from services.normalization_service import normalize_and_match
from services.openfda_ingestion_service import OPENFDA_URL, ingest_openfda_label_results

logger = logging.getLogger(__name__)


def _enrich_enabled() -> bool:
    return os.getenv("OPENFDA_ENRICH_ON_INTAKE", "true").lower() in ("1", "true", "yes")


def _max_drugs() -> int:
    try:
        return max(1, min(int(os.getenv("OPENFDA_INTAKE_MAX_DRUGS", "6")), 12))
    except ValueError:
        return 6


def _label_limit() -> int:
    try:
        return max(1, min(int(os.getenv("OPENFDA_INTAKE_LABEL_LIMIT", "2")), 10))
    except ValueError:
        return 2


def _delay_sec() -> float:
    try:
        return max(0.0, float(os.getenv("OPENFDA_INTAKE_DELAY_SEC", "0.12")))
    except ValueError:
        return 0.12


def _label_set_id(item: dict) -> str:
    o = item.get("openfda") or {}
    sid = o.get("set_id") if isinstance(o, dict) else None
    if isinstance(sid, list) and sid:
        return str(sid[0])
    if isinstance(sid, str) and sid:
        return sid
    return ""


def _fetch_labels(search: str, limit: int) -> tuple[list[dict], int, Optional[str]]:
    """Returns (results, http_calls, error_message)."""
    params: dict[str, Any] = {"search": search, "limit": max(1, min(limit, 10))}
    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key
    timeout = float(os.getenv("OPENFDA_TIMEOUT_SECONDS", "25"))
    try:
        response = httpx.get(OPENFDA_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        preview = (exc.response.text or "")[:400]
        return [], 1, f"HTTP {exc.response.status_code}: {preview or exc.response.reason_phrase}"
    except Exception as exc:
        return [], 1, str(exc)[:400]

    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        message = err.get("message") if isinstance(err, dict) else str(err)
        return [], 1, message or "openFDA error object"

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return [], 1, "openFDA response missing results[]"

    return results, 1, None


def fetch_labels_for_normalized_drug(term: str, *, limit: int) -> tuple[list[dict], int, list[str]]:
    """Try generic_name then substance_name search. Returns (labels, api_calls, errors)."""
    token = (term or "").strip().lower().replace('"', " ").replace("\\", " ")
    if not token or len(token) > 80:
        return [], 0, []

    errors: list[str] = []
    calls = 0
    q1 = f'openfda.generic_name:"{token}"'
    results, c1, e1 = _fetch_labels(q1, limit)
    calls += c1
    if e1:
        errors.append(f"generic:{e1}")
    if results:
        return results, calls, errors

    q2 = f'openfda.substance_name:"{token}"'
    results2, c2, e2 = _fetch_labels(q2, limit)
    calls += c2
    if e2:
        errors.append(f"substance:{e2}")
    return results2 or [], calls, errors


def enrich_db_from_openfda_for_intake_meds(
    db: Session,
    new_medications: str,
    current_medications: Optional[str],
) -> dict[str, Any]:
    """
    For each unique normalized medication token, pull a few SPL labels from openFDA and merge
    extracted DrugInteraction rows into the database, then ``detect_interactions`` can pick them up.
    """
    stats: dict[str, Any] = {
        "enabled": True,
        "terms": [],
        "api_calls": 0,
        "labels_fetched": 0,
        "ingest": {},
        "errors": [],
    }
    if not _enrich_enabled():
        stats["enabled"] = False
        return stats

    seen: set[str] = set()
    terms: list[str] = []
    for t in normalize_and_match(new_medications, db):
        if t and t not in seen:
            seen.add(t)
            terms.append(t)
    for t in normalize_and_match(current_medications, db):
        if t and t not in seen:
            seen.add(t)
            terms.append(t)

    terms = terms[:_max_drugs()]
    stats["terms"] = list(terms)
    if not terms:
        return stats

    lim = _label_limit()
    delay = _delay_sec()
    by_set: dict[str, dict] = {}

    for i, term in enumerate(terms):
        if i and delay:
            time.sleep(delay)
        batch, calls, errs = fetch_labels_for_normalized_drug(term, limit=lim)
        stats["api_calls"] += calls
        stats["errors"].extend(errs)
        for item in batch:
            if not isinstance(item, dict):
                continue
            sid = _label_set_id(item) or json.dumps(item.get("openfda", {}), sort_keys=True)[:120]
            if sid not in by_set:
                by_set[sid] = item

    combined = list(by_set.values())
    stats["labels_fetched"] = len(combined)
    if not combined:
        logger.info("openfda intake enrich no_labels terms=%s errors=%s", terms, stats["errors"])
        return stats

    try:
        ingest_stats = ingest_openfda_label_results(db, combined)
        stats["ingest"] = {
            "inserted": ingest_stats.get("inserted", 0),
            "parsed": ingest_stats.get("parsed", 0),
            "skipped": ingest_stats.get("skipped", 0),
            "failed": ingest_stats.get("failed", 0),
        }
    except Exception as exc:
        logger.exception("openfda intake enrich ingest_failed terms=%s", terms)
        stats["errors"].append(str(exc)[:500])
    return stats
