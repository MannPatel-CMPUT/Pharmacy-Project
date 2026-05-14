from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from schemas.auth import ForgotPasswordBody, LoginBody, ResetPasswordBody, SignupBody
from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
def signup(body: SignupBody):
    digits = "".join(c for c in body.phone if c.isdigit())
    if len(digits) < 10:
        raise HTTPException(status_code=400, detail="Enter a phone number with at least 10 digits.")
    try:
        row = auth_service.create_user(
            body.username,
            body.email,
            digits,
            body.password,
        )
    except ValueError as e:
        if str(e) == "USERNAME_TAKEN":
            raise HTTPException(status_code=409, detail="That username is already taken.") from e
        if str(e) == "EMAIL_TAKEN":
            raise HTTPException(status_code=409, detail="That email is already registered.") from e
        raise
    token = auth_service.create_token(int(row["id"]), row["username"])
    resp = JSONResponse({"ok": True, "username": row["username"]}, status_code=201)
    auth_service.set_auth_cookie(resp, token)
    return resp


@router.post("/login")
def login(body: LoginBody):
    user = auth_service.find_user_by_username(body.username)
    if not user or not auth_service.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth_service.create_token(int(user["id"]), user["username"])
    resp = JSONResponse({"ok": True, "username": user["username"]})
    auth_service.set_auth_cookie(resp, token)
    return resp


@router.post("/logout")
def logout():
    resp = JSONResponse({"ok": True})
    auth_service.clear_auth_cookie(resp)
    return resp


@router.get("/me")
def me(request: Request):
    raw = request.cookies.get(auth_service.COOKIE_NAME)
    if not raw:
        return JSONResponse({"user": None}, status_code=401)
    payload = auth_service.decode_token(raw)
    if not payload:
        r = JSONResponse({"user": None}, status_code=401)
        auth_service.clear_auth_cookie(r)
        return r
    user = auth_service.find_user_by_username(str(payload.get("u", "")))
    if not user:
        r = JSONResponse({"user": None}, status_code=401)
        auth_service.clear_auth_cookie(r)
        return r
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "phone": user["phone"],
        }
    }


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordBody, request: Request):
    token = auth_service.create_password_reset(body.email)
    # Prefer X-Forwarded-* (set by upstream reverse proxy) so the link points to
    # the public host, not 127.0.0.1.
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    fwd_proto = request.headers.get("x-forwarded-proto", "http")
    base = f"{fwd_proto}://{fwd_host}" if fwd_host else str(request.base_url).rstrip("/")
    out: dict = {"ok": True, "message": "If an account exists for that email, you can reset your password below."}
    if token:
        out["reset_url"] = f"{base}/reset-password?token={token}"
    return out


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody):
    ok = auth_service.reset_password_with_token(body.token, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    return {"ok": True}
