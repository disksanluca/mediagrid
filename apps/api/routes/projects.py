from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Channel, Job, JobStatus, Project, ProjectStatus
from ..schemas import ContentPlan, ProjectCreate, ProjectPlanUpdate, ProjectRead
from ..services import create_plan, enqueue_job, record_event

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
    plan = ContentPlan(
        project_id=project.id,
        engine=channel.default_engine,
        hook=payload.hook,
        angle=payload.angle,
        target_duration_seconds=round(sum(scene.duration_seconds for scene in payload.scenes)),
        scenes=payload.scenes,
        requires_fact_review=True,
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
    active = db.scalars(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "RENDER",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="Render is already queued or running")
    job = enqueue_job(db, project.id, "RENDER", {"edl": project.edl})
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{project_id}/output")
def download_output(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != ProjectStatus.QC.value:
        raise HTTPException(status_code=404, detail="Render is not available")
    output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
    if not output.is_file():
        raise HTTPException(status_code=404, detail="Render is not available")
    return FileResponse(output, media_type="video/mp4", filename=f"mediagrid-{project_id}.mp4")
