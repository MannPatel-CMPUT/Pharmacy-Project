from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias, DrugInteraction
from services.interaction_engine import detect_interactions


def _build_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_detect_interactions_returns_structured_pairwise_findings():
    db = _build_db_session()

    warfarin = Drug(generic_name="warfarin")
    aspirin = Drug(generic_name="aspirin")
    db.add_all([warfarin, aspirin])
    db.flush()

    db.add_all([
        DrugAlias(drug_id=warfarin.id, alias="warfarin"),
        DrugAlias(drug_id=aspirin.id, alias="aspirin"),
        DrugInteraction(
            drug_a_id=min(warfarin.id, aspirin.id),
            drug_b_id=max(warfarin.id, aspirin.id),
            severity="major",
            description="Increased bleeding risk",
            clinical_effect="Increased bleeding risk",
            mechanism="Additive anticoagulation",
            monitoring="Monitor INR",
            source="test",
        ),
    ])
    db.commit()

    findings = detect_interactions(db, "Warfarin", "Aspirin")
    assert len(findings) == 1
    row = findings[0]
    assert row["severity"] == "Major"
    assert row["description"] == "Increased bleeding risk"
    assert row["mechanism"] == "Additive anticoagulation"
    assert row["monitoring"] == "Monitor INR"
    assert row["source"] == "test"


def test_detect_interactions_matches_class_based_pair_from_openfda_style_data():
    db = _build_db_session()

    warfarin = Drug(generic_name="warfarin")
    nsaids = Drug(generic_name="nsaids")
    ibuprofen = Drug(generic_name="ibuprofen")
    db.add_all([warfarin, nsaids, ibuprofen])
    db.flush()

    db.add_all(
        [
            DrugAlias(drug_id=warfarin.id, alias="warfarin"),
            DrugAlias(drug_id=nsaids.id, alias="nsaids"),
            DrugAlias(drug_id=ibuprofen.id, alias="ibuprofen"),
            DrugInteraction(
                drug_a_id=min(warfarin.id, nsaids.id),
                drug_b_id=max(warfarin.id, nsaids.id),
                severity="major",
                description="Warfarin and NSAIDs increase bleeding risk.",
                clinical_effect="Warfarin and NSAIDs increase bleeding risk.",
                source="openfda",
            ),
        ]
    )
    db.commit()

    findings = detect_interactions(db, "Warfarin", "Ibuprofen")
    assert len(findings) == 1
    assert findings[0]["source"] == "openfda"
    assert findings[0]["normalized_pair"] == ["nsaids", "warfarin"]
