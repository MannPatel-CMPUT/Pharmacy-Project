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
