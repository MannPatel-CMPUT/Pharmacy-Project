from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from services.knowledge_ingestion_service import ingest_knowledge_dataset


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_ingest_knowledge_dataset_skips_invalid_and_duplicates():
    db = _session()
    csv_text = "\n".join([
        "drug_a,drug_b,severity,clinical_effect,mechanism,monitoring",
        "warfarin,aspirin,major,Increased bleeding risk,Additive,Monitor INR",
        "warfarin,aspirin,major,Duplicate row,Duplicate,Duplicate",
        "warfarin,warfarin,major,Invalid pair,NA,NA",
    ])

    stats = ingest_knowledge_dataset("sample.csv", csv_text.encode("utf-8"), db)
    assert stats == {"total_rows": 3, "inserted": 1, "skipped": 2, "failed": 0}
