import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias, DrugInteraction
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


def test_ingest_ddii_csv_drugbank_shape():
    """db_drug_interactions.csv style: Drug 1, Drug 2, Interaction Description."""
    db = _session()
    csv_text = (
        "Drug 1,Drug 2,Interaction Description\n"
        "warfarin,aspirin,Concurrent use may increase bleeding risk.\n"
        "metformin,cimetidine,May increase metformin exposure.\n"
    )
    stats = ingest_knowledge_dataset("db_drug_interactions.csv", csv_text.encode("utf-8"), db)
    assert stats.get("format") == "db_drug_interactions_csv"
    assert stats.get("inserted", 0) >= 1
    assert stats.get("total_rows", 0) >= 1
    from database import DrugInteraction as DI, Drug

    def pair_sev(a: str, b: str) -> str | None:
        da = db.query(Drug).filter_by(generic_name=a).first()
        dbb = db.query(Drug).filter_by(generic_name=b).first()
        if not da or not dbb:
            return None
        lo, hi = sorted([da.id, dbb.id])
        ix = db.query(DI).filter_by(drug_a_id=lo, drug_b_id=hi).first()
        return ix.severity if ix else None

    assert pair_sev("warfarin", "aspirin") == "major"
    assert pair_sev("metformin", "cimetidine") == "moderate"


def test_ingest_ddii_csv_respects_risk_severity_column():
    db = _session()
    csv_text = (
        "Drug 1,Drug 2,Interaction Description,Risk Severity\n"
        "warfarin,aspirin,Some vague text.,minor\n"
    )
    stats = ingest_knowledge_dataset("db_drug_interactions.csv", csv_text.encode("utf-8"), db)
    assert stats.get("format") == "db_drug_interactions_csv"
    assert stats.get("inserted") == 1
    from database import DrugInteraction as DI, Drug

    da = db.query(Drug).filter_by(generic_name="warfarin").first()
    dba = db.query(Drug).filter_by(generic_name="aspirin").first()
    lo, hi = sorted([da.id, dba.id])
    ix = db.query(DI).filter_by(drug_a_id=lo, drug_b_id=hi).one()
    assert ix.severity == "minor"


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
