"""Authenticated MediaGrid Creative Director foundation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..creative.contracts import (
    CreativeBriefWrite,
    CreativeDecisionWrite,
    CreativeDirectionsWrite,
    CreativeDNAWrite,
    CreativeStoryboardWrite,
)
from ..creative.motion import (
    MotionRequest,
    derive_motion,
    motion_output,
    motion_props,
    queue_motion,
    verify_motion,
)
from ..creative.service import (
    channel_for,
    decide,
    directions_read,
    generate_directions,
    latest,
    project_for,
    review_read,
    save_brief,
    save_dna,
    save_storyboard,
    serialized,
    storyboard_read,
)
from ..database import get_db
from ..ingestion import sha256_file
from ..models import (
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeStoryboardRevision,
    Job,
    JobStatus,
)
from ..schemas import JobRead

router = APIRouter(tags=["creative"])


@router.get("/channels/{channel_id}/creative-dna")
def read_dna(channel_id: str, db: Session = Depends(get_db)) -> dict:
    channel_for(db, channel_id)
    row = latest(db, CreativeDNARevision, channel_id)
    if row is None:
        raise HTTPException(404, "Creative DNA not found")
    return serialized(row)


@router.put("/channels/{channel_id}/creative-dna")
def write_dna(channel_id: str, payload: CreativeDNAWrite,
              db: Session = Depends(get_db)) -> dict:
    return save_dna(db, channel_id, payload.expected_revision, payload.content)


@router.get("/projects/{project_id}/creative/brief")
def read_brief(project_id: str, db: Session = Depends(get_db)) -> dict:
    project_for(db, project_id)
    row = latest(db, CreativeBriefRevision, project_id)
    if row is None:
        raise HTTPException(404, "Creative brief not found")
    return serialized(row)


@router.put("/projects/{project_id}/creative/brief")
def write_brief(project_id: str, payload: CreativeBriefWrite,
                db: Session = Depends(get_db)) -> dict:
    return save_brief(db, project_id, payload.expected_revision, payload.content)


@router.get("/projects/{project_id}/creative/directions")
def read_directions(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    row = latest(db, CreativeDirectionSet, project_id)
    if row is None:
        raise HTTPException(404, "Creative directions not found")
    return directions_read(db, project, row)


@router.post("/projects/{project_id}/creative/directions")
def write_directions(project_id: str, payload: CreativeDirectionsWrite,
                     db: Session = Depends(get_db)) -> dict:
    return generate_directions(db, project_id, payload)


@router.get("/projects/{project_id}/creative/storyboard")
def read_storyboard(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    row = latest(db, CreativeStoryboardRevision, project_id)
    if row is None:
        raise HTTPException(404, "Creative storyboard not found")
    return storyboard_read(db, project, row)


@router.put("/projects/{project_id}/creative/storyboard")
def write_storyboard(project_id: str, payload: CreativeStoryboardWrite,
                     db: Session = Depends(get_db)) -> dict:
    return save_storyboard(db, project_id, payload)


@router.get("/projects/{project_id}/creative/review")
def read_review(project_id: str, db: Session = Depends(get_db)) -> dict:
    return review_read(db, project_for(db, project_id))


@router.post("/projects/{project_id}/creative/decision")
def write_decision(project_id: str, payload: CreativeDecisionWrite,
                   db: Session = Depends(get_db)) -> dict:
    return decide(db, project_id, payload)


@router.post("/projects/{project_id}/creative/motion/preview")
def motion_preview(project_id: str, payload: MotionRequest,
                   db: Session = Depends(get_db)) -> dict:
    derived = derive_motion(db, project_id, payload)
    props = motion_props(derived["plan"])
    for sound in props["sounds"]:
        sound["media_file"] = sound["source_asset_id"]
    return {**derived, "props": props}


@router.post("/projects/{project_id}/creative/motion/render", response_model=JobRead,
             status_code=202)
def motion_render(project_id: str, payload: MotionRequest,
                  db: Session = Depends(get_db)) -> Job:
    return queue_motion(db, project_id, payload)


@router.get("/projects/{project_id}/creative/motion/jobs/{job_id}/video")
def motion_video(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.project_id != project_id or job.job_type != "CREATIVE_MOTION":
        raise HTTPException(404, "Creative motion job not found")
    if job.status != JobStatus.SUCCEEDED.value or not job.result:
        raise HTTPException(409, "Creative motion output is not ready")
    try:
        verify_motion(db, project_id, job.payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    output = motion_output(job.id)
    if not output.is_file() or sha256_file(output) != job.result.get("sha256"):
        raise HTTPException(409, "Creative motion artifact is missing or changed")
    return FileResponse(output, media_type="video/mp4", filename=f"mediagrid-motion-{job.id}.mp4")
