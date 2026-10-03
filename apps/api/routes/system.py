from fastapi import APIRouter

from ..config import get_settings
from ..engines import ENGINES
from ..schemas import SystemStatus
from ..services import ffmpeg_available, ollama_connected

router = APIRouter(prefix="/system", tags=["system"])


@router.get("", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    settings = get_settings()
    if settings.database_url.startswith("postgresql"):
        database = "postgresql"
    elif settings.database_url.startswith("sqlite"):
        database = "sqlite"
    else:
        database = "other"
    return SystemStatus(
        mode=settings.mediagrid_mode,
        paid_ai_allowed=settings.allow_paid_ai,
        database=database,
        ffmpeg=ffmpeg_available(),
        ollama="CONNECTED" if await ollama_connected() else "NOT_CONNECTED",
        dry_run=settings.dry_run,
        engines=list(ENGINES),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
