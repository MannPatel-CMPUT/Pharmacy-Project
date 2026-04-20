"""Tests for optional per-intake openFDA enrichment."""

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from services import drug_interaction_service
from services.drug_interaction_service import check_drug_interactions
from services.openfda_intake_enrichment import enrich_db_from_openfda_for_intake_meds


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_enrich_disabled_skips_terms(monkeypatch):
    monkeypatch.setenv("OPENFDA_ENRICH_ON_INTAKE", "false")
    db = _session()
    stats = enrich_db_from_openfda_for_intake_meds(db, "warfarin", "aspirin")
    assert stats.get("enabled") is False
    assert stats.get("api_calls", 0) == 0


def test_check_drug_interactions_invokes_enrich_when_enabled(monkeypatch):
    monkeypatch.setenv("OPENFDA_ENRICH_ON_INTAKE", "true")
    calls = []

    def fake_enrich(db, new_meds, cur_meds):
        calls.append((new_meds, cur_meds))
        return {"enabled": True}

    db = _session()
    with patch.object(drug_interaction_service, "enrich_db_from_openfda_for_intake_meds", fake_enrich):
        check_drug_interactions(db, "a", "b")
    assert calls == [("a", "b")]
