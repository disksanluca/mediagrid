import hashlib
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..ingestion import probe_video, sha256_file
from ..models import ACTIVE_JOB_STATUSES, Asset, Job, JobStatus, UploadSession, new_id
from ..schemas import AssetRead, AssetRightsUpdate
from ..services import record_event

router = APIRouter(prefix="/assets", tags=["assets"])
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_RESUMABLE_BYTES = 20 * 1024 * 1024 * 1024
MAX_CHUNK_BYTES = 8 * 1024 * 1024


class UploadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    media_type: str = "video/mp4"
    size_bytes: int = Field(gt=0, le=MAX_RESUMABLE_BYTES)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    rights_status: str = "UNKNOWN"
    source_url: str | None = Field(default=None, max_length=2000)
    creator: str | None = Field(default=None, max_length=240)
    license_name: str | None = Field(default=None, max_length=120)
    commercial_use: bool = False


def upload_paths(upload_id: str) -> tuple[Path, Path]:
    folder = get_settings().mediagrid_data_dir / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{upload_id}.part", folder / f"{upload_id}.lock"


@contextmanager
def upload_lock(path: Path):
    fd = None
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError as exc:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if attempt or age < 3600:
                raise HTTPException(409, "Upload is already being written") from exc
            path.unlink(missing_ok=True)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            path.unlink(missing_ok=True)


def upload_state(session: UploadSession) -> dict:
    return {
        "id": session.id, "name": session.name, "size_bytes": session.expected_size,
        "received_bytes": session.received_bytes, "status": session.status,
        "asset_id": session.asset_id, "error": session.error,
        "rights_status": session.rights_status, "creator": session.creator,
        "source_url": session.source_url, "license_name": session.license_name,
        "commercial_use": session.commercial_use,
    }


def proxy_job(db: Session, asset: Asset) -> Job | None:
    if (asset.metadata_json or {}).get("proxy_sha256"):
        return None
    existing = db.scalar(
        select(Job).where(
            Job.job_type == "PROXY",
            Job.payload["asset_id"].as_string() == asset.id,
        ).order_by(Job.created_at.desc()).limit(1)
    )
    if existing:
        return existing
    job = Job(job_type="PROXY", payload={"asset_id": asset.id, "sha256": asset.sha256})
    db.add(job)
    db.flush()
    asset.metadata_json = {**(asset.metadata_json or {}), "ingest_status": (
        "PROXY_QUEUED" if job.status == JobStatus.QUEUED.value else "WAITING_FOR_WORKER")}
    record_event(db, f"PROXY_{job.status}", "job", job.id,
                 after={"asset_id": asset.id})
    return job


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
def create_upload(payload: UploadCreate, db: Session = Depends(get_db)) -> dict:
    if payload.media_type != "video/mp4" or not payload.name.lower().endswith(".mp4"):
        raise HTTPException(422, "Resumable import currently accepts MP4 only")
    if payload.rights_status not in {"OWNED", "LICENSED", "UNKNOWN", "RESTRICTED"}:
        raise HTTPException(422, "Invalid rights status")
    if payload.rights_status == "LICENSED" and not payload.license_name:
        raise HTTPException(422, "License name is required")
    if payload.source_url and not payload.source_url.startswith(("https://", "http://")):
        raise HTTPException(422, "Source URL must be HTTP or HTTPS")
    folder = get_settings().mediagrid_data_dir / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(folder).free < payload.size_bytes + 256 * 1024 * 1024:
        raise HTTPException(507, "Not enough local storage for this original")
    session = UploadSession(
        name=Path(payload.name).name, media_type=payload.media_type,
        expected_size=payload.size_bytes, expected_sha256=payload.sha256,
        received_bytes=0, status="OPEN", rights_status=payload.rights_status,
        source_url=payload.source_url,
        creator=payload.creator, license_name=payload.license_name,
        commercial_use=payload.commercial_use,
    )
    db.add(session)
    db.flush()
    part, _ = upload_paths(session.id)
    part.touch(exist_ok=False)
    record_event(db, "UPLOAD_CREATED", "upload", session.id,
                 after={"name": session.name, "size_bytes": session.expected_size})
    db.commit()
    return upload_state(session)


@router.get("/uploads/{upload_id}")
def read_upload(upload_id: str, db: Session = Depends(get_db)) -> dict:
    session = db.get(UploadSession, upload_id)
    if session is None:
        raise HTTPException(404, "Upload not found")
    if session.status == "OPEN":
        part, lock = upload_paths(upload_id)
        if not lock.exists() and part.is_file():
            actual = part.stat().st_size
            if actual > session.expected_size:
                session.status = "FAILED"
                session.error = "Partial file exceeds expected size"
            elif actual != session.received_bytes:
                session.received_bytes = actual
            db.commit()
    return upload_state(session)


@router.put("/uploads/{upload_id}")
async def write_upload(
    upload_id: str, request: Request,
    upload_offset: int = Header(ge=0, alias="Upload-Offset"),
    db: Session = Depends(get_db),
) -> dict:
    chunk = bytearray()
    async for block in request.stream():
        if len(chunk) + len(block) > MAX_CHUNK_BYTES:
            raise HTTPException(413, "Chunk exceeds 8 MiB")
        chunk.extend(block)
    if not chunk:
        raise HTTPException(422, "Empty chunk")
    session = db.get(UploadSession, upload_id)
    if session is None:
        raise HTTPException(404, "Upload not found")
    part, lock = upload_paths(upload_id)
    with upload_lock(lock):
        if session.status != "OPEN" or not part.is_file():
            raise HTTPException(409, "Upload is not open")
        actual = part.stat().st_size
        if actual > session.expected_size or upload_offset + len(chunk) > session.expected_size:
            raise HTTPException(422, "Chunk exceeds declared file size")
        if upload_offset < actual and upload_offset + len(chunk) <= actual:
            with part.open("rb") as source:
                source.seek(upload_offset)
                if source.read(len(chunk)) != chunk:
                    raise HTTPException(409, "Repeated chunk differs from saved bytes")
        elif upload_offset == actual:
            with part.open("ab") as target:
                target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            actual += len(chunk)
        else:
            raise HTTPException(409, f"Resume from byte {actual}")
        session.received_bytes = actual
        db.commit()
    return upload_state(session)


@router.post("/uploads/{upload_id}/complete")
def complete_upload(upload_id: str, db: Session = Depends(get_db)) -> dict:
    session = db.get(UploadSession, upload_id)
    if session is None:
        raise HTTPException(404, "Upload not found")
    if session.status == "COMPLETE" and session.asset_id:
        asset = db.get(Asset, session.asset_id)
        if asset is None:
            raise HTTPException(409, "Completed upload references a missing asset")
        job = proxy_job(db, asset)
        db.commit()
        return {"upload": upload_state(session), "asset_id": asset.id,
                "proxy_job_id": job.id if job else None}
    part, lock = upload_paths(upload_id)
    with upload_lock(lock):
        if session.status != "OPEN":
            raise HTTPException(409, "Upload is not open")
        target = get_settings().mediagrid_data_dir / "assets" / session.id
        source = part if part.is_file() else target
        if not source.is_file() or source.stat().st_size != session.expected_size:
            raise HTTPException(409, "Upload is incomplete")
        digest = sha256_file(source)
        if session.expected_sha256 and digest != session.expected_sha256:
            session.status = "FAILED"
            session.error = "SHA-256 does not match the declared original"
            db.commit()
            raise HTTPException(422, session.error)
        try:
            probe = probe_video(source)
        except ValueError as exc:
            session.status = "FAILED"
            session.error = str(exc)
            db.commit()
            raise HTTPException(422, session.error) from exc
        asset = db.scalar(select(Asset).where(Asset.sha256 == digest))
        if asset is None:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source == part:
                os.replace(part, target)
            asset = Asset(
                id=session.id, name=session.name, media_type="video/mp4",
                path=str(target.resolve()), sha256=digest,
                rights_status=session.rights_status, creator=session.creator,
                source_url=session.source_url,
                license_name=session.license_name,
                commercial_use=session.commercial_use,
                metadata_json={"size_bytes": session.expected_size, **probe,
                               "ingest_status": "PROXY_QUEUED"},
            )
            db.add(asset)
            db.flush()
            record_event(db, "ASSET_IMPORTED", "asset", asset.id,
                         after={"name": asset.name, "sha256": digest,
                                "size_bytes": session.expected_size})
        elif source == part:
            part.unlink(missing_ok=True)
        session.status = "COMPLETE"
        session.asset_id = asset.id
        session.received_bytes = session.expected_size
        job = proxy_job(db, asset)
        db.commit()
    return {"upload": upload_state(session), "asset_id": asset.id,
            "proxy_job_id": job.id if job else None}


@router.get("", response_model=list[AssetRead])
def list_assets(db: Session = Depends(get_db)) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.created_at.desc())))


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def upload_asset(
    file: UploadFile = File(...),
    rights_status: str = Form("UNKNOWN"),
    source_url: str | None = Form(None),
    creator: str | None = Form(None),
    license_name: str | None = Form(None),
    commercial_use: bool = Form(False),
    db: Session = Depends(get_db),
) -> Asset:
    if rights_status not in {"UNKNOWN", "OWNED", "LICENSED", "RESTRICTED"}:
        raise HTTPException(422, "Invalid rights status")
    if rights_status == "LICENSED" and not license_name:
        raise HTTPException(422, "License name is required for licensed media")
    if source_url and not source_url.startswith(("https://", "http://")):
        raise HTTPException(422, "Source URL must be HTTP or HTTPS")
    name = Path(file.filename or "arquivo").name[:240]
    asset = Asset(
        id=new_id(),
        name=name,
        media_type=(file.content_type or "application/octet-stream")[:40],
        path="",
        sha256="",
        rights_status=rights_status,
        source_url=source_url,
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


@router.get("/{asset_id}/proxy")
def download_proxy(asset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    digest = (asset.metadata_json or {}).get("proxy_sha256")
    path = get_settings().mediagrid_data_dir / "proxies" / f"{asset.id}.mp4"
    if not digest or not path.is_file() or sha256_file(path) != digest:
        raise HTTPException(409, "Verified proxy is not available")
    return FileResponse(path, media_type="video/mp4", headers={"ETag": digest})


@router.get("/{asset_id}/waveform")
def download_waveform(asset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    digest = (asset.metadata_json or {}).get("waveform_sha256")
    path = get_settings().mediagrid_data_dir / "proxies" / f"{asset.id}-waveform.png"
    if not digest or not path.is_file() or sha256_file(path) != digest:
        raise HTTPException(409, "Verified waveform is not available")
    return FileResponse(path, media_type="image/png", headers={"ETag": digest})


@router.patch("/{asset_id}/rights", response_model=AssetRead)
def update_asset_rights(
    asset_id: str, payload: AssetRightsUpdate, db: Session = Depends(get_db)
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    if payload.rights_status == "LICENSED" and not payload.license_name:
        raise HTTPException(422, "License name is required for licensed media")
    if payload.source_url and not payload.source_url.startswith(("https://", "http://")):
        raise HTTPException(422, "Source URL must be HTTP or HTTPS")
    before = {
        "rights_status": asset.rights_status,
        "license_name": asset.license_name,
        "commercial_use": asset.commercial_use,
    }
    asset.rights_status = payload.rights_status
    asset.creator = payload.creator
    if "source_url" in payload.model_fields_set:
        asset.source_url = payload.source_url
    asset.license_name = payload.license_name
    asset.commercial_use = payload.commercial_use
    record_event(
        db,
        "ASSET_RIGHTS_UPDATED",
        "asset",
        asset.id,
        before=before,
        after=payload.model_dump(),
    )
    db.commit()
    db.refresh(asset)
    return asset


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
            Job.status.in_(ACTIVE_JOB_STATUSES),
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
