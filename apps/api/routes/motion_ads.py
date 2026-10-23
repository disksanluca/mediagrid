"""Creator supplied motion ad briefs; no AI claims or external publication."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..motion_ad import MotionAdCreate, create_motion_ad
from ..schemas import ProjectRead

router = APIRouter(prefix="/motion-ads", tags=["motion-ads"])


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_from_brief(payload: MotionAdCreate, db: Session = Depends(get_db)):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Canal não encontrado")
    project = create_motion_ad(db, channel, payload)
    db.commit()
    db.refresh(project)
    return project
