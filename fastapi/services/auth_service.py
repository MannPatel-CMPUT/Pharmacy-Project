"""File-backed portal auth (bcrypt + JWT cookie). Used when Pharma Checker UI is served from FastAPI."""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Request

_logger = logging.getLogger(__name__)
_ENV = os.getenv("ENV", "").lower()
_IS_PRODUCTION = _ENV == "production"
_DEV_JWT_DEFAULTS = frozenset({"dev-only-change-in-production", "dev-jwt-change-me"})
_raw_jwt = os.getenv("JWT_SECRET")
if _IS_PRODUCTION:
    if not _raw_jwt or _raw_jwt in _DEV_JWT_DEFAULTS:
        raise RuntimeError("JWT_SECRET must be set in production")
    JWT_SECRET = _raw_jwt
else:
    if _raw_jwt:
        JWT_SECRET = _raw_jwt
    else:
        JWT_SECRET = "dev-only-change-in-production"
        _logger.warning("JWT_SECRET unset; using dev default (not for production).")
JWT_ALG = "HS256"
COOKIE_NAME = "pharma_auth"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60

_lock = threading.Lock()

_REPO = Path(__file__).resolve().parent.parent
_DATA = _REPO / "data"
_portal_users_env = os.getenv("PORTAL_USERS_PATH")
if _portal_users_env:
    _USERS_FILE = Path(_portal_users_env).expanduser().resolve()
else:
    _USERS_FILE = _DATA / "portal_users.json"
_RESETS_FILE = _DATA / "password_resets.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_users() -> dict[str, Any]:
    raw = _read_json(_USERS_FILE, {"users": []})
    if not isinstance(raw, dict) or not isinstance(raw.get("users"), list):
        return {"users": []}
    return raw


def _save_users(data: dict[str, Any]) -> None:
    _write_json(_USERS_FILE, data)


def _load_resets() -> dict[str, Any]:
    raw = _read_json(_RESETS_FILE, {"resets": []})
    if not isinstance(raw, dict) or not isinstance(raw.get("resets"), list):
        return {"resets": []}
    return raw


def _save_resets(data: dict[str, Any]) -> None:
    _write_json(_RESETS_FILE, data)


def find_user_by_username(username: str) -> Optional[dict[str, Any]]:
    u = username.strip().lower()
    for row in _load_users()["users"]:
        if str(row.get("username", "")).lower() == u:
            return row
    return None


def find_user_by_email(email: str) -> Optional[dict[str, Any]]:
    e = email.strip().lower()
    for row in _load_users()["users"]:
        if str(row.get("email", "")).lower() == e:
            return row
    return None


def create_user(username: str, email: str, phone: str, password: str) -> dict[str, Any]:
    with _lock:
        data = _load_users()
        un = username.strip()
        if any(str(x.get("username", "")).lower() == un.lower() for x in data["users"]):
            raise ValueError("USERNAME_TAKEN")
        em = email.strip().lower()
        if any(str(x.get("email", "")).lower() == em for x in data["users"]):
            raise ValueError("EMAIL_TAKEN")
        uid = max((int(x.get("id", 0)) for x in data["users"]), default=0) + 1
        row = {
            "id": uid,
            "username": un,
            "email": email.strip(),
            "phone": phone.strip(),
            "password_hash": _hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data["users"].append(row)
        _save_users(data)
        return row


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "u": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALG],
            # Node portal signs `sub` as a number; PyJWT >=2.10 enforces string `sub`.
            # We only rely on `u` (username), so relax that one check.
            options={"verify_sub": False},
        )
    except jwt.PyJWTError:
        return None


def verify_session_cookie(request: Request) -> bool:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return False
    payload = decode_token(raw)
    if not payload or "u" not in payload:
        return False
    user = find_user_by_username(str(payload["u"]))
    return user is not None


def set_auth_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def create_password_reset(email: str) -> Optional[str]:
    """Returns reset token if user exists, else None (caller still responds generically)."""
    user = find_user_by_email(email)
    if not user:
        return None
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    with _lock:
        data = _load_resets()
        data["resets"] = [r for r in data["resets"] if str(r.get("email", "")).lower() != email.strip().lower()]
        data["resets"].append(
            {
                "email": email.strip().lower(),
                "token": token,
                "exp": exp.isoformat(),
            }
        )
        _save_resets(data)
    return token


def reset_password_with_token(token: str, new_password: str) -> bool:
    with _lock:
        data = _load_resets()
        now = datetime.now(timezone.utc)
        found = None
        for r in data["resets"]:
            if r.get("token") != token:
                continue
            try:
                exp = datetime.fromisoformat(str(r.get("exp", "")))
            except ValueError:
                continue
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                continue
            found = r
            break
        if not found:
            return False
        email = str(found["email"])
        users_data = _load_users()
        updated = False
        for u in users_data["users"]:
            if str(u.get("email", "")).lower() == email:
                u["password_hash"] = _hash_password(new_password)
                updated = True
                break
        if not updated:
            return False
        _save_users(users_data)
        data["resets"] = [r for r in data["resets"] if r.get("token") != token]
        _save_resets(data)
        return True
