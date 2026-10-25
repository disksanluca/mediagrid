"""Authenticated MediaGrid Creative Director foundation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..creative.contracts import (
    CreativeBriefWrite,
    CreativeDecisionWrite,
    CreativeDirectionsWrite,
    CreativeDNAWrite,
    CreativeStoryboardWrite,
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
from ..models import (
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeStoryboardRevision,
)

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
