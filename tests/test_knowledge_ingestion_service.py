import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias
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
    assert stats["total_rows"] == 3
    assert stats["inserted"] == 1
    assert stats["skipped"] == 2
    assert stats["failed"] == 0
    assert stats.get("format") == "dataset_rows"


def test_ingest_openfda_label_json_upload():
    db = _session()
    for name in ["warfarin", "ibuprofen", "naproxen", "aspirin", "clarithromycin", "simvastatin"]:
        drug = Drug(generic_name=name)
        db.add(drug)
        db.flush()
        db.add(DrugAlias(drug_id=drug.id, alias=name))
    db.commit()

    bundle = {
        "meta": {"results": {"total": 1}},
        "results": [
            {
                "openfda": {
                    "generic_name": ["Warfarin"],
                    "set_id": ["set-w"],
                },
                "drug_interactions": [
                    "Concurrent use of warfarin and NSAIDs increases bleeding risk."
                ],
            },
        ],
    }
    stats = ingest_knowledge_dataset("labels.json", json.dumps(bundle).encode("utf-8"), db)
    assert stats.get("format") == "openfda_label_json"
    assert stats["inserted"] >= 1
    assert stats["total_fetched"] == 1


def test_ingest_json_unrecognized_shape_returns_fatal():
    db = _session()
    stats = ingest_knowledge_dataset("bad.json", json.dumps({"foo": []}).encode("utf-8"), db)
    assert stats.get("fatal") is True
    assert stats.get("failed") == 1
    assert "error" in stats
