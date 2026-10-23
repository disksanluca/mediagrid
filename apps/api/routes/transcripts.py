"""Local word transcription and editorial caption review."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.render.caption_video import caption_output

from ..asr_words import available
from ..captions import Cue, Word, probe_media, to_srt, to_vtt, validate_timing
from ..config import get_settings
from ..database import get_db
from ..ingestion import sha256_file
from ..models import Asset, Job, JobStatus, Transcript
from ..services import record_event
from ..transcripts import replace_words, serialize

router = APIRouter(prefix="/assets", tags=["transcripts"])


class TranscriptWrite(BaseModel):
    expected_revision: int = Field(ge=0)
    language: str = Field(min_length=2, max_length=20)
    words: list[Word] = Field(default_factory=list, max_length=200_000)
    cues: list[Cue] = Field(default_factory=list, max_length=50_000)


class ReviewWrite(BaseModel):
    expected_revision: int = Field(ge=1)


class CaptionRenderWrite(BaseModel):
    expected_revision: int = Field(ge=1)


def source_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    if not asset.media_type.startswith(("audio/", "video/")):
        raise HTTPException(422, "Only audio and video can have a transcript")
    source = get_settings().mediagrid_data_dir / "assets" / asset.id
    if not source.is_file() or sha256_file(source) != asset.sha256:
        raise HTTPException(409, "Original media is missing or changed")
    return asset


@router.get("/asr-status")
def asr_status() -> dict:
    return {"word_asr_available": available(), "engine": "FASTER_WHISPER_CPU"}


@router.post("/{asset_id}/transcribe-words", status_code=status.HTTP_202_ACCEPTED)
def queue_words(asset_id: str, db: Session = Depends(get_db)) -> dict:
    asset = source_asset(db, asset_id)
    if not available():
        raise HTTPException(503, "Local word ASR needs the asr extra and a model directory")
    if db.scalar(select(Transcript).where(Transcript.asset_id == asset_id)):
        raise HTTPException(409, "Transcript exists; edit it without overwriting human corrections")
    active = db.scalar(select(Job).where(
        Job.job_type == "ASR_WORDS",
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        Job.payload["asset_id"].as_string() == asset_id,
    ))
    if active:
        return {"job_id": active.id, "status": active.status}
    job = Job(job_type="ASR_WORDS", payload={
        "asset_id": asset_id, "sha256": asset.sha256,
    })
    db.add(job)
    db.flush()
    record_event(db, "ASR_WORDS_QUEUED", "job", job.id, after={"asset_id": asset_id})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{asset_id}/transcript-v2")
def read_transcript(asset_id: str, db: Session = Depends(get_db)) -> dict:
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if transcript is None:
        raise HTTPException(404, "Timed transcript is not available")
    return serialize(db, transcript)


@router.put("/{asset_id}/transcript-v2")
def write_transcript(
    asset_id: str, payload: TranscriptWrite, db: Session = Depends(get_db)
) -> dict:
    asset = source_asset(db, asset_id)
    duration_ms, has_audio = probe_media(
        get_settings().mediagrid_data_dir / "assets" / asset.id
    )
    if not has_audio:
        raise HTTPException(422, "Media has no audio stream")
    try:
        validate_timing(payload.words, payload.cues, duration_ms)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    active_asr = db.scalar(select(Job).where(
        Job.job_type == "ASR_WORDS",
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        Job.payload["asset_id"].as_string() == asset_id,
    ))
    if active_asr:
        raise HTTPException(409, "Wait for local ASR before saving manual corrections")
    current = transcript.revision if transcript else 0
    if current != payload.expected_revision:
        raise HTTPException(409, "Transcript changed; reload before saving")
    if transcript is None:
        transcript = Transcript(
            asset_id=asset_id, source_sha256=asset.sha256,
            engine="MANUAL", model_id="human", model_version="1",
            language=payload.language, revision=1,
            status="REVIEW_REQUIRED", cues_json=[cue.model_dump() for cue in payload.cues],
        )
        db.add(transcript)
        db.flush()
    else:
        if transcript.source_sha256 != asset.sha256:
            raise HTTPException(409, "Transcript belongs to a different source revision")
        transcript.language = payload.language
        transcript.revision += 1
        transcript.status = "REVIEW_REQUIRED"
        transcript.cues_json = [cue.model_dump() for cue in payload.cues]
    replace_words(db, transcript, payload.words)
    record_event(db, "TRANSCRIPT_EDITED", "asset", asset_id,
                 after={"revision": transcript.revision, "cues": len(payload.cues)})
    db.commit()
    return serialize(db, transcript)


@router.post("/{asset_id}/captions/approve")
def approve_captions(
    asset_id: str, payload: ReviewWrite, db: Session = Depends(get_db)
) -> dict:
    asset = source_asset(db, asset_id)
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if transcript is None or transcript.revision != payload.expected_revision:
        raise HTTPException(409, "Transcript changed; reload before approval")
    if transcript.source_sha256 != asset.sha256 or not transcript.cues_json:
        raise HTTPException(409, "Caption source or cues are unavailable")
    cues = [Cue.model_validate(cue) for cue in transcript.cues_json]
    duration_ms, _ = probe_media(get_settings().mediagrid_data_dir / "assets" / asset.id)
    try:
        validate_timing([], cues, duration_ms)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if transcript.status != "APPROVED":
        transcript.status = "APPROVED"
        transcript.revision += 1
        record_event(db, "CAPTIONS_APPROVED", "asset", asset_id,
                     after={"revision": transcript.revision, "source_sha256": asset.sha256})
        db.commit()
    return serialize(db, transcript)


@router.get("/{asset_id}/captions.{extension}")
def export_captions(
    asset_id: str, extension: str, db: Session = Depends(get_db)
) -> PlainTextResponse:
    if extension not in {"srt", "vtt"}:
        raise HTTPException(404, "Subtitle format not found")
    asset = source_asset(db, asset_id)
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if transcript is None or transcript.status != "APPROVED":
        raise HTTPException(409, "Review and approve captions before export")
    if transcript.source_sha256 != asset.sha256:
        raise HTTPException(409, "Original changed after caption review")
    cues = [Cue.model_validate(cue) for cue in transcript.cues_json]
    body = to_srt(cues) if extension == "srt" else to_vtt(cues)
    filename = f'attachment; filename="captions-{asset.id}.{extension}"'
    return PlainTextResponse(
        body, media_type="application/x-subrip" if extension == "srt" else "text/vtt",
        headers={"Content-Disposition": filename},
    )


@router.post("/{asset_id}/captions/render", status_code=status.HTTP_202_ACCEPTED)
def queue_caption_render(
    asset_id: str, payload: CaptionRenderWrite, db: Session = Depends(get_db)
) -> dict:
    asset = source_asset(db, asset_id)
    if not asset.media_type.startswith("video/"):
        raise HTTPException(422, "Caption video requires a video asset")
    if asset.rights_status not in {"OWNED", "LICENSED"}:
        raise HTTPException(409, "Confirm media rights before rendering a derivative")
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if (transcript is None or transcript.status != "APPROVED"
            or transcript.revision != payload.expected_revision
            or transcript.source_sha256 != asset.sha256):
        raise HTTPException(409, "Approve the current caption revision before rendering")
    jobs = db.scalars(select(Job).where(
        Job.job_type == "CAPTION_RENDER",
        Job.payload["asset_id"].as_string() == asset_id,
    ).order_by(Job.created_at.desc())).all()
    for existing in jobs:
        if existing.payload.get("revision") != transcript.revision:
            continue
        if existing.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
            return {"job_id": existing.id, "status": existing.status}
        if existing.status == JobStatus.SUCCEEDED.value:
            output = caption_output(asset_id, transcript.revision)
            if output.is_file() and sha256_file(output) == (existing.result or {}).get("sha256"):
                return {"job_id": existing.id, "status": existing.status}
    job = Job(job_type="CAPTION_RENDER", payload={
        "asset_id": asset_id, "sha256": asset.sha256, "revision": transcript.revision,
    })
    db.add(job)
    db.flush()
    record_event(db, "CAPTION_RENDER_QUEUED", "job", job.id,
                 after={"asset_id": asset_id, "revision": transcript.revision})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{asset_id}/captions/render-status")
def caption_render_status(asset_id: str, db: Session = Depends(get_db)) -> dict | None:
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if transcript is None or transcript.status != "APPROVED":
        return None
    jobs = db.scalars(select(Job).where(
        Job.job_type == "CAPTION_RENDER",
        Job.payload["asset_id"].as_string() == asset_id,
    ).order_by(Job.created_at.desc())).all()
    job = next((item for item in jobs
                if item.payload.get("revision") == transcript.revision), None)
    return {"job_id": job.id, "status": job.status, "error": job.error} if job else None


@router.get("/{asset_id}/captions/render/{job_id}")
def download_caption_render(
    asset_id: str, job_id: str, db: Session = Depends(get_db)
) -> FileResponse:
    asset = source_asset(db, asset_id)
    job = db.get(Job, job_id)
    if (job is None or job.job_type != "CAPTION_RENDER"
            or job.payload.get("asset_id") != asset_id):
        raise HTTPException(404, "Caption render job not found")
    if job.status != JobStatus.SUCCEEDED.value or not job.result:
        raise HTTPException(409, "Caption render has not succeeded")
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
    if (transcript is None or transcript.status != "APPROVED"
            or transcript.revision != job.payload.get("revision")
            or transcript.source_sha256 != asset.sha256):
        raise HTTPException(409, "Caption approval changed after this render")
    output = caption_output(asset_id, transcript.revision)
    if not output.is_file() or sha256_file(output) != job.result.get("sha256"):
        raise HTTPException(409, "Caption MP4 is missing or changed")
    return FileResponse(output, media_type="video/mp4",
                        filename=f"captions-{asset_id}-r{transcript.revision}.mp4")
