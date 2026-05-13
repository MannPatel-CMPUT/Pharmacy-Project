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

from main import app
from database import Base, Drug, DrugAlias, DrugInteraction, get_db

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


def test_create_intake_uses_local_drug_interaction_rows():
    """Same data model as db_drug_interactions.csv — pairs stored in SQLite."""
    db = TestingSessionLocal()
    w = Drug(generic_name="warfarin")
    ib = Drug(generic_name="ibuprofen")
    db.add_all([w, ib])
    db.flush()
    db.add_all([
        DrugAlias(drug_id=w.id, alias="warfarin"),
        DrugAlias(drug_id=ib.id, alias="ibuprofen"),
        DrugInteraction(
            drug_a_id=min(w.id, ib.id),
            drug_b_id=max(w.id, ib.id),
            severity="major",
            description="NSAIDs may increase bleeding with warfarin.",
            clinical_effect="Bleeding risk",
            source="db_drug_interactions_csv",
        ),
    ])
    db.commit()
    db.close()

    intake_response = client.post(
        "/intakes",
        json={
            "patient_name": "Interaction Test",
            "patient_age": 67,
            "medications": "Warfarin",
            "current_medications": "Ibuprofen",
            "patient_allergies": "none",
            "notes": "",
        },
    )
    assert intake_response.status_code == 201
    data = intake_response.json()
    assert data["drug_interactions"] is not None
    interactions = json.loads(data["drug_interactions"])
    assert len(interactions) >= 1
    assert interactions[0]["source"] == "db_drug_interactions_csv"
    assert interactions[0]["normalized_pair"] == ["ibuprofen", "warfarin"]


def test_config_status_endpoint():
    response = client.get("/config/status")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_enabled"] is False
    assert body["counseling_engine"] == "template"


def test_create_intake_includes_template_counseling():
    response = client.post("/intakes", json=SAMPLE_INTAKE)
    assert response.status_code == 201
    data = response.json()
    assert "Educational prototype only. Not for diagnosis or prescribing." in data["counseling_points"]


def test_check_interactions_returns_counseling_source():
    create = client.post("/intakes", json=SAMPLE_INTAKE)
    assert create.status_code == 201
    intake_id = create.json()["id"]

    res = client.post(f"/intakes/{intake_id}/check-interactions")
    assert res.status_code == 200
    body = res.json()
    assert body["counseling_source"] == "template"
    assert "counseling_points" in body
    assert "interactions" in body
