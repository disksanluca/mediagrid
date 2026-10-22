"""Validation and staging for user supplied scene media."""

import hashlib
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Asset

RENDERABLE_MEDIA = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "video/mp4": ("video", ".mp4"),
}
RENDERABLE_AUDIO = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
}


def scene_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(422, f"Mídia {asset_id} não encontrada na biblioteca.")
    if asset.media_type not in RENDERABLE_MEDIA:
        raise HTTPException(422, f"Formato de mídia não suportado na cena: {asset.media_type}.")
    if asset.rights_status not in {"OWNED", "LICENSED"}:
        raise HTTPException(422, f"Confirme os direitos de uso de {asset.name} antes do render.")
    if asset.rights_status == "LICENSED" and not asset.license_name:
        raise HTTPException(422, f"Registre a licença de {asset.name} antes do render.")
    source = get_settings().mediagrid_data_dir / "assets" / asset.id
    if not source.is_file():
        raise HTTPException(422, f"Arquivo de mídia ausente: {asset.name}.")
    return asset


def sound_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(422, f"Áudio {asset_id} não encontrado na biblioteca.")
    if asset.media_type not in RENDERABLE_AUDIO:
        raise HTTPException(422, f"Formato de áudio não suportado: {asset.media_type}.")
    if asset.rights_status not in {"OWNED", "LICENSED"}:
        raise HTTPException(422, f"Confirme os direitos de uso de {asset.name} antes do render.")
    if asset.rights_status == "LICENSED" and not asset.license_name:
        raise HTTPException(422, f"Registre a licença de {asset.name} antes do render.")
    if not (get_settings().mediagrid_data_dir / "assets" / asset.id).is_file():
        raise HTTPException(422, f"Arquivo de áudio ausente: {asset.name}.")
    return asset


def validate_scene_assets(db: Session, scenes: list) -> None:
    for scene in scenes:
        asset_id = scene.asset_id if hasattr(scene, "asset_id") else scene.get("asset_id")
        start = (
            scene.clip_start_seconds
            if hasattr(scene, "clip_start_seconds")
            else scene.get("clip_start_seconds", 0)
        )
        end = (
            scene.clip_end_seconds
            if hasattr(scene, "clip_end_seconds")
            else scene.get("clip_end_seconds")
        )
        if start < 0 or (end is not None and end <= start):
            raise HTTPException(422, "Intervalo do clipe inválido.")
        if (start > 0 or end is not None) and not asset_id:
            raise HTTPException(422, "Escolha um MP4 antes de definir o trecho.")
        if asset_id:
            asset = scene_asset(db, asset_id)
            if (start > 0 or end is not None) and asset.media_type != "video/mp4":
                raise HTTPException(422, "O intervalo de trecho só pode ser usado com MP4.")


def stage_scene_assets(
    db: Session, tracks: list[dict], public_dir: Path
) -> dict[str, dict[str, str]]:
    """Copy selected assets into Remotion's per-job public directory."""
    result = {}
    public_dir.mkdir(parents=True, exist_ok=True)
    for asset_id in {item.get("asset_id") for item in tracks if item.get("asset_id")}:
        asset = scene_asset(db, asset_id)
        source = get_settings().mediagrid_data_dir / "assets" / asset.id
        kind, extension = RENDERABLE_MEDIA[asset.media_type]
        target = public_dir / f"{asset.id}{extension}"
        digest = hashlib.sha256()
        with source.open("rb") as original, target.open("wb") as staged:
            while chunk := original.read(1024 * 1024):
                digest.update(chunk)
                staged.write(chunk)
        if digest.hexdigest() != asset.sha256:
            target.unlink(missing_ok=True)
            raise ValueError(f"Arquivo de mídia foi alterado após a importação: {asset.name}")
        result[asset.id] = {"media_kind": kind, "media_file": target.name}
    return result


def stage_sound_assets(
    db: Session, asset_ids: set[str], public_dir: Path
) -> dict[str, str]:
    """Stage and hash-check each local sound before passing it to Remotion."""
    result: dict[str, str] = {}
    public_dir.mkdir(parents=True, exist_ok=True)
    for asset_id in asset_ids:
        asset = sound_asset(db, asset_id)
        source = get_settings().mediagrid_data_dir / "assets" / asset.id
        target = public_dir / f"{asset.id}{RENDERABLE_AUDIO[asset.media_type]}"
        digest = hashlib.sha256()
        with source.open("rb") as original, target.open("wb") as staged:
            while chunk := original.read(1024 * 1024):
                digest.update(chunk)
                staged.write(chunk)
        if digest.hexdigest() != asset.sha256:
            target.unlink(missing_ok=True)
            raise ValueError(f"Áudio alterado após a importação: {asset.name}")
        result[asset.id] = target.name
    return result
