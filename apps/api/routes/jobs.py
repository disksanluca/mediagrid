from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Asset, Job, JobStatus, initial_job_status
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


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    if job.attempt >= job.max_attempts:
        raise HTTPException(status_code=409, detail="Retry limit reached")
    job.status = initial_job_status()
    job.error = None
    job.progress = 0
    if job.job_type == "PROXY":
        asset = db.get(Asset, job.payload.get("asset_id"))
        if asset:
            asset.metadata_json = {
                **(asset.metadata_json or {}), "ingest_status": (
                    "PROXY_QUEUED" if job.status == JobStatus.QUEUED.value
                    else "WAITING_FOR_WORKER"),
            }
    db.commit()
    db.refresh(job)
    return job
