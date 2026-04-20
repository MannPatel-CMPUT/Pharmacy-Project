"""
Integration tests for the Pharmacy Workflow API.
Uses an in-memory SQLite database so tests are isolated and fast.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.openfda_ingestion_service as ingestion
import services.ollama_service as ollama
from main import app
from database import Base, get_db

# StaticPool ensures all connections in-process share the same in-memory database.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Wipe and recreate all tables before each test for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

SAMPLE_INTAKE = {
    "patient_name": "Test Patient",
    "patient_age": 45,
    "medications": "Aspirin",
    "current_medications": "",
    "patient_allergies": "none",
    "notes": ""
}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Create intake
# ---------------------------------------------------------------------------

def test_create_intake_returns_201():
    response = client.post("/intakes", json=SAMPLE_INTAKE)
    assert response.status_code == 201
    data = response.json()
    assert data["patient_name"] == "Test Patient"
    assert data["status"] == "new"
    assert "id" in data


def test_create_intake_missing_patient_name_returns_422():
    payload = {**SAMPLE_INTAKE, "patient_name": ""}
    response = client.post("/intakes", json=payload)
    assert response.status_code == 422


def test_create_intake_invalid_age_returns_422():
    payload = {**SAMPLE_INTAKE, "patient_age": 200}
    response = client.post("/intakes", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# List intakes
# ---------------------------------------------------------------------------

def test_list_intakes_empty():
    response = client.get("/intakes")
    assert response.status_code == 200
    assert response.json() == []


def test_list_intakes_returns_created_intake():
    client.post("/intakes", json=SAMPLE_INTAKE)
    response = client.get("/intakes")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_intakes_pagination():
    for i in range(5):
        client.post("/intakes", json={**SAMPLE_INTAKE, "patient_name": f"Patient {i}"})
    response = client.get("/intakes?skip=0&limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_intakes_search():
    client.post("/intakes", json={**SAMPLE_INTAKE, "patient_name": "Alice Smith"})
    client.post("/intakes", json={**SAMPLE_INTAKE, "patient_name": "Bob Jones"})
    response = client.get("/intakes?search=alice")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_name"] == "Alice Smith"


# ---------------------------------------------------------------------------
# Get single intake
# ---------------------------------------------------------------------------

def test_get_intake_by_id():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    intake_id = create.json()["id"]
    response = client.get(f"/intakes/{intake_id}")
    assert response.status_code == 200
    assert response.json()["id"] == intake_id


def test_get_intake_not_found():
    response = client.get("/intakes/9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def test_valid_status_transition():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    intake_id = create.json()["id"]
    response = client.post(f"/intakes/{intake_id}/status", json={"status": "triage"})
    assert response.status_code == 200
    assert response.json()["status"] == "triage"


def test_invalid_status_transition_returns_400():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    intake_id = create.json()["id"]
    # "new" → "dispensed" is not allowed
    response = client.post(f"/intakes/{intake_id}/status", json={"status": "dispensed"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------

def test_status_history_recorded():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    intake_id = create.json()["id"]
    client.post(f"/intakes/{intake_id}/status", json={"status": "triage"})

    response = client.get(f"/intakes/{intake_id}/history")
    assert response.status_code == 200
    history = response.json()
    # Initial "new" entry + transition to "triage"
    assert len(history) >= 2
    assert history[-1]["to_status"] == "triage"


# ---------------------------------------------------------------------------
# Delete intake
# ---------------------------------------------------------------------------

def test_delete_intake():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    intake_id = create.json()["id"]
    response = client.delete(f"/intakes/{intake_id}")
    assert response.status_code == 204
    assert client.get(f"/intakes/{intake_id}").status_code == 404


def test_delete_intake_not_found():
    response = client.delete("/intakes/9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_statistics_endpoint():
    client.post("/intakes", json=SAMPLE_INTAKE)
    response = client.get("/intakes/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] >= 1


def test_openfda_sync_endpoint(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "openfda": {
                            "generic_name": ["Warfarin"],
                            "brand_name": ["Coumadin"],
                            "set_id": ["abc-123"],
                        },
                        "drug_interactions": [
                            "Warfarin and aspirin may cause serious bleeding. Monitor patient closely."
                        ],
                        "warnings": [
                            "Warfarin with ibuprofen should be avoided in serious cases."
                        ],
                        "contraindications": [
                            "Warfarin is contraindicated with rivaroxaban."
                        ],
                    }
                ]
            }

    monkeypatch.setattr(ingestion.httpx, "get", lambda *args, **kwargs: DummyResponse())

    response = client.post("/knowledge/openfda-sync")
    assert response.status_code == 200
    data = response.json()
    assert data["total_fetched"] == 1
    assert data["parsed"] >= 1
    assert data["inserted"] >= 1
    assert data["failed"] == 0


def test_config_status_endpoint(monkeypatch):
    class DummyTagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "llama3:latest"}]}

    monkeypatch.setattr(ollama.httpx, "get", lambda *args, **kwargs: DummyTagsResponse())
    response = client.get("/config/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ollama_reachable"] is True
    assert "configured_model" in body


def test_create_intake_falls_back_when_ollama_unavailable(monkeypatch):
    def raise_conn_error(*args, **kwargs):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(ollama.httpx, "post", raise_conn_error)

    response = client.post("/intakes", json=SAMPLE_INTAKE)
    assert response.status_code == 201
    data = response.json()
    assert "Educational prototype only. Not for diagnosis or prescribing." in data["counseling_points"]


def test_knowledge_upload_csv_endpoint():
    csv_data = (
        "drug_a,drug_b,severity,clinical_effect,mechanism,monitoring\n"
        "warfarin,aspirin,major,Increased bleeding risk,Additive anticoagulation,Monitor INR and bleeding\n"
        "warfarin,warfarin,major,Invalid self pair,NA,NA\n"
        "lisinopril,potassium,moderate,Hyperkalemia risk,Potassium retention,Monitor potassium\n"
    )
    files = {"file": ("interactions.csv", csv_data, "text/csv")}
    response = client.post("/knowledge/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
    assert data["inserted"] == 2
    assert data["skipped"] == 1
    assert data["failed"] == 0


def test_knowledge_upload_json_endpoint_with_bad_rows():
    payload = [
        {
            "drug_a": "atorvastatin",
            "drug_b": "erythromycin",
            "severity": "major",
            "clinical_effect": "Myopathy risk",
            "mechanism": "CYP inhibition",
            "monitoring": "Monitor muscle symptoms",
        },
        {
            "drug_a": "atorvastatin",
            "drug_b": "erythromycin",
            "severity": "major",
            "clinical_effect": "Duplicate",
            "mechanism": "Duplicate",
            "monitoring": "Duplicate",
        },
        {
            "drug_a": "",
            "drug_b": "ibuprofen",
            "severity": "minor",
            "clinical_effect": "Bad row",
            "mechanism": "Bad row",
            "monitoring": "Bad row",
        },
    ]
    files = {"file": ("interactions.json", json.dumps(payload), "application/json")}
    response = client.post("/knowledge/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
    assert data["inserted"] == 1
    assert data["skipped"] == 2
    assert data["failed"] == 0
