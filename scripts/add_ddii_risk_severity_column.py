#!/usr/bin/env python3
"""
Rewrite a Drug 1 / Drug 2 / Interaction Description CSV to include ``Risk Severity``.

Uses the same rules as ``services.ddi_severity_classifier.classify_ddii_interaction_severity``.
Run from repo root::

    PYTHONPATH=fastapi python3 scripts/add_ddii_risk_severity_column.py fastapi/data/db_drug_interactions.csv
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "fastapi"))
    from services.ddi_severity_classifier import classify_ddii_interaction_severity  # noqa: E402

    ap = argparse.ArgumentParser(description="Add Risk Severity column to DDII CSV")
    ap.add_argument("csv_path", type=Path, help="Path to db_drug_interactions.csv")
    args = ap.parse_args()
    path: Path = args.csv_path.resolve()
    if not path.is_file():
        raise SystemExit(f"not found: {path}")

    out_fields = ["Drug 1", "Drug 2", "Interaction Description", "Risk Severity"]
    tmp = path.with_suffix(path.suffix + ".tmp")

    with path.open(encoding="utf-8-sig", newline="") as fin, tmp.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=out_fields, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            desc = (row.get("Interaction Description") or "").strip()
            sev = classify_ddii_interaction_severity(desc)
            writer.writerow(
                {
                    "Drug 1": (row.get("Drug 1") or "").strip(),
                    "Drug 2": (row.get("Drug 2") or "").strip(),
                    "Interaction Description": desc,
                    "Risk Severity": sev,
                }
            )

    shutil.move(str(tmp), str(path))
    print(f"updated {path} with column {out_fields[-1]!r}")


if __name__ == "__main__":
    main()
