"""Ollama integration for personalized counseling generation.

This service only summarizes deterministic interaction facts and patient context.
It does NOT detect interactions or assign severity.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
MAX_JSON_RETRIES = 2

REQUIRED_KEYS = [
    "interaction_summary",
    "patient_specific_risk",
    "top_counseling_points",
    "monitoring_points",
    "red_flags",
    "when_to_contact_clinician",
    "evidence_used",
]

logger = logging.getLogger(__name__)


def get_ollama_config() -> dict[str, str]:
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
    }


def check_ollama_status() -> dict[str, Any]:
    config = get_ollama_config()
    url = f"{config['base_url']}/api/tags"

    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        model_names = [m.get("name", "") for m in payload.get("models", [])]
        configured_model = config["model"]
        available = any(configured_model in name for name in model_names)
        return {
            "ollama_reachable": True,
            "configured_model": configured_model,
            "model_available": available,
            "base_url": config["base_url"],
        }
    except Exception as exc:
        return {
            "ollama_reachable": False,
            "configured_model": config["model"],
            "model_available": False,
            "base_url": config["base_url"],
            "error": str(exc),
        }


def _build_prompt(interactions: list[dict], patient_context: dict[str, Any]) -> str:
    return (
        "You are generating pharmacy counseling text from precomputed interaction facts. "
        "Do not detect new interactions. Do not change severity labels. "
        "Personalize wording to the patient context (age, allergies, notes) when relevant, "
        "but do not invent clinical facts beyond the interaction list. "
        "Use ONLY the facts given. Return strict JSON with keys: "
        f"{', '.join(REQUIRED_KEYS)}.\n\n"
        f"Patient context JSON:\n{json.dumps(patient_context, ensure_ascii=False)}\n\n"
        f"Deterministic interaction facts JSON:\n{json.dumps(interactions, ensure_ascii=False)}\n"
    )


def _coerce_json(response_text: str) -> dict[str, Any]:
    """Parse first JSON object from model output (handles prose, markdown fences)."""
    text = (response_text or "").strip()
    if not text:
        raise ValueError("Empty Ollama response")

    # Strip common markdown fences and take the fenced block if present.
    if "```" in text:
        segments = text.split("```")
        for segment in segments:
            seg = segment.strip()
            if not seg:
                continue
            if seg.lower().startswith("json"):
                seg = seg[4:].lstrip().strip()
            if seg.startswith("{"):
                text = seg
                break

    start = text.find("{")
    if start == -1:
        logger.debug("Ollama response had no JSON object start: %r", text[:400])
        raise ValueError("No JSON object found in Ollama response")

    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        logger.debug("Ollama JSON decode failed: %s text=%r", exc, text[:400])
        raise ValueError(f"Invalid JSON in Ollama response: {exc}") from exc

    if not isinstance(obj, dict):
        raise ValueError("Ollama JSON root must be an object")
    return obj


def _validate_output(payload: dict[str, Any], interactions: list[dict]) -> dict[str, Any]:
    for key in REQUIRED_KEYS:
        payload.setdefault(key, [] if key not in {"interaction_summary", "patient_specific_risk"} else "")

    # Normalize list-shaped fields.
    for key in REQUIRED_KEYS:
        if key in {"interaction_summary", "patient_specific_risk"}:
            payload[key] = str(payload.get(key, ""))
        elif not isinstance(payload.get(key), list):
            payload[key] = [str(payload.get(key))] if payload.get(key) else []

    if not payload["evidence_used"]:
        payload["evidence_used"] = [
            f"{row.get('drug1')} + {row.get('drug2')} ({row.get('severity')})"
            for row in interactions
        ]

    payload["disclaimer"] = "Educational prototype only. Not for diagnosis or prescribing."
    return payload


def generate_personalized_counseling(
    interactions: list[dict],
    patient_context: dict[str, Any],
) -> dict[str, Any]:
    config = get_ollama_config()
    url = f"{config['base_url']}/api/generate"
    prompt = _build_prompt(interactions, patient_context)

    last_error = "unknown"
    for _ in range(MAX_JSON_RETRIES + 1):
        try:
            response = httpx.post(
                url,
                json={
                    "model": config["model"],
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            raw = payload.get("response", "")
            parsed = _coerce_json(raw)
            return _validate_output(parsed, interactions)
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Ollama generate attempt failed: %s", last_error)
            continue

    raise RuntimeError(f"Ollama generation failed: {last_error}")
