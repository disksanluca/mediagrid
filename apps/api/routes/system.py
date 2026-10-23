import json
import subprocess
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from workers.render.narrative_3d import blender_executable

from ..config import get_settings
from ..database import get_db
from ..doctor import DoctorReport, run_doctor
from ..engines import ENGINES
from ..hardware import HardwareProfile, profile_hardware
from ..local_media import (
    installed_portuguese_voices,
    transcription_available,
    voice_available,
    voice_choice,
)
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


@router.get("/doctor", response_model=DoctorReport)
def system_doctor(internet: bool = False, db: Session = Depends(get_db)) -> DoctorReport:
    return run_doctor(db, check_internet=internet)


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


class BlenderChoice(BaseModel):
    path: str


class VoiceChoice(BaseModel):
    voice_name: str
    rate: int = Field(ge=-5, le=5)


@router.get("/voice")
def voice_status() -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(403, "Voice selection is local-desktop only")
    voice, rate = voice_choice()
    options = installed_portuguese_voices()
    return {"available": bool(options) and (voice is None or voice in options),
            "voices": list(options), "voice_name": voice, "rate": rate}


@router.put("/voice")
def set_voice(choice: VoiceChoice) -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(403, "Voice selection is local-desktop only")
    if choice.voice_name not in installed_portuguese_voices():
        raise HTTPException(422, "Choose an installed pt-BR voice")
    path = _setup_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    saved.update({"voice_name": choice.voice_name, "voice_rate": choice.rate})
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return voice_status()


@router.get("/blender")
def blender_status() -> dict:
    configured = blender_executable()
    return {"available": configured is not None,
            "path": str(configured) if configured else None,
            "required_version": "4.5 LTS"}


@router.put("/blender")
def set_blender(choice: BlenderChoice) -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(403, "Blender selection is local-desktop only")
    path = Path(choice.path)
    if (not path.is_absolute() or path.name.lower() != "blender.exe"
            or not path.is_file()):
        raise HTTPException(422, "Choose the official Blender 4.5 LTS blender.exe")
    path = path.resolve()
    try:
        result = subprocess.run([str(path), "--background", "--version"],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, "Blender could not be started") from exc
    if result.returncode or not result.stdout.startswith("Blender 4.5."):
        raise HTTPException(422, "MediaGrid 3D currently requires Blender 4.5 LTS")
    settings_path = _setup_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    saved["blender_path"] = str(path)
    temporary = settings_path.with_name(f".{settings_path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(settings_path)
    return {"available": True, "path": str(path),
            "required_version": "4.5 LTS"}
