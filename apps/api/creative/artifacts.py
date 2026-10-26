"""Audiovisual review is a separate append-only decision, never a storyboard mutation."""

from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..ingestion import sha256_file
from ..models import Job, MotionArtifactReview
from ..motion_contracts.canonical import contract_sha256
from ..motion_contracts.models import Contract, Digest
from ..services import record_event
from .motion import motion_output, verify_motion
from .service import project_for


class ArtifactDecision(Contract):
    expected_revision: int = Field(ge=0)
    expected_plan_sha256: Digest
    expected_video_sha256: Digest
    decision: Literal["REQUEST_REVIEW", "APPROVE", "REJECT"]
    notes: str = Field(min_length=3, max_length=2000)
    video_watched: bool = False
    audio_checked: bool = False
    rights_checked: bool = False

    @model_validator(mode="after")
    def confirmation(self):
        if self.decision == "APPROVE" and not (
            self.video_watched and self.audio_checked and self.rights_checked
        ):
            raise ValueError("Confirm audiovisual and rights review before approving")
        return self


def owned_job(db, project_id, job_id):
    project_for(db, project_id)
    job = db.get(Job, job_id)
    if not job or job.project_id != project_id or job.job_type != "CREATIVE_MOTION":
        raise HTTPException(404, "Motion job not found")
    if job.status != "SUCCEEDED" or not job.result:
        raise HTTPException(409, "Artifact is not ready")
    return job


def artifact_for(db, project_id, job_id):
    job = owned_job(db, project_id, job_id)
    try:
        plan = verify_motion(db, project_id, job.payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    path = motion_output(job.id)
    if (
        job.result.get("plan_sha256") != job.payload["plan_sha256"]
        or not path.is_file()
        or sha256_file(path) != job.result.get("sha256")
    ):
        raise HTTPException(409, "Exact artifact missing or changed")
    return job, plan, path


def history(db, job_id):
    return list(
        db.scalars(
            select(MotionArtifactReview)
            .where(MotionArtifactReview.job_id == job_id)
            .order_by(MotionArtifactReview.revision)
        )
    )


def read_artifact_review(db, project_id, job_id):
    job = owned_job(db, project_id, job_id)
    plan = job.payload["plan"]
    blockers = []
    try:
        artifact_for(db, project_id, job_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        blockers.append(str(exc.detail))
    rows = history(db, job_id)
    row = rows[-1] if rows else None
    deps = plan.get("dependencies_sha256") or contract_sha256(plan["assets"])
    current = (
        not blockers
        and row is not None
        and (
            row.plan_sha256,
            row.video_sha256,
            row.snapshot_sha256,
            row.dependencies_sha256,
        )
        == (
            job.payload["plan_sha256"],
            job.result["sha256"],
            plan["approved_snapshot_sha256"],
            deps,
        )
    )
    return {
        "status": ("APPROVED_ARTIFACT" if row.decision == "APPROVE" else row.decision)
        if current
        else ("STALE" if blockers or row else "AWAITING_HUMAN_REVIEW"),
        "blockers": blockers,
        "revision": row.revision if row else 0,
        "plan_sha256": job.payload["plan_sha256"],
        "video_sha256": job.result["sha256"],
        "publication_enabled": False,
        "history": [
            {
                "revision": r.revision,
                "decision": r.decision,
                "actor": r.actor,
                "notes": r.notes,
                "video_sha256": r.video_sha256,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


def decide_artifact(db, project_id, job_id, request: ArtifactDecision, actor: str):
    job, plan, _ = artifact_for(db, project_id, job_id)
    if (request.expected_plan_sha256, request.expected_video_sha256) != (
        job.payload["plan_sha256"],
        job.result["sha256"],
    ):
        raise HTTPException(409, "Review targets a different plan/video")
    request_hash = contract_sha256({"request": request.model_dump(), "actor": actor})
    rows = history(db, job_id)
    if any(r.request_sha256 == request_hash for r in rows):
        return read_artifact_review(db, project_id, job_id)
    if request.expected_revision != (rows[-1].revision if rows else 0):
        raise HTTPException(409, "Artifact review revision changed")
    row = MotionArtifactReview(
        project_id=project_id,
        job_id=job_id,
        revision=request.expected_revision + 1,
        request_sha256=request_hash,
        plan_sha256=job.payload["plan_sha256"],
        video_sha256=job.result["sha256"],
        snapshot_sha256=plan["approved_snapshot_sha256"],
        dependencies_sha256=plan.get("dependencies_sha256") or contract_sha256(plan["assets"]),
        decision=request.decision,
        actor=actor,
        notes=request.notes,
    )
    db.add(row)
    try:
        db.flush()
        db.expire_all()
        artifact_for(db, project_id, job_id)
        record_event(
            db,
            "MOTION_ARTIFACT_REVIEWED",
            "job",
            job_id,
            after={"decision": row.decision, "video_sha256": row.video_sha256},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if any(r.request_sha256 == request_hash for r in history(db, job_id)):
            return read_artifact_review(db, project_id, job_id)
        raise HTTPException(409, "Artifact review changed concurrently") from exc
    return read_artifact_review(db, project_id, job_id)
