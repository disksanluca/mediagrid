import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Asset, Job, JobStatus, new_id
from ..schemas import AssetRead
from ..services import record_event

router = APIRouter(prefix="/assets", tags=["assets"])
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


@router.get("", response_model=list[AssetRead])
def list_assets(db: Session = Depends(get_db)) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.created_at.desc())))


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def upload_asset(
    file: UploadFile = File(...),
    rights_status: str = Form("UNKNOWN"),
    creator: str | None = Form(None),
    license_name: str | None = Form(None),
    commercial_use: bool = Form(False),
    db: Session = Depends(get_db),
) -> Asset:
    if rights_status not in {"UNKNOWN", "OWNED", "LICENSED", "RESTRICTED"}:
        raise HTTPException(422, "Invalid rights status")
    name = Path(file.filename or "arquivo").name[:240]
    asset = Asset(
        id=new_id(),
        name=name,
        media_type=(file.content_type or "application/octet-stream")[:40],
        path="",
        sha256="",
        rights_status=rights_status,
        creator=creator,
        license_name=license_name,
        commercial_use=commercial_use,
    )
    folder = get_settings().mediagrid_data_dir / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / asset.id
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File exceeds 500 MB limit")
                digest.update(chunk)
                output.write(chunk)
        if not size:
            raise HTTPException(422, "Empty file")
        existing = db.scalar(select(Asset).where(Asset.sha256 == digest.hexdigest()))
        if existing:
            target.unlink(missing_ok=True)
            return existing
        asset.sha256 = digest.hexdigest()
        asset.path = str(target.resolve())
        asset.metadata_json = {"size_bytes": size}
        db.add(asset)
        db.flush()
        record_event(db, "ASSET_IMPORTED", "asset", asset.id, after={"name": name, "size": size})
        db.commit()
        db.refresh(asset)
        return asset
    except Exception:
        target.unlink(missing_ok=True)
        raise


@router.get("/{asset_id}/file")
def download_asset(asset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    path = get_settings().mediagrid_data_dir / "assets" / asset.id
    if not path.is_file():
        raise HTTPException(404, "Asset file is missing")
    return FileResponse(path, media_type=asset.media_type, filename=asset.name)


@router.post("/{asset_id}/transcribe", status_code=status.HTTP_202_ACCEPTED)
def transcribe_asset(asset_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    if not (asset.media_type.startswith("audio/") or asset.media_type.startswith("video/")):
        raise HTTPException(422, "Only audio and video can be transcribed")
    active = db.scalar(
        select(Job).where(
            Job.job_type == "TRANSCRIBE",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            Job.payload["asset_id"].as_string() == asset_id,
        )
    )
    if active:
        raise HTTPException(409, "Transcription is already queued")
    job = Job(job_type="TRANSCRIBE", payload={"asset_id": asset_id})
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "status": job.status}


@router.get("/{asset_id}/transcript")
def get_transcript(asset_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    if db.get(Asset, asset_id) is None:
        raise HTTPException(404, "Asset not found")
    path = get_settings().mediagrid_data_dir / "transcripts" / f"{asset_id}.txt"
    if not path.is_file():
        raise HTTPException(404, "Transcript is not available")
    return PlainTextResponse(path.read_text(encoding="utf-8"))
