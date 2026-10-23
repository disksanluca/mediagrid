"""Human-reviewed cuts from an approved, hashed source transcript."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from workers.render.clips import clip_output

from ..captions import Cue, probe_media
from ..config import get_settings
from ..database import get_db
from ..ingestion import sha256_file
from ..models import ACTIVE_JOB_STATUSES, Asset, ClipCandidate, Job, JobStatus, Transcript
from ..services import record_event
from ..transcripts import words_for
from .transcripts import source_asset

router = APIRouter(prefix="/assets", tags=["clips"])


class ClipAction(BaseModel):
    expected_revision: int = Field(ge=1)
    action: str
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    aspect: str | None = None
    focus_x: float | None = Field(default=None, ge=0, le=1)
    focus_y: float | None = Field(default=None, ge=0, le=1)


class ClipRenderWrite(BaseModel):
    expected_revision: int = Field(ge=1)


def current_transcript(db: Session, asset: Asset) -> Transcript:
    transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset.id))
    if (transcript is None or transcript.status != "APPROVED"
            or transcript.source_sha256 != asset.sha256):
        raise HTTPException(409, "Approve the current timed transcript before making cuts")
    return transcript


def clip_asset(db: Session, asset_id: str) -> Asset:
    asset = source_asset(db, asset_id)
    if not asset.media_type.startswith("video/"):
        raise HTTPException(422, "Clip machine requires a video source")
    if asset.rights_status not in {"OWNED", "LICENSED"}:
        raise HTTPException(409, "Confirm video rights before making derivatives")
    return asset


def candidate_for(db: Session, asset: Asset, candidate_id: str) -> ClipCandidate:
    candidate = db.get(ClipCandidate, candidate_id)
    if candidate is None or candidate.asset_id != asset.id:
        raise HTTPException(404, "Clip candidate not found")
    transcript = current_transcript(db, asset)
    if (candidate.source_sha256 != asset.sha256
            or candidate.transcript_revision != transcript.revision):
        raise HTTPException(409, "Clip analysis is stale; analyze the current transcript")
    return candidate


def serialize(candidate: ClipCandidate, words, asset: Asset) -> dict:
    before = " ".join(word.text for word in words if
                      candidate.context_start_ms <= word.start_ms < candidate.start_ms)
    spoken = " ".join(word.text for word in words if
                      candidate.start_ms <= word.start_ms < candidate.end_ms)
    after = " ".join(word.text for word in words if
                     candidate.end_ms <= word.start_ms < candidate.context_end_ms)
    return {
        "id": candidate.id, "asset_id": candidate.asset_id,
        "source_sha256": candidate.source_sha256, "source_url": asset.source_url,
        "transcript_revision": candidate.transcript_revision,
        "analysis_version": candidate.analysis_version,
        "start_ms": candidate.start_ms, "end_ms": candidate.end_ms,
        "context_start_ms": candidate.context_start_ms,
        "context_end_ms": candidate.context_end_ms,
        "word_start_index": candidate.word_start_index,
        "word_end_index": candidate.word_end_index,
        "score": candidate.score, "reason_codes": candidate.reason_codes,
        "status": candidate.status,
        "selected_start_ms": candidate.selected_start_ms,
        "selected_end_ms": candidate.selected_end_ms,
        "aspect": candidate.aspect,
        "focus_x": candidate.focus_x, "focus_y": candidate.focus_y,
        "revision": candidate.revision,
        "context_before": before, "spoken_text": spoken, "context_after": after,
    }


@router.post("/{asset_id}/clips/analyze", status_code=status.HTTP_202_ACCEPTED)
def queue_analysis(asset_id: str, db: Session = Depends(get_db)) -> dict:
    asset = clip_asset(db, asset_id)
    transcript = current_transcript(db, asset)
    duration_ms, has_audio = probe_media(
        get_settings().mediagrid_data_dir / "assets" / asset.id
    )
    if not has_audio or duration_ms < 12_000:
        raise HTTPException(422, "Clip analysis needs at least 12 seconds with audio")
    if not words_for(db, transcript.id):
        raise HTTPException(422, "Approved transcript has no words")
    jobs = db.scalars(select(Job).where(
        Job.job_type == "CLIP_ANALYSIS",
        Job.payload["asset_id"].as_string() == asset_id,
    ).order_by(Job.created_at.desc())).all()
    for existing in jobs:
        if existing.payload.get("transcript_revision") != transcript.revision:
            continue
        if existing.status in {*ACTIVE_JOB_STATUSES, "SUCCEEDED"}:
            return {"job_id": existing.id, "status": existing.status}
    job = Job(job_type="CLIP_ANALYSIS", payload={
        "asset_id": asset.id, "sha256": asset.sha256,
        "transcript_revision": transcript.revision,
    })
    db.add(job)
    db.flush()
    record_event(db, f"CLIP_ANALYSIS_{job.status}", "job", job.id,
                 after={"asset_id": asset.id, "revision": transcript.revision})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{asset_id}/clips")
def list_clips(asset_id: str, db: Session = Depends(get_db)) -> list[dict]:
    asset = clip_asset(db, asset_id)
    transcript = current_transcript(db, asset)
    words = words_for(db, transcript.id)
    candidates = db.scalars(select(ClipCandidate).where(
        ClipCandidate.asset_id == asset_id,
        ClipCandidate.source_sha256 == asset.sha256,
        ClipCandidate.transcript_revision == transcript.revision,
    ).order_by(ClipCandidate.start_ms)).all()
    return [serialize(candidate, words, asset) for candidate in candidates]


@router.patch("/{asset_id}/clips/{candidate_id}")
def update_clip(asset_id: str, candidate_id: str,
                payload: ClipAction, db: Session = Depends(get_db)) -> dict:
    asset = clip_asset(db, asset_id)
    candidate = candidate_for(db, asset, candidate_id)
    if candidate.revision != payload.expected_revision:
        raise HTTPException(409, "Clip changed; reload before editing")
    if payload.action not in {"edit", "select", "reject"}:
        raise HTTPException(422, "Action must be edit, select or reject")
    transcript = current_transcript(db, asset)
    if payload.action == "edit":
        start = payload.start_ms if payload.start_ms is not None else (
            candidate.selected_start_ms if candidate.selected_start_ms is not None
            else candidate.start_ms
        )
        end = payload.end_ms if payload.end_ms is not None else (
            candidate.selected_end_ms if candidate.selected_end_ms is not None
            else candidate.end_ms
        )
        if not candidate.context_start_ms <= start < end <= candidate.context_end_ms:
            raise HTTPException(422, "Edit must stay within saved source context")
        if end - start < 1000:
            raise HTTPException(422, "Clip must last at least one second")
        words = words_for(db, transcript.id)
        if any(word.start_ms < edge < word.end_ms for word in words for edge in (start, end)):
            raise HTTPException(422, "Clip boundary splits a transcript word")
        cues = [Cue.model_validate(item) for item in transcript.cues_json]
        if any(cue.start_ms < edge < cue.end_ms for cue in cues for edge in (start, end)):
            raise HTTPException(422, "Clip boundary splits an approved caption cue")
        aspect = payload.aspect if payload.aspect is not None else candidate.aspect
        if aspect not in {"source", "vertical"}:
            raise HTTPException(422, "Aspect must be source or vertical")
        candidate.selected_start_ms = start
        candidate.selected_end_ms = end
        candidate.aspect = aspect
        candidate.focus_x = payload.focus_x if payload.focus_x is not None else candidate.focus_x
        candidate.focus_y = payload.focus_y if payload.focus_y is not None else candidate.focus_y
        candidate.status = "EDITED"
    elif payload.action == "select":
        if candidate.status == "REJECTED":
            raise HTTPException(409, "Edit a rejected candidate before selecting it")
        candidate.status = "SELECTED"
    else:
        candidate.status = "REJECTED"
    candidate.revision += 1
    record_event(db, "CLIP_CANDIDATE_REVIEWED", "clip_candidate", candidate.id,
                 after={"action": payload.action, "revision": candidate.revision})
    db.commit()
    return serialize(candidate, words_for(db, transcript.id), asset)


@router.post("/{asset_id}/clips/{candidate_id}/render",
             status_code=status.HTTP_202_ACCEPTED)
def queue_clip_render(asset_id: str, candidate_id: str,
                      payload: ClipRenderWrite, db: Session = Depends(get_db)) -> dict:
    asset = clip_asset(db, asset_id)
    candidate = candidate_for(db, asset, candidate_id)
    if candidate.revision != payload.expected_revision or candidate.status != "SELECTED":
        raise HTTPException(409, "Select and review current clip revision before rendering")
    jobs = db.scalars(select(Job).where(
        Job.job_type == "CLIP_RENDER",
        Job.payload["candidate_id"].as_string() == candidate_id,
    ).order_by(Job.created_at.desc())).all()
    for existing in jobs:
        if existing.payload.get("revision") != candidate.revision:
            continue
        if existing.status in ACTIVE_JOB_STATUSES:
            return {"job_id": existing.id, "status": existing.status}
        if existing.status == JobStatus.SUCCEEDED.value:
            output = clip_output(candidate.id, candidate.revision)
            if output.is_file() and sha256_file(output) == (existing.result or {}).get("sha256"):
                return {"job_id": existing.id, "status": existing.status}
    job = Job(job_type="CLIP_RENDER", payload={
        "asset_id": asset.id, "sha256": asset.sha256,
        "candidate_id": candidate.id, "revision": candidate.revision,
        "transcript_revision": candidate.transcript_revision,
    })
    db.add(job)
    db.flush()
    record_event(db, f"CLIP_RENDER_{job.status}", "job", job.id,
                 after={"candidate_id": candidate.id, "revision": candidate.revision})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{asset_id}/clips/{candidate_id}/render-status")
def clip_render_status(asset_id: str, candidate_id: str,
                       db: Session = Depends(get_db)) -> dict | None:
    asset = clip_asset(db, asset_id)
    candidate = candidate_for(db, asset, candidate_id)
    jobs = db.scalars(select(Job).where(
        Job.job_type == "CLIP_RENDER",
        Job.payload["candidate_id"].as_string() == candidate_id,
    ).order_by(Job.created_at.desc())).all()
    job = next((item for item in jobs
                if item.payload.get("revision") == candidate.revision), None)
    return {"job_id": job.id, "status": job.status, "error": job.error} if job else None


@router.get("/{asset_id}/clips/{candidate_id}/render/{job_id}")
def download_clip(asset_id: str, candidate_id: str, job_id: str,
                  db: Session = Depends(get_db)) -> FileResponse:
    asset = clip_asset(db, asset_id)
    candidate = candidate_for(db, asset, candidate_id)
    job = db.get(Job, job_id)
    if (job is None or job.job_type != "CLIP_RENDER"
            or job.payload.get("candidate_id") != candidate_id):
        raise HTTPException(404, "Clip render job not found")
    if (job.status != JobStatus.SUCCEEDED.value or not job.result
            or candidate.status != "SELECTED"
            or job.payload.get("revision") != candidate.revision):
        raise HTTPException(409, "Clip review changed or render did not succeed")
    output = clip_output(candidate.id, candidate.revision)
    if not output.is_file() or sha256_file(output) != job.result.get("sha256"):
        raise HTTPException(409, "Rendered clip is missing or changed")
    return FileResponse(output, media_type="video/mp4",
                        filename=f"clip-{candidate.id}-r{candidate.revision}.mp4")
