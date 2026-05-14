from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy import event, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import logging

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharmacy.db")

_connect_args: dict = {"check_same_thread": False}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Wait for writers (e.g. background CSV ingest) instead of immediate "database is locked".
    _connect_args["timeout"] = float(os.getenv("SQLITE_LOCK_TIMEOUT", "60"))

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
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
            return explicit
        logger.warning("DRUG_INTERACTIONS_CSV is set but file not found: %s", explicit)
        return None
    default_csv = Path(__file__).resolve().parent / "data" / "db_drug_interactions.csv"
    if default_csv.is_file():
        logger.info("DRUG_INTERACTIONS_CSV not set; loading %s", default_csv)
        return str(default_csv)
    logger.info(
        "No interaction CSV: set DRUG_INTERACTIONS_CSV or copy db_drug_interactions.csv to %s",
        default_csv,
    )
    return None


def _load_ddii_csv_if_configured() -> None:
    """
    One-time load of db_drug_interactions.csv into drug_interactions.

    Set ``DRUG_INTERACTIONS_CSV`` to the absolute path of your CSV, or place the file at
    ``fastapi/data/db_drug_interactions.csv``. Skips if that source is already present.

    Set ``DDI_CSV_FORCE_RELOAD=1`` (once) to delete all rows with source ``db_drug_interactions_csv``
    and re-import from the configured file (slow on large CSVs — unset after a successful run).
    """
    path = _resolve_ddii_csv_path()
    if not path:
        return

    from services.ddi_csv_ingestion import SOURCE_TAG, ingest_ddii_csv_file

    force = os.getenv("DDI_CSV_FORCE_RELOAD", "").strip().lower() in ("1", "true", "yes")
    if force:
        with SessionLocal() as db:
            deleted = (
                db.query(DrugInteraction)
                .filter(DrugInteraction.source == SOURCE_TAG)
                .delete(synchronize_session=False)
            )
            db.commit()
            logger.info(
                "DDI_CSV_FORCE_RELOAD: removed %s drug_interactions rows (source=%s)",
                deleted,
                SOURCE_TAG,
            )

    with SessionLocal() as db:
        n = db.query(DrugInteraction).filter(DrugInteraction.source == SOURCE_TAG).count()
        if n > 0:
            logger.info("Drug interaction CSV already loaded (%s pairs), skipping ingest", n)
            return

    try:
        with SessionLocal() as db:
            stats = ingest_ddii_csv_file(db, path)
        logger.info(
            "Loaded drug interactions CSV: inserted=%s skipped=%s rows=%s",
            stats.get("inserted"),
            stats.get("skipped"),
            stats.get("total_rows"),
        )
    except Exception:
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
