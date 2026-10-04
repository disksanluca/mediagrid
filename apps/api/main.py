from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth
from .config import get_settings
from .migrate import main as migrate
from .routes import channels, jobs, projects, system


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.mediagrid_mode != "LOCAL" and not auth.auth_configured():
        raise RuntimeError(
            "Public mode requires MEDIAGRID_ADMIN_PASSWORD and MEDIAGRID_SESSION_SECRET"
        )
    migrate()
    structlog.get_logger().info("mediagrid_started")
    yield


app = FastAPI(
    title="MediaGrid Core API",
    version="0.1.0",
    description="Local-first content operating system",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
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


for router in (auth.router, channels.router, projects.router, jobs.router, system.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "MediaGrid", "docs": "/docs", "health": "/api/v1/system/health"}
