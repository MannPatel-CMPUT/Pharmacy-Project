from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import os
import json
from sqlalchemy import text

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharmacy.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


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


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _ordered_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def _seed_drug_knowledge() -> None:
    data_path = os.path.join(os.path.dirname(__file__), "data", "drug_interactions.json")
    if not os.path.exists(data_path):
        return

    with SessionLocal() as db:
        already_seeded = db.query(Drug).count() > 0
        if already_seeded:
            return

        with open(data_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)

        names: set[str] = set()
        for left, rights in seed_data.get("interactions", {}).items():
            names.add(_norm(left))
            for right in rights.keys():
                names.add(_norm(right))
        for drug_list in seed_data.get("categories", {}).values():
            names.update(_norm(item) for item in drug_list)

        if not names:
            return

        drug_by_name: dict[str, Drug] = {}
        for name in sorted(n for n in names if n):
            drug = Drug(generic_name=name)
            db.add(drug)
            db.flush()

            alias = DrugAlias(drug_id=drug.id, alias=name)
            db.add(alias)
            drug_by_name[name] = drug

        for left, rights in seed_data.get("interactions", {}).items():
            for right, description in rights.items():
                left_norm = _norm(left)
                right_norm = _norm(right)
                if not left_norm or not right_norm:
                    continue
                left_drug = drug_by_name.get(left_norm)
                right_drug = drug_by_name.get(right_norm)
                if not left_drug or not right_drug:
                    continue

                pair = _ordered_pair(left_drug.id, right_drug.id)
                exists = db.query(DrugInteraction).filter(
                    DrugInteraction.drug_a_id == pair[0],
                    DrugInteraction.drug_b_id == pair[1],
                ).first()
                if exists:
                    continue

                normalized_description = description.strip()
                lower_desc = normalized_description.lower()
                if "major" in lower_desc:
                    severity = "major"
                elif "moderate" in lower_desc:
                    severity = "moderate"
                elif "minor" in lower_desc:
                    severity = "minor"
                else:
                    severity = "unknown"

                db.add(
                    DrugInteraction(
                        drug_a_id=pair[0],
                        drug_b_id=pair[1],
                        severity=severity,
                        description=normalized_description,
                        clinical_effect=normalized_description,
                        source="seed_json",
                    )
                )

        db.commit()


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
