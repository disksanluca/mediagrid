import json
import os
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..engines import get_engine
from ..local_media import voice_matches
from ..models import Channel, Job, JobStatus, Project, ProjectStatus
from ..schemas import ContentPlan, ProjectCreate, ProjectPlanUpdate, ProjectRead, ProjectReview
from ..services import build_local_plan, create_plan, enqueue_job, record_event

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(channel_id: str | None = None, db: Session = Depends(get_db)) -> list[Project]:
    statement = select(Project).order_by(Project.created_at.desc())
    if channel_id:
        statement = statement.where(Project.channel_id == channel_id)
    return list(db.scalars(statement))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    if db.get(Channel, payload.channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    project = Project(**payload.model_dump())
    db.add(project)
    db.flush()
    record_event(
        db, "PROJECT_CREATED", "project", project.id, after=payload.model_dump(mode="json")
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/plan", response_model=ContentPlan)
def plan_project(project_id: str, db: Session = Depends(get_db)) -> ContentPlan:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    plan = create_plan(db, project)
    channel = db.get(Channel, project.channel_id)
    if (
        channel
        and plan.origin != "OUTLINE"
        and (channel.editorial_profile or {}).get("auto_render") is True
    ):
        enqueue_job(db, project.id, "RENDER", {"edl": project.edl})
    db.commit()
    return plan


@router.put("/{project_id}/plan", response_model=ProjectRead)
def update_plan(
    project_id: str, payload: ProjectPlanUpdate, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    channel = db.get(Channel, project.channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    original_narrations = {
        scene.id: scene.narration.strip()
        for scene in build_local_plan(project, channel).scenes
    }
    still_outline = (project.plan or {}).get("origin") == "OUTLINE" and any(
        scene.narration.strip() == original_narrations.get(scene.id)
        for scene in payload.scenes
    )
    plan = ContentPlan(
        project_id=project.id,
        engine=channel.default_engine,
        origin="OUTLINE" if still_outline else "MANUAL",
        hook=payload.hook,
        angle=payload.angle,
        target_duration_seconds=round(sum(scene.duration_seconds for scene in payload.scenes)),
        scenes=payload.scenes,
        requires_fact_review=True,
        review_checks=(project.plan or {}).get("review_checks")
        or list(get_engine(channel.default_engine).review_checks),
        source_refs=(project.plan or {}).get("source_refs", []),
    )
    project.plan = plan.model_dump()
    project.script = {"language": channel.language, "segments": [s.narration for s in plan.scenes]}
    project.edl = {
        "version": 1,
        "format": project.format,
        "tracks": {
            "video": [
                {
                    "scene_id": s.id,
                    "duration": s.duration_seconds,
                    "visual_type": s.visual_type,
                    "transition": s.transition,
                }
                for s in plan.scenes
            ],
            "audio": [{"scene_id": s.id, "text": s.narration} for s in plan.scenes],
            "captions": [{"scene_id": s.id, "text": s.on_screen_text} for s in plan.scenes],
        },
    }
    project.status = ProjectStatus.SCRIPTED.value
    record_event(
        db, "SCRIPT_EDITED", "project", project.id, after={"scene_count": len(plan.scenes)}
    )
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/render", status_code=status.HTTP_202_ACCEPTED)
def queue_render(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.edl:
        raise HTTPException(status_code=409, detail="Create a validated plan before rendering")
    if (project.plan or {}).get("origin") == "OUTLINE":
        raise HTTPException(
            status_code=409,
            detail="O plano ainda é um esboço. Revise e salve a narração antes do render.",
        )
    active = db.scalars(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "RENDER",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="Render is already queued or running")
    active_voice = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "VOICE",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active_voice:
        raise HTTPException(409, "Aguarde a geração da nova voz antes de renderizar.")
    if project.status in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        was_approved = project.status == ProjectStatus.APPROVED.value
        project.plan = {
            key: value for key, value in (project.plan or {}).items() if key != "review"
        }
        project.status = ProjectStatus.SCRIPTED.value
        record_event(
            db,
            "PROJECT_APPROVAL_REVOKED" if was_approved else "PROJECT_OUTPUT_INVALIDATED",
            "project",
            project.id,
        )
    job = enqueue_job(db, project.id, "RENDER", {"edl": project.edl})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.post("/{project_id}/voice", status_code=status.HTTP_202_ACCEPTED)
def queue_voice(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if not project.script:
        raise HTTPException(409, "Create a plan before generating voice")
    if (project.plan or {}).get("origin") == "OUTLINE":
        raise HTTPException(409, "Revise e salve a narração antes de gerar a voz.")
    active = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "VOICE",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active:
        raise HTTPException(409, "Voice is already queued")
    active_render = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "RENDER",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active_render:
        raise HTTPException(409, "Aguarde o render atual antes de gerar uma nova voz.")
    if project.status in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        was_approved = project.status == ProjectStatus.APPROVED.value
        project.plan = {
            key: value for key, value in (project.plan or {}).items() if key != "review"
        }
        project.status = ProjectStatus.SCRIPTED.value
        record_event(
            db,
            "PROJECT_APPROVAL_REVOKED" if was_approved else "PROJECT_OUTPUT_INVALIDATED",
            "project",
            project.id,
        )
    job = enqueue_job(db, project.id, "VOICE")
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{project_id}/voice")
def download_voice(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    output = get_settings().mediagrid_data_dir / "voice" / f"{project_id}.wav"
    if not voice_matches(project_id, project.script):
        raise HTTPException(404, "Voice is not available")
    return FileResponse(output, media_type="audio/wav", filename=f"mediagrid-{project_id}.wav")


@router.get("/{project_id}/output")
def download_output(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status not in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        raise HTTPException(status_code=404, detail="Render is not available")
    output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
    if not output.is_file():
        raise HTTPException(status_code=404, detail="Render is not available")
    return FileResponse(output, media_type="video/mp4", filename=f"mediagrid-{project_id}.mp4")


@router.post("/{project_id}/review", response_model=ProjectRead)
def approve_project_review(
    project_id: str, payload: ProjectReview, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if project.status != ProjectStatus.QC.value:
        raise HTTPException(409, "A completed render is required before review")
    output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
    if not output.is_file():
        raise HTTPException(409, "Rendered MP4 is missing")
    if not payload.facts_confirmed or not payload.rights_confirmed:
        raise HTTPException(409, "Confirm facts and media rights before approval")
    review = {
        "approved_at": datetime.now(UTC).isoformat(),
        "source_urls": [str(url) for url in payload.source_urls],
        "facts_confirmed": True,
        "rights_confirmed": True,
        "notes": payload.notes,
    }
    project.plan = {**(project.plan or {}), "review": review}
    project.status = ProjectStatus.APPROVED.value
    record_event(db, "PROJECT_APPROVED", "project", project.id, after=review)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/export")
def export_reviewed_project(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    review = (project.plan or {}).get("review")
    if project.status != ProjectStatus.APPROVED.value or not review:
        raise HTTPException(409, "Human review and approval are required")
    data_dir = get_settings().mediagrid_data_dir
    video = data_dir / "renders" / f"{project_id}.mp4"
    if not video.is_file():
        raise HTTPException(404, "Rendered MP4 is missing")
    exports = data_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    target = exports / f"{project_id}.zip"
    temporary = exports / f".{project_id}.{uuid4().hex}.partial"
    manifest = {
        "format": "MediaGrid Manual Export",
        "project_id": project.id,
        "title": project.title,
        "channel_id": project.channel_id,
        "approved_review": review,
        "publication": "manual",
        "platform_status": "not_published",
    }
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(video, "video.mp4")
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return FileResponse(
        target, media_type="application/zip", filename=f"mediagrid-{project_id}.zip"
    )
