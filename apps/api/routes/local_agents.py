"""Local Creative Director jobs. Generation never grants editorial approval."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..creative.contracts import (
    CreativeBrief,
    CreativeStoryboard,
    CreativeStoryboardWrite,
)
from ..creative.contracts import (
    CreativeDirectionSet as DirectionContract,
)
from ..creative.engine import recipes_read
from ..creative.local_agents import TASKS, loopback_url, provider_status
from ..creative.service import (
    commit_revision,
    direction_status,
    latest,
    project_for,
    require_revision,
    review_read,
    save_storyboard,
    serialized,
)
from ..database import get_db
from ..models import (
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeStoryboardRevision,
    Job,
    JobStatus,
    now,
)
from ..schemas import JobRead
from ..services import record_event

router = APIRouter(tags=["creative-agents"])


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Literal["script", "directions", "storyboard", "continuity",
                  "references", "motion", "qa"]
    expected_brief_revision: int = Field(ge=1)
    expected_dna_revision: int = Field(ge=1)
    direction_id: str | None = Field(default=None, max_length=60)


class AdoptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    expected_brief_revision: int = Field(ge=1)
    expected_dna_revision: int = Field(ge=1)
    expected_direction_revision: int = Field(default=0, ge=0)


def _enabled() -> None:
    settings = get_settings()
    if settings.mediagrid_mode != "LOCAL" or not settings.mediagrid_agents_enabled:
        raise HTTPException(503, "Local creative agents are disabled")
    try:
        loopback_url()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/creative/agents/status")
def status():
    settings = get_settings()
    if settings.mediagrid_mode != "LOCAL" or not settings.mediagrid_agents_enabled:
        return {"state": "DISABLED", "model": settings.mediagrid_agents_model,
                "models": [], "loaded_models": [], "tasks": TASKS}
    return {**provider_status(), "tasks": TASKS}


@router.post("/projects/{project_id}/creative/agents/jobs", response_model=JobRead,
             status_code=202)
def enqueue(project_id: str, payload: GenerateRequest, db: Session = Depends(get_db)):
    _enabled()
    project = project_for(db, project_id)
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    if not brief or not dna:
        raise HTTPException(409, "Save brief and Creative DNA first")
    require_revision(brief, payload.expected_brief_revision)
    require_revision(dna, payload.expected_dna_revision)
    brief_content = CreativeBrief.model_validate(brief.payload)
    if (payload.task in {"script", "storyboard"}
            and brief_content.factual_mode == "FACT_CHECK_REQUIRED"
            and not any(source.fact_reviewed for source in brief_content.sources)):
        raise HTTPException(409, "Review at least one factual source before drafting")
    active = db.scalar(select(func.count()).select_from(Job).where(
        Job.job_type == "CREATIVE_AI",
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ))
    if active:
        raise HTTPException(429, "A local creative generation is already queued or running")
    daily = db.scalar(select(func.count()).select_from(Job).where(
        Job.job_type == "CREATIVE_AI", Job.created_at >= now() - timedelta(days=1),
    ))
    if daily >= 12:
        raise HTTPException(429, "Daily local creative job budget reached")
    context: dict = {}
    if payload.task in {"storyboard", "continuity", "qa"}:
        scripts = db.scalars(select(Job).where(
            Job.project_id == project_id, Job.job_type == "CREATIVE_AI",
            Job.status == JobStatus.SUCCEEDED.value,
        ).order_by(Job.created_at.desc()).limit(30)).all()
        script_job = next((item for item in scripts if (item.result or {}).get("task") == "script"
                           and item.result.get("brief_sha256") == brief.sha256), None)
        if script_job is None:
            raise HTTPException(409, "A current local script draft is required")
        context["script"] = script_job.result["content"]
        context["script_sha256"] = script_job.result["content_sha256"]
    if payload.task in {"storyboard", "motion", "qa"}:
        directions = latest(db, CreativeDirectionSet, project_id)
        if not directions or direction_status(db, project, directions) != "CURRENT":
            raise HTTPException(409, "Current creative directions required")
        context["directions"] = directions.payload["directions"]
        context["directions_sha256"] = directions.sha256
        if payload.direction_id:
            valid_ids = {item["id"] for item in directions.payload["directions"]}
            if payload.direction_id not in valid_ids:
                raise HTTPException(422, "Select a current direction")
            context["direction_id"] = payload.direction_id
        elif payload.task == "storyboard":
            raise HTTPException(422, "Select a direction for the storyboard")
    if payload.task == "motion":
        state = review_read(db, project)
        if state["status"] != "APPROVED_STORYBOARD" or state["blockers"]:
            raise HTTPException(409, "Approved current storyboard required for motion planning")
        context["approved_snapshot_sha256"] = state["current_snapshot_sha256"]
        board = latest(db, CreativeStoryboardRevision, project_id)
        context["storyboard_scene_count"] = len(board.payload["shots"])
        context["storyboard_duration_ms"] = board.payload["duration_ms"]
        context["recipe_catalog"] = [
            {"id": recipe["id"], "scene_count": len(recipe["shots"]),
             "canvas_format": ("vertical" if recipe["canvas"]["height"]
                               > recipe["canvas"]["width"] else
                               "square" if recipe["canvas"]["height"]
                               == recipe["canvas"]["width"] else "horizontal")}
            for recipe in recipes_read()["recipes"] if recipe["status"] == "SUPPORTED"
        ]
        context["compatible_recipe_ids"] = sorted({
            recipe["id"] for recipe in context["recipe_catalog"]
            if recipe["scene_count"] == context["storyboard_scene_count"]
            and recipe["canvas_format"] == brief_content.format
            and context["storyboard_duration_ms"] <= 30000
        })
        if not context["compatible_recipe_ids"]:
            raise HTTPException(409, "No compatible M4 recipe for this approved storyboard")
    if len(str(context).encode("utf-8")) > 14000:
        raise HTTPException(422, "Creative context exceeds local model budget")
    job = Job(project_id=project_id, job_type="CREATIVE_AI", priority=200,
              max_attempts=1, payload={"task": payload.task,
                                       "brief_sha256": brief.sha256,
                                       "dna_sha256": dna.sha256,
                                       "context": context})
    db.add(job)
    db.flush()
    record_event(db, "CREATIVE_AI_QUEUED", "job", job.id,
                 after={"project_id": project_id, "task": payload.task})
    db.commit()
    db.refresh(job)
    return job


@router.get("/projects/{project_id}/creative/agents/jobs", response_model=list[JobRead])
def list_jobs(project_id: str, db: Session = Depends(get_db)):
    project_for(db, project_id)
    return db.scalars(select(Job).where(Job.project_id == project_id,
                                        Job.job_type == "CREATIVE_AI")
                      .order_by(Job.created_at.desc()).limit(30)).all()


def _result(db: Session, project_id: str, job_id: str, task: str) -> tuple[Job, object]:
    project = project_for(db, project_id)
    job = db.get(Job, job_id)
    if not job or job.project_id != project_id or job.job_type != "CREATIVE_AI":
        raise HTTPException(404, "Creative agent job not found")
    if job.status != JobStatus.SUCCEEDED.value or not job.result or job.result.get("task") != task:
        raise HTTPException(409, "Validated agent draft is not ready")
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    if not brief or not dna or (brief.sha256, dna.sha256) != (
        job.result["brief_sha256"], job.result["dna_sha256"]
    ):
        raise HTTPException(409, "Creative inputs changed; regenerate the draft")
    return job, project


@router.post("/projects/{project_id}/creative/agents/jobs/{job_id}/adopt-directions")
def adopt_directions(project_id: str, job_id: str, request: AdoptRequest,
                     db: Session = Depends(get_db)):
    job, project = _result(db, project_id, job_id, "directions")
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    require_revision(brief, request.expected_brief_revision)
    require_revision(dna, request.expected_dna_revision)
    current = latest(db, CreativeDirectionSet, project_id)
    require_revision(current, request.expected_revision)
    content = DirectionContract.model_validate(job.result["content"])
    row = CreativeDirectionSet(project_id=project_id, revision=request.expected_revision+1,
                               brief_sha256=brief.sha256, dna_sha256=dna.sha256,
                               origin="ollama_local", payload=content.model_dump(mode="json"),
                               sha256=job.result["content_sha256"])
    commit_revision(db, row, "CREATIVE_AI_DIRECTIONS_ADOPTED", "project", project_id)
    return serialized(row)


@router.post("/projects/{project_id}/creative/agents/jobs/{job_id}/adopt-storyboard")
def adopt_storyboard(project_id: str, job_id: str, request: AdoptRequest,
                     db: Session = Depends(get_db)):
    job, project = _result(db, project_id, job_id, "storyboard")
    directions = latest(db, CreativeDirectionSet, project_id)
    if (not directions or directions.sha256
            != job.payload.get("context", {}).get("directions_sha256")):
        raise HTTPException(409, "Creative directions changed; regenerate storyboard")
    content = CreativeStoryboard.model_validate(job.result["content"])
    return save_storyboard(db, project_id, CreativeStoryboardWrite(
        expected_revision=request.expected_revision,
        expected_direction_revision=request.expected_direction_revision,
        content=content,
    ))
