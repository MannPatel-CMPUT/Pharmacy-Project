from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy import event, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import logging

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharmacy.db")

_connect_args: dict = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    # Wait for writers (e.g. background CSV ingest) instead of immediate "database is locked".
    _connect_args["timeout"] = float(os.getenv("SQLITE_LOCK_TIMEOUT", "60"))

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    # Recycle connections every 5 min so hosted Postgres (Render) doesn't hand
    # us a stale connection killed by the server's idle-in-transaction reaper.
    # Ignored for SQLite.
    pool_recycle=int(os.getenv("SQLA_POOL_RECYCLE_SEC", "300")),
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record) -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=60000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
logger = logging.getLogger(__name__)


class Intake(Base):
    __tablename__ = "intakes"

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String, index=True)
    patient_age = Column(Integer, nullable=True)
    patient_gender = Column(String, nullable=True)
    patient_phone = Column(String, nullable=True)
    patient_allergies = Column(Text, nullable=True)
    medications = Column(Text)
    current_medications = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    counseling_points = Column(Text, nullable=True)
    pharmacist_notes = Column(Text, nullable=True)
    drug_interactions = Column(Text, nullable=True)
    status = Column(String, default="new")
    created_by = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    dispensed = Column(String, nullable=True)
    dispensed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    status_history = relationship("StatusHistory", back_populates="intake", cascade="all, delete-orphan")
    counseling_logs = relationship("GeneratedCounselingLog", back_populates="intake", cascade="all, delete-orphan")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(Integer, ForeignKey("intakes.id"), index=True)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    changed_by = Column(String, nullable=True)

    intake = relationship("Intake", back_populates="status_history")


class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, index=True)
    generic_name = Column(String, unique=True, index=True, nullable=False)
    brand_name = Column(String, nullable=True)

    aliases = relationship("DrugAlias", back_populates="drug", cascade="all, delete-orphan")


class DrugAlias(Base):
    __tablename__ = "drug_aliases"

    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)

    drug = relationship("Drug", back_populates="aliases")


class DrugInteraction(Base):
    __tablename__ = "drug_interactions"

    id = Column(Integer, primary_key=True, index=True)
    drug_a_id = Column(Integer, ForeignKey("drugs.id"), nullable=False, index=True)
    drug_b_id = Column(Integer, ForeignKey("drugs.id"), nullable=False, index=True)
    severity = Column(String, nullable=False, default="moderate")
    description = Column(Text, nullable=False)
    clinical_effect = Column(Text, nullable=True)
    mechanism = Column(Text, nullable=True)
    monitoring = Column(Text, nullable=True)
    source = Column(String, nullable=True, default="seed")

    __table_args__ = (
        UniqueConstraint("drug_a_id", "drug_b_id", name="uq_drug_interaction_pair"),
    )


class InteractionDocument(Base):
    __tablename__ = "interaction_documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="dataset")
    source_id = Column(String, nullable=True, index=True)
    section = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_payload = Column(Text, nullable=False, default="[]")
    parsed_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GeneratedCounselingLog(Base):
    __tablename__ = "generated_counseling_logs"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(Integer, ForeignKey("intakes.id"), nullable=True, index=True)
    patient_name = Column(String, nullable=True)
    medications = Column(Text, nullable=False)
    counseling_json = Column(Text, nullable=False)
    generator = Column(String, default="template_service")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intake = relationship("Intake", back_populates="counseling_logs")


class DdiCsvIngestManifest(Base):
    """
    Single-row (id=1) marker: bundled DDII CSV was fully ingested for a given file fingerprint.

    Prevents skipping re-import after a partial ingest (crash mid-file) or when the CSV file
    is replaced without changing ``DDI_CSV_FORCE_RELOAD``.
    """

    __tablename__ = "ddi_csv_ingest_manifest"

    id = Column(Integer, primary_key=True)
    csv_path = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_mtime = Column(Integer, nullable=False)
    ingest_complete = Column(Integer, nullable=False, default=0)
    last_ingest_stats = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PortalUser(Base):
    """Persistent user store for pharmacist accounts (both password + Google OAuth).

    Migrated from ``fastapi/data/portal_users.json`` — the JSON file was on Render's
    ephemeral disk and was wiped on every redeploy, causing all real accounts
    created between deploys to disappear.
    """

    __tablename__ = "portal_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True, default="")
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PortalPasswordReset(Base):
    """Short-lived password-reset tokens (1 h). Persistent so a redeploy mid-reset works."""

    __tablename__ = "portal_password_resets"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    exp = Column(DateTime, nullable=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_ddii_csv_path() -> str | None:
    """
    Prefer ``DRUG_INTERACTIONS_CSV`` when set; otherwise use ``fastapi/data/db_drug_interactions.csv`` if present.
    """
    explicit = (os.getenv("DRUG_INTERACTIONS_CSV") or "").strip()
    if explicit:
        if os.path.isfile(explicit):
            print(f"[ddi_csv] using DRUG_INTERACTIONS_CSV env: {explicit}", flush=True)
            return explicit
        print(f"[ddi_csv] DRUG_INTERACTIONS_CSV is set but file not found: {explicit}", flush=True)
        return None
    default_csv = Path(__file__).resolve().parent / "data" / "db_drug_interactions.csv"
    if default_csv.is_file():
        print(f"[ddi_csv] DRUG_INTERACTIONS_CSV not set; using default: {default_csv}", flush=True)
        return str(default_csv)
    print(
        f"[ddi_csv] no CSV file found — set DRUG_INTERACTIONS_CSV or place file at {default_csv}",
        flush=True,
    )
    return None


def _ddii_csv_fingerprint(csv_path: str) -> tuple[str, int, int]:
    """Resolved path, size in bytes, mtime (seconds) for change detection."""
    p = Path(csv_path).expanduser().resolve()
    st = p.stat()
    return str(p), int(st.st_size), int(st.st_mtime)


def _load_ddii_csv_if_configured() -> None:
    """
    Load ``db_drug_interactions.csv`` into ``drug_interactions`` when needed.

    Skips only when a manifest row (id=1) records a **completed** ingest for the **same**
    resolved path, size, and mtime as the CSV on disk, and at least one interaction row exists.

    Re-imports (after clearing CSV-backed rows) when: the CSV file changed, ingest never
    finished (``ingest_complete=0``), manifest is missing, ``DDI_CSV_FORCE_RELOAD=1``, or
    manifest claims success but all CSV rows were removed manually.
    """
    path = _resolve_ddii_csv_path()
    if not path:
        return

    from services.ddi_csv_ingestion import SOURCE_TAG, ingest_ddii_csv_file

    resolved, size, mtime = _ddii_csv_fingerprint(path)
    force = os.getenv("DDI_CSV_FORCE_RELOAD", "").strip().lower() in ("1", "true", "yes")

    def _manifest_ok_for_skip(m: DdiCsvIngestManifest | None, row_count: int) -> bool:
        if force or m is None or m.ingest_complete != 1:
            return False
        if m.csv_path != resolved or m.file_size != size or m.file_mtime != mtime:
            return False
        return row_count > 0

    try:
        with SessionLocal() as db:
            man = db.get(DdiCsvIngestManifest, 1)
            n = db.query(DrugInteraction).filter(DrugInteraction.source == SOURCE_TAG).count()
            if _manifest_ok_for_skip(man, n):
                print(
                    f"[ddi_csv] unchanged and fully ingested ({n} pairs); skipping",
                    flush=True,
                )
                return

            # RESUME logic: If the CSV file is identical to what's tracked in
            # the manifest AND we're not forcing a fresh reload, keep the rows
            # already inserted from the previous (possibly interrupted) run.
            # The ingest itself preloads `known_pairs` and dedups, so re-running
            # only inserts the pairs still missing. This is critical on free-tier
            # hosted Postgres where the worker may be killed mid-run — each
            # restart makes forward progress instead of restarting from 0.
            file_unchanged = (
                man is not None
                and man.csv_path == resolved
                and man.file_size == size
                and man.file_mtime == mtime
            )
            can_resume = (not force) and file_unchanged and n > 0

            if force:
                print("[ddi_csv] DDI_CSV_FORCE_RELOAD: clearing manifest and CSV-backed rows", flush=True)
            elif can_resume:
                print(
                    f"[ddi_csv] RESUMING previous run: keeping {n} already-inserted "
                    f"CSV-backed rows; will only insert missing pairs",
                    flush=True,
                )
            elif man is None:
                print("[ddi_csv] manifest missing; clearing any partial CSV-backed rows", flush=True)
            elif man.ingest_complete != 1:
                print("[ddi_csv] previous ingest incomplete + file changed; clearing CSV-backed rows", flush=True)
            elif not file_unchanged:
                print(
                    f"[ddi_csv] CSV file changed (was {man.file_size} bytes mtime {man.file_mtime}; "
                    f"now {size} bytes mtime {mtime}); reloading",
                    flush=True,
                )
            elif n == 0:
                print("[ddi_csv] manifest reports success but 0 rows in DB; re-importing", flush=True)

            if can_resume:
                deleted = 0  # keep existing rows
            else:
                deleted = (
                    db.query(DrugInteraction)
                    .filter(DrugInteraction.source == SOURCE_TAG)
                    .delete(synchronize_session=False)
                )
            now = datetime.now(timezone.utc)
            # Update the manifest in place (or insert if missing) — avoids the
            # delete-then-merge pattern which triggers StaleDataError on Postgres
            # because SQLAlchemy's identity map still tracks the deleted row.
            if man is None:
                db.add(
                    DdiCsvIngestManifest(
                        id=1,
                        csv_path=resolved,
                        file_size=size,
                        file_mtime=mtime,
                        ingest_complete=0,
                        last_ingest_stats=None,
                        updated_at=now,
                    )
                )
            else:
                man.csv_path = resolved
                man.file_size = size
                man.file_mtime = mtime
                man.ingest_complete = 0
                man.last_ingest_stats = None
                man.updated_at = now
            db.commit()
            if can_resume:
                print(
                    f"[ddi_csv] prepared ingest (resuming; {n} rows already present)",
                    flush=True,
                )
            else:
                print(
                    f"[ddi_csv] prepared ingest (removed {deleted} old CSV-backed interaction rows)",
                    flush=True,
                )

        with SessionLocal() as db:
            print(f"[ddi_csv] beginning CSV ingest from {resolved}", flush=True)
            stats = ingest_ddii_csv_file(db, path)
            now = datetime.now(timezone.utc)
            stats_json = json.dumps(
                {
                    "inserted": stats.get("inserted"),
                    "skipped": stats.get("skipped"),
                    "total_rows": stats.get("total_rows"),
                    "failed": stats.get("failed"),
                }
            )
            man2 = db.get(DdiCsvIngestManifest, 1)
            if man2 is None:
                db.add(
                    DdiCsvIngestManifest(
                        id=1,
                        csv_path=resolved,
                        file_size=size,
                        file_mtime=mtime,
                        ingest_complete=1,
                        last_ingest_stats=stats_json,
                        updated_at=now,
                    )
                )
            else:
                man2.csv_path = resolved
                man2.file_size = size
                man2.file_mtime = mtime
                man2.ingest_complete = 1
                man2.last_ingest_stats = stats_json
                man2.updated_at = now
            db.commit()
        print(
            f"[ddi_csv] ingest complete: inserted={stats.get('inserted')} "
            f"skipped={stats.get('skipped')} total_rows={stats.get('total_rows')}",
            flush=True,
        )
        logger.info(
            "Loaded drug interactions CSV: inserted=%s skipped=%s rows=%s",
            stats.get("inserted"),
            stats.get("skipped"),
            stats.get("total_rows"),
        )
    except Exception as e:
        print(f"[ddi_csv] FAILED: {type(e).__name__}: {e}", flush=True)
        logger.exception("Failed to ingest DRUG_INTERACTIONS_CSV")


def _load_seed_interactions_json() -> None:
    """
    Merge ``fastapi/data/drug_interactions.json`` into ``drug_interactions``.

    Runs on every startup; skips pairs already present (e.g. from the large CSV).
    Fills gaps where the TDCommons/Kaggle export omits common pairs (e.g. warfarin + aspirin).
    """
    path = Path(__file__).resolve().parent / "data" / "drug_interactions.json"
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Could not read seed interactions: %s", path)
        return

    from services.knowledge_ingestion_service import ingest_seed_interactions_bundle

    db = SessionLocal()
    try:
        stats = ingest_seed_interactions_bundle(
            db, payload, interaction_source="seed_json"
        )
        if stats.get("fatal"):
            logger.error("Seed interactions ingest failed: %s", stats.get("error"))
            db.rollback()
            return
        db.commit()
        if stats.get("inserted", 0) or stats.get("skipped", 0):
            logger.info(
                "Seed interactions JSON: inserted=%s skipped=%s rows=%s",
                stats.get("inserted"),
                stats.get("skipped"),
                stats.get("total_rows"),
            )
    except Exception:
        db.rollback()
        logger.exception("Failed to ingest seed drug_interactions.json")
    finally:
        db.close()


def init_db_schema() -> None:
    """Create tables and run lightweight migrations (fast; safe before accepting traffic)."""
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def init_db_interaction_sources() -> None:
    """Load large CSV + JSON seed into ``drug_interactions`` (can take many minutes)."""
    _load_ddii_csv_if_configured()
    _load_seed_interactions_json()


def init_db() -> None:
    """Full init: schema plus interaction sources (used by scripts; servers may defer the latter)."""
    init_db_schema()
    init_db_interaction_sources()


def _run_lightweight_migrations() -> None:
    """Best-effort SQLite column backfills for existing local databases."""
    try:
        with engine.begin() as conn:
            if not str(engine.url).startswith("sqlite"):
                return

            intakes_cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info('intakes')")).fetchall()
            }
            if "patient_gender" not in intakes_cols:
                conn.execute(text("ALTER TABLE intakes ADD COLUMN patient_gender TEXT"))
            if "patient_phone" not in intakes_cols:
                conn.execute(text("ALTER TABLE intakes ADD COLUMN patient_phone TEXT"))
            if "created_by" not in intakes_cols:
                conn.execute(text("ALTER TABLE intakes ADD COLUMN created_by TEXT"))

            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info('drug_interactions')")).fetchall()
            }
            if "clinical_effect" not in existing:
                conn.execute(text("ALTER TABLE drug_interactions ADD COLUMN clinical_effect TEXT"))
            if "mechanism" not in existing:
                conn.execute(text("ALTER TABLE drug_interactions ADD COLUMN mechanism TEXT"))
            if "monitoring" not in existing:
                conn.execute(text("ALTER TABLE drug_interactions ADD COLUMN monitoring TEXT"))
    except Exception:
        # Non-fatal: service should still run even if migration step fails.
        return
