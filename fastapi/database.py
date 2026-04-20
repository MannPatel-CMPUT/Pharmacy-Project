from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import os
import json
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import logging

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharmacy.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
logger = logging.getLogger(__name__)


class Intake(Base):
    __tablename__ = "intakes"

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String, index=True)
    patient_age = Column(Integer, nullable=True)
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
    source = Column(String, nullable=False, default="openfda")
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


def _seed_drug_knowledge() -> None:
    """Merge seed `drug_interactions.json` into the DB (idempotent). Runs even if drugs already exist."""
    data_path = os.path.join(os.path.dirname(__file__), "data", "drug_interactions.json")
    if not os.path.exists(data_path):
        return

    with open(data_path, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    # Lazy import avoids circular import (services.knowledge_ingestion_service imports database).
    from services.knowledge_ingestion_service import ingest_seed_interactions_bundle

    with SessionLocal() as db:
        try:
            stats = ingest_seed_interactions_bundle(db, seed_data, interaction_source="seed_json")
            if stats.get("fatal"):
                logger.warning("seed skipped fatal=%s error=%s", stats.get("fatal"), stats.get("error"))
                return
            db.commit()
        except IntegrityError:
            # Parallel app startups can race on seed inserts; skip duplicates gracefully.
            db.rollback()
            logger.info("seed duplicate_conflicts_skipped=true")


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    _seed_drug_knowledge()


def _run_lightweight_migrations() -> None:
    """Best-effort SQLite column backfills for existing local databases."""
    try:
        with engine.begin() as conn:
            if not str(engine.url).startswith("sqlite"):
                return

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
