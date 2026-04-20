import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias, DrugInteraction
from services.knowledge_ingestion_service import (
    ingest_knowledge_dataset,
    ingest_knowledge_large_json_file,
)
from services.openfda_ingestion_service import ingest_openfda_label_json_stream


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


def test_ingest_seed_shaped_json_upload():
    db = _session()
    bundle = {
        "interactions": {
            "warfarin": {"aspirin": "Major: Increased bleeding risk. Monitor INR closely."},
        },
        "categories": {"nsaids": ["ibuprofen", "naproxen"]},
    }
    stats = ingest_knowledge_dataset("drug_interactions.json", json.dumps(bundle).encode("utf-8"), db)
    assert stats.get("format") == "drug_interactions_seed"
    assert stats["inserted"] == 1
    assert stats["skipped"] == 0
    assert stats["pairs_seen"] == 1
    pairs = db.query(DrugInteraction).count()
    assert pairs == 1
    drugs = {d.generic_name for d in db.query(Drug).all()}
    assert "warfarin" in drugs and "aspirin" in drugs and "ibuprofen" in drugs


def test_ingest_seed_shaped_json_idempotent():
    db = _session()
    bundle = {
        "interactions": {"warfarin": {"aspirin": "Major: bleed."}},
        "categories": {},
    }
    ingest_knowledge_dataset("seed.json", json.dumps(bundle).encode("utf-8"), db)
    stats2 = ingest_knowledge_dataset("seed.json", json.dumps(bundle).encode("utf-8"), db)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] >= 1
    assert db.query(DrugInteraction).count() == 1


def test_ingest_seed_merges_when_drugs_already_exist():
    """If openFDA (or anything) created Drug rows first, startup seed used to skip entirely."""
    db = _session()
    warfarin = Drug(generic_name="warfarin")
    db.add(warfarin)
    db.flush()
    db.add(DrugAlias(drug_id=warfarin.id, alias="warfarin"))
    db.commit()

    bundle = {
        "interactions": {"warfarin": {"aspirin": "Major: bleed."}},
        "categories": {},
    }
    stats = ingest_knowledge_dataset("seed.json", json.dumps(bundle).encode("utf-8"), db)
    assert stats["inserted"] == 1
    assert db.query(Drug).count() == 2
    assert db.query(DrugInteraction).count() == 1


def test_ingest_openfda_label_json_stream_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENFDA_STREAM_COMMIT_EVERY", "1")
    db = _session()
    bundle = {
        "meta": {"results": {"total": 2}},
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
            {
                "openfda": {
                    "generic_name": ["Aspirin"],
                    "set_id": ["set-a"],
                },
                "drug_interactions": ["Monitor when combining aspirin with anticoagulants."],
            },
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    stats = ingest_openfda_label_json_stream(db, str(path))
    assert stats.get("streaming") is True
    assert stats["total_fetched"] == 2
    assert stats["inserted"] >= 1


def test_ingest_knowledge_large_json_rejects_non_openfda(tmp_path):
    db = _session()
    p = tmp_path / "seed.json"
    p.write_text(
        json.dumps({"interactions": {"warfarin": {"aspirin": "Major: x"}}, "categories": {}}),
        encoding="utf-8",
    )
    stats = ingest_knowledge_large_json_file(db, "seed.json", str(p))
    assert stats.get("fatal") is True
    assert "openFDA" in (stats.get("error") or "")
