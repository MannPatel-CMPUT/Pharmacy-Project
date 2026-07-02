"""Portal auth (bcrypt + JWT cookie). Users persisted in Postgres/SQLite.

Users used to live in ``fastapi/data/portal_users.json`` — on Render that file is
on ephemeral disk and got wiped every redeploy, silently losing every real
account created between deploys. This module now reads/writes ``portal_users`` in
whatever DB ``DATABASE_URL`` points at, and migrates any pre-existing JSON file
on first startup.
"""

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

from database import PortalPasswordReset, PortalUser, SessionLocal

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

# Legacy JSON file path — read only, used for the one-shot migration on first boot.
_REPO = Path(__file__).resolve().parent.parent
_DATA = _REPO / "data"
_portal_users_env = os.getenv("PORTAL_USERS_PATH")
if _portal_users_env:
    _LEGACY_USERS_FILE = Path(_portal_users_env).expanduser().resolve()
else:
    _LEGACY_USERS_FILE = _DATA / "portal_users.json"


def _user_to_dict(u: PortalUser) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "phone": u.phone or "",
        "password_hash": u.password_hash,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def migrate_json_users_if_needed() -> None:
    """
    One-time migration: if the ``portal_users`` DB table is empty and the legacy
    JSON file has rows, copy them in. Safe to call on every startup — no-op after
    the first successful run.
    """
    if not _LEGACY_USERS_FILE.exists():
        return
    try:
        raw = json.loads(_LEGACY_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    rows = raw.get("users") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        return
    with SessionLocal() as db:
        if db.query(PortalUser).count() > 0:
            return  # Already migrated (or DB already populated); leave alone.
        added = 0
        for r in rows:
            try:
                username = str(r["username"]).strip()
                email = str(r["email"]).strip().lower()
                phone = str(r.get("phone", "") or "").strip()
                password_hash = str(r["password_hash"])
                created_raw = r.get("created_at")
                try:
                    created_at = datetime.fromisoformat(str(created_raw))
                except (TypeError, ValueError):
                    created_at = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            db.add(
                PortalUser(
                    username=username,
                    email=email,
                    phone=phone,
                    password_hash=password_hash,
                    created_at=created_at,
                )
            )
            added += 1
        if added:
            db.commit()
            _logger.info("Migrated %s users from JSON file to portal_users table", added)
            print(f"[auth] migrated {added} users from portal_users.json → DB", flush=True)


def find_user_by_username(username: str) -> Optional[dict[str, Any]]:
    u = username.strip().lower()
    with SessionLocal() as db:
        row = (
            db.query(PortalUser)
            .filter(PortalUser.username.ilike(u))
            .first()
        )
        return _user_to_dict(row) if row else None


def find_user_by_email(email: str) -> Optional[dict[str, Any]]:
    e = email.strip().lower()
    with SessionLocal() as db:
        row = (
            db.query(PortalUser)
            .filter(PortalUser.email.ilike(e))
            .first()
        )
        return _user_to_dict(row) if row else None


def get_all_users() -> list[dict[str, Any]]:
    """Return all users for pharmacist dropdown."""
    with SessionLocal() as db:
        rows = db.query(PortalUser).order_by(PortalUser.username.asc()).all()
        return [_user_to_dict(u) for u in rows]


def create_user(username: str, email: str, phone: str, password: str) -> dict[str, Any]:
    un = username.strip()
    em = email.strip().lower()
    with _lock, SessionLocal() as db:
        if db.query(PortalUser).filter(PortalUser.username.ilike(un)).first():
            raise ValueError("USERNAME_TAKEN")
        if db.query(PortalUser).filter(PortalUser.email.ilike(em)).first():
            raise ValueError("EMAIL_TAKEN")
        row = PortalUser(
            username=un,
            email=email.strip(),
            phone=phone.strip(),
            password_hash=_hash_password(password),
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _user_to_dict(row)


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
    normalized = email.strip().lower()
    with _lock, SessionLocal() as db:
        # Drop any prior pending resets for this email so only one is active.
        db.query(PortalPasswordReset).filter(
            PortalPasswordReset.email == normalized
        ).delete(synchronize_session=False)
        db.add(PortalPasswordReset(email=normalized, token=token, exp=exp))
        db.commit()
    return token


def reset_password_with_token(token: str, new_password: str) -> bool:
    now = datetime.now(timezone.utc)
    with _lock, SessionLocal() as db:
        reset = (
            db.query(PortalPasswordReset)
            .filter(PortalPasswordReset.token == token)
            .first()
        )
        if not reset:
            return False
        exp = reset.exp
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            db.delete(reset)
            db.commit()
            return False
        user = (
            db.query(PortalUser)
            .filter(PortalUser.email.ilike(reset.email))
            .first()
        )
        if not user:
            return False
        user.password_hash = _hash_password(new_password)
        db.delete(reset)
        db.commit()
        return True
