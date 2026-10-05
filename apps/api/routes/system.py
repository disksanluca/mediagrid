import json
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import get_settings
from ..engines import ENGINES
from ..hardware import HardwareProfile, profile_hardware
from ..local_media import transcription_available, voice_available
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
        tts="AVAILABLE" if voice_available() else "NOT_CONFIGURED",
        transcription="AVAILABLE" if transcription_available() else "NOT_CONFIGURED",
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/hardware", response_model=HardwareProfile)
def hardware_profile() -> HardwareProfile:
    return profile_hardware()


class SetupState(BaseModel):
    complete: bool
    profile: Literal["LIGHT", "BALANCED", "QUALITY", "HIGH_PERFORMANCE"] | None = None
    data_dir: str


class SetupChoice(BaseModel):
    profile: Literal["LIGHT", "BALANCED", "QUALITY", "HIGH_PERFORMANCE"]


def _setup_path():
    return get_settings().mediagrid_data_dir / "settings.json"


@router.get("/setup", response_model=SetupState)
def setup_status() -> SetupState:
    path = _setup_path()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    return SetupState(
        complete=settings.get("setup_complete") is True,
        profile=settings.get("hardware_profile"),
        data_dir=str(get_settings().mediagrid_data_dir.resolve()),
    )


@router.post("/setup", response_model=SetupState)
def complete_setup(choice: SetupChoice) -> SetupState:
    path = _setup_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
    existing.update({"setup_complete": True, "hardware_profile": choice.profile})
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return setup_status()
