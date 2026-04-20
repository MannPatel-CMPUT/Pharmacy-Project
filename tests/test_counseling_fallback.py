from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.counseling_service as counseling_service
from database import Base


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_generate_counseling_falls_back_to_template(monkeypatch):
    db = _session()

    def _boom(*args, **kwargs):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(counseling_service, "generate_personalized_counseling", _boom)

    result = counseling_service.generate_counseling(
        db,
        patient_name="Test",
        medications="warfarin",
        interactions=[{"drug1": "warfarin", "drug2": "aspirin", "severity": "Major", "description": "risk"}],
        patient_age=70,
    )

    assert result["source"] == "template_fallback"
    assert "Educational prototype only. Not for diagnosis or prescribing." in result["text"]


def test_ollama_coerce_json_with_prose_prefix():
    from services.ollama_service import _coerce_json

    text = (
        'Here is the counseling JSON:\n'
        '{"interaction_summary": "s", "patient_specific_risk": "r", '
        '"top_counseling_points": ["a"], "monitoring_points": [], '
        '"red_flags": [], "when_to_contact_clinician": [], "evidence_used": ["e"]}'
    )
    d = _coerce_json(text)
    assert d["interaction_summary"] == "s"
    assert d["patient_specific_risk"] == "r"
    assert d["top_counseling_points"] == ["a"]
