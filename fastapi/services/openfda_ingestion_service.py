"""openFDA ingestion service for deterministic interaction knowledge extraction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from database import DrugAlias, DrugInteraction, InteractionDocument
from services.knowledge_repository import ensure_alias, get_or_create_drug, ordered_pair

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Generic class names that appear frequently in label text and their deterministic
# expansion targets for interaction matching.
_CLASS_TO_DRUGS = {
    "nsaids": ["ibuprofen", "naproxen", "aspirin"],
    "nsaid": ["ibuprofen", "naproxen", "aspirin"],
    "nonsteroidal anti-inflammatory drugs": ["ibuprofen", "naproxen", "aspirin"],
    "nonsteroidal anti inflammatory drugs": ["ibuprofen", "naproxen", "aspirin"],
}

# Phrase patterns that usually indicate interaction language in openFDA documents.
_INTERACTION_HINTS = (
    "interact",
    "interaction",
    "contraindicat",
    "monitor",
    "avoid",
    "concurrent",
    "increase",
    "decrease",
    "bleeding",
)

# Deterministic sentence-level patterns for high-confidence pair extraction.
_CONNECTOR_PATTERNS = [
    re.compile(
        r"\b(?:concurrent\s+)?use\s+of\s+([a-z][a-z0-9\-\s]{1,80}?)\s+(?:and|with|plus|or)\s+([a-z][a-z0-9\-\s]{1,80}?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z0-9\-\s]{1,80}?)\s+(?:and|with|plus|or)\s+([a-z][a-z0-9\-\s]{1,80}?)\s+(?:increases?|decreases?|may\s+increase|may\s+decrease|causes?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z0-9\-\s]{1,80}?)\s+may\s+increase\s+([a-z][a-z0-9\-\s]{1,80}?)\s+(?:levels?|concentrations?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z0-9\-\s]{1,80}?)\s+may\s+decrease\s+([a-z][a-z0-9\-\s]{1,80}?)\s+(?:levels?|concentrations?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z0-9\-\s]{1,80}?)\s+(?:and|with|plus)\s+([a-z][a-z0-9\-\s]{1,80}?)\s+(?:may\s+)?(?:cause|increase|decrease|lead to|result in|should be avoided)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z0-9\-\s]{1,80}?)\s+is\s+contraindicated\s+with\s+([a-z][a-z0-9\-\s]{1,80}?)\b",
        re.IGNORECASE,
    ),
]

logger = logging.getLogger(__name__)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _preview(text: str, limit: int = 140) -> str:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _severity_from_text(text: str) -> str:
    lowered = (text or "").lower()
    if "contraindicated" in lowered:
        return "contraindicated"
    if any(term in lowered for term in ("serious", "life-threatening", "fatal")):
        return "major"
    if any(term in lowered for term in ("monitor", "dose adjustment", "adjust dose")):
        return "moderate"
    if any(term in lowered for term in ("increase", "decrease", "risk")):
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


def _entity_candidates(index_aliases: dict[str, int], current_drug_name: str) -> list[str]:
    # Longest-first avoids partial token issues (e.g. "statin" before "simvastatin").
    candidates = sorted(set(index_aliases.keys()) | set(_CLASS_TO_DRUGS.keys()), key=len, reverse=True)
    if current_drug_name and current_drug_name not in candidates:
        candidates.append(current_drug_name)
    return candidates


def _expand_entity(entity: str, current_drug_name: str, exclude_current: bool = True) -> list[str]:
    norm = _normalize(entity)
    if not norm:
        return []
    if norm in _CLASS_TO_DRUGS:
        return [item for item in _CLASS_TO_DRUGS[norm] if (not exclude_current or item != current_drug_name)]
    if exclude_current and norm == current_drug_name:
        return []
    return [norm]


def _find_entities(sentence: str, candidates: list[str]) -> list[str]:
    sentence_norm = _normalize(sentence)
    found: list[str] = []
    for candidate in candidates:
        if re.search(rf"\b{re.escape(candidate)}\b", sentence_norm):
            found.append(candidate)
    return found


def _resolve_entity(term: str, candidates: list[str]) -> str | None:
    norm = _normalize(term)
    if not norm:
        return None
    if norm in candidates:
        return norm
    for candidate in candidates:
        if re.search(rf"\b{re.escape(candidate)}\b", norm):
            return candidate
    tokens = norm.split()
    if 1 <= len(tokens) <= 3 and not any(
        token in {"concurrent", "use", "of", "drug", "drugs", "agent", "agents"} for token in tokens
    ):
        return norm
    return None


def _extract_pairs(text: str, index_aliases: dict[str, int], current_drug_name: str) -> list[dict[str, str]]:
    extracted: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    candidates = _entity_candidates(index_aliases, current_drug_name)

    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_lower = sentence.lower()
        if not any(hint in sentence_lower for hint in _INTERACTION_HINTS):
            continue

        # High-confidence phrase matches.
        for pattern in _CONNECTOR_PATTERNS:
            for match in pattern.finditer(sentence):
                left_term = _resolve_entity(match.group(1), candidates)
                right_term = _resolve_entity(match.group(2), candidates)
                if not left_term or not right_term or left_term == right_term:
                    continue
                for left_name in _expand_entity(left_term, current_drug_name, exclude_current=False):
                    for right_name in _expand_entity(right_term, current_drug_name, exclude_current=False):
                        if not left_name or not right_name or left_name == right_name:
                            continue
                        left, right = sorted([left_name, right_name])
                        key = (left, right, sentence)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        extracted.append(
                            {
                                "drug1": left,
                                "drug2": right,
                                "text": sentence,
                                "confidence": "high",
                                "reason": f"pattern:{pattern.pattern[:48]}",
                            }
                        )

        # Fallback: if the index drug and one additional known entity are present.
        if current_drug_name and re.search(rf"\b{re.escape(current_drug_name)}\b", sentence_lower):
            found = [entity for entity in _find_entities(sentence_lower, candidates) if entity != current_drug_name]
            for entity in found:
                for mapped in _expand_entity(entity, current_drug_name):
                    left, right = sorted([current_drug_name, mapped])
                    key = (left, right, sentence)
                    if left == right or key in seen_keys:
                        continue
                    seen_keys.add(key)
                    extracted.append(
                        {
                            "drug1": left,
                            "drug2": right,
                            "text": sentence,
                            "confidence": "medium",
                            "reason": f"co-mention:{entity}",
                        }
                    )

    return extracted


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
    stats = {"total_fetched": 0, "parsed": 0, "inserted": 0, "failed": 0, "skipped": 0}

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
            openfda = item.get("openfda", {}) or {}
            set_id = _safe_list(openfda.get("set_id"))
            source_id = set_id[0] if set_id else "unknown"
            interaction_chunks = _safe_list(item.get("drug_interactions"))
            interaction_text_exists = bool(interaction_chunks and any(chunk.strip() for chunk in interaction_chunks))
            interaction_preview = _preview(interaction_chunks[0]) if interaction_chunks else ""

            logger.info(
                "openfda record source_id=%s interaction_text_exists=%s interaction_preview=%r",
                source_id,
                interaction_text_exists,
                interaction_preview,
            )

            if not aliases:
                stats["failed"] += 1
                logger.info("openfda record source_id=%s action=fail reason=no_aliases", source_id)
                continue

            primary_name = aliases[0]
            brand = _safe_list(openfda.get("brand_name"))
            drug = get_or_create_drug(db, primary_name, brand[0] if brand else None)
            ensure_alias(db, drug, primary_name)
            for alias in aliases[1:]:
                ensure_alias(db, drug, alias)

            for alias in aliases:
                known_aliases.setdefault(alias, drug.id)

            sections = _split_sections(item)

            for section_name, raw_text in sections:
                parsed_pairs = _extract_pairs(raw_text, known_aliases, primary_name)
                parsed_payload = []
                section_preview = _preview(raw_text)

                logger.info(
                    "openfda section source_id=%s section=%s pair_extracted=%s preview=%r",
                    source_id,
                    section_name,
                    bool(parsed_pairs),
                    section_preview,
                )

                for parsed in parsed_pairs:
                    left_name = parsed["drug1"]
                    right_name = parsed["drug2"]
                    sentence = parsed["text"]
                    confidence = parsed["confidence"]

                    severity = _severity_from_text(sentence)
                    action = "unknown"
                    reason = ""
                    stats["parsed"] += 1

                    if confidence != "high":
                        stats["skipped"] += 1
                        action = "skip"
                        reason = "low_confidence"
                    else:
                        left_drug = get_or_create_drug(db, left_name)
                        right_drug = get_or_create_drug(db, right_name)
                        ensure_alias(db, left_drug, left_name)
                        ensure_alias(db, right_drug, right_name)
                        pair = ordered_pair(left_drug.id, right_drug.id)
                        if pair in known_pairs:
                            stats["skipped"] += 1
                            action = "skip"
                            reason = "existing_pair"
                        else:
                            inserted = _upsert_interaction(db, left_drug.id, right_drug.id, severity, sentence)
                            if inserted:
                                stats["inserted"] += 1
                                known_pairs.add(pair)
                                action = "insert"
                                reason = "inserted"
                            else:
                                stats["skipped"] += 1
                                action = "skip"
                                reason = "upsert_conflict"

                    logger.info(
                        "openfda pair source_id=%s extracted=%s drug_a=%s drug_b=%s severity=%s action=%s reason=%s confidence=%s",
                        source_id,
                        True,
                        left_name,
                        right_name,
                        severity,
                        action,
                        reason,
                        confidence,
                    )

                    if action != "insert":
                        continue

                    parsed_payload.append(
                        {
                            "drug1": left_name,
                            "drug2": right_name,
                            "severity": severity,
                            "text": sentence,
                            "confidence": confidence,
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
            logger.exception("openfda record source_id=%s action=fail reason=exception", source_id if "source_id" in locals() else "unknown")
            db.rollback()
            continue

    db.commit()
    logger.info(
        "openfda summary total_fetched=%s parsed=%s inserted=%s skipped=%s failed=%s",
        stats["total_fetched"],
        stats["parsed"],
        stats["inserted"],
        stats["skipped"],
        stats["failed"],
    )
    return stats
