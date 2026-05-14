"""DDII interaction text → severity (no DB / SQLAlchemy imports).

The rules here produce one of: ``contraindicated`` / ``major`` / ``moderate`` / ``minor``
from a free-text DrugBank/DDII-style description so risk shown in the UI reflects what
the description actually says (e.g. "may increase the QTc-prolonging activities of …"
becomes ``major`` rather than the generic ``moderate``).
"""

from __future__ import annotations

import re

ALLOWED_SEVERITIES = frozenset({"contraindicated", "major", "moderate", "minor"})


# ---------------------------------------------------------------------------
# Explicit CSV cell parsing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INCREASE_PHRASES = (
    "may increase",
    "can increase",
    "increase the",
    "might increase",
    "can be increased",
    " is increased",
)

_DECREASE_PHRASES = (
    "may decrease",
    "can decrease",
    "decrease the",
    "might decrease",
    "can be decreased",
    " is decreased",
)


def _has_increase(t: str) -> bool:
    return any(p in t for p in _INCREASE_PHRASES)


def _has_decrease(t: str) -> bool:
    return any(p in t for p in _DECREASE_PHRASES)


# Activities whose *increase* is clinically dangerous (→ major).
_HIGH_RISK_ACTIVITIES = (
    "qtc-prolonging",
    "qt-prolonging",
    "qt prolong",
    "qtc prolong",
    "serotonergic",
    "anticoagulant",
    "hypoglycemic",
    "hypokalemic",
    "arrhythmogenic",
    "atrioventricular blocking",
    "av block",
    "cardiotoxic",
    "nephrotoxic",
    "hepatotoxic",
    "neurotoxic",
    "ototoxic",
    "myelosuppressive",
    "immunosuppressive",
    "respiratory depressant",
    "thrombogenic",
    "vasopressor",
)

# Severe clinical outcomes — if mentioned at all (and not in a "decrease/reduce"
# protective phrasing) push severity to major.
_SEVERE_OUTCOMES = (
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
    "ventricular tachycardia",
    "stevens-johnson",
    "toxic epidermal necrolysis",
    "serotonin syndrome",
    "myelosuppression",
    "agranulocytosis",
    "pancytopenia",
    "rhabdomyolysis",
    "oversedation",
    "profound sedation",
    "hepatic failure",
    "renal failure",
    "acute liver failure",
    "lactic acidosis",
    "neuroleptic malignant syndrome",
)


def _reduces_dangerous_effect(t: str) -> bool:
    """DrugBank-style lines where drug1 *reduces* an adverse activity of drug2.

    Used to avoid promoting "may decrease the cardiotoxic activities of …" to ``major``
    just because the word ``cardiotoxic`` appears.
    """
    return (
        "may decrease the" in t
        or "can decrease the" in t
        or ("may decrease " in t and " activities" in t)
        or ("can decrease " in t and " activities" in t)
    )


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_ddii_interaction_severity(description: str) -> str:
    """Conservative severity from free-text interaction lines (DrugBank / DDII style).

    Used when the CSV has no valid ``Risk Severity`` cell, or when rebuilding that column.
    """
    t = (description or "").lower()
    if not t.strip():
        return "moderate"

    # 1. Explicit "no clinical significance" wording → minor
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

    # 2. Hard contraindications
    if (
        "contraindicat" in t
        or "should not be used" in t
        or "should not be co-administered" in t
        or "must not" in t
        or "is not recommended" in t and "combination" in t
    ):
        return "contraindicated"

    # 3. Explicit "major" framings
    if "major" in t and "risk" in t:
        return "major"
    if any(x in t for x in ("significantly", "substantially")) and "risk" in t:
        return "major"
    if "hypertensive crisis" in t or "hypertensive emergency" in t:
        return "major"

    reduces = _reduces_dangerous_effect(t)
    has_inc = _has_increase(t)
    has_dec = _has_decrease(t)

    # 4. Protective: "may decrease the <toxic/sedative/CNS depressant> activities of …"
    #    The combination *reduces* the second drug's adverse effect → minor.
    if reduces:
        protective_targets = (
            "cardiotoxic",
            "nephrotoxic",
            "hepatotoxic",
            "neurotoxic",
            "ototoxic",
            "myelosuppressive",
            "immunosuppressive",
            "sedative",
            "central nervous system depressant",
            "cns depressant",
            "respiratory depressant",
            "qtc-prolonging",
            "qt-prolonging",
            "serotonergic",
            "anticoagulant",
            "hypoglycemic",
            "hypokalemic",
            "arrhythmogenic",
            "atrioventricular blocking",
        )
        if any(p in t for p in protective_targets):
            return "minor"

    # 5. Severe outcomes mentioned anywhere (and not in a protective phrasing).
    if not reduces and any(m in t for m in _SEVERE_OUTCOMES):
        return "major"

    # 6. CNS depressant additive effect
    if "cns depress" in t or "central nervous system depressant" in t:
        if has_inc:
            return "major"

    # 7. Increase of a high-risk activity → major
    if has_inc and any(act in t for act in _HIGH_RISK_ACTIVITIES):
        return "major"

    # 8. Decrease of an antidote / protective therapy → escalate
    #    "may decrease the antihypertensive activities" can risk uncontrolled BP, but
    #    DrugBank treats this as moderate; keep as moderate to avoid over-flagging.

    # 9. "Risk or severity of adverse effects can be increased" → moderate baseline
    if "risk or severity of adverse effects can be increased" in t:
        return "moderate"

    # 10. Generic PK / activity shifts → moderate
    if any(
        x in t
        for x in (
            "moderate",
            "may increase",
            "may decrease",
            "can increase",
            "can decrease",
            "can be increased",
            "can be decreased",
            "might increase",
            "might decrease",
            "absorption",
            "metabolism",
            "serum concentration",
            "therapeutic efficacy",
            "excretion rate",
            "plasma concentration",
            "bioavailability",
        )
    ):
        return "moderate"

    # 11. Explicit "minor" / "unlikely" wording
    if "minor" in t or "unlikely" in t:
        return "minor"

    # Default fallback
    return "moderate"
