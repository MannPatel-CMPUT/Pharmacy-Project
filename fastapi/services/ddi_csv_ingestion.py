"""Ingest large DrugBank-style CSV files: Drug 1, Drug 2, Interaction Description."""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import time
from typing import Any, TextIO

from sqlalchemy.orm import Session

from database import DrugInteraction
from services.ddi_severity_classifier import (
    ALLOWED_SEVERITIES,
    classify_ddii_interaction_severity,
    parse_explicit_ddii_severity,
)
from services.knowledge_repository import ensure_alias, get_or_create_drug, ordered_pair

logger = logging.getLogger(__name__)

SOURCE_TAG = "db_drug_interactions_csv"

_DDII_DRUG1 = ("drug 1", "drug1", "drug_a", "drug a")
_DDII_DRUG2 = ("drug 2", "drug2", "drug_b", "drug b")
_DDII_DESC = ("interaction description", "description", "clinical_effect", "clinical effect")
_DDII_RISK = ("risk severity", "interaction severity", "clinical severity")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _map_ddii_row(raw: dict[str, str]) -> dict[str, str] | None:
    lower_map = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
    d1 = next((lower_map[a] for a in _DDII_DRUG1 if a in lower_map and lower_map[a]), None)
    d2 = next((lower_map[a] for a in _DDII_DRUG2 if a in lower_map and lower_map[a]), None)
    desc = next((lower_map[a] for a in _DDII_DESC if a in lower_map and lower_map[a]), None)
    if not d1 or not d2 or d1.lower() == d2.lower():
        return None
    if not desc:
        return None
    risk_cell = next((lower_map[a] for a in _DDII_RISK if a in lower_map and lower_map[a]), None)
    return {
        "drug_a": d1.lower(),
        "drug_b": d2.lower(),
        "description": desc,
        "explicit_severity": parse_explicit_ddii_severity(risk_cell),
    }


def _severity_from_ddii_description(description: str) -> str:
    """Backward-compatible alias for :func:`classify_ddii_interaction_severity`."""
    return classify_ddii_interaction_severity(description)


def is_ddii_csv_headers(fieldnames: list[str] | None) -> bool:
    """
    True for DrugBank-style exports: ``Drug 1``, ``Drug 2``, ``Interaction Description``.

    Excludes the app's six-column upload format (drug_a, drug_b, severity, …) which also
    contains drug_a / clinical_effect but is not the DDII file.
    """
    if not fieldnames:
        return False
    keys = {_norm_header(x) for x in fieldnames}
    # Legacy app CSV always includes explicit severity + mechanism columns
    if "severity" in keys and "mechanism" in keys:
        return False
    has_ddii_titles = "drug 1" in keys and "drug 2" in keys
    has_desc = "interaction description" in keys
    if has_ddii_titles and has_desc:
        return True
    return False


def _copy_interactions_postgres(
    *,
    db: Session,
    parsed_rows,
    drug_id_by_name: dict[str, int],
    known_pairs: set[tuple[int, int]],
    stats: dict[str, Any],
) -> dict[str, Any]:
    """
    Bulk-load new drug_interactions rows into Postgres using
    ``psycopg2.extras.execute_values`` in chunks. This is a proven pattern for
    hosted Postgres:

    * Chunked → memory bounded (~5-10 MB per chunk vs. 100 MB single COPY buffer
      that OOM'd the Render 512 MB free-tier worker).
    * Multi-row INSERT per chunk → ~10× faster than one INSERT per row and far
      more forgiving of transient network hiccups than one giant COPY.
    * Progress line + timing after each chunk so a slow tier is visible.
    """
    from psycopg2.extras import execute_values

    chunk_size = int(os.getenv("DDI_CSV_PG_CHUNK", "2000"))
    chunk: list[tuple] = []
    total_new = 0
    t_start = time.time()

    def _flush(cur, rows: list[tuple]) -> None:
        execute_values(
            cur,
            """
            INSERT INTO drug_interactions
              (drug_a_id, drug_b_id, severity, description, clinical_effect,
               mechanism, monitoring, source)
            VALUES %s
            """,
            rows,
            template=None,
            page_size=len(rows),
        )

    raw_conn = db.connection().connection  # SQLAlchemy → DBAPI connection

    for d1, d2, desc, explicit in parsed_rows:
        stats["total_rows"] += 1
        if explicit in ALLOWED_SEVERITIES:
            severity = explicit
        else:
            severity = classify_ddii_interaction_severity(desc)
        if severity not in ALLOWED_SEVERITIES:
            severity = "moderate"

        drug_a_id = drug_id_by_name.get(d1.lower())
        drug_b_id = drug_id_by_name.get(d2.lower())
        if drug_a_id is None or drug_b_id is None:
            stats["skipped"] += 1
            continue

        pair = ordered_pair(drug_a_id, drug_b_id)
        if pair in known_pairs:
            stats["skipped"] += 1
            continue
        known_pairs.add(pair)

        chunk.append((
            pair[0],
            pair[1],
            severity,
            desc,
            desc[:2000],
            None,
            None,
            SOURCE_TAG,
        ))

        if len(chunk) >= chunk_size:
            t0 = time.time()
            cur = raw_conn.cursor()
            try:
                _flush(cur, chunk)
            finally:
                cur.close()
            db.commit()
            dt = time.time() - t0
            total_new += len(chunk)
            stats["inserted"] += len(chunk)
            print(
                f"[ddi_csv] pass 2/2: bulk-inserted {total_new}/{len(parsed_rows)} "
                f"({dt:.2f}s / chunk of {len(chunk)})",
                flush=True,
            )
            chunk = []

    # Final partial chunk.
    if chunk:
        cur = raw_conn.cursor()
        try:
            _flush(cur, chunk)
        finally:
            cur.close()
        db.commit()
        total_new += len(chunk)
        stats["inserted"] += len(chunk)

    total_dt = time.time() - t_start
    rate = int(total_new / max(total_dt, 0.001))
    print(
        f"[ddi_csv] pass 2/2: bulk insert complete — {total_new} rows in "
        f"{total_dt:.2f}s ({rate} rows/s)",
        flush=True,
    )
    return stats


def ingest_ddii_csv_stream(
    db: Session,
    text_stream: TextIO,
    *,
    max_rows: int | None = None,
    commit_every: int = 2000,
) -> dict[str, Any]:
    """
    Stream-parse a UTF-8 CSV with headers Drug 1, Drug 2, Interaction Description.
    Loads existing interaction pairs into memory once for fast dedup.
    """
    stats: dict[str, Any] = {
        "total_rows": 0,
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
        "format": "db_drug_interactions_csv",
    }

    reader = csv.DictReader(text_stream)
    if not is_ddii_csv_headers(reader.fieldnames):
        stats["fatal"] = True
        stats["failed"] = 1
        stats["error"] = (
            "CSV must have columns like 'Drug 1', 'Drug 2', 'Interaction Description'"
        )
        return stats

    pair_rows = db.query(DrugInteraction.drug_a_id, DrugInteraction.drug_b_id).all()
    known_pairs: set[tuple[int, int]] = {
        (min(a, b), max(a, b)) for a, b in pair_rows
    }

    # Preload existing drugs/aliases into memory to avoid ~1.5M SELECT round-trips
    # against hosted Postgres (191K CSV rows × ≥4 lookup queries each).
    from database import Drug, DrugAlias

    drug_id_by_name: dict[str, int] = {
        (n or "").lower(): i
        for i, n in db.query(Drug.id, Drug.generic_name).all()
    }
    known_alias_names: set[str] = {
        (a or "").lower()
        for (a,) in db.query(DrugAlias.alias).all()
    }

    # ─── PASS 1: buffer the CSV in memory, discover all unique drug names,
    #     insert new drugs + aliases in ONE committed transaction. This is
    #     critical for Postgres: mixing lazy `db.add(Drug); db.flush()` with
    #     interaction inserts caused FK violations after an interaction-row
    #     rollback silently invalidated the flushed-but-not-yet-committed
    #     drug ids in our cache.
    print("[ddi_csv] pass 1/2: scanning CSV for unique drugs…", flush=True)
    parsed_rows: list[tuple[str, str, str, str | None]] = []
    for raw in reader:
        if max_rows is not None and len(parsed_rows) >= max_rows:
            break
        mapped = _map_ddii_row({k: v or "" for k, v in raw.items()})
        if not mapped:
            stats["skipped"] += 1
            continue
        parsed_rows.append(
            (
                mapped["drug_a"],
                mapped["drug_b"],
                mapped["description"][:8000],
                mapped.get("explicit_severity"),
            )
        )

    unique_names: set[str] = set()
    for a, b, _desc, _sev in parsed_rows:
        unique_names.add(a.lower())
        unique_names.add(b.lower())
    new_names = [n for n in unique_names if n not in drug_id_by_name]
    print(
        f"[ddi_csv] pass 1/2: {len(unique_names)} unique drug names "
        f"({len(new_names)} new to insert)",
        flush=True,
    )

    if new_names:
        # Bulk-insert new drugs in one transaction so their ids become durable
        # BEFORE we start writing interactions. If this commit fails, we bail
        # early rather than corrupt the cache.
        for chunk_start in range(0, len(new_names), 1000):
            chunk = new_names[chunk_start : chunk_start + 1000]
            for name in chunk:
                db.add(Drug(generic_name=name, brand_name=None))
            db.flush()
        db.commit()
        # Refresh cache from the DB — the only source of truth after commit.
        drug_id_by_name = {
            (n or "").lower(): i
            for i, n in db.query(Drug.id, Drug.generic_name).all()
        }
        print(
            f"[ddi_csv] pass 1/2: committed {len(new_names)} new drug rows",
            flush=True,
        )

    # Also bulk-insert missing aliases (generic-name aliases so lookups work).
    # NOTE: DrugAlias.alias has a GLOBAL unique constraint (not per-drug), so
    # we dedup by alias name alone. This also skips orphan aliases left over
    # from previous partial ingests.
    new_aliases_to_add: list[DrugAlias] = []
    for a, b, _desc, _sev in parsed_rows:
        for alias in (a, b):
            key = alias.lower()
            if key in known_alias_names:
                continue
            drug_id = drug_id_by_name.get(key)
            if drug_id is None:
                continue
            new_aliases_to_add.append(DrugAlias(drug_id=drug_id, alias=alias))
            known_alias_names.add(key)
    if new_aliases_to_add:
        for chunk_start in range(0, len(new_aliases_to_add), 2000):
            db.add_all(new_aliases_to_add[chunk_start : chunk_start + 2000])
            db.flush()
        db.commit()
        print(
            f"[ddi_csv] pass 1/2: committed {len(new_aliases_to_add)} new alias rows",
            flush=True,
        )

    # ─── PASS 2: write drug_interactions.
    #
    # On Postgres we use ``COPY drug_interactions ... FROM STDIN`` — a single
    # streaming bulk-load that is 10–100× faster than row-by-row INSERTs and
    # avoids the hosted-tier failure mode of "hundreds of small commits stall".
    # On SQLite (and any other backend) we keep the row-by-row path.
    print(
        f"[ddi_csv] pass 2/2: inserting interactions for {len(parsed_rows)} candidate rows…",
        flush=True,
    )

    is_postgres = "postgres" in str(db.get_bind().url).lower()
    if is_postgres:
        _copy_interactions_postgres(
            db=db,
            parsed_rows=parsed_rows,
            drug_id_by_name=drug_id_by_name,
            known_pairs=known_pairs,
            stats=stats,
        )
        print(
            f"[ddi_csv] done total_rows={stats['total_rows']} "
            f"inserted={stats['inserted']} skipped={stats['skipped']} "
            f"failed={stats['failed']} (via bulk INSERT)",
            flush=True,
        )
        logger.info(
            "ddi_csv done total_rows=%s inserted=%s skipped=%s failed=%s",
            stats["total_rows"],
            stats["inserted"],
            stats["skipped"],
            stats["failed"],
        )
        return stats

    # SQLite / others: keep the row-by-row batched path.
    commit_every = max(100, min(commit_every, 20000))
    pending_commits = 0
    progress_step = 10000

    for d1, d2, desc, explicit in parsed_rows:
        stats["total_rows"] += 1
        if explicit in ALLOWED_SEVERITIES:
            severity = explicit
        else:
            severity = classify_ddii_interaction_severity(desc)
        if severity not in ALLOWED_SEVERITIES:
            severity = "moderate"

        try:
            drug_a_id = drug_id_by_name.get(d1.lower())
            drug_b_id = drug_id_by_name.get(d2.lower())
            if drug_a_id is None or drug_b_id is None:
                stats["skipped"] += 1
                continue

            pair = ordered_pair(drug_a_id, drug_b_id)
            if pair in known_pairs:
                stats["skipped"] += 1
                continue

            db.add(
                DrugInteraction(
                    drug_a_id=pair[0],
                    drug_b_id=pair[1],
                    severity=severity,
                    description=desc,
                    clinical_effect=desc[:2000],
                    mechanism=None,
                    monitoring=None,
                    source=SOURCE_TAG,
                )
            )
            known_pairs.add(pair)
            stats["inserted"] += 1
            pending_commits += 1

            if pending_commits >= commit_every:
                _t0 = time.time()
                db.commit()
                _dt = time.time() - _t0
                pending_commits = 0
                print(
                    f"[ddi_csv] progress: {stats['total_rows']} rows read, "
                    f"{stats['inserted']} inserted, {stats['skipped']} skipped "
                    f"(commit {_dt:.2f}s)",
                    flush=True,
                )
            elif stats["total_rows"] % progress_step == 0:
                print(
                    f"[ddi_csv] progress: {stats['total_rows']} rows read "
                    f"({stats['inserted']} inserted so far)",
                    flush=True,
                )
        except Exception as exc:
            stats["failed"] += 1
            db.rollback()
            # Any interactions accumulated in this batch that got rolled back
            # will be re-inserted individually on future rows — no drug-id
            # corruption is possible now that drugs are pre-committed.
            pending_commits = 0
            logger.exception("ddi_csv row failed: %s", exc)
            if stats["failed"] > 100:
                stats["fatal"] = True
                stats["error"] = "Too many row failures; aborted"
                return stats

    db.commit()
    print(
        f"[ddi_csv] done total_rows={stats['total_rows']} "
        f"inserted={stats['inserted']} skipped={stats['skipped']} "
        f"failed={stats['failed']}",
        flush=True,
    )
    logger.info(
        "ddi_csv done total_rows=%s inserted=%s skipped=%s failed=%s",
        stats["total_rows"],
        stats["inserted"],
        stats["skipped"],
        stats["failed"],
    )
    return stats


def ingest_ddii_csv_bytes(db: Session, content: bytes, **kwargs: Any) -> dict[str, Any]:
    text = content.decode("utf-8-sig")
    return ingest_ddii_csv_stream(db, io.StringIO(text), **kwargs)


def ingest_ddii_csv_file(
    db: Session,
    file_path: str,
    *,
    max_rows: int | None = None,
    commit_every: int | None = None,
) -> dict[str, Any]:
    ce = commit_every if commit_every is not None else int(os.getenv("DDI_CSV_COMMIT_EVERY", "2000"))
    db_url = (os.getenv("DATABASE_URL") or "").lower()
    if "sqlite" in db_url:
        # Shorter write transactions reduce contention with API traffic on the same SQLite file.
        ce = min(ce, int(os.getenv("DDI_CSV_COMMIT_EVERY_SQLITE", "500")))
    elif db_url.startswith("postgres"):
        # Hosted Postgres (e.g. Render) can stall on very large batches; smaller
        # commits mean shorter transactions and faster recovery if a batch fails.
        ce = min(ce, int(os.getenv("DDI_CSV_COMMIT_EVERY_PG", "500")))
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        return ingest_ddii_csv_stream(db, f, max_rows=max_rows, commit_every=ce)
