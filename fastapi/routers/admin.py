"""Lightweight admin/observability endpoints (no PII)."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import DdiCsvIngestManifest, DrugInteraction, get_db
from services import auth_service


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_logged_in(request: Request) -> str:
    """Any authenticated pharmacy staff can read admin stats."""
    raw = request.cookies.get(auth_service.COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Login required")
    payload = auth_service.decode_token(raw)
    username = str((payload or {}).get("u") or "") if payload else ""
    if not username:
        raise HTTPException(status_code=401, detail="Login required")
    return username


@router.get("/ddi-stats")
def ddi_stats(
    request: Request,
    db: Session = Depends(get_db),
    _user: str = Depends(_require_logged_in),
):
    """
    Return counts and manifest state for the drug interactions dataset.

    Useful to verify — post-deploy on Postgres — that the ~191K-row CSV plus the
    seed JSON both loaded and to confirm which file fingerprint was ingested.
    """
    total = db.query(func.count(DrugInteraction.id)).scalar() or 0

    by_source_rows = (
        db.query(DrugInteraction.source, func.count(DrugInteraction.id))
        .group_by(DrugInteraction.source)
        .all()
    )
    by_source = {(src or "unknown"): int(cnt) for src, cnt in by_source_rows}

    by_severity_rows = (
        db.query(DrugInteraction.severity, func.count(DrugInteraction.id))
        .group_by(DrugInteraction.severity)
        .all()
    )
    by_severity = {(sev or "unknown"): int(cnt) for sev, cnt in by_severity_rows}

    manifest: Optional[DdiCsvIngestManifest] = db.get(DdiCsvIngestManifest, 1)
    manifest_out = None
    if manifest is not None:
        try:
            stats = (
                json.loads(manifest.last_ingest_stats)
                if manifest.last_ingest_stats
                else None
            )
        except Exception:
            stats = None
        manifest_out = {
            "csv_path": manifest.csv_path,
            "file_size": manifest.file_size,
            "file_mtime": manifest.file_mtime,
            "ingest_complete": bool(manifest.ingest_complete),
            "last_ingest_stats": stats,
            "updated_at": (
                manifest.updated_at.isoformat() if manifest.updated_at else None
            ),
        }

    return {
        "drug_interactions_total": int(total),
        "by_source": by_source,
        "by_severity": by_severity,
        "csv_manifest": manifest_out,
    }
