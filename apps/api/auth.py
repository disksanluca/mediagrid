import hashlib
import hmac
import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE_NAME = "mediagrid_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
_failed_attempts: dict[str, list[float]] = defaultdict(list)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


def auth_configured() -> bool:
    settings = get_settings()
    return bool(settings.mediagrid_admin_password and settings.mediagrid_session_secret)


def _signature(expiry: int) -> str:
    secret = get_settings().mediagrid_session_secret
    if not secret:
        raise RuntimeError("Session secret is missing")
    return hmac.new(secret.encode(), str(expiry).encode(), hashlib.sha256).hexdigest()


def is_authenticated(request: Request) -> bool:
    if not auth_configured():
        return get_settings().mediagrid_mode == "LOCAL"
    token = request.cookies.get(COOKIE_NAME, "")
    try:
        expiry_text, signature = token.split(".", maxsplit=1)
        expiry = int(expiry_text)
    except (ValueError, TypeError):
        return False
    return expiry > time.time() and hmac.compare_digest(signature, _signature(expiry))


@router.get("/session")
def session(request: Request) -> dict[str, bool]:
    return {"authenticated": is_authenticated(request), "login_required": auth_configured()}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, bool]:
    settings = get_settings()
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Administrator login is not configured")
    forwarded = request.headers.get("x-forwarded-for", "")
    address = forwarded.split(",", maxsplit=1)[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.time()
    attempts = [stamp for stamp in _failed_attempts[address] if now - stamp < 900]
    _failed_attempts[address] = attempts
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    if not secrets.compare_digest(payload.password, settings.mediagrid_admin_password or ""):
        attempts.append(now)
        raise HTTPException(status_code=401, detail="Invalid password")
    _failed_attempts.pop(address, None)
    expiry = int(now) + SESSION_SECONDS
    secure = bool(
        settings.mediagrid_public_url and settings.mediagrid_public_url.startswith("https://")
    )
    response.set_cookie(
        COOKIE_NAME,
        f"{expiry}.{_signature(expiry)}",
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=SESSION_SECONDS,
        path="/",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}
