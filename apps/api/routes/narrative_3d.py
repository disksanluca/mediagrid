"""Versioned, human-directed Blender stories with blocking before final render."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workers.render.narrative_3d import (
    RIG_VERSION,
    WORLD_VERSION,
    blender_executable,
    blender_script,
    narrative_output,
    story_sha256,
)

from ..captions import probe_media
from ..config import get_settings
from ..database import get_db
from ..ingestion import sha256_file
from ..models import Asset, Job, JobStatus, Narrative3D, Project
from ..services import record_event

router = APIRouter(prefix="/projects", tags=["narrative-3d"])


class StoryShot(BaseModel):
    duration_ms: int = Field(ge=1500, le=6000)
    beat_text: str = Field(min_length=3, max_length=180)
    action: Literal["notice", "reach", "react", "celebrate"]
    camera: Literal["wide", "medium", "close"]
    lighting: Literal["calm", "tense", "bright"]


class StoryWrite(BaseModel):
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=3, max_length=160)
    aspect: Literal["vertical", "horizontal"]
    shots: list[StoryShot] = Field(min_length=3, max_length=8)
    audio_asset_id: str | None = None

    @model_validator(mode="after")
    def valid_story(self) -> "StoryWrite":
        if sum(shot.duration_ms for shot in self.shots) > 45_000:
            raise ValueError("3D story must be at most 45 seconds")
        if len({shot.beat_text.strip() for shot in self.shots}) != len(self.shots):
            raise ValueError("Each 3D shot needs a distinct story beat")
        return self


class BlockingApproval(BaseModel):
    expected_revision: int = Field(ge=1)
    watched_full_preview: bool
    character_continuity_checked: bool
    story_timing_checked: bool


def sequence_for(db: Session, project_id: str) -> Narrative3D | None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if project.content_type != "narrative_3d":
        raise HTTPException(422, "This project is not a 3D narrative")
    return db.scalar(select(Narrative3D).where(Narrative3D.project_id == project_id))


def serialize(sequence: Narrative3D) -> dict:
    return {
        "id": sequence.id, "project_id": sequence.project_id,
        "revision": sequence.revision, "status": sequence.status,
        "title": sequence.title, "aspect": sequence.aspect,
        "shots": sequence.shots_json,
        "rig_version": sequence.rig_version,
        "world_version": sequence.world_version,
        "audio_asset_id": sequence.audio_asset_id,
        "audio_sha256": sequence.audio_sha256,
        "blocking_job_id": sequence.blocking_job_id,
        "blocking_sha256": sequence.blocking_sha256,
        "story_sha256": story_sha256(sequence),
        "blender_available": blender_executable() is not None,
    }


def render_job(db: Session, sequence: Narrative3D, quality: str) -> Job | None:
    jobs = db.scalars(select(Job).where(
        Job.project_id == sequence.project_id,
        Job.job_type == "NARRATIVE_3D_RENDER",
        Job.payload["sequence_id"].as_string() == sequence.id,
    ).order_by(Job.created_at.desc())).all()
    return next((job for job in jobs if job.payload.get("revision") == sequence.revision
                 and job.payload.get("quality") == quality), None)


@router.get("/{project_id}/narrative-3d")
def read_story(project_id: str, db: Session = Depends(get_db)) -> dict | None:
    sequence = sequence_for(db, project_id)
    if sequence is None:
        return None
    return serialize(sequence)


@router.put("/{project_id}/narrative-3d")
def save_story(project_id: str, payload: StoryWrite,
               db: Session = Depends(get_db)) -> dict:
    sequence = sequence_for(db, project_id)
    project = db.get(Project, project_id)
    if (sequence.revision if sequence else 0) != payload.expected_revision:
        raise HTTPException(409, "3D story changed; reload before saving")
    if sequence and db.scalar(select(Job).where(
        Job.project_id == project_id,
        Job.job_type == "NARRATIVE_3D_RENDER",
        Job.payload["sequence_id"].as_string() == sequence.id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    )):
        raise HTTPException(409, "Wait for the current 3D render")
    audio_sha = None
    if payload.audio_asset_id:
        asset = db.get(Asset, payload.audio_asset_id)
        if asset is None or not asset.media_type.startswith("audio/"):
            raise HTTPException(422, "3D soundtrack needs a local audio asset")
        if (asset.rights_status not in {"OWNED", "LICENSED"}
                or asset.rights_status == "LICENSED" and not asset.license_name):
            raise HTTPException(409, "Confirm soundtrack rights before using it")
        source = get_settings().mediagrid_data_dir / "assets" / asset.id
        if not source.is_file() or sha256_file(source) != asset.sha256:
            raise HTTPException(409, "Soundtrack file missing or changed")
        duration_ms, has_audio = probe_media(source)
        if not has_audio or duration_ms + 50 < sum(s.duration_ms for s in payload.shots):
            raise HTTPException(422, "Soundtrack is shorter than the story")
        audio_sha = asset.sha256
    if sequence is None:
        sequence = Narrative3D(project_id=project_id)
        db.add(sequence)
    else:
        waiting_jobs = db.scalars(select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "NARRATIVE_3D_RENDER",
            Job.payload["sequence_id"].as_string() == sequence.id,
            Job.status == JobStatus.WAITING_FOR_WORKER.value,
        )).all()
        for waiting_job in waiting_jobs:
            waiting_job.status = JobStatus.CANCELLED.value
            waiting_job.error = "3D story changed before a worker became available"
            record_event(db, "NARRATIVE_3D_WAIT_CANCELLED", "job", waiting_job.id)
        sequence.revision += 1
    sequence.status = "REVIEW_REQUIRED"
    project.format = payload.aspect
    sequence.title = payload.title.strip()
    sequence.aspect = payload.aspect
    sequence.shots_json = [shot.model_dump() for shot in payload.shots]
    sequence.rig_version = RIG_VERSION
    sequence.world_version = WORLD_VERSION
    sequence.audio_asset_id = payload.audio_asset_id
    sequence.audio_sha256 = audio_sha
    sequence.blocking_job_id = None
    sequence.blocking_sha256 = None
    db.flush()
    record_event(db, "NARRATIVE_3D_SAVED", "narrative_3d", sequence.id,
                 after={"revision": sequence.revision, "story_sha256": story_sha256(sequence)})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "3D story changed; reload before saving") from exc
    return serialize(sequence)


def queue(project_id: str, quality: Literal["blocking", "final"], db: Session) -> dict:
    sequence = sequence_for(db, project_id)
    if sequence is None:
        raise HTTPException(404, "Save a 3D story first")
    if quality == "blocking" and sequence.status != "REVIEW_REQUIRED":
        raise HTTPException(409, "Blocking is available only before approval")
    if quality == "final" and sequence.status != "APPROVED":
        raise HTTPException(409, "Approve the blocking preview before final render")
    try:
        rig_sha = sha256_file(blender_script())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    existing = render_job(db, sequence, quality)
    if existing and existing.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
        return {"job_id": existing.id, "status": existing.status}
    output = narrative_output(sequence.id, sequence.revision, quality)
    if (existing and existing.status == "SUCCEEDED" and output.is_file()
            and sha256_file(output) == (existing.result or {}).get("sha256")):
        return {"job_id": existing.id, "status": existing.status}
    if existing and existing.status == "WAITING_FOR_WORKER":
        if blender_executable():
            existing.status = JobStatus.QUEUED.value
            existing.error = None
            record_event(db, "NARRATIVE_3D_WORKER_AVAILABLE", "job", existing.id)
            db.commit()
        return {"job_id": existing.id, "status": existing.status}
    waiting = blender_executable() is None
    job = Job(project_id=project_id, job_type="NARRATIVE_3D_RENDER", payload={
        "sequence_id": sequence.id, "revision": sequence.revision,
        "quality": quality, "story_sha256": story_sha256(sequence),
        "rig_sha256": rig_sha,
    }, status=(JobStatus.WAITING_FOR_WORKER.value if waiting else JobStatus.QUEUED.value))
    db.add(job)
    db.flush()
    record_event(db, "NARRATIVE_3D_WAITING_FOR_WORKER" if waiting
                 else "NARRATIVE_3D_QUEUED", "job", job.id,
                 after={"quality": quality, "revision": sequence.revision})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.post("/{project_id}/narrative-3d/blocking", status_code=status.HTTP_202_ACCEPTED)
def queue_blocking(project_id: str, db: Session = Depends(get_db)) -> dict:
    return queue(project_id, "blocking", db)


@router.post("/{project_id}/narrative-3d/final", status_code=status.HTTP_202_ACCEPTED)
def queue_final(project_id: str, db: Session = Depends(get_db)) -> dict:
    return queue(project_id, "final", db)


@router.post("/{project_id}/narrative-3d/approve-blocking")
def approve_blocking(project_id: str, payload: BlockingApproval,
                     db: Session = Depends(get_db)) -> dict:
    sequence = sequence_for(db, project_id)
    if sequence is None:
        raise HTTPException(404, "3D story not found")
    if sequence.revision != payload.expected_revision:
        raise HTTPException(409, "3D story changed; reload before approving")
    if sequence.status != "REVIEW_REQUIRED" or not all((
        payload.watched_full_preview, payload.character_continuity_checked,
        payload.story_timing_checked,
    )):
        raise HTTPException(422, "Watch the full blocking and check continuity and timing")
    job = render_job(db, sequence, "blocking")
    output = narrative_output(sequence.id, sequence.revision, "blocking")
    if (job is None or job.status != "SUCCEEDED" or not output.is_file()
            or sha256_file(output) != (job.result or {}).get("sha256")
            or (job.result or {}).get("story_sha256") != story_sha256(sequence)):
        raise HTTPException(409, "Current blocking preview is missing or changed")
    sequence.blocking_job_id = job.id
    sequence.blocking_sha256 = job.result["sha256"]
    sequence.status = "APPROVED"
    record_event(db, "NARRATIVE_3D_BLOCKING_APPROVED", "narrative_3d", sequence.id,
                 after={"revision": sequence.revision,
                        "blocking_sha256": sequence.blocking_sha256})
    db.commit()
    return serialize(sequence)


@router.get("/{project_id}/narrative-3d/{quality}/render-status")
def render_status(project_id: str, quality: Literal["blocking", "final"],
                  db: Session = Depends(get_db)) -> dict | None:
    sequence = sequence_for(db, project_id)
    if sequence is None:
        return None
    job = render_job(db, sequence, quality)
    return {"job_id": job.id, "status": job.status, "progress": job.progress,
            "error": job.error} if job else None


@router.get("/{project_id}/narrative-3d/{quality}/render/{job_id}")
def download(project_id: str, quality: Literal["blocking", "final"], job_id: str,
             db: Session = Depends(get_db)) -> FileResponse:
    sequence = sequence_for(db, project_id)
    job = db.get(Job, job_id)
    if (sequence is None or job is None or job.job_type != "NARRATIVE_3D_RENDER"
            or job.project_id != project_id or job.payload.get("sequence_id") != sequence.id
            or job.payload.get("quality") != quality):
        raise HTTPException(404, "3D render not found")
    if (job.status != "SUCCEEDED" or job.payload.get("revision") != sequence.revision
            or (quality == "final" and sequence.status != "APPROVED")):
        raise HTTPException(409, "3D render is stale or incomplete")
    output = narrative_output(sequence.id, sequence.revision, quality)
    if not output.is_file() or sha256_file(output) != (job.result or {}).get("sha256"):
        raise HTTPException(409, "3D output is missing or changed")
    return FileResponse(output, media_type="video/mp4",
                        filename=f"mediagrid-3d-{quality}.mp4")
