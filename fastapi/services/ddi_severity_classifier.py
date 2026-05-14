"""DDII interaction text → severity (no DB / SQLAlchemy imports)."""

from __future__ import annotations

import re

ALLOWED_SEVERITIES = frozenset({"contraindicated", "major", "moderate", "minor"})


def parse_explicit_ddii_severity(raw: str | None) -> str | None:
    """Map a CSV cell to ``contraindicated`` / ``major`` / ``moderate`` / ``minor`` if unambiguous."""
    if not raw:
        return None
    t = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if not t:
        return None
    if t in ALLOWED_SEVERITIES:
        return t
    aliases = {
        "very high": "contraindicated",
        "very_high": "contraindicated",
        "extreme": "contraindicated",
        "high": "major",
        "medium": "moderate",
        "low": "minor",
        "none": "minor",
        "minimal": "minor",
    }
    return aliases.get(t)


def _reduces_toxicity_or_effect(t: str) -> bool:
    """DrugBank-style lines where drug1 *reduces* an adverse activity of drug2."""
    return (
        "may decrease the" in t
        or "can decrease the" in t
        or ("may decrease " in t and " activities" in t)
        or ("can decrease " in t and " activities" in t)
    )


def classify_ddii_interaction_severity(description: str) -> str:
    """
    Conservative severity from free-text interaction lines (DrugBank / DDII style).

    Used when the CSV has no valid ``Risk Severity`` cell, or when rebuilding that column.
    """
    t = (description or "").lower()

    if any(
        p in t
        for p in (
            "no clinically significant",
            "unlikely to be clinically significant",
            "not expected to be clinically significant",
            "clinically insignificant",
            "negligible effect",
        )
    ):
        if "life-threatening" not in t and "fatal" not in t:
            return "minor"

    if "contraindicat" in t or "should not be used" in t or "must not" in t:
        return "contraindicated"

    if any(x in t for x in ("significantly", "substantially")) and "risk" in t:
        return "major"
    if "major" in t and "risk" in t:
        return "major"

    if not _reduces_toxicity_or_effect(t):
        if any(
            m in t
            for m in (
                "life-threatening",
                "fatal",
                " death",
                " coma",
                "anaphylaxis",
                "bleeding",
                "hemorrhage",
                "hemorrhagic",
                "respiratory depression",
                "respiratory suppress",
                "torsade",
                "ventricular fibrillation",
                "stevens-johnson",
                "toxic epidermal necrolysis",
                "serotonin syndrome",
                "myelosuppression",
                "agranulocytosis",
                "pancytopenia",
                "oversedation",
                "profound sedation",
                "hepatic failure",
                "renal failure",
                "acute liver failure",
            )
        ):
            return "major"
        if "cns depress" in t and (
            "increase" in t or "increased" in t or "can be increased" in t
        ):
            return "major"
        inc = ("may increase" in t) or ("can increase" in t) or ("increase the" in t)
        if inc and any(
            x in t for x in ("cardiotoxic", "nephrotoxic", "hepatotoxic", "neurotoxic", "ototoxic")
        ):
            return "major"
        if "immunosuppress" in t and inc:
            return "major"

    if "hypertensive crisis" in t or "hypertensive emergency" in t:
        return "major"

    if "the risk or severity of adverse effects can be increased" in t:
        return "moderate"

    if any(
        x in t
        for x in (
            "moderate",
            "may increase",
            "may decrease",
            "can increase",
            "can decrease",
            "can be increased",
            "might increase",
            "might decrease",
        )
    ):
        return "moderate"

    if "minor" in t or "unlikely" in t:
        return "minor"
    return "moderate"
