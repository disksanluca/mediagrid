from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..local_media import voice_configuration_digest
from ..models import Asset, Job, JobStatus, initial_job_status, now
from ..schemas import JobRead
from ..services import record_event

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


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_queued_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.CANCELLED.value:
        return job
    cancellable = (JobStatus.QUEUED.value, JobStatus.WAITING_FOR_WORKER.value)
    if job.status not in cancellable:
        raise HTTPException(status_code=409, detail="Only jobs still waiting can be cancelled")
    previous = job.status
    result = db.execute(update(Job).where(
        Job.id == job_id, Job.status.in_(cancellable),
    ).values(status=JobStatus.CANCELLED.value, finished_at=now(),
             lease_owner=None, lease_expires_at=None),
        execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Worker already claimed this job")
    if job.job_type == "PROXY":
        asset = db.get(Asset, (job.payload or {}).get("asset_id"))
        if asset:
            asset.metadata_json = {**(asset.metadata_json or {}),
                                   "ingest_status": "CANCELLED"}
    record_event(db, "JOB_CANCELLED", "job", job_id,
                 before={"status": previous},
                 after={"status": JobStatus.CANCELLED.value})
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried")
    if job.attempt >= job.max_attempts:
        raise HTTPException(status_code=409, detail="Retry limit reached")
    previous = job.status
    next_status = initial_job_status()
    result = db.execute(update(Job).where(
        Job.id == job_id, Job.status == previous,
    ).values(status=next_status, error=None, progress=0, result=None,
             started_at=None, finished_at=None, heartbeat_at=None,
             lease_owner=None, lease_expires_at=None),
        execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Job changed; reload before retrying")
    db.refresh(job)
    if job.job_type == "VOICE" and get_settings().mediagrid_mode == "LOCAL":
        job.payload = {**(job.payload or {}),
                       "voice_config_sha256": voice_configuration_digest()}
    if job.job_type == "PROXY":
        asset = db.get(Asset, job.payload.get("asset_id"))
        if asset:
            asset.metadata_json = {
                **(asset.metadata_json or {}), "ingest_status": (
                    "PROXY_QUEUED" if job.status == JobStatus.QUEUED.value
                    else "WAITING_FOR_WORKER"),
            }
    record_event(db, "JOB_RETRIED", "job", job_id,
                 before={"status": previous}, after={"status": job.status})
    db.commit()
    db.refresh(job)
    return job
