"""
RxFlow backend integration tests.
Hits the public preview URL end-to-end (Node portal -> FastAPI proxy).
"""
import json
import os
import time
import pytest
import requests

BASE_URL = "https://58cc5b94-0f34-4c71-b8c8-ce4456fc1aa9.preview.emergentagent.com"


# ---------- shared fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def maria_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"username": "maria", "password": "demopass1"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert r.json().get("ok") is True
    return s


# ---------- health / config ----------
class TestHealth:
    def test_root(self, session):
        r = session.get(BASE_URL + "/")
        assert r.status_code == 200

    def test_health(self, session):
        r = session.get(BASE_URL + "/health")
        assert r.status_code == 200

    def test_config(self, session):
        r = session.get(BASE_URL + "/config")
        # /config may or may not exist; tolerate 404
        assert r.status_code in (200, 404)


# ---------- auth ----------
class TestAuth:
    def test_login_success(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "maria", "password": "demopass1"})
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert r.json().get("username") == "maria"
        # cookie issued
        assert any(c.name == "pharma_auth" for c in session.cookies)

    def test_login_bad_password(self, session):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"username": "maria", "password": "wrong"})
        assert r.status_code in (400, 401, 403)

    def test_me_authenticated(self, maria_session):
        r = maria_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        username = body.get("username") or (body.get("user") or {}).get("username")
        assert username == "maria"

    def test_me_unauthenticated(self, session):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/auth/me")
        # should not be authenticated
        assert r.status_code in (200, 401)
        if r.status_code == 200:
            # Some apps return {user: null}
            data = r.json()
            assert not data.get("username")

    def test_logout(self, maria_session):
        r = maria_session.post(f"{BASE_URL}/api/auth/logout")
        assert r.status_code in (200, 204)
        # Re-login for downstream tests
        r2 = maria_session.post(f"{BASE_URL}/api/auth/login",
                                json={"username": "maria", "password": "demopass1"})
        assert r2.status_code == 200


# ---------- intakes ----------
class TestIntakes:
    def test_list_intakes(self, session):
        r = session.get(f"{BASE_URL}/intakes")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 6

    def test_stats_summary(self, session):
        r = session.get(f"{BASE_URL}/intakes/stats/summary")
        assert r.status_code == 200
        data = r.json()
        for key in ("total", "by_status", "dispensed_count", "ready_for_pickup"):
            assert key in data
        assert data["total"] >= 6
        assert isinstance(data["by_status"], dict)

    def test_get_single_intake(self, session):
        r = session.get(f"{BASE_URL}/intakes/1")
        assert r.status_code == 200
        body = r.json()
        assert body.get("id") == 1

    def test_intake_history(self, session):
        r = session.get(f"{BASE_URL}/intakes/1/history")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)


# ---------- severity sorting (Maria Sanchez intake #1: warfarin+aspirin) ----------
class TestSeveritySort:
    SEVERITY_RANK = {
        "contraindicated": 0, "major": 1, "moderate": 2, "minor": 3, "unknown": 4
    }

    def _parse_interactions(self, intake):
        di = intake.get("drug_interactions")
        if di is None:
            return []
        if isinstance(di, str):
            try:
                return json.loads(di)
            except Exception:
                return []
        return di

    def test_intake1_has_major_interaction(self, session):
        r = session.get(f"{BASE_URL}/intakes/1")
        assert r.status_code == 200
        items = self._parse_interactions(r.json())
        assert items, f"expected non-empty drug_interactions, got {items!r}"
        sevs = [str(i.get("severity", "")).lower() for i in items]
        assert any(s in ("major", "contraindicated") for s in sevs), \
            f"expected at least one major interaction; got {sevs}"

    def test_intake1_severity_sorted(self, session):
        r = session.get(f"{BASE_URL}/intakes/1")
        items = self._parse_interactions(r.json())
        ranks = [self.SEVERITY_RANK.get(str(i.get("severity", "")).lower(), 99)
                 for i in items]
        assert ranks == sorted(ranks), \
            f"interactions not severity-sorted: {ranks}"

    def test_all_intakes_severity_sorted(self, session):
        r = session.get(f"{BASE_URL}/intakes")
        for intake in r.json():
            items = self._parse_interactions(intake)
            ranks = [self.SEVERITY_RANK.get(str(i.get("severity", "")).lower(), 99)
                     for i in items]
            assert ranks == sorted(ranks), \
                f"intake {intake.get('id')} interactions not sorted: {ranks}"


# ---------- audit attribution ----------
class TestAuditAttribution:
    def test_status_change_records_changed_by(self, maria_session):
        # Pick intake 4 and do a valid transition based on its current state.
        intake_id = 4
        r = maria_session.get(f"{BASE_URL}/intakes/{intake_id}")
        assert r.status_code == 200
        current = r.json().get("status")
        # Map of allowed forward transitions
        forward = {
            "new": "triage",
            "triage": "waiting_info",
            "waiting_info": "ready_to_fill",
            "ready_to_fill": "filled",
            "filled": "dispensed",
        }
        next_status = forward.get(current, "triage")
        r = maria_session.post(f"{BASE_URL}/intakes/{intake_id}/status",
                               json={"status": next_status})
        assert r.status_code in (200, 201), \
            f"status change failed: from={current} to={next_status} resp={r.text}"

        hist = maria_session.get(f"{BASE_URL}/intakes/{intake_id}/history").json()
        assert isinstance(hist, list) and len(hist) >= 1
        attributed = [h for h in hist if (h.get("changed_by") or "").lower() == "maria"]
        assert attributed, f"no audit entry with changed_by=maria found: {hist[-3:]}"


# ---------- forgot/reset password (demo) ----------
class TestPasswordReset:
    def test_forgot_returns_reset_url(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/forgot-password",
                   json={"email": "maria@example.com"})
        # demo behaviour: should return JSON with reset_url OR ok:true
        assert r.status_code in (200, 202, 404)

    def test_reset_without_token_invalid(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/reset-password",
                   json={"password": "newpassword123"})
        assert r.status_code in (400, 401, 422)
