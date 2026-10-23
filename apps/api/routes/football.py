"""Human-marked football sequences with source-locked revisions."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workers.render.football import football_output

from ..captions import probe_media
from ..config import get_settings
from ..database import get_db
from ..ingestion import sha256_file
from ..models import (
    ACTIVE_JOB_STATUSES,
    Asset,
    Channel,
    FootballSequence,
    Job,
    JobStatus,
    Project,
)
from ..services import record_event

router = APIRouter(prefix="/projects", tags=["football"])


class FootballShotWrite(BaseModel):
    asset_id: str = Field(min_length=1)
    in_ms: int = Field(ge=0)
    out_ms: int = Field(gt=0)
    role: Literal["build_up", "action", "reaction", "replay", "celebration"]
    verified_event_id: str | None = Field(default=None, max_length=80)
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def valid_span(self) -> "FootballShotWrite":
        if self.out_ms <= self.in_ms or self.out_ms - self.in_ms < 500:
            raise ValueError("Football shot needs at least 0.5 second")
        if self.role in {"action", "replay"} and not (self.verified_event_id or "").strip():
            raise ValueError("Action and replay need a human-verified event ID")
        return self


class FootballSequenceWrite(BaseModel):
    expected_revision: int = Field(ge=0)
    aspect: Literal["horizontal", "vertical"]
    shots: list[FootballShotWrite] = Field(min_length=1, max_length=24)
    score_label: str | None = Field(default=None, max_length=80)
    score_source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def valid_score(self) -> "FootballSequenceWrite":
        if bool((self.score_label or "").strip()) != bool(self.score_source_url):
            raise ValueError("A score label needs a source URL, and vice versa")
        if self.score_label and any(char in self.score_label for char in "\r\n{}"):
            raise ValueError("Score label must be one plain line")
        if sum(shot.out_ms - shot.in_ms for shot in self.shots) > 180_000:
            raise ValueError("Football sequence exceeds three minutes")
        actions: set[str] = set()
        for shot in self.shots:
            if shot.role == "action" and shot.verified_event_id:
                actions.add(shot.verified_event_id)
            if shot.role == "replay" and shot.verified_event_id not in actions:
                raise ValueError("Replay needs an earlier action with the same event ID")
        return self


class FootballApproval(BaseModel):
    expected_revision: int = Field(ge=1)
    events_verified: bool
    rights_confirmed: bool
    score_verified: bool


def sequence_for(db: Session, project_id: str) -> tuple[Project, FootballSequence | None]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    channel = db.get(Channel, project.channel_id)
    if channel is None or channel.default_engine != "football":
        raise HTTPException(422, "Football sequence needs a Football project")
    sequence = db.scalar(select(FootballSequence).where(
        FootballSequence.project_id == project_id
    ))
    return project, sequence


def serialize(sequence: FootballSequence) -> dict:
    return {
        "id": sequence.id, "project_id": sequence.project_id,
        "revision": sequence.revision, "status": sequence.status,
        "aspect": sequence.aspect, "shots": sequence.shots_json,
        "score_label": sequence.score_label,
        "score_source_url": sequence.score_source_url,
    }


@router.get("/{project_id}/football")
def read_sequence(project_id: str, db: Session = Depends(get_db)) -> dict | None:
    _, sequence = sequence_for(db, project_id)
    return serialize(sequence) if sequence else None


@router.put("/{project_id}/football")
def save_sequence(project_id: str, payload: FootballSequenceWrite,
                  db: Session = Depends(get_db)) -> dict:
    _, sequence = sequence_for(db, project_id)
    if (sequence.revision if sequence else 0) != payload.expected_revision:
        raise HTTPException(409, "Football sequence changed; reload before saving")
    if sequence and db.scalar(select(Job).where(
        Job.job_type == "FOOTBALL_RENDER",
        Job.payload["sequence_id"].as_string() == sequence.id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    )):
        raise HTTPException(409, "Wait for the current football render")
    pinned: list[dict] = []
    settings = get_settings()
    for shot in payload.shots:
        asset = db.get(Asset, shot.asset_id)
        if asset is None or not asset.media_type.startswith("video/"):
            raise HTTPException(422, "Football shot needs a local video asset")
        if asset.rights_status not in {"OWNED", "LICENSED"}:
            raise HTTPException(409, f"Confirm rights for {asset.name}")
        source = settings.mediagrid_data_dir / "assets" / asset.id
        if not source.is_file() or sha256_file(source) != asset.sha256:
            raise HTTPException(409, f"Source missing or changed: {asset.name}")
        duration_ms, _ = probe_media(source)
        if shot.out_ms > duration_ms + 50:
            raise HTTPException(422, f"Shot exceeds source duration: {asset.name}")
        pinned.append({**shot.model_dump(), "source_sha256": asset.sha256})
    if sequence is None:
        sequence = FootballSequence(project_id=project_id)
        db.add(sequence)
    else:
        sequence.revision += 1
    sequence.status = "REVIEW_REQUIRED"
    sequence.aspect = payload.aspect
    sequence.shots_json = pinned
    sequence.score_label = payload.score_label.strip() if payload.score_label else None
    sequence.score_source_url = str(payload.score_source_url) if payload.score_source_url else None
    db.flush()
    record_event(db, "FOOTBALL_SEQUENCE_SAVED", "football_sequence", sequence.id,
                 after={"revision": sequence.revision, "shots": len(pinned)})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Football sequence changed; reload before saving") from exc
    return serialize(sequence)


@router.post("/{project_id}/football/approve")
def approve_sequence(project_id: str, payload: FootballApproval,
                     db: Session = Depends(get_db)) -> dict:
    _, sequence = sequence_for(db, project_id)
    if sequence is None:
        raise HTTPException(404, "Football sequence not found")
    if sequence.revision != payload.expected_revision:
        raise HTTPException(409, "Football sequence changed; reload before approving")
    if not all((payload.events_verified, payload.rights_confirmed,
                payload.score_verified or not sequence.score_label)):
        raise HTTPException(422, "Verify events, rights and any score before rendering")
    sequence.status = "APPROVED"
    record_event(db, "FOOTBALL_SEQUENCE_APPROVED", "football_sequence", sequence.id,
                 after={"revision": sequence.revision})
    db.commit()
    return serialize(sequence)


def render_job(db: Session, sequence: FootballSequence) -> Job | None:
    jobs = db.scalars(select(Job).where(
        Job.job_type == "FOOTBALL_RENDER",
        Job.payload["sequence_id"].as_string() == sequence.id,
    ).order_by(Job.created_at.desc())).all()
    return next((job for job in jobs
                 if job.payload.get("revision") == sequence.revision), None)


@router.post("/{project_id}/football/render", status_code=status.HTTP_202_ACCEPTED)
def queue_render(project_id: str, db: Session = Depends(get_db)) -> dict:
    _, sequence = sequence_for(db, project_id)
    if sequence is None or sequence.status != "APPROVED":
        raise HTTPException(409, "Approve the current football sequence before rendering")
    existing = render_job(db, sequence)
    if existing and existing.status in ACTIVE_JOB_STATUSES:
        return {"job_id": existing.id, "status": existing.status}
    if existing and existing.status == "SUCCEEDED":
        output = football_output(sequence.id, sequence.revision)
        if output.is_file() and sha256_file(output) == (existing.result or {}).get("sha256"):
            return {"job_id": existing.id, "status": existing.status}
    job = Job(project_id=project_id, job_type="FOOTBALL_RENDER", payload={
        "sequence_id": sequence.id, "revision": sequence.revision,
    })
    db.add(job)
    db.flush()
    record_event(db, f"FOOTBALL_RENDER_{job.status}", "job", job.id,
                 after={"sequence_id": sequence.id, "revision": sequence.revision})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{project_id}/football/render-status")
def read_render(project_id: str, db: Session = Depends(get_db)) -> dict | None:
    _, sequence = sequence_for(db, project_id)
    if sequence is None:
        return None
    job = render_job(db, sequence)
    return {"job_id": job.id, "status": job.status, "error": job.error} if job else None


@router.get("/{project_id}/football/render/{job_id}")
def download_render(project_id: str, job_id: str,
                    db: Session = Depends(get_db)) -> FileResponse:
    _, sequence = sequence_for(db, project_id)
    job = db.get(Job, job_id)
    if (sequence is None or job is None or job.job_type != "FOOTBALL_RENDER"
            or job.payload.get("sequence_id") != sequence.id):
        raise HTTPException(404, "Football render not found")
    if (sequence.status != "APPROVED" or job.status != "SUCCEEDED"
            or job.payload.get("revision") != sequence.revision):
        raise HTTPException(409, "Football approval changed or render did not succeed")
    output = football_output(sequence.id, sequence.revision)
    if not output.is_file() or sha256_file(output) != (job.result or {}).get("sha256"):
        raise HTTPException(409, "Rendered file missing or changed")
    return FileResponse(output, media_type="video/mp4", filename="football-edit.mp4")
