#!/usr/bin/env python3
"""Convert an openFDA Human Drug Label JSON file into a CSV of interaction-style rows (optional offline use)."""

from __future__ import annotations

import csv
import json
import re
import string
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

EXPECTED_COLUMNS = [
    "drug_a",
    "drug_b",
    "severity",
    "clinical_effect",
    "mechanism",
    "monitoring",
    "source",
]

TEXT_FIELDS = ("drug_interactions", "warnings", "contraindications")

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "with",
    "without",
    "use",
    "concurrent",
    "drug",
    "drugs",
    "patients",
    "patient",
    "therapy",
    "treatment",
    "administered",
    "this",
    "medicine",
    "is",
    "when",
    "reported",
    "reactions",
    "serious",
    "contraindicated",
}
NON_DRUG_TOKENS = {"and", "with", "may", "increase", "increases"}
COMMON_ENGLISH_WORDS = {
    "bleeding",
    "risk",
    "level",
    "levels",
    "effect",
    "effects",
    "reaction",
    "reactions",
    "serious",
    "common",
    "severe",
    "high",
    "low",
    "inr",
    "closely",
    "medicine",
}
DRUG_CLASS_TERMS = {"nsaids", "opioids", "benzodiazepines"}

PAIR_PATTERNS = [
    re.compile(r"\bconcurrent use of\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\s+and\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9\- ]{1,60}?)\s+and\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9\- ]{1,60}?)\s+with\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9\- ]{1,60}?)\s+increases\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z][A-Za-z0-9\- ]{1,60}?)\s+may increase\s+([A-Za-z][A-Za-z0-9\- ]{1,60}?)\b", re.IGNORECASE),
]


def normalize_name(name: str) -> str:
    cleaned = name.lower().strip()
    cleaned = cleaned.strip(string.punctuation + " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    tokens = cleaned.split()
    while tokens and tokens[0] in STOPWORDS:
        tokens.pop(0)
    while tokens and tokens[-1] in STOPWORDS:
        tokens.pop()
    if len(tokens) > 3:
        tokens = tokens[-3:]
    cleaned = " ".join(tokens)
    return cleaned


def severity_from_text(text: str) -> str:
    lowered = text.lower()
    if "contraindicated" in lowered:
        return "contraindicated"
    if "life-threatening" in lowered or "serious" in lowered:
        return "major"
    if "monitor" in lowered:
        return "moderate"
    return "unknown"


def extract_mechanism(text: str) -> str:
    match = re.search(r"\b(?:via|through|by)\s+([^.;\n]{5,180})", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def extract_monitoring(text: str) -> str:
    match = re.search(r"\b(monitor[^.;\n]{0,180})", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def likely_drug_name(name: str) -> bool:
    tokens = [t for t in re.split(r"\s+", name) if t]
    if not tokens:
        return False
    if len(tokens) > 5:
        return False
    if any(token.lower() in NON_DRUG_TOKENS for token in tokens):
        return False
    if any(token.lower() in COMMON_ENGLISH_WORDS for token in tokens):
        return False
    if all(token.lower() in STOPWORDS for token in tokens):
        return False
    alpha_chars = sum(ch.isalpha() for ch in name)
    return alpha_chars >= 2


def summarize_clinical_effect(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    sentence = re.split(r"(?<=[.;])\s+", cleaned, maxsplit=1)[0]
    return sentence[:220].rstrip(" ;.")


def extract_pairs(text: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for pattern in PAIR_PATTERNS:
        for match in pattern.finditer(text):
            left = normalize_name(match.group(1))
            right = normalize_name(match.group(2))
            if not left or not right:
                continue
            if left == right:
                continue
            if not likely_drug_name(left) or not likely_drug_name(right):
                continue
            pairs.append((left, right))
    return pairs


def iter_text_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Sequence):
        for item in value:
            if isinstance(item, str):
                yield item


def load_results(input_path: Path) -> List[dict]:
    try:
        raw = input_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"input file not found: {input_path}")
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        raise ValueError("unexpected JSON structure (expected object at top level)")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("unexpected JSON structure (expected 'results' array)")

    return [item for item in results if isinstance(item, dict)]


def resolve_input_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".json":
            raise SystemExit("Error: input file must be a .json file")
        return [input_path]

    if input_path.is_dir():
        files = sorted(path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() == ".json")
        if not files:
            raise SystemExit(f"Error: no .json files found in directory: {input_path}")
        return files

    raise SystemExit(f"Error: input path not found: {input_path}")


def convert(input_path: Path, output_path: Path) -> Tuple[int, int, int, int]:
    json_files = resolve_input_files(input_path)
    rows: List[dict] = []
    skipped = 0
    seen_rows = set()
    warned_class_pairs = set()
    total_records = 0
    files_processed = 0

    for json_file in json_files:
        try:
            results = load_results(json_file)
        except ValueError as exc:
            print(f"Warning: skipping file '{json_file}': {exc}")
            continue
        files_processed += 1

        for record in results:
            total_records += 1
            snippets: List[str] = []
            for field in TEXT_FIELDS:
                snippets.extend(iter_text_values(record.get(field)))

            if not snippets:
                skipped += 1
                continue

            record_had_row = False
            for snippet in snippets:
                for pair in extract_pairs(snippet):
                    if pair[0] in DRUG_CLASS_TERMS or pair[1] in DRUG_CLASS_TERMS:
                        class_pair = (pair[0], pair[1])
                        if class_pair not in warned_class_pairs:
                            print(
                                f"Warning: extracted pair may contain a drug class, not a specific drug: "
                                f"{pair[0]} / {pair[1]}"
                            )
                            warned_class_pairs.add(class_pair)

                    row = {
                        "drug_a": pair[0],
                        "drug_b": pair[1],
                        "severity": severity_from_text(snippet),
                        "clinical_effect": summarize_clinical_effect(snippet),
                        "mechanism": extract_mechanism(snippet),
                        "monitoring": extract_monitoring(snippet),
                        "source": "openFDA",
                    }
                    row_key = tuple(row[column] for column in EXPECTED_COLUMNS)
                    if row_key in seen_rows:
                        continue
                    seen_rows.add(row_key)
                    rows.append(row)
                    record_had_row = True

            if not record_had_row:
                skipped += 1

    try:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise SystemExit(f"Error: cannot write output CSV: {exc}")

    if files_processed == 0:
        raise SystemExit("Error: no valid JSON files were processed")

    return files_processed, total_records, len(rows), skipped


def main(argv: Sequence[str]) -> int:
    if len(argv) != 3:
        print("Usage: python scripts/openfda_json_to_csv.py <input_path> <output.csv>")
        return 1

    input_path = Path(argv[1])
    output_path = Path(argv[2])

    files_processed, total_records, rows_created, rows_skipped = convert(input_path, output_path)
    print(f"Files processed: {files_processed}")
    print(f"Total records inspected: {total_records}")
    print(f"Total rows written: {rows_created}")
    print(f"Rows skipped: {rows_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
