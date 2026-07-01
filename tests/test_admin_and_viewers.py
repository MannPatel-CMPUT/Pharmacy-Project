"""
Regression tests for endpoints added in the P0-DDII / P2-P3 batch (Feb 2026):
- GET  /api/admin/ddi-stats           (admin — cookie required)
- POST /intakes/viewing               (concurrency viewer registry — anonymous safe)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from services import viewers_registry, auth_service

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
def _clear_viewers():
    """Reset the in-memory viewers registry between tests."""
    with viewers_registry._lock:
        viewers_registry._state.clear()
    yield
    with viewers_registry._lock:
        viewers_registry._state.clear()


def _auth_cookie(username: str, user_id: int = 1) -> dict:
    """Mint a valid session cookie for tests without hitting /api/auth/signup."""
    token = auth_service.create_token(user_id, username)
    return {auth_service.COOKIE_NAME: token}


# ─────────────────── /api/admin/ddi-stats ───────────────────

def test_ddi_stats_requires_login():
    r = client.get("/api/admin/ddi-stats")
    assert r.status_code == 401
    assert r.json()["detail"].lower().startswith("login")


def test_ddi_stats_shape_when_empty():
    r = client.get("/api/admin/ddi-stats", cookies=_auth_cookie("alice"))
    assert r.status_code == 200
    body = r.json()
    assert body["drug_interactions_total"] == 0
    assert body["by_source"] == {}
    assert body["by_severity"] == {}
    # Manifest is None until the CSV ingest runs (test env has DRUG_INTERACTIONS_CSV="")
    assert body["csv_manifest"] is None


# ─────────────────── /intakes/viewing ───────────────────

def test_viewing_anonymous_returns_empty_map():
    r = client.post("/intakes/viewing", json={"intake_ids": [1, 2, 3]})
    assert r.status_code == 200
    assert r.json() == {"viewers": {}, "self": None}


def test_viewing_records_heartbeat_and_excludes_self():
    r = client.post(
        "/intakes/viewing",
        json={"intake_ids": [7]},
        cookies=_auth_cookie("alice", user_id=1),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["self"] == "alice"
    # alice is the only viewer — and is excluded from her own response
    assert body["viewers"] == {"7": []}


def test_viewing_shows_other_users():
    # bob heartbeats first
    client.post(
        "/intakes/viewing",
        json={"intake_ids": [42]},
        cookies=_auth_cookie("bob", user_id=2),
    )
    # alice queries and should see bob (but not herself)
    r = client.post(
        "/intakes/viewing",
        json={"intake_ids": [42, 99]},
        cookies=_auth_cookie("alice", user_id=1),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["self"] == "alice"
    assert body["viewers"] == {"42": ["bob"], "99": []}


def test_viewing_ignores_stale_heartbeats(monkeypatch):
    """Heartbeats older than STALE_AFTER_SECONDS drop off."""
    from datetime import datetime, timedelta, timezone

    # Record bob's heartbeat, then age it beyond the cutoff by patching the
    # stored timestamp directly.
    client.post(
        "/intakes/viewing",
        json={"intake_ids": [5]},
        cookies=_auth_cookie("bob", user_id=2),
    )
    with viewers_registry._lock:
        for key in list(viewers_registry._state.keys()):
            viewers_registry._state[key] = datetime.now(timezone.utc) - timedelta(
                seconds=viewers_registry.STALE_AFTER_SECONDS + 5
            )

    r = client.post(
        "/intakes/viewing",
        json={"intake_ids": [5]},
        cookies=_auth_cookie("alice", user_id=1),
    )
    assert r.status_code == 200
    # bob's heartbeat has expired — alice sees nobody
    assert r.json()["viewers"] == {"5": []}


def test_viewing_rejects_absurd_batches():
    # Pydantic max_length=200 → 201 ids should 422
    r = client.post(
        "/intakes/viewing",
        json={"intake_ids": list(range(201))},
        cookies=_auth_cookie("alice", user_id=1),
    )
    assert r.status_code == 422
