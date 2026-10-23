from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth
from .config import Settings, get_settings
from .migrate import main as migrate
from .routes import (
    assets,
    channels,
    clips,
    football,
    geo,
    jobs,
    knowledge,
    motion_ads,
    narrative_3d,
    politics,
    projects,
    system,
    transcripts,
    trends,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    validate_runtime_config(settings)
    migrate()
    structlog.get_logger().info("mediagrid_started")
    yield


def validate_runtime_config(settings: Settings) -> None:
    """Reject unsafe server configuration before any migration or request."""
    if settings.mediagrid_mode == "LOCAL":
        return
    if not (settings.mediagrid_admin_password and settings.mediagrid_session_secret):
        raise RuntimeError(
            "Server mode requires MEDIAGRID_ADMIN_PASSWORD and MEDIAGRID_SESSION_SECRET"
        )
    if not settings.database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Server mode requires PostgreSQL via postgresql+psycopg://")
    if not (settings.mediagrid_public_url or "").startswith("https://"):
        raise RuntimeError("Server mode requires an HTTPS MEDIAGRID_PUBLIC_URL")
    if settings.allow_paid_ai or not settings.dry_run:
        raise RuntimeError("Server mode requires ALLOW_PAID_AI=false and DRY_RUN=true")
    if not settings.mediagrid_server_experimental:
        raise RuntimeError("Server worker protocol is unfinished; server mode is experimental")


app = FastAPI(
    title="MediaGrid Core API",
    version="0.1.0",
    description="Local-first content operating system",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if get_settings().mediagrid_mode == "LOCAL" and path.startswith("/api/v1/"):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in {
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
        }:
            return JSONResponse({"detail": "Invalid local origin"}, status_code=403)
    public_paths = {"/", "/api/v1/system/health", "/api/v1/auth/login", "/api/v1/auth/session"}
    if path.startswith("/api/v1/") and path not in public_paths:
        if not auth.is_authenticated(request):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            public_url = get_settings().mediagrid_public_url
            if origin and public_url and origin.rstrip("/") != public_url.rstrip("/"):
                return JSONResponse({"detail": "Invalid origin"}, status_code=403)
    return await call_next(request)


for router in (
    auth.router,
    channels.router,
    projects.router,
    politics.router,
    geo.router,
    trends.router,
    motion_ads.router,
    assets.router,
    transcripts.router,
    clips.router,
    football.router,
    knowledge.router,
    narrative_3d.router,
    jobs.router,
    system.router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "MediaGrid", "docs": "/docs", "health": "/api/v1/system/health"}
