from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import os

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


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(Integer, ForeignKey("intakes.id"), index=True)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    changed_by = Column(String, nullable=True)

    intake = relationship("Intake", back_populates="status_history")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
