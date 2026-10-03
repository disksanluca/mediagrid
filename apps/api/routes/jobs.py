from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job
from ..schemas import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)) -> list[Job]:
    statement = select(Job).order_by(Job.created_at.desc())
    if status:
        statement = statement.where(Job.status == status.upper())
    return list(db.scalars(statement))


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
