"""openFDA ingestion service for deterministic interaction knowledge extraction."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from database import DrugAlias, DrugInteraction, InteractionDocument
from services.knowledge_repository import ensure_alias, get_or_create_drug, ordered_pair

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PAIR_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9-]{2,})\s+(?:and|with|plus)\s+([A-Za-z][A-Za-z0-9-]{2,})\b",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _severity_from_text(text: str) -> str:
    lowered = (text or "").lower()
    if "contraindicated" in lowered:
        return "contraindicated"
    if "serious" in lowered:
        return "major"
    if "monitor" in lowered:
        return "moderate"
    return "minor"


def _extract_aliases(result: dict) -> list[str]:
    openfda = result.get("openfda", {}) or {}
    aliases: set[str] = set()
    for key in ("generic_name", "brand_name", "substance_name"):
        for value in _safe_list(openfda.get(key)):
            norm = _normalize(value)
            if norm:
                aliases.add(norm)
    return sorted(aliases)


def _split_sections(result: dict) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for field in ("drug_interactions", "warnings", "contraindications"):
        for chunk in _safe_list(result.get(field)):
            text = chunk.strip()
            if text:
                sections.append((field, text))
    return sections


def _extract_pairs(text: str, index_aliases: dict[str, int], current_drug_name: str) -> list[tuple[str, str, str]]:
    pairs: set[tuple[str, str, str]] = set()
    sentences = _SENTENCE_SPLIT.split(text)

    for sentence in sentences:
        sentence_lower = sentence.lower()
        if not any(k in sentence_lower for k in ("interact", "contraindicat", "monitor", "avoid", "with")):
            continue

        # Known-drug matching heuristic.
        mentions = [alias for alias in index_aliases.keys() if alias in sentence_lower]
        for alias in mentions:
            if alias == current_drug_name:
                continue
            left, right = sorted([current_drug_name, alias])
            pairs.add((left, right, sentence.strip()))

        # Regex pair fallback heuristic.
        for match in _PAIR_PATTERN.finditer(sentence):
            a = _normalize(match.group(1))
            b = _normalize(match.group(2))
            if not a or not b or a == b:
                continue
            left, right = sorted([a, b])
            pairs.add((left, right, sentence.strip()))

    return list(pairs)


def _upsert_interaction(db: Session, drug_a_id: int, drug_b_id: int, severity: str, description: str) -> bool:
    pair = ordered_pair(drug_a_id, drug_b_id)
    existing = db.query(DrugInteraction).filter(
        DrugInteraction.drug_a_id == pair[0],
        DrugInteraction.drug_b_id == pair[1],
    ).first()

    if existing:
        return False

    db.add(
        DrugInteraction(
            drug_a_id=pair[0],
            drug_b_id=pair[1],
            severity=severity,
            description=description[:2000],
            clinical_effect=description[:2000],
            source="openfda",
        )
    )
    return True


def sync_openfda_knowledge(db: Session, limit: int = 25) -> dict[str, int]:
    stats = {"total_fetched": 0, "parsed": 0, "inserted": 0, "failed": 0}

    try:
        response = httpx.get(OPENFDA_URL, params={"limit": max(1, min(limit, 100))}, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
    except Exception:
        stats["failed"] += 1
        return stats

    stats["total_fetched"] = len(results)

    # Build alias index from currently known aliases for sentence matching.
    known_aliases = {row.alias: row.drug_id for row in db.query(DrugAlias).all()}
    known_pairs = {
        (min(row.drug_a_id, row.drug_b_id), max(row.drug_a_id, row.drug_b_id))
        for row in db.query(DrugInteraction.drug_a_id, DrugInteraction.drug_b_id).all()
    }

    for item in results:
        try:
            aliases = _extract_aliases(item)
            if not aliases:
                stats["failed"] += 1
                continue

            primary_name = aliases[0]
            openfda = item.get("openfda", {}) or {}
            brand = _safe_list(openfda.get("brand_name"))
            drug = get_or_create_drug(db, primary_name, brand[0] if brand else None)
            ensure_alias(db, drug, primary_name)
            for alias in aliases[1:]:
                ensure_alias(db, drug, alias)

            # refresh known aliases with current document aliases
            for alias in aliases:
                known_aliases.setdefault(alias, drug.id)

            sections = _split_sections(item)
            set_id = _safe_list(openfda.get("set_id"))
            source_id = set_id[0] if set_id else None

            for section_name, raw_text in sections:
                parsed_pairs = _extract_pairs(raw_text, known_aliases, primary_name)
                parsed_payload = []

                for left_name, right_name, sentence in parsed_pairs:
                    left_drug = get_or_create_drug(db, left_name)
                    right_drug = get_or_create_drug(db, right_name)
                    ensure_alias(db, left_drug, left_name)
                    ensure_alias(db, right_drug, right_name)
                    pair = ordered_pair(left_drug.id, right_drug.id)
                    if pair in known_pairs:
                        continue

                    severity = _severity_from_text(sentence)
                    inserted = _upsert_interaction(
                        db,
                        left_drug.id,
                        right_drug.id,
                        severity,
                        sentence,
                    )
                    if inserted:
                        stats["inserted"] += 1
                        known_pairs.add(pair)
                    stats["parsed"] += 1

                    parsed_payload.append(
                        {
                            "drug1": left_name,
                            "drug2": right_name,
                            "severity": severity,
                            "text": sentence,
                        }
                    )

                db.add(
                    InteractionDocument(
                        source="openfda",
                        source_id=source_id,
                        section=section_name,
                        raw_text=raw_text[:5000],
                        parsed_payload=json.dumps(parsed_payload),
                        parsed_count=len(parsed_payload),
                        created_at=datetime.now(timezone.utc),
                    )
                )
        except Exception:
            stats["failed"] += 1
            db.rollback()
            continue

    db.commit()
    return stats
