from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

SQLALCHEMY_DATABASE_URL = "sqlite:///./pharmacy.db"

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
    current_medications = Column(Text, nullable=True)  # For drug interaction checking
    notes = Column(Text, nullable=True)
    counseling_points = Column(Text, nullable=True)
    pharmacist_notes = Column(Text, nullable=True)
    drug_interactions = Column(Text, nullable=True)  # JSON string of interactions
    status = Column(String, default="new")
    assigned_to = Column(String, nullable=True)
    dispensed = Column(String, nullable=True)  # "yes", "no", or None
    dispensed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
