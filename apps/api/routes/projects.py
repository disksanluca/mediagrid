from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel, Project
from ..schemas import ContentPlan, ProjectCreate, ProjectRead
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


@router.post("/{project_id}/render", status_code=status.HTTP_202_ACCEPTED)
def queue_render(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.edl:
        raise HTTPException(status_code=409, detail="Create a validated plan before rendering")
    job = enqueue_job(db, project.id, "RENDER", {"edl": project.edl})
    db.commit()
    return {"job_id": job.id, "status": job.status}
