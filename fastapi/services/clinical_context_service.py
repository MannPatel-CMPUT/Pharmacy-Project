"""Generate allergy and lifestyle warnings from patient context."""

from __future__ import annotations

import re
from typing import Optional

_NKDA_VARIANTS: frozenset[str] = frozenset({
    "nkda", "no known drug allergies", "none", "nka",
    "no allergies", "no known allergies", "nil", "nil known",
})

_ALLERGY_DRUG_FAMILIES: dict[str, list[str]] = {
    "penicillin": ["amoxicillin", "ampicillin", "piperacillin", "nafcillin", "oxacillin", "dicloxacillin", "flucloxacillin"],
    "cephalosporin": ["cephalexin", "cefazolin", "ceftriaxone", "cefdinir", "cefuroxime", "cefpodoxime", "cefixime"],
    "sulfa": ["sulfamethoxazole", "trimethoprim", "sulfadiazine", "sulfasalazine", "sulfacetamide"],
    "fluoroquinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "norfloxacin", "ofloxacin"],
    "tetracycline": ["doxycycline", "minocycline", "tetracycline", "demeclocycline"],
    "nsaid": ["ibuprofen", "naproxen", "aspirin", "diclofenac", "indomethacin", "celecoxib", "meloxicam", "ketorolac"],
    "statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin", "fluvastatin", "pitavastatin"],
    "opioid": ["hydrocodone", "oxycodone", "morphine", "codeine", "tramadol", "fentanyl", "buprenorphine"],
    "benzodiazepine": ["alprazolam", "lorazepam", "diazepam", "clonazepam", "temazepam", "midazolam", "triazolam"],
    "ace inhibitor": ["lisinopril", "enalapril", "ramipril", "captopril", "perindopril", "quinapril", "benazepril"],
    "beta blocker": ["metoprolol", "atenolol", "propranolol", "carvedilol", "bisoprolol", "labetalol", "nebivolol"],
    "anticoagulant": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "heparin"],
}

_LIFESTYLE_RULES: list[dict] = [
    {
        "condition": "smoking",
        "values": ("yes", "former"),
        "keywords": [],
        "warning": "Smoking can affect the metabolism of many medications. This may reduce effectiveness or require dose adjustments — consult your pharmacist.",
    },
    {
        "condition": "alcohol_use",
        "values": ("regular", "occasional"),
        "keywords": [],
        "warning": "Alcohol use may increase the risk of side effects with certain medications, including drowsiness, dizziness, or stomach upset. Ask your pharmacist if alcohol is safe with your current medications.",
    },
    {
        "condition": "alcohol_use",
        "values": ("regular",),
        "keywords": ["warfarin", "metronidazole", "tinidazole", "isoniazid", "acetaminophen", "paracetamol", "ketoconazole"],
        "warning": "Regular alcohol use combined with one or more of your medications may cause serious harm, including increased bleeding risk or liver damage. Avoid alcohol or consult your doctor.",
    },
    {
        "condition": "alcohol_use",
        "values": ("regular", "occasional"),
        "keywords": ["alprazolam", "lorazepam", "diazepam", "clonazepam", "zolpidem", "hydrocodone", "oxycodone", "morphine", "codeine", "tramadol"],
        "warning": "Alcohol combined with sedative or pain medications can cause dangerous over-sedation or breathing problems. Avoid alcohol entirely.",
    },
    {
        "condition": "renal_status",
        "values": ("mild", "moderate", "severe"),
        "keywords": [],
        "warning": "Kidney impairment affects how medications are cleared from the body. Dose adjustments or additional monitoring may be required.",
    },
    {
        "condition": "hepatic_status",
        "values": ("mild", "moderate", "severe"),
        "keywords": [],
        "warning": "Liver impairment affects drug metabolism. Some medications may accumulate and become more toxic. Consult your doctor about safe dosing.",
    },
    {
        "condition": "pregnancy",
        "values": ("yes",),
        "keywords": [],
        "warning": "Some medications are not safe during pregnancy and may harm the baby. Please confirm all current medications are approved for use in pregnancy with your doctor or pharmacist.",
    },
]


def _tokenize(text: Optional[str]) -> list[str]:
    if not text:
        return []
    return [t.strip().lower() for t in re.split(r"[,;\s/]+", text) if t.strip()]


def _is_nkda(allergies: str) -> bool:
    return allergies.strip().lower() in _NKDA_VARIANTS


def build_allergy_warnings(
    allergies: Optional[str],
    medications: Optional[str],
    current_medications: Optional[str],
) -> list[str]:
    if not allergies:
        return []
    if _is_nkda(allergies):
        return []

    allergy_tokens = _tokenize(allergies)
    all_meds_text = " , ".join(filter(None, [medications, current_medications]))
    med_tokens = _tokenize(all_meds_text)

    if not allergy_tokens or not med_tokens:
        return []

    warnings: list[str] = []
    flagged: set[str] = set()

    for allergy in allergy_tokens:
        if allergy in _NKDA_VARIANTS or len(allergy) < 3:
            continue

        for med in med_tokens:
            if len(med) < 3:
                continue
            if allergy in med or med in allergy:
                key = f"direct|{allergy}|{med}"
                if key not in flagged:
                    flagged.add(key)
                    warnings.append(
                        f"⚠ Allergy alert: Patient reports allergy to '{allergy}'. "
                        f"'{med.title()}' may be related to this allergen — verify with prescriber before dispensing."
                    )

        for family, members in _ALLERGY_DRUG_FAMILIES.items():
            if allergy == family or (len(allergy) > 3 and (allergy in family or family in allergy)):
                for member in members:
                    for med in med_tokens:
                        if len(med) < 3:
                            continue
                        if member in med or med in member:
                            key = f"family|{family}|{med}"
                            if key not in flagged:
                                flagged.add(key)
                                warnings.append(
                                    f"⚠ Allergy alert: Patient reports allergy to '{allergy}' ({family} family). "
                                    f"'{med.title()}' may belong to the same drug class — confirm safety with prescriber."
                                )

    return warnings


def build_lifestyle_warnings(
    smoking: Optional[str] = None,
    alcohol_use: Optional[str] = None,
    renal_status: Optional[str] = None,
    hepatic_status: Optional[str] = None,
    pregnancy: Optional[str] = None,
    medications: Optional[str] = None,
    current_medications: Optional[str] = None,
) -> list[str]:
    context: dict[str, str] = {
        "smoking": (smoking or "").strip().lower(),
        "alcohol_use": (alcohol_use or "").strip().lower(),
        "renal_status": (renal_status or "").strip().lower(),
        "hepatic_status": (hepatic_status or "").strip().lower(),
        "pregnancy": (pregnancy or "").strip().lower(),
    }

    all_meds_text = " , ".join(filter(None, [medications, current_medications]))
    med_tokens = _tokenize(all_meds_text)

    warnings: list[str] = []
    seen: set[str] = set()

    for rule in _LIFESTYLE_RULES:
        cond = rule["condition"]
        val = context.get(cond, "")
        if not val or val not in rule["values"]:
            continue

        keywords: list[str] = rule.get("keywords", [])
        if keywords:
            matched = any(
                any(k in m or m in k for m in med_tokens)
                for k in keywords
            )
            if not matched:
                continue

        warning_text: str = rule["warning"]
        if warning_text not in seen:
            seen.add(warning_text)
            warnings.append(warning_text)

    return warnings
