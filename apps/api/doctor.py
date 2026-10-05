"""Read-only local diagnostics shared by API, desktop UI and technical CLI."""

import importlib.util
import json
import shutil
import socket
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .hardware import profile_hardware
from .local_media import transcription_available, voice_available
from .services import local_ollama_url


class DoctorCheck(BaseModel):
    id: str
    name: str
    status: str
    detail: str


class DoctorReport(BaseModel):
    checked_at: datetime
    checks: list[DoctorCheck]


def _storage_check(folder: Path) -> DoctorCheck:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
        return DoctorCheck(
            id="storage", name="Armazenamento", status="READY", detail=str(folder.resolve())
        )
    except OSError as exc:
        return DoctorCheck(id="storage", name="Armazenamento", status="ERROR", detail=str(exc))


def _internet_check() -> DoctorCheck:
    try:
        with socket.create_connection(("registry.npmjs.org", 443), timeout=2):
            pass
        return DoctorCheck(
            id="internet",
            name="Internet",
            status="READY",
            detail="Disponível para downloads opcionais",
        )
    except OSError:
        return DoctorCheck(
            id="internet",
            name="Internet",
            status="OPTIONAL",
            detail="Offline; o uso local continua disponível",
        )


def _ollama_check() -> DoctorCheck:
    base_url = local_ollama_url()
    if base_url is None:
        return DoctorCheck(
            id="ollama",
            name="Ollama",
            status="MISSING",
            detail="Configure apenas localhost para IA local",
        )
    try:
        with httpx.Client(timeout=0.7, trust_env=False) as client:
            response = client.get(f"{base_url}/api/tags")
            response.raise_for_status()
        return DoctorCheck(
            id="ollama", name="Ollama", status="READY", detail="Serviço de IA local responde"
        )
    except httpx.HTTPError:
        return DoctorCheck(
            id="ollama",
            name="Ollama",
            status="OPTIONAL",
            detail="Ollama local está desligado ou não instalado",
        )


def run_doctor(db: Session, *, check_internet: bool = False) -> DoctorReport:
    checks: list[DoctorCheck] = []
    try:
        db.execute(text("SELECT 1"))
        checks.append(
            DoctorCheck(id="database", name="Banco local", status="READY", detail="SQLite responde")
        )
    except Exception as exc:
        checks.append(
            DoctorCheck(id="database", name="Banco local", status="ERROR", detail=str(exc))
        )
    checks.append(_storage_check(get_settings().mediagrid_data_dir))
    for executable in ("ffmpeg", "ffprobe"):
        available = shutil.which(executable) is not None
        checks.append(
            DoctorCheck(
                id=executable,
                name=executable.upper(),
                status="READY" if available else "MISSING",
                detail="Disponível localmente"
                if available
                else "Necessário para vídeo e áudio; instale localmente",
            )
        )
    checks.append(_ollama_check())
    comfy_available = False
    try:
        with socket.create_connection(("127.0.0.1", 8188), timeout=0.3):
            comfy_available = True
    except OSError:
        pass
    checks.append(
        DoctorCheck(
            id="comfyui",
            name="ComfyUI",
            status="READY" if comfy_available else "OPTIONAL",
            detail="Serviço local responde"
            if comfy_available
            else "Geração de imagens opcional não instalada",
        )
    )
    for identifier, name, available in (
        ("voice", "Voz offline", voice_available()),
        ("transcription", "Transcrição offline", transcription_available()),
        ("whisperx", "WhisperX", importlib.util.find_spec("whisperx") is not None),
        ("chatterbox", "Chatterbox", importlib.util.find_spec("chatterbox") is not None),
    ):
        checks.append(
            DoctorCheck(
                id=identifier,
                name=name,
                status="READY" if available else "OPTIONAL",
                detail="Disponível neste computador"
                if available
                else "Módulo local opcional não instalado",
            )
        )
    hardware = profile_hardware()
    checks.append(
        DoctorCheck(
            id="gpu",
            name="GPU",
            status="READY" if hardware.gpu else "OPTIONAL",
            detail=hardware.gpu or "Sem GPU detectada; perfil LIGHT recomendado",
        )
    )
    checks.append(
        DoctorCheck(
            id="disk",
            name="Espaço livre",
            status="READY" if hardware.disk_free_gb >= 5 else "ERROR",
            detail=f"{hardware.disk_free_gb} GB livres na unidade de dados",
        )
    )
    if check_internet:
        checks.append(_internet_check())
    return DoctorReport(checked_at=datetime.now(UTC), checks=checks)


def main() -> None:
    from .migrate import main as migrate

    migrate()
    with SessionLocal() as db:
        print(
            json.dumps(
                run_doctor(db, check_internet=True).model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
