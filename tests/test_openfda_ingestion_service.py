import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Drug, DrugAlias, InteractionDocument
from services.interaction_engine import detect_interactions
from services.openfda_ingestion_service import sync_openfda_knowledge


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_openfda_sync_extracts_high_confidence_pairs_and_class_mapping(monkeypatch):
    db = _session()

    for name in ["warfarin", "ibuprofen", "naproxen", "aspirin", "clarithromycin", "simvastatin"]:
        drug = Drug(generic_name=name)
        db.add(drug)
        db.flush()
        db.add(DrugAlias(drug_id=drug.id, alias=name))
    db.commit()

    payload = {
        "results": [
            {
                "openfda": {
                    "generic_name": ["Warfarin"],
                    "set_id": ["set-warfarin"],
                },
                "drug_interactions": [
                    "Concurrent use of warfarin and NSAIDs increases bleeding risk."
                ],
            },
            {
                "openfda": {
                    "generic_name": ["Clarithromycin"],
                    "set_id": ["set-clarithromycin"],
                },
                "drug_interactions": [
                    "Clarithromycin may increase simvastatin concentrations."
                ],
            },
        ]
    }

    monkeypatch.setattr(
        "services.openfda_ingestion_service.httpx.get",
        lambda *args, **kwargs: _MockResponse(payload),
    )

    stats = sync_openfda_knowledge(db, limit=2)

    assert stats["inserted"] == 4
    assert stats["parsed"] == 4
    assert stats["failed"] == 0

    warfarin_findings = detect_interactions(db, "Warfarin", "Ibuprofen")
    assert len(warfarin_findings) == 1
    assert warfarin_findings[0]["source"] == "openfda"

    statin_findings = detect_interactions(db, "Simvastatin", "Clarithromycin")
    assert len(statin_findings) == 1
    assert statin_findings[0]["source"] == "openfda"


def test_openfda_sync_keeps_unparseable_text_as_document(monkeypatch):
    db = _session()
    warfarin = Drug(generic_name="warfarin")
    db.add(warfarin)
    db.flush()
    db.add(DrugAlias(drug_id=warfarin.id, alias="warfarin"))
    db.commit()

    payload = {
        "results": [
            {
                "openfda": {
                    "generic_name": ["Warfarin"],
                    "set_id": ["set-warfarin"],
                },
                "warnings": [
                    "Avoid sunlight exposure and drink water."
                ],
            }
        ]
    }

    monkeypatch.setattr(
        "services.openfda_ingestion_service.httpx.get",
        lambda *args, **kwargs: _MockResponse(payload),
    )

    stats = sync_openfda_knowledge(db, limit=1)

    assert stats["inserted"] == 0
    assert stats["parsed"] == 0
    assert stats["failed"] == 0

    # No interaction from unparseable label text.
    findings = detect_interactions(db, "Warfarin", "Ibuprofen")
    assert findings == []

    docs = db.query(InteractionDocument).all()
    assert len(docs) == 1
    assert docs[0].parsed_count == 0
    assert "Avoid sunlight exposure" in docs[0].raw_text


def test_openfda_sync_returns_error_on_http_failure(monkeypatch):
    db = _session()

    def _raise(*args, **kwargs):
        req = httpx.Request("GET", "https://api.fda.gov/drug/label.json")
        resp = httpx.Response(429, request=req, text="Too Many Requests")
        raise httpx.HTTPStatusError("rate limited", request=req, response=resp)

    monkeypatch.setattr("services.openfda_ingestion_service.httpx.get", _raise)
    stats = sync_openfda_knowledge(db, limit=5)
    assert stats["failed"] >= 1
    assert "error" in stats
    assert "429" in stats["error"] or "HTTP" in stats["error"]


def test_openfda_sync_returns_error_on_openfda_error_json(monkeypatch):
    db = _session()
    err_body = {"error": {"code": "OVER_LIMIT", "message": "Too many requests"}}
    monkeypatch.setattr(
        "services.openfda_ingestion_service.httpx.get",
        lambda *args, **kwargs: _MockResponse(err_body),
    )
    stats = sync_openfda_knowledge(db, limit=1)
    assert stats.get("failed") == 1
    assert "error" in stats
    assert "Too many" in stats["error"] or "requests" in stats["error"].lower()
