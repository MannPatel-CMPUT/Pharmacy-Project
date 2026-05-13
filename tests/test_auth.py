"""Auth cookie must be attached to the same response object that is returned."""

import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_signup_sets_session_cookie():
    sfx = uuid.uuid4().hex[:10]
    r = client.post(
        "/api/auth/signup",
        json={
            "username": f"user_{sfx}",
            "email": f"{sfx}@example.com",
            "phone": "(555) 123-4567",
            "password": "hunter2long",
        },
    )
    assert r.status_code == 201, r.text
    assert "pharma_auth" in r.cookies or any(
        h[0].lower() == b"set-cookie" and b"pharma_auth" in h[1] for h in r.headers.raw
    )


def test_login_sets_session_cookie():
    sfx = uuid.uuid4().hex[:10]
    client.post(
        "/api/auth/signup",
        json={
            "username": f"log_{sfx}",
            "email": f"log_{sfx}@example.com",
            "phone": "5559876543",
            "password": "password1234",
        },
    )
    r = client.post(
        "/api/auth/login",
        json={"username": f"log_{sfx}", "password": "password1234"},
    )
    assert r.status_code == 200, r.text
    assert "pharma_auth" in r.cookies or any(
        h[0].lower() == b"set-cookie" and b"pharma_auth" in h[1] for h in r.headers.raw
    )
