from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .migrate import main as migrate
from .routes import channels, jobs, projects, system


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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

for router in (channels.router, projects.router, jobs.router, system.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "MediaGrid", "docs": "/docs", "health": "/api/v1/system/health"}
